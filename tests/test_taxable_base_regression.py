"""Regresión FAU04: bases tributarias separadas del valor comercial."""

from __future__ import annotations

import base64
from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

import pytest
from facturacion_dian_api.core.dian.client import DianClient
from facturacion_dian_api.core.dian.response_parser import DianResponse
from facturacion_dian_api.core.signing.xades import verify_document_signature
from fastapi.testclient import TestClient
from lxml import etree

from tests.test_optional_buyer_fiscal import real_crypto
from tests.test_payments_and_rounding import NS, PROFILES, build, with_lines


def excluded_line() -> dict:
    # Importes del incidente, con identidad y descripción sintéticas.
    return {
        "description": "Artículo excluido de prueba", "item_code": "QA-EXCLUDED",
        "quantity": "22", "unit_price": "1850", "line_total": "40700",
        "tax_type": "EXCLUDED", "tax_amount": "0",
    }


def taxable_line(kind: str, base: str, amount: str) -> dict:
    return {
        "description": "Artículo tributario de prueba", "item_code": "QA-TAX",
        "quantity": "1", "unit_price": base, "line_total": base,
        "tax_type": kind, "tax_amount": amount,
    }


def assert_totals(root: etree._Element, tag: str, base: str, gross: str, tax: str, payable: str) -> None:
    total = "RequestedMonetaryTotal" if tag == "DebitNoteLine" else "LegalMonetaryTotal"
    expected = {
        "LineExtensionAmount": Decimal(gross), "TaxExclusiveAmount": Decimal(base),
        "TaxInclusiveAmount": Decimal(gross) + Decimal(tax), "PayableAmount": Decimal(payable),
    }
    for name, value in expected.items():
        actual = root.xpath(f"string(cac:{total}/cbc:{name})", namespaces=NS)
        assert Decimal(actual) == value, (name, actual, value)
    # Ecuaciones de la tabla de reglas FAU04/CAU04/DAU04 y sus equivalentes DEE.
    tax_path = "cac:TaxTotal[1]" if tag == "CreditNoteLine" else "cac:TaxTotal"
    bases = root.xpath(f"cac:{tag}/{tax_path}/cac:TaxSubtotal/cbc:TaxableAmount/text()", namespaces=NS)
    assert sum(map(Decimal, bases), Decimal(0)) == Decimal(base)
    taxes = root.xpath("cac:TaxTotal/cbc:TaxAmount/text()", namespaces=NS)
    assert sum(map(Decimal, taxes), Decimal(0)) == Decimal(tax)


