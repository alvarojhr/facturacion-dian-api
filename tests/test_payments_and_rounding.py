"""HTTP/core/XML regressions for combined instruments and supplied COP IVA."""

from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import ROUND_UP, Decimal, localcontext
from io import BytesIO
from zipfile import ZipFile

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from facturacion_dian_api.core.dian.client import DianClient
from facturacion_dian_api.core.dian.response_parser import DianResponse
from facturacion_dian_api.core.models import DocumentLine, DocumentSubmitRequest
from facturacion_dian_api.core.signing.certificate import CertificateBundle
from facturacion_dian_api.core.signing.xades import sign_document_xml, verify_document_signature
from facturacion_dian_api.core.submission import _build_document_xml, _compute_document_codes
from facturacion_dian_api.server.contracts import DocumentSubmissionRequest
from facturacion_dian_api.server.mappers import to_core_submission_request
from fastapi.testclient import TestClient
from lxml import etree
from pydantic import ValidationError

NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
PROFILES = [
    ("sample_invoice_payload", "FACTURA_ELECTRONICA", "InvoiceLine"),
    ("sample_pos_payload", "DOCUMENTO_EQUIVALENTE_POS", "InvoiceLine"),
    ("sample_credit_note_payload", "NOTA_CREDITO", "CreditNoteLine"),
    ("sample_debit_note_payload", "NOTA_DEBITO", "DebitNoteLine"),
    ("sample_credit_note_payload", "NOTA_AJUSTE_DEE_CREDITO", "CreditNoteLine"),
    ("sample_debit_note_payload", "NOTA_AJUSTE_DEE_DEBITO", "CreditNoteLine"),
]


def line(base: str = "2801", tax: str = "532", rate: str = "IVA_19", **kwargs: object) -> dict:
    return {
        "description": "Metro vendido", "item_code": "MT-1", "unit_code": "MTR",
        "quantity": "3.333", "unit_price": "840.34", "line_total": base,
        "tax_type": rate, "tax_amount": tax, **kwargs,
    }


def with_lines(payload: dict, lines: list[dict]) -> dict:
    payload = deepcopy(payload)
    payload["line_items"] = lines
    subtotal = sum(Decimal(item["line_total"]) for item in lines)
    tax = sum(Decimal(item.get("tax_amount", sum(Decimal(t["amount"]) for t in item.get("taxes", [])))) for item in lines)
    payload["totals"] = {"subtotal": str(subtotal), "tax_total": str(tax), "total": str(subtotal + tax)}
    return payload


def build(payload: dict) -> tuple[DocumentSubmitRequest, etree._Element]:
    core = to_core_submission_request(DocumentSubmissionRequest.model_validate(payload))
    key, qr = _compute_document_codes(core)
    return core, _build_document_xml(core, key, qr)


@pytest.mark.parametrize(("fixture", "profile", "tag"), PROFILES)
@pytest.mark.parametrize(("methods", "codes"), [
    (["CASH", "DEBIT_CARD"], ["10", "49"]),
    (["CASH", "TRANSFER"], ["10", "31"]),
    (["DEBIT_CARD", "CREDIT_CARD"], ["49", "48"]),
])
def test_all_instruments_and_supplied_cop_survive_every_profile(
    request: pytest.FixtureRequest, fixture: str, profile: str, tag: str,
    methods: list[str], codes: list[str],
) -> None:
    payload = with_lines(request.getfixturevalue(fixture), [line()])
    payload["document"].pop("payment_method")
    payload["document"].update(type=profile, payment_methods=methods, payment_form="CONTADO")
    core, root = build(payload)
    assert core.resolved_payment_methods == methods
    assert root.xpath("cac:PaymentMeans/cbc:PaymentMeansCode/text()", namespaces=NS) == codes
    assert root.xpath("cac:PaymentMeans/cbc:ID/text()", namespaces=NS) == ["1", "1"]
    assert root.xpath("cac:TaxTotal/cbc:TaxAmount/text()", namespaces=NS) == ["532.00"]
    assert root.xpath("cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount/text()", namespaces=NS) == ["2801.00"]
    assert root.xpath(f"cac:{tag}/cbc:LineExtensionAmount/text()", namespaces=NS) == ["2801.00"]
    assert root.xpath(f"cac:{tag}/cac:TaxTotal/cbc:TaxAmount/text()", namespaces=NS) == ["532.00"]
    assert root.xpath(f"cac:{tag}/cac:Price/cbc:PriceAmount/text()", namespaces=NS) == ["840.34"]
    assert root.xpath(f"cac:{tag}/cbc:*[contains(local-name(), 'Quantity')]/text()", namespaces=NS) == ["3.333"]
    assert root.xpath("//*[local-name()='PayableAmount']/text()") == ["3333.00"]
    assert not root.xpath("//cac:AllowanceCharge | //cbc:PayableRoundingAmount", namespaces=NS)
    # Key must depend on the supplied IVA, rather than an internally replaced 532.19.
    exact = with_lines(payload, [line(tax="532.19")])
    assert _compute_document_codes(core)[0] != _compute_document_codes(build(exact)[0])[0]


