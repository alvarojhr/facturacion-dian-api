"""Core document submission and status services."""

from __future__ import annotations

import base64
import logging
from decimal import Decimal
from uuid import uuid4

from facturacion_dian_api.core.config import resolve_wsdl_url, settings
from facturacion_dian_api.core.cufe.calculator import (
    CudeFields,
    CufeFields,
    build_qr_url,
    calculate_cude,
    calculate_cufe,
)
from facturacion_dian_api.core.dian.client import DianClient
from facturacion_dian_api.core.dian.envelope import zip_and_encode
from facturacion_dian_api.core.dian.response_parser import DianResponse
from facturacion_dian_api.core.errors import CertificateConfigurationError, ConfigurationError
from facturacion_dian_api.core.filenames import build_dian_filename, build_document_filename
from facturacion_dian_api.core.models import (
    AttachedDocumentBuildRequest,
    AttachedDocumentBuildResponse,
    DocumentSubmissionResult,
    DocumentSubmitRequest,
    DownloadByKeyResult,
    Environment,
    SubmissionArtifacts,
)
from facturacion_dian_api.core.runtime_config import (
    resolved_environment,
    resolved_issuer_nit,
    resolved_software_id,
    resolved_software_pin,
    resolved_technical_key,
    resolved_test_set_id,
    resolved_tipo_ambiente,
)
from facturacion_dian_api.core.signing.certificate import get_certificate_bundle
from facturacion_dian_api.core.signing.xades import sign_document_xml, verify_document_signature
from facturacion_dian_api.core.xml.attached_document_builder import build_attached_document_xml
from facturacion_dian_api.core.xml.credit_note_builder import build_credit_note_xml
from facturacion_dian_api.core.xml.debit_note_builder import build_debit_note_xml
from facturacion_dian_api.core.xml.invoice_builder import build_invoice_xml
from facturacion_dian_api.core.xml.namespaces import NS_DS
from lxml import etree

logger = logging.getLogger(__name__)