@pytest.mark.parametrize(("fixture", "profile", "tag"), PROFILES)
@pytest.mark.parametrize("case", ["excluded", "mixed", "zero_base", "withholding", "multiple_taxes", "adjustments"])
def test_monetary_totals_match_emitted_tax_bases(request, fixture, profile, tag, case):
    items = [excluded_line()]
    expected_base = "0"
    if case in {"mixed", "adjustments"}:
        items += [taxable_line("IVA_19", "1000", "190"), taxable_line("IVA_5", "2000", "100"),
                  taxable_line("EXEMPT", "3000", "0"), taxable_line("IVA_0", "4000", "0")]
        expected_base = "10000"
    elif case == "zero_base":
        items += [{"description": "Base explícita cero", "item_code": "QA-ZERO", "quantity": "1", "unit_price": "1000",
                   "line_total": "1000", "taxes": [{"tax_type": "IVA_19", "taxable_amount": "0", "amount": "0"}]}]
    elif case == "withholding":
        items[0].pop("tax_type")
        items[0].pop("tax_amount")
        items[0]["taxes"] = [{"tax_type": "EXCLUDED", "amount": "0"},
                             {"tax_type": "RETEFUENTE", "percent": "1", "amount": "407"}]
    elif case == "multiple_taxes":
        items += [{"description": "Bases explícitas de varios tributos", "item_code": "QA-MULTI", "quantity": "1",
                   "unit_price": "1000", "line_total": "1000", "taxes": [
                       {"tax_type": "RETEFUENTE", "taxable_amount": "0", "percent": "1", "amount": "0"},
                       {"tax_type": "IVA_19", "taxable_amount": "900", "amount": "171"},
                       {"tax_type": "INC", "taxable_amount": "500", "percent": "8", "amount": "40"}]}]
        expected_base = "900" if tag == "CreditNoteLine" else "1400"
    payload = with_lines(request.getfixturevalue(fixture), items)
    payload["document"]["type"] = profile
    if case == "withholding":
        payload["totals"].update(tax_total="0", withholding_total="407", total="40293")
    if case == "adjustments":
        payload["totals"].update(
            allowance_total="100", charge_total="20", prepaid_amount="50",
            payable_rounding_amount="0.01", total="50860.01",
            allowance_charges=[{"charge_indicator": False, "amount": "100", "reason": "Descuento global"},
                               {"charge_indicator": True, "amount": "20", "reason": "Cargo global"}],
        )
    core, root = build(payload)
    assert_totals(root, tag, expected_base, payload["totals"]["subtotal"],
                  payload["totals"]["tax_total"], payload["totals"]["total"])
    assert core.subtotal == Decimal(payload["totals"]["subtotal"])
    assert not root.xpath(f"cac:{tag}[1]/cac:TaxTotal", namespaces=NS)
    if case == "excluded":
        assert not root.xpath("cac:TaxTotal", namespaces=NS)
    if case == "withholding":
        assert root.xpath("cac:WithholdingTaxTotal/cbc:TaxAmount/text()", namespaces=NS) == ["407.00"]


@pytest.mark.parametrize(("fixture", "profile", "tag"), PROFILES)
def test_excluded_http_preparation_and_exact_signed_retry(
    request, fixture, profile, tag, client: TestClient, monkeypatch,
):
    bundle = request.getfixturevalue("real_crypto")
    payload = with_lines(request.getfixturevalue(fixture), [excluded_line()])
    payload["document"]["type"] = profile
    payload["submission_options"]["prepare_only"] = True
    original_payload = deepcopy(payload)
    transmitted = []

    async def transport(self, filename, content_b64, test_set_id=None):
        with ZipFile(BytesIO(base64.b64decode(content_b64))) as archive:
            transmitted.append(archive.read(archive.namelist()[0]))
        return DianResponse(is_valid=True, validation_result_present=True, status_code="00")

    monkeypatch.setattr(DianClient, "send_test_set_async", transport)
    monkeypatch.setattr(DianClient, "send_bill_sync", transport)
    prepared = client.post("/api/v1/documents/submissions", json=payload)
    assert prepared.status_code == 200, prepared.text
    body = prepared.json()
    assert body["status"] == "prepared"
    assert not transmitted
    artifact = body["artifacts"]
    signed = base64.b64decode(artifact["xml_base64"])
    root = etree.fromstring(signed)
    verify_document_signature(root, bundle)
    assert_totals(root, tag, "0", "40700", "0", "40700")
    assert body["document_key"] == build(original_payload)[1].xpath("string(cbc:UUID)", namespaces=NS)

    def forbid_resigning(*args):
        raise AssertionError("El reintento debe conservar exactamente el XML firmado")

    monkeypatch.setattr("facturacion_dian_api.core.submission.sign_document_xml", forbid_resigning)
    payload["submission_options"].update(prepare_only=False, signed_xml_base64=artifact["xml_base64"],
                                         signed_xml_filename=artifact["xml_filename"])
    for _ in range(2):
        sent = client.post("/api/v1/documents/submissions", json=payload)
        assert sent.status_code == 200, sent.text
        assert sent.json()["artifacts"]["xml_base64"] == artifact["xml_base64"]
        assert sent.json()["document_key"] == body["document_key"]
    assert transmitted == [signed, signed]