@pytest.mark.parametrize(("method", "code"), [
    ("CASH", "10"), ("CARD", "48"), ("CREDIT_CARD", "48"), ("DEBIT_CARD", "49"),
    ("TRANSFER", "31"), ("CHECK", "20"), ("CREDIT", "30"),
])
def test_single_instrument_legacy_and_list_are_xml_equivalent(sample_invoice_payload: dict, method: str, code: str) -> None:
    payload = deepcopy(sample_invoice_payload)
    payload["document"]["payment_method"] = method
    legacy, legacy_xml = build(payload)
    payload["document"].pop("payment_method")
    payload["document"]["payment_methods"] = [method]
    current, current_xml = build(payload)
    assert legacy.payment_method == method
    assert current.payment_method is None
    assert etree.tostring(legacy_xml) == etree.tostring(current_xml)
    assert current_xml.xpath("cac:PaymentMeans/cbc:PaymentMeansCode/text()", namespaces=NS) == [code]


@pytest.mark.parametrize("document", [
    {"payment_method": "CASH", "payment_methods": ["TRANSFER"]},
    {"payment_method": "CASH", "payment_methods": ["CASH"]},
    {"payment_method": None, "payment_methods": []},
    {"payment_method": None},
    {"payment_method": "VOUCHER"},
    {"payment_method": None, "payment_methods": ["CASH", "VOUCHER"]},
    {"payment_method": None, "payment_methods": [{"method": "CASH", "amount": 10}]},
    {"payment_method": "CREDIT_CARD", "payment_form": "CREDITO"},
    {"payment_method": "CASH", "payment_due_date": "2000-01-01"},
])
def test_invalid_payments_fail_http_and_core_before_signing(
    sample_invoice_payload: dict, client: TestClient, document: dict,
) -> None:
    payload = deepcopy(sample_invoice_payload)
    core = build(payload)[0].model_dump()
    core.update(document)
    with pytest.raises(ValidationError):
        DocumentSubmitRequest.model_validate(core)
    payload["document"].update(document)
    assert client.post("/api/v1/documents/submissions", json=payload).status_code == 422


def test_credit_terms_repeat_due_date_and_pos_requires_cash_terms(sample_invoice_payload: dict) -> None:
    payload = deepcopy(sample_invoice_payload)
    payload["document"].pop("payment_method")
    due = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
    payload["document"].update(payment_methods=["CHECK", "CREDIT"], payment_form="CREDITO", payment_due_date=due)
    _, root = build(payload)
    assert root.xpath("cac:PaymentMeans/cbc:ID/text()", namespaces=NS) == ["2", "2"]
    assert root.xpath("cac:PaymentMeans/cbc:PaymentDueDate/text()", namespaces=NS) == [due, due]
    payload["document"]["type"] = "DOCUMENTO_EQUIVALENTE_POS"
    with pytest.raises(ValidationError, match="POS requires"):
        DocumentSubmissionRequest.model_validate(payload)


@pytest.mark.parametrize(("actual", "accepted"), [
    ("188.01", True), ("188", True), ("187.99", False),
    ("191.99", True), ("192", True), ("192.01", False),
])
def test_general_iva_tolerance_boundaries_in_both_directions(sample_invoice_payload: dict, actual: str, accepted: bool) -> None:
    item = line("1000", actual, quantity="1", unit_price="1000")
    if accepted:
        core, _ = build(with_lines(sample_invoice_payload, [item]))
        assert core.lines[0].taxes[0].amount == Decimal(actual)
    else:
        with pytest.raises(ValidationError, match="IVA_19 amount"):
            DocumentLine.model_validate(item)
        with pytest.raises(ValidationError, match="IVA_19 amount"):
            DocumentSubmissionRequest.model_validate(with_lines(sample_invoice_payload, [item]))


