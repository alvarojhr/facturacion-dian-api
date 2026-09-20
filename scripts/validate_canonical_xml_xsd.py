#!/usr/bin/env python3
"""Validate canonical API examples against an official DIAN UBL XSD folder."""

from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from facturacion_dian_api.core.cufe.calculator import EventCudeFields, calculate_event_cude
from facturacion_dian_api.core.signing.certificate import CertificateBundle
from facturacion_dian_api.core.signing.xades import COLOMBIA_TZ, sign_document
from facturacion_dian_api.core.submission import _build_document_xml, _compute_document_codes
from facturacion_dian_api.core.xml.application_response_builder import (
    build_application_response_xml,
)
from facturacion_dian_api.core.xml.attached_document_builder import build_attached_document_xml
from facturacion_dian_api.server.contracts import (
    AttachedDocumentRequest,
    DocumentSubmissionRequest,
    EmitEventRequest,
)
from facturacion_dian_api.server.examples import (
    ATTACHED_DOCUMENT_REQUEST_EXAMPLE,
    DOCUMENT_SUBMISSION_REQUEST_EXAMPLES,
    EMIT_EVENT_OPENAPI_EXAMPLES,
)
from facturacion_dian_api.server.mappers import (
    to_core_attached_document_request,
    to_core_event_request,
    to_core_submission_request,
)
from lxml import etree

SCHEMA_BY_ROOT = {
    "Invoice": "UBL-Invoice-2.1.xsd",
    "CreditNote": "UBL-CreditNote-2.1.xsd",
    "DebitNote": "UBL-DebitNote-2.1.xsd",
    "ApplicationResponse": "UBL-ApplicationResponse-2.1.xsd",
    "AttachedDocument": "UBL-AttachedDocument-2.1.xsd",
}


def _ephemeral_bundle() -> CertificateBundle:
    """Create a short-lived test certificate; no production secret is needed for XSD QA."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "XSD QA")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    return CertificateBundle(private_key, certificate, [])


def _validate(root: etree._Element, xsd_dir: Path, label: str) -> None:
    local_name = etree.QName(root).localname
    schema_path = xsd_dir / SCHEMA_BY_ROOT[local_name]
    schema = etree.XMLSchema(etree.parse(schema_path))
    schema.assertValid(root)
    print(f"OK {label}: {schema_path.name}")


def _document_roots() -> list[tuple[str, etree._Element]]:
    roots: list[tuple[str, etree._Element]] = []
    payloads = [deepcopy(payload) for payload in DOCUMENT_SUBMISSION_REQUEST_EXAMPLES]
    dee_credit = deepcopy(payloads[2])
    dee_credit["document"]["type"] = "NOTA_AJUSTE_DEE_CREDITO"
    dee_debit = deepcopy(payloads[3])
    dee_debit["document"]["type"] = "NOTA_AJUSTE_DEE_DEBITO"
    payloads.extend([dee_credit, dee_debit])
    for payload in list(payloads):
        if "payment_method" in payload["document"]:
            mixed = deepcopy(payload)
            mixed["document"].pop("payment_method")
            mixed["document"]["payment_methods"] = ["CASH", "CREDIT_CARD", "DEBIT_CARD", "TRANSFER"]
            payloads.append(mixed)
    for payload in payloads:
        request = to_core_submission_request(DocumentSubmissionRequest.model_validate(payload))
        document_key, qr_url = _compute_document_codes(request)
        label = request.document_type + (" combined payments" if request.payment_methods else "")
        roots.append((label, _build_document_xml(request, document_key, qr_url)))
    return roots


def _event_roots() -> list[tuple[str, etree._Element]]:
    roots: list[tuple[str, etree._Element]] = []
    now = datetime.now(COLOMBIA_TZ).replace(microsecond=0)
    issue_date = now.date().isoformat()
    issue_time = now.strftime("%H:%M:%S") + "-05:00"
    for example in EMIT_EVENT_OPENAPI_EXAMPLES.values():
        request = to_core_event_request(EmitEventRequest.model_validate(example["value"]))
        event_number = request.event_number or f"{request.event_type}{request.document_cufe[:12]}"
        cude = calculate_event_cude(
            EventCudeFields(
                num_de=event_number,
                fec_emi=issue_date,
                hor_emi=issue_time,
                nit_fe="900123456",
                doc_adq=request.supplier_nit,
                response_code=request.event_type,
                document_id=request.document_number,
                document_type_code=request.document_type_code,
                software_pin=request.software_pin or "pin-demo-001",
            )
        )
        roots.append(
            (
                f"EVENTO_{request.event_type}",
                build_application_response_xml(
                    request,
                    cude,
                    event_number,
                    issue_date,
                    issue_time,
                ),
            )
        )
    return roots


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--xsd-dir",
        type=Path,
        required=True,
        help="Official DIAN XSD/maindoc directory",
    )
    args = parser.parse_args()

    bundle = _ephemeral_bundle()
    document_roots = _document_roots()
    event_roots = _event_roots()
    for label, root in [*document_roots, *event_roots]:
        _validate(sign_document(root, bundle), args.xsd_dir, label)

    attached_payload = deepcopy(ATTACHED_DOCUMENT_REQUEST_EXAMPLE)
    invoice = sign_document(deepcopy(document_roots[0][1]), bundle)
    def invoice_value(name: str) -> str:
        return str(
            invoice.xpath(f"string(/*/*[local-name()='{name}'][1])")
        ).strip()
    attached_payload.update(
        document_number=invoice_value("ID"),
        cufe=invoice_value("UUID"),
        issue_date=invoice_value("IssueDate"),
        issue_time=invoice_value("IssueTime"),
        invoice_xml_base64=base64.b64encode(etree.tostring(invoice)).decode("ascii"),
    )
    # Container assertions must describe this exact signed document.
    for role, target in (("Supplier", "issuer"), ("Customer", "receiver")):
        path = (f"/*/*[local-name()='Accounting{role}Party']/*[local-name()='Party']"
                "/*[local-name()='PartyTaxScheme']")
        for field, xpath in (("name", "RegistrationName"), ("nit", "CompanyID"), ("tax_level_code", "TaxLevelCode")):
            attached_payload[f"{target}_{field}"] = str(invoice.xpath(f"string({path}/*[local-name()='{xpath}'])"))
        attached_payload[f"{target}_dv"] = str(invoice.xpath(f"string({path}/*[local-name()='CompanyID']/@schemeID)")) or None

    dian_response = deepcopy(event_roots[0][1])
    dian_response.xpath(
        "//*[local-name()='DocumentResponse']/*[local-name()='Response']"
        "/*[local-name()='ResponseCode']"
    )[0].text = "02"
    reference = dian_response.xpath(
        "//*[local-name()='DocumentResponse']/*[local-name()='DocumentReference']"
    )[0]
    reference.xpath("./*[local-name()='ID']")[0].text = attached_payload["document_number"]
    reference.xpath("./*[local-name()='UUID']")[0].text = attached_payload["cufe"]
    reference.xpath("./*[local-name()='DocumentTypeCode']")[0].text = "01"
    signed_response = sign_document(dian_response, bundle)
    attached_payload["application_response_xml_base64"] = base64.b64encode(
        etree.tostring(signed_response)
    ).decode("ascii")
    attached_request = AttachedDocumentRequest.model_validate(attached_payload)
    attached_xml = build_attached_document_xml(
        to_core_attached_document_request(attached_request)
    )
    _validate(
        sign_document(etree.fromstring(attached_xml), bundle),
        args.xsd_dir,
        "ATTACHED_DOCUMENT",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
