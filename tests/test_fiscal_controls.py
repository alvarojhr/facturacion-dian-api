"""Fiscal regression tests derived from the 2026-09-14 audit findings."""

from __future__ import annotations

import base64
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from facturacion_dian_api.core.filenames import build_dian_filename, build_document_filename
from facturacion_dian_api.core.runtime_config import compute_nit_dv, resolved_issuer_dv
from facturacion_dian_api.core.signing.xades import sign_document
from facturacion_dian_api.core.xml.credit_note_builder import build_credit_note_xml
from facturacion_dian_api.core.xml.invoice_builder import build_invoice_xml
from facturacion_dian_api.server.contracts import DocumentSubmissionRequest, EmitEventRequest
from facturacion_dian_api.server.mappers import to_core_submission_request
from fastapi.testclient import TestClient
from lxml import etree
from pydantic import ValidationError

NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}


def test_totals_and_line_arithmetic_are_rejected_before_submission(sample_invoice_payload: dict) -> None:
    payload = deepcopy(sample_invoice_payload)
    payload["totals"]["subtotal"] = 1
    with pytest.raises(ValidationError, match="totals.subtotal"):
        DocumentSubmissionRequest.model_validate(payload)

    payload = deepcopy(sample_invoice_payload)
    payload["line_items"][0]["line_total"] = 49997
    with pytest.raises(ValidationError, match="line_total differs from calculation"):
        DocumentSubmissionRequest.model_validate(payload)


def test_unknown_tax_is_rejected_and_multiple_taxes_keep_their_schemes(
    sample_invoice_payload: dict,
) -> None:
    typo = deepcopy(sample_invoice_payload)
    typo["line_items"][0]["tax_type"] = "IVA19"
    with pytest.raises(ValidationError):
        DocumentSubmissionRequest.model_validate(typo)

    payload = deepcopy(sample_invoice_payload)
    payload["line_items"] = [
        {
            "description": "Servicio gravado",
            "item_code": "SERV-1",
            "quantity": 1,
            "unit_price": 100,
            "line_total": 100,
            "taxes": [
                {"tax_type": "IVA_19", "amount": 19},
                {"tax_type": "INC", "amount": 8, "percent": 8},
            ],
        }
    ]
    payload["totals"] = {"subtotal": 100, "tax_total": 27, "total": 127}
    request = DocumentSubmissionRequest.model_validate(payload)
    root = build_invoice_xml(to_core_submission_request(request), "a" * 96)
    assert root.xpath("cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID/text()", namespaces=NS) == ["01", "04"]


def test_credit_payment_emits_form_two_and_due_date(sample_invoice_payload: dict) -> None:
    payload = deepcopy(sample_invoice_payload)
    payload["document"].update(
        payment_method="CREDIT",
        payment_form="CREDITO",
        payment_due_date=(date.today() + timedelta(days=30)).isoformat(),
    )
    root = build_invoice_xml(
        to_core_submission_request(DocumentSubmissionRequest.model_validate(payload)),
        "a" * 96,
    )
    assert root.xpath("string(cac:PaymentMeans/cbc:ID)", namespaces=NS) == "2"
    assert root.xpath(
        "string(cac:PaymentMeans/cbc:PaymentDueDate)", namespaces=NS
    ) == (date.today() + timedelta(days=30)).isoformat()


def test_dee_credit_adjustment_uses_type_94_and_cude_reference(
    sample_credit_note_payload: dict,
) -> None:
    payload = deepcopy(sample_credit_note_payload)
    payload["document"]["type"] = "NOTA_AJUSTE_DEE_CREDITO"
    request = to_core_submission_request(DocumentSubmissionRequest.model_validate(payload))
    root = build_credit_note_xml(request, "b" * 96)
    assert root.xpath("string(cbc:CreditNoteTypeCode)", namespaces=NS) == "94"
    uuid = root.xpath("cac:BillingReference/cac:InvoiceDocumentReference/cbc:UUID", namespaces=NS)[0]
    assert uuid.get("schemeName") == "CUDE-SHA384"