@pytest.mark.parametrize(("base", "actual", "accepted"), [
    ("1900.20", "100", True), ("1900", "100", True), ("1899.80", "100", False),
    ("2099.80", "100", True), ("2100", "100", True), ("2100.20", "100", False),
    ("1900", "99", False), ("2100", "101", False),
    ("1900", "90", False),  # tie follows HALF_EVEN (100), not arbitrary ±5
])
def test_nearest_ten_is_specific_to_iva_and_not_a_universal_five_peso_margin(
    sample_invoice_payload: dict, base: str, actual: str, accepted: bool,
) -> None:
    payload = with_lines(sample_invoice_payload, [line(base, actual, "IVA_5", quantity="1", unit_price=base)])
    if accepted:
        assert build(payload)[0].tax_total == Decimal(actual)
    else:
        with pytest.raises(ValidationError, match="IVA_5 amount"):
            build(payload)


def test_non_iva_zero_and_excluded_stay_exact(sample_invoice_payload: dict) -> None:
    for kind in ["IVA_0", "EXEMPT", "EXCLUDED"]:
        with pytest.raises(ValidationError, match="amount=0"):
            build(with_lines(sample_invoice_payload, [line(tax="1", rate=kind)]))
    item = line("1900", "0", quantity="1", unit_price="1900")
    item.pop("tax_type")
    item.pop("tax_amount")
    item["taxes"] = [{"tax_type": "INC", "amount": "100", "percent": "5"}]
    with pytest.raises(ValidationError, match="INC amount must equal"):
        build(with_lines(sample_invoice_payload, [item]))


