"""Core document submission and status services."""

from __future__ import annotations

import base64
import logging
from uuid import uuid4

from facturacion_dian_kit.core.config import resolve_wsdl_url, settings
from facturacion_dian_kit.core.cufe.calculator import (
    CudeFields,
    CufeFields,
    build_qr_url,
    calculate_cude,
    calculate_cufe,
)
from facturacion_dian_kit.core.dian.client import DianClient
from facturacion_dian_kit.core.dian.envelope import zip_and_encode
from facturacion_dian_kit.core.dian.response_parser import DianResponse
from facturacion_dian_kit.core.errors import CertificateConfigurationError, ConfigurationError
from facturacion_dian_kit.core.models import (
    AttachedDocumentBuildRequest,
    AttachedDocumentBuildResponse,
    DocumentSubmissionResult,
    DocumentSubmitRequest,
    Environment,
    SubmissionArtifacts,
)
from facturacion_dian_kit.core.runtime_config import (
    resolved_environment,
    resolved_issuer_nit,
    resolved_software_id,
    resolved_software_pin,
    resolved_technical_key,
    resolved_test_set_id,
    resolved_tipo_ambiente,
)
from facturacion_dian_kit.core.signing.certificate import get_certificate_bundle
from facturacion_dian_kit.core.signing.xades import sign_document_xml
from facturacion_dian_kit.core.xml.attached_document_builder import build_attached_document_xml
from facturacion_dian_kit.core.xml.credit_note_builder import build_credit_note_xml
from facturacion_dian_kit.core.xml.debit_note_builder import build_debit_note_xml
from facturacion_dian_kit.core.xml.invoice_builder import build_invoice_xml
from lxml import etree

logger = logging.getLogger(__name__)