def _base64_encode(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def _document_number(req: DocumentSubmitRequest) -> str:
    if req.document_type in {"NOTA_CREDITO", "NOTA_AJUSTE_DEE_CREDITO"} and req.credit_note_number:
        return req.credit_note_number
    if req.document_type in {"NOTA_DEBITO", "NOTA_AJUSTE_DEE_DEBITO"} and req.debit_note_number:
        return req.debit_note_number
    return req.invoice_number


def _aggregate_tax(req: DocumentSubmitRequest, tax_types: set[str]) -> Decimal:
    return sum(
        (tax.amount for line in req.lines for tax in line.taxes if tax.tax_type in tax_types),
        Decimal("0"),
    )


def _compute_document_codes(req: DocumentSubmitRequest) -> tuple[str, str]:
    val_iva = _aggregate_tax(req, {"IVA_19", "IVA_5", "IVA_0", "EXEMPT"})
    # The CUFE/CUDE seed's ValImp2 field is specifically scheme 04 (INC).
    # Scheme 02 (IC) remains in the XML but does not belong in ValImp2.
    val_inc = _aggregate_tax(req, {"INC"})
    val_ica = _aggregate_tax(req, {"ICA"})
    buyer_identifier = (req.customer_nit or "222222222222").strip()

    if req.document_type == "FACTURA_ELECTRONICA":
        document_key = calculate_cufe(
            CufeFields(
                num_fac=req.invoice_number,
                fec_fac=req.issue_date,
                hor_fac=req.issue_time,
                val_fac=req.subtotal,
                val_iva=val_iva,
                val_inc=val_inc,
                val_ica=val_ica,
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
                val_inc=val_inc,
                val_ica=val_ica,
                val_tot_fac=req.total,
                nit_ofe=resolved_issuer_nit(req),
                num_adq=buyer_identifier,
                software_pin=resolved_software_pin(req),
                tipo_ambiente=resolved_tipo_ambiente(req),
            )
        )

    return document_key, build_qr_url(document_key, resolved_environment(req))


def _build_document_xml(
    req: DocumentSubmitRequest,
    document_key: str,
    qr_url: str,
) -> etree._Element:
    if req.document_type in {
        "NOTA_CREDITO",
        "NOTA_AJUSTE_DEE_CREDITO",
        "NOTA_AJUSTE_DEE_DEBITO",
    }:
        return build_credit_note_xml(req, document_key, qr_url)
    if req.document_type in {"NOTA_DEBITO", "NOTA_AJUSTE_DEE_DEBITO"}:
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

    if req.document_type in {
        "FACTURA_ELECTRONICA",
        "FACTURA_CONTINGENCIA_FACTURADOR",
        "FACTURA_CONTINGENCIA_DIAN",
    }:
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
        del include_xml_artifact  # signed XML is mandatory for fiscal recovery
        _validate_submission_config(req)

        submission_id = str(uuid4())
        document_number = _document_number(req)
        xml_filename = build_document_filename(
            req.document_type,
            issuer_nit=resolved_issuer_nit(req),
            provider_code=req.file_provider_code,
            document_number=document_number,
            issue_date=req.issue_date,
            sequence=req.file_sequence,
        )
        document_key, qr_url = _compute_document_codes(req)
        logger.info("Submitting %s (%s)", document_number, req.document_type)

        if req.signed_xml_base64:
            if req.signed_xml_filename != xml_filename:
                raise ConfigurationError(
                    "signed_xml_filename does not match the technical filename for this request"
                )
            try:
                signed_xml = base64.b64decode(req.signed_xml_base64, validate=True)
                signed_root = etree.fromstring(
                    signed_xml,
                    parser=etree.XMLParser(resolve_entities=False, no_network=True),
                )
            except (ValueError, etree.XMLSyntaxError) as exc:
                raise ConfigurationError(f"Invalid signed_xml_base64: {exc}") from exc
            parsed_number = str(
                signed_root.xpath("string(/*/*[local-name()='ID'][1])")
            ).strip()
            parsed_key = str(
                signed_root.xpath("string(/*/*[local-name()='UUID'][1])")
            ).strip()
            if signed_root.find(f".//{{{NS_DS}}}Signature") is None:
                raise ConfigurationError("signed_xml_base64 does not contain ds:Signature")
            if parsed_number != document_number or parsed_key != document_key:
                raise ConfigurationError("Signed XML does not match the fiscal request/key")
            try:
                verify_document_signature(signed_root, get_certificate_bundle())
            except (FileNotFoundError, ValueError) as exc:
                raise CertificateConfigurationError(str(exc)) from exc
        else:
            xml_root = _build_document_xml(req, document_key, qr_url)
            try:
                bundle = get_certificate_bundle()
                signed_xml = sign_document_xml(xml_root, bundle)
            except FileNotFoundError as exc:
                raise CertificateConfigurationError(str(exc)) from exc
            except ValueError as exc:
                raise CertificateConfigurationError(str(exc)) from exc

        artifacts = SubmissionArtifacts(
            xml_base64=_base64_encode(signed_xml),
            xml_filename=xml_filename,
        )
        if req.prepare_only:
            return DocumentSubmissionResult(
                submission_id=submission_id,
                tracking_id=None,
                document_key=document_key,
                qr_url=qr_url,
                status="prepared",
                messages=["Signed document prepared; persist it before transmission"],
                dian_response={"prepared": True, "transmitted": False},
                artifacts=artifacts,
                client_reference=req.client_reference,
            )

        zip_filename = build_dian_filename(
            family="z",
            issuer_nit=resolved_issuer_nit(req),
            provider_code=req.file_provider_code,
            document_number=document_number,
            issue_date=req.issue_date,
            sequence=req.file_sequence,
            extension="zip",
        )
        zip_filename, content_b64 = zip_and_encode(xml_filename, signed_xml, zip_filename)
        client = DianClient(endpoint_url=resolve_wsdl_url(resolved_environment(req)))

        if resolved_environment(req) == "habilitacion":
            dian_response = await client.send_test_set_async(
                zip_filename,
                content_b64,
                resolved_test_set_id(req),
            )
        else:
            dian_response = await client.send_bill_sync(zip_filename, content_b64)

        artifacts.application_response_xml_base64 = (
            _base64_encode(dian_response.xml_bytes)
            if dian_response.xml_bytes is not None
            else None
        )
        artifacts.application_response_xml_filename = (
            build_dian_filename(
                family=(
                    "ars"
                    if req.document_type.startswith("DOCUMENTO_EQUIVALENTE_POS")
                    or req.document_type.startswith("NOTA_AJUSTE_DEE")
                    else "ar"
                ),
                issuer_nit=resolved_issuer_nit(req),
                provider_code=req.file_provider_code,
                document_number=document_number,
                issue_date=req.issue_date,
                sequence=req.file_sequence,
            )
            if dian_response.xml_bytes is not None
            else None
        )

        return DocumentSubmissionResult(
            submission_id=submission_id,
            tracking_id=dian_response.tracking_id,
            document_key=document_key,
            qr_url=qr_url,
            status=dian_response.processing_status,  # type: ignore[arg-type]
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
            # En GetStatus el XML que devuelve DIAN siempre es el Application
            # Response firmado por la DIAN (no el documento original del emisor).
            # Antes lo veníamos exponiendo como ``xml_base64`` con el filename
            # ``status_<tracking>.xml``, pero eso confundía al cliente — quien
            # debe persistir el AR en una columna distinta del SIGNED_XML del
            # emisor. Ahora lo mapeamos al campo correcto para que la semántica
            # sea consistente con submit_document.
            artifacts = SubmissionArtifacts(
                application_response_xml_base64=_base64_encode(dian_response.xml_bytes),
                application_response_xml_filename=f"ar_{tracking_id}.xml",
            )

        return DocumentSubmissionResult(
            submission_id=tracking_id,
            tracking_id=tracking_id,
            status=dian_response.processing_status,  # type: ignore[arg-type]
            messages=_collect_messages(dian_response),
            dian_response=dian_response.to_dict(),
            artifacts=artifacts,
        )

    async def download_by_key(
        self,
        document_key: str,
        *,
        environment: Environment | None = None,
    ) -> DownloadByKeyResult:
        resolved: Environment = environment or settings.dian.environment
        client = DianClient(endpoint_url=resolve_wsdl_url(resolved))
        result = await client.get_xml_by_document_key(document_key)

        xml_base64 = None
        if result.xml_bytes:
            xml_base64 = _base64_encode(result.xml_bytes)

        return DownloadByKeyResult(
            success=result.success,
            document_key=document_key,
            xml_base64=xml_base64,
            xml_filename=f"dian_{document_key[:20]}.xml" if result.success else None,
            status=result.status,
            error_message=result.error_message or None,
            raw_response=result.to_dict(),
        )

    def build_attached_document(
        self,
        req: AttachedDocumentBuildRequest,
    ) -> AttachedDocumentBuildResponse:
        xml_filename = build_dian_filename(
            family="ad",
            issuer_nit=req.issuer_nit,
            provider_code=req.file_provider_code,
            document_number=req.document_number,
            issue_date=req.issue_date,
            sequence=req.file_sequence,
        )
        xml_bytes = build_attached_document_xml(req)
        try:
            xml_root = etree.fromstring(xml_bytes)
            xml_bytes = sign_document_xml(xml_root, get_certificate_bundle())
        except (FileNotFoundError, ValueError) as exc:
            raise CertificateConfigurationError(str(exc)) from exc
        zip_filename, content_b64 = zip_and_encode(xml_filename, xml_bytes)
        return AttachedDocumentBuildResponse(
            xml_filename=xml_filename,
            zip_filename=zip_filename,
            content_base64=content_b64,
        )