def test_small_line_differences_accumulate_by_numeric_rate_in_http_and_core(sample_invoice_payload: dict) -> None:
    items = [line() for _ in range(11)]  # 11 * -0.19 = -2.09 COP
    for index, item in enumerate(items):
        item.pop("tax_type")
        item.pop("tax_amount")
        item["taxes"] = [{"tax_type": "IVA_19", "percent": "19.00" if index % 2 else "19", "amount": "532"}]
    accepted = with_lines(sample_invoice_payload, items[:10])
    core, root = build(accepted)
    assert len(root.xpath("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS)) == 1
    payload = with_lines(sample_invoice_payload, items)
    with pytest.raises(ValidationError, match="IVA aggregate rate 19"):
        DocumentSubmissionRequest.model_validate(payload)
    invalid = core.model_dump()
    invalid.update(payload["totals"], lines=items)
    with pytest.raises(ValidationError, match="IVA aggregate rate 19"):
        DocumentSubmitRequest.model_validate(invalid)


def test_different_rates_do_not_cancel_invalid_aggregates(sample_invoice_payload: dict) -> None:
    items = [line("1000", "191", quantity="1", unit_price="1000") for _ in range(3)]
    items += [line("1000", "49", "IVA_5", quantity="1", unit_price="1000") for _ in range(3)]
    assert sum(Decimal(i["tax_amount"]) for i in items) == Decimal("720")
    with pytest.raises(ValidationError, match="IVA aggregate rate"):
        build(with_lines(sample_invoice_payload, items))


def test_fractional_discount_centavos_and_partial_returns(sample_invoice_payload: dict, sample_credit_note_payload: dict) -> None:
    items = [line(), line("90.50", "4.52", "IVA_5", quantity="1.5", unit_price="67", allowance_charges=[
        {"amount": "10", "charge_indicator": False, "reason": "Descuento real"}
    ])]
    items += [line("1", "0", kind, quantity="0.5", unit_price="2") for kind in ["IVA_0", "EXEMPT", "EXCLUDED"]]
    # Change the process rounding mode to prove validation chooses HALF_EVEN.
    with localcontext() as ctx:
        ctx.rounding = ROUND_UP
        core, root = build(with_lines(sample_invoice_payload, items))
    assert core.tax_total == Decimal("536.52")
    assert root.xpath("cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount/text()", namespaces=NS) == ["532.00", "4.52", "0.00"]
    notes = [line("933", "178", quantity="1.111"), line("1868", "354", quantity="2.222")]
    for item in notes:
        note, _ = build(with_lines(sample_credit_note_payload, [item]))
        assert note.lines[0].quantity == Decimal(item["quantity"])
    assert sum(Decimal(i["tax_amount"]) for i in notes) == Decimal("532")
    assert sum(Decimal(i["line_total"]) for i in notes) == Decimal("2801")


@pytest.mark.parametrize("field", ["subtotal", "tax_total", "total", "allowance_total", "charge_total", "withholding_total"])
def test_document_equations_remain_exact(sample_invoice_payload: dict, field: str) -> None:
    payload = with_lines(sample_invoice_payload, [line()])
    payload["totals"][field] = str(Decimal(payload["totals"].get(field, "0")) + Decimal("0.01"))
    with pytest.raises(ValidationError, match=f"totals.{field}"):
        build(payload)


@pytest.mark.parametrize(("offset", "accepted"), [
    ("-1.99", True), ("-2", True), ("-2.01", False),
    ("1.99", True), ("2", True), ("2.01", False),
])
def test_line_extension_has_two_peso_boundary(sample_invoice_payload: dict, offset: str, accepted: bool) -> None:
    item = line(str(Decimal("1000") + Decimal(offset)), "0", "EXCLUDED", quantity="1", unit_price="1000")
    payload = with_lines(sample_invoice_payload, [item])
    if accepted:
        assert build(payload)[0].subtotal == Decimal(item["line_total"])
    else:
        with pytest.raises(ValidationError, match="line_total differs"):
            build(payload)


def test_payable_adjustment_and_advance_do_not_change_iva(sample_invoice_payload: dict) -> None:
    payload = with_lines(sample_invoice_payload, [line()])
    payload["document"].pop("payment_method")
    payload["document"]["payment_methods"] = ["CASH", "TRANSFER"]
    payload["totals"].update(prepaid_amount="100", payable_rounding_amount="-0.01", total="3232.99")
    _, root = build(payload)
    assert root.xpath("//cbc:PayableAmount/text()", namespaces=NS) == ["3232.99"]
    assert root.xpath("cac:TaxTotal/cbc:TaxAmount/text()", namespaces=NS) == ["532.00"]
    invalid = with_lines(payload, [line(tax="540")])
    # Even a balancing payable adjustment cannot conceal an invalid IVA.
    invalid["totals"].update(payable_rounding_amount="-8", total="3333")
    with pytest.raises(ValidationError, match="IVA_19 amount"):
        build(invalid)


def test_tax_base_zero_and_precise_rate_are_not_replaced_during_serialization(sample_invoice_payload: dict) -> None:
    item = line("10000", "0", quantity="1", unit_price="10000")
    item.pop("tax_type")
    item.pop("tax_amount")
    item["taxes"] = [
        {"tax_type": "IVA_19", "taxable_amount": "0", "amount": "0"},
        {"tax_type": "INC", "percent": "2.5123", "amount": "251.23"},
    ]
    _, root = build(with_lines(sample_invoice_payload, [item]))
    assert root.xpath("cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount/text()", namespaces=NS) == ["0.00", "10000.00"]
    assert root.xpath("cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent/text()", namespaces=NS) == ["19.00", "2.5123"]


def test_non_iva_aggregate_also_checks_accumulated_rounding(sample_invoice_payload: dict) -> None:
    item = line("0.01", "0", quantity="1", unit_price="0.01")
    item.pop("tax_type")
    item.pop("tax_amount")
    item["taxes"] = [{"tax_type": "INC", "percent": "50", "amount": "0.00"}]
    # HALF_EVEN(0.005) = 0.00 per line, but 403 lines aggregate to 2.02.
    with pytest.raises(ValidationError, match="INC aggregate rate"):
        build(with_lines(sample_invoice_payload, [deepcopy(item) for _ in range(403)]))
    items = [deepcopy(item) for _ in range(403)]
    for mixed in items[201:]:
        mixed["taxes"][0].update(tax_type="OTHER", scheme_id="04", scheme_name="INC")
    with pytest.raises(ValidationError, match="INC aggregate rate"):
        build(with_lines(sample_invoice_payload, items))


def test_openapi_describes_both_payment_representations(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    document = schema["components"]["schemas"]["DocumentInput"]
    assert len(document["oneOf"]) == 2
    array = next(entry for entry in document["properties"]["payment_methods"]["anyOf"] if entry["type"] == "array")
    assert array["minItems"] == 1
    assert {"CREDIT_CARD", "DEBIT_CARD"} <= set(array["items"]["enum"])
    examples = schema["paths"]["/api/v1/documents/submissions"]["post"]["requestBody"]["content"]["application/json"]["examples"]
    assert examples["efectivo_debito_iva_cop"]["value"]["document"]["payment_methods"] == ["CASH", "DEBIT_CARD"]


def test_tolerance_cannot_create_a_nonzero_free_line(sample_invoice_payload: dict) -> None:
    item = line("1", "0", "EXCLUDED", quantity="1", unit_price="0", reference_price="100", reference_price_type_code="01")
    with pytest.raises(ValidationError, match="Free lines require line_total=0"):
        build(with_lines(sample_invoice_payload, [item]))


def test_non_iva_reference_rounding_is_half_even_regardless_of_global_context(sample_invoice_payload: dict) -> None:
    item = line("100.50", "0", quantity="1", unit_price="100.50")
    item.pop("tax_type")
    item.pop("tax_amount")
    item["taxes"] = [{"tax_type": "INC", "percent": "1", "amount": "1.00"}]
    with localcontext() as ctx:
        ctx.rounding = ROUND_UP
        core, _ = build(with_lines(sample_invoice_payload, [item]))
    assert core.tax_total == Decimal("1.00")


@pytest.mark.parametrize(("fixture", "profile", "tag"), PROFILES)
def test_http_preparation_and_retry_keep_real_signature_money_key_and_exact_zip_bytes(
    request: pytest.FixtureRequest, client: TestClient, monkeypatch: pytest.MonkeyPatch,
    fixture: str, profile: str, tag: str,
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Offline fiscal QA")])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1)).sign(key, hashes.SHA256()))
    bundle = CertificateBundle(key, cert, [])
    monkeypatch.setattr("facturacion_dian_api.core.submission.get_certificate_bundle", lambda: bundle)
    monkeypatch.setattr("facturacion_dian_api.core.submission.sign_document_xml", sign_document_xml)
    transmitted: list[bytes] = []

    async def transport(self: DianClient, filename: str, content_b64: str, test_set_id: str | None = None) -> DianResponse:
        with ZipFile(BytesIO(base64.b64decode(content_b64))) as archive:
            transmitted.append(archive.read(archive.namelist()[0]))
        return DianResponse(is_valid=True, validation_result_present=True, status_code="00")

    monkeypatch.setattr(DianClient, "send_test_set_async", transport)
    monkeypatch.setattr(DianClient, "send_bill_sync", transport)
    payload = with_lines(request.getfixturevalue(fixture), [line()])
    payload["document"].pop("payment_method")
    payload["document"].update(type=profile, payment_methods=["CASH", "DEBIT_CARD"])
    payload["submission_options"]["prepare_only"] = True
    prepared = client.post("/api/v1/documents/submissions", json=payload)
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["status"] == "prepared"
    assert not transmitted
    artifact = prepared.json()["artifacts"]
    signed = base64.b64decode(artifact["xml_base64"])
    root = etree.fromstring(signed)
    verify_document_signature(root, bundle)
    assert root.xpath(f"cac:{tag}/cac:TaxTotal/cbc:TaxAmount/text()", namespaces=NS) == ["532.00"]
    payload["submission_options"].update(prepare_only=False, signed_xml_base64=artifact["xml_base64"], signed_xml_filename=artifact["xml_filename"])

    def forbid_resigning(*args: object) -> bytes:
        raise AssertionError("Signed retry must never be rebuilt or signed again")

    monkeypatch.setattr("facturacion_dian_api.core.submission.sign_document_xml", forbid_resigning)
    for _ in range(2):
        sent = client.post("/api/v1/documents/submissions", json=payload)
        assert sent.status_code == 200, sent.text
        assert sent.json()["artifacts"]["xml_base64"] == artifact["xml_base64"]
        assert sent.json()["document_key"] == prepared.json()["document_key"]
    assert transmitted == [signed, signed]
    assert hashlib.sha256(transmitted[1]).digest() == hashlib.sha256(signed).digest()