def test_dee_debit_adjustment_is_a_credit_note_type_93_with_ncs_filename(
    sample_debit_note_payload: dict,
) -> None:
    payload = deepcopy(sample_debit_note_payload)
    payload["document"]["type"] = "NOTA_AJUSTE_DEE_DEBITO"
    request = to_core_submission_request(DocumentSubmissionRequest.model_validate(payload))
    root = build_credit_note_xml(request, "e" * 96)
    assert etree.QName(root).localname == "CreditNote"
    assert root.xpath("string(cbc:CreditNoteTypeCode)", namespaces=NS) == "93"
    assert (
        build_document_filename(
            "NOTA_AJUSTE_DEE_DEBITO",
            issuer_nit="800197268",
            provider_code="000",
            document_number="NA1",
            issue_date=payload["document"]["issue_date"],
            sequence=1,
        ).startswith("ncs")
    )


@pytest.mark.parametrize(
    ("document_type", "mode", "expected_code"),
    [
        ("DOCUMENTO_EQUIVALENTE_POS_CONTINGENCIA_EMISOR", "EMISOR", "07"),
        ("DOCUMENTO_EQUIVALENTE_POS_CONTINGENCIA_DIAN", "DIAN", "08"),
    ],
)
def test_dee_contingency_modes_emit_official_type_codes(
    sample_pos_payload: dict,
    document_type: str,
    mode: str,
    expected_code: str,
) -> None:
    now = datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0)
    payload = deepcopy(sample_pos_payload)
    payload["document"].update(
        type=document_type,
        issue_date=now.date().isoformat(),
        contingency={
            "incident_id": "INC-1",
            "mode": mode,
            "reason": "Indisponibilidad técnica",
            "started_at": (now - timedelta(hours=2)).isoformat(),
            "recovered_at": (now - timedelta(hours=1)).isoformat(),
        },
    )
    payload["references"] = {
        "contingency_reference_number": "PAPER-1",
        "contingency_reference_date": (now - timedelta(hours=2)).date().isoformat(),
    }
    request = to_core_submission_request(DocumentSubmissionRequest.model_validate(payload))
    root = build_invoice_xml(request, "c" * 96)
    assert root.xpath("string(cbc:InvoiceTypeCode)", namespaces=NS) == expected_code
    assert root.xpath("string(cac:AdditionalDocumentReference/cbc:ID)", namespaces=NS) == "PAPER-1"


def test_fev_dian_contingency_uses_type_04(sample_invoice_payload: dict) -> None:
    now = datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0)
    payload = deepcopy(sample_invoice_payload)
    payload["document"].update(
        type="FACTURA_CONTINGENCIA_DIAN",
        contingency={
            "incident_id": "DIAN-OUTAGE-1",
            "mode": "DIAN",
            "reason": "Indisponibilidad de los servicios DIAN",
            "started_at": (now - timedelta(hours=2)).isoformat(),
            "recovered_at": (now - timedelta(hours=1)).isoformat(),
        },
    )
    payload["references"] = {
        "contingency_reference_number": "PC000001",
        "contingency_reference_date": (now - timedelta(hours=2)).date().isoformat(),
    }
    request = to_core_submission_request(DocumentSubmissionRequest.model_validate(payload))
    root = build_invoice_xml(request, "1" * 96)
    assert root.xpath("string(cbc:InvoiceTypeCode)", namespaces=NS) == "04"


def test_event_032_requires_receiver_and_retry_timestamp_pair() -> None:
    base = {
        "event_type": "032",
        "document_cufe": "a" * 96,
        "document_number": "FV1",
        "supplier_nit": "900123456",
        "supplier_name": "Proveedor",
        "submission_options": {"file_sequence": 1},
    }
    with pytest.raises(ValidationError, match="receiver_person"):
        EmitEventRequest.model_validate(base)

    partial_timestamp = dict(base, event_type="030", event_issue_date="2026-09-15")
    with pytest.raises(ValidationError, match="must be provided together"):
        EmitEventRequest.model_validate(partial_timestamp)

    retry_without_timestamp = dict(
        base,
        event_type="030",
        submission_options={
            "file_sequence": 1,
            "signed_event_xml_base64": "PHNpZ25lZC8+",
        },
    )
    with pytest.raises(ValidationError, match="original event_issue_date"):
        EmitEventRequest.model_validate(retry_without_timestamp)