def _base64_encode(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def _document_number(req: DocumentSubmitRequest) -> str:
    if req.document_type == "NOTA_CREDITO" and req.credit_note_number:
        return req.credit_note_number
    if req.document_type == "NOTA_DEBITO" and req.debit_note_number:
        return req.debit_note_number
    return req.invoice_number


def _aggregate_tax(req: DocumentSubmitRequest, tax_prefix: str) -> int:
    return sum(line.tax_amount for line in req.lines if line.tax_type.startswith(tax_prefix))


def _compute_document_codes(req: DocumentSubmitRequest) -> tuple[str, str]:
    val_iva = _aggregate_tax(req, "IVA")
    buyer_identifier = req.customer_nit or "222222222222"

    if req.document_type == "FACTURA_ELECTRONICA":
        document_key = calculate_cufe(
            CufeFields(
                num_fac=req.invoice_number,
                fec_fac=req.issue_date,
                hor_fac=req.issue_time,
                val_fac=req.subtotal,
                val_iva=val_iva,
                val_inc=0,
                val_ica=0,
                val_tot_fac=req.total,
                nit_ofe=resolved_issuer_nit(req),
                num_adq=buyer_identifier,
                clave_tecnica=resolved_technical_key(req),
                tipo_ambiente=resolved_tipo_ambiente(req),
            )
        )
    else:
        document_key = calculate_cude(
            CudeFields(
                num_fac=_document_number(req),
                fec_fac=req.issue_date,
                hor_fac=req.issue_time,
                val_fac=req.subtotal,
                val_iva=val_iva,
                val_inc=0,
                val_ica=0,
                val_tot_fac=req.total,
                nit_ofe=resolved_issuer_nit(req),
                num_adq=buyer_identifier,
                software_pin=resolved_software_pin(req),
                tipo_ambiente=resolved_tipo_ambiente(req),
            )
        )

    return document_key, build_qr_url(document_key)


def _build_document_xml(
    req: DocumentSubmitRequest,
    document_key: str,
    qr_url: str,
) -> etree._Element:
    if req.document_type == "NOTA_CREDITO":
        return build_credit_note_xml(req, document_key, qr_url)
    if req.document_type == "NOTA_DEBITO":
        return build_debit_note_xml(req, document_key, qr_url)
    return build_invoice_xml(req, document_key, qr_url)


def _collect_messages(dian_response: DianResponse) -> list[str]:
    if dian_response.error_messages:
        return dian_response.error_messages

    values = [
        dian_response.status_message.strip(),
        dian_response.status_description.strip(),
    ]
    return [value for value in values if value]


def _validate_submission_config(req: DocumentSubmitRequest) -> None:
    required_pairs = {
        "issuer_nit": resolved_issuer_nit(req),
        "software_id": resolved_software_id(req),
        "software_pin": resolved_software_pin(req),
    }

    if req.document_type == "FACTURA_ELECTRONICA":
        required_pairs["technical_key"] = resolved_technical_key(req)

    if resolved_environment(req) == "habilitacion":
        required_pairs["test_set_id"] = resolved_test_set_id(req)

    missing = [name for name, value in required_pairs.items() if not value.strip()]
    if missing:
        joined = ", ".join(sorted(missing))
        raise ConfigurationError(f"Missing required submission settings: {joined}")


class DocumentSubmissionService:
    """Application service that signs and submits DIAN documents."""

    async def submit_document(
        self,
        req: DocumentSubmitRequest,
        *,
        include_xml_artifact: bool = True,
    ) -> DocumentSubmissionResult:
        _validate_submission_config(req)

        submission_id = str(uuid4())
        document_number = _document_number(req)
        xml_filename = f"ws_{document_number}.xml"
        document_key, qr_url = _compute_document_codes(req)
        logger.info("Submitting %s (%s)", document_number, req.document_type)

        xml_root = _build_document_xml(req, document_key, qr_url)

        try:
            bundle = get_certificate_bundle()
            signed_xml = sign_document_xml(xml_root, bundle)
        except FileNotFoundError as exc:
            raise CertificateConfigurationError(str(exc)) from exc
        except ValueError as exc:
            raise CertificateConfigurationError(str(exc)) from exc

        zip_filename, content_b64 = zip_and_encode(xml_filename, signed_xml)
        client = DianClient(endpoint_url=resolve_wsdl_url(resolved_environment(req)))

        if resolved_environment(req) == "habilitacion":
            dian_response = await client.send_test_set_async(
                zip_filename,
                content_b64,
                resolved_test_set_id(req),
            )
        else:
            dian_response = await client.send_bill_sync(zip_filename, content_b64)

        artifacts = None
        if include_xml_artifact:
            artifacts = SubmissionArtifacts(
                xml_base64=_base64_encode(signed_xml),
                xml_filename=xml_filename,
            )

        return DocumentSubmissionResult(
            submission_id=submission_id,
            tracking_id=dian_response.tracking_id or submission_id,
            document_key=document_key,
            qr_url=qr_url,
            status="accepted" if dian_response.is_accepted else "rejected",
            messages=_collect_messages(dian_response),
            dian_response=dian_response.to_dict(),
            artifacts=artifacts,
            client_reference=req.client_reference,
        )

    async def get_status(
        self,
        tracking_id: str,
        *,
        environment: Environment | None = None,
        include_xml_artifact: bool = True,
    ) -> DocumentSubmissionResult:
        resolved: Environment = environment or settings.dian.environment
        client = DianClient(endpoint_url=resolve_wsdl_url(resolved))
        if resolved == "habilitacion":
            dian_response = await client.get_status_zip(tracking_id)
        else:
            dian_response = await client.get_status(tracking_id)

        artifacts = None
        if include_xml_artifact and dian_response.xml_bytes is not None:
            artifacts = SubmissionArtifacts(
                xml_base64=_base64_encode(dian_response.xml_bytes),
                xml_filename=f"status_{tracking_id}.xml",
            )

        return DocumentSubmissionResult(
            submission_id=tracking_id,
            tracking_id=tracking_id,
            status="accepted" if dian_response.is_accepted else "rejected",
            messages=_collect_messages(dian_response),
            dian_response=dian_response.to_dict(),
            artifacts=artifacts,
        )

    def build_attached_document(
        self,
        req: AttachedDocumentBuildRequest,
    ) -> AttachedDocumentBuildResponse:
        xml_filename = f"ad_{req.document_number}.xml"
        xml_bytes = build_attached_document_xml(req)
        zip_filename, content_b64 = zip_and_encode(xml_filename, xml_bytes)
        return AttachedDocumentBuildResponse(
            xml_filename=xml_filename,
            zip_filename=zip_filename,
            content_base64=content_b64,
        )