def test_decimal_discounts_free_prices_and_withholdings_are_consistent(
    sample_invoice_payload: dict,
) -> None:
    payload = deepcopy(sample_invoice_payload)
    payload["line_items"] = [
        {
            "description": "Muestra comercial",
            "item_code": "MUE-1",
            "quantity": 1,
            "unit_price": 0,
            "line_total": 0,
            "reference_price": 100,
            "reference_price_type_code": "01",
            "taxes": [{"tax_type": "EXCLUDED", "amount": 0}],
        },
        {
            "description": "Servicio",
            "item_code": "SER-1",
            "quantity": 1,
            "unit_price": 100.50,
            "line_total": 90.50,
            "allowance_charges": [
                {"charge_indicator": False, "amount": 10, "reason": "Descuento comercial"}
            ],
            "taxes": [
                {"tax_type": "RETEFUENTE", "amount": 9.05, "percent": 10}
            ],
        },
    ]
    payload["totals"] = {
        "subtotal": 90.50,
        "tax_total": 0,
        "withholding_total": 9.05,
        "total": 81.45,
    }
    request = DocumentSubmissionRequest.model_validate(payload)
    root = build_invoice_xml(to_core_submission_request(request), "d" * 96)
    assert root.xpath("string(cac:WithholdingTaxTotal/cbc:TaxAmount)", namespaces=NS) == "9.05"
    assert root.xpath("string(cac:InvoiceLine[1]/cac:PricingReference//cbc:PriceAmount)", namespaces=NS) == "100.00"


def test_request_specific_nit_never_uses_global_dv(sample_invoice_payload: dict) -> None:
    payload = deepcopy(sample_invoice_payload)
    payload.pop("issuer", None)
    request = to_core_submission_request(DocumentSubmissionRequest.model_validate(payload))
    request.issuer_nit = "12345678"
    request.issuer_dv = None
    assert resolved_issuer_dv(request) == compute_nit_dv("12345678")


def test_partial_or_inconsistent_issuer_identity_is_rejected(
    sample_invoice_payload: dict,
) -> None:
    payload = deepcopy(sample_invoice_payload)
    payload["issuer"] = {"nit": "900123456"}
    with pytest.raises(ValidationError, match="Body-owned issuer is incomplete"):
        DocumentSubmissionRequest.model_validate(payload)

    payload["issuer"] = {
        **deepcopy(sample_invoice_payload.get("issuer", {})),
        "nit": "900123456",
        "dv": "7",
        "name": "Emisor",
    }
    with pytest.raises(ValidationError, match="issuer.dv"):
        DocumentSubmissionRequest.model_validate(payload)


def test_expired_certificate_is_rejected_before_signing() -> None:
    bundle = SimpleNamespace(
        is_valid=False,
        not_valid_after=datetime(2020, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="expired or not yet valid"):
        sign_document(etree.Element("Invoice"), bundle)  # type: ignore[arg-type]


def test_technical_filenames_are_stable_for_retry_and_unique_by_sequence() -> None:
    first = build_document_filename(
        "FACTURA_ELECTRONICA",
        issuer_nit="800197268",
        provider_code="000",
        document_number="FV1",
        issue_date="2026-09-15",
        sequence=1,
    )
    retry = build_document_filename(
        "FACTURA_ELECTRONICA",
        issuer_nit="800197268",
        provider_code="000",
        document_number="FV1",
        issue_date="2026-09-15",
        sequence=1,
    )
    second = build_dian_filename(
        family="fv",
        issuer_nit="800197268",
        provider_code="000",
        document_number="FV2",
        issue_date="2026-09-15",
        sequence=2,
    )
    assert first == retry == "fv08001972680002600000001.xml"
    assert second == "fv08001972680002600000002.xml"


def test_notes_can_use_internal_numbering_without_a_dian_resolution(
    sample_credit_note_payload: dict,
) -> None:
    payload = deepcopy(sample_credit_note_payload)
    payload.pop("resolution", None)
    request = to_core_submission_request(DocumentSubmissionRequest.model_validate(payload))
    root = build_credit_note_xml(request, "f" * 96)
    assert root.xpath("//sts:InvoiceControl", namespaces={**NS, "sts": "dian:gov:co:facturaelectronica:Structures-2-1"}) == []


def test_note_references_must_be_complete(sample_credit_note_payload: dict) -> None:
    payload = deepcopy(sample_credit_note_payload)
    payload["references"].pop("referenced_issue_date")
    with pytest.raises(ValidationError, match="number, key and issue date"):
        DocumentSubmissionRequest.model_validate(payload)


def test_dee_adjustment_cannot_use_only_a_billing_period(
    sample_credit_note_payload: dict,
) -> None:
    payload = deepcopy(sample_credit_note_payload)
    payload["document"]["type"] = "NOTA_AJUSTE_DEE_CREDITO"
    payload["references"] = {
        "reason": "Ajuste de venta POS",
        "response_code": "1",
        "billing_period_start": "2026-09-01",
        "billing_period_end": "2026-09-15",
    }
    with pytest.raises(ValidationError, match="complete referenced document"):
        DocumentSubmissionRequest.model_validate(payload)


def test_past_document_requires_the_exact_persisted_signed_xml(
    sample_invoice_payload: dict,
) -> None:
    payload = deepcopy(sample_invoice_payload)
    payload["document"]["issue_date"] = "2026-01-01"
    with pytest.raises(ValidationError, match="newly signed document"):
        DocumentSubmissionRequest.model_validate(payload)

    payload["submission_options"].update(
        signed_xml_base64="PHNpZ25lZC8+",
        signed_xml_filename="fv09001234560002600000001.xml",
    )
    DocumentSubmissionRequest.model_validate(payload)


def test_document_allowance_total_must_match_its_breakdown(
    sample_invoice_payload: dict,
) -> None:
    payload = deepcopy(sample_invoice_payload)
    payload["totals"].update(
        allowance_total=10,
        total=118990,
        allowance_charges=[
            {
                "charge_indicator": False,
                "amount": 9,
                "reason": "Descuento global",
            }
        ],
    )
    with pytest.raises(ValidationError, match="allowance_total"):
        DocumentSubmissionRequest.model_validate(payload)


def test_two_phase_flow_reuses_exact_signed_xml(
    client: TestClient,
    sample_invoice_payload: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_sign(root: etree._Element, bundle: object) -> bytes:
        del bundle
        content = root.xpath(
            "ext:UBLExtensions/ext:UBLExtension[last()]/ext:ExtensionContent",
            namespaces=NS,
        )[0]
        etree.SubElement(content, "{http://www.w3.org/2000/09/xmldsig#}Signature")
        return etree.tostring(root)

    monkeypatch.setattr("facturacion_dian_api.core.submission.sign_document_xml", fake_sign)
    monkeypatch.setattr(
        "facturacion_dian_api.core.submission.verify_document_signature",
        lambda root, bundle: None,
    )
    payload = deepcopy(sample_invoice_payload)
    payload["submission_options"]["prepare_only"] = True
    prepared = client.post("/api/v1/documents/submissions", json=payload)
    assert prepared.status_code == 200
    assert prepared.json()["status"] == "prepared"
    assert prepared.json()["tracking_id"] is None

    artifact = prepared.json()["artifacts"]
    payload["submission_options"].update(
        prepare_only=False,
        signed_xml_base64=artifact["xml_base64"],
        signed_xml_filename=artifact["xml_filename"],
    )
    sent = client.post("/api/v1/documents/submissions", json=payload)
    assert sent.status_code == 200
    assert sent.json()["status"] == "accepted"
    assert sent.json()["artifacts"]["xml_base64"] == artifact["xml_base64"]
