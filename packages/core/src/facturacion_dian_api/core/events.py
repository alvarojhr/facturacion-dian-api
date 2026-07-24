"""RADIAN receiver-event service (ApplicationResponse 030/031/032/033).

Orchestrates the whole round trip: build the ApplicationResponse, sign it with
XAdES, ZIP it, transmit it through ``SendEventUpdateStatus`` and parse DIAN's
verdict.

The service is stateless, like the rest of this API: it neither keeps the
event sequence nor enforces the DIAN ordering ``030 → 032 → (033 | 031)``.
Both belong to the caller — events consume no DIAN numbering range, so a retry
may safely resend the very same document.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime

from facturacion_dian_api.core.config import resolve_wsdl_url, settings
from facturacion_dian_api.core.cufe.calculator import EventCudeFields, calculate_event_cude
from facturacion_dian_api.core.dian.client import DianClient
from facturacion_dian_api.core.dian.envelope import zip_and_encode
from facturacion_dian_api.core.dian.response_parser import DianResponse
from facturacion_dian_api.core.errors import CertificateConfigurationError, ConfigurationError
from facturacion_dian_api.core.models import (
    EventArtifacts,
    EventSubmissionResult,
    EventSubmitRequest,
)
from facturacion_dian_api.core.signing.certificate import get_certificate_bundle
from facturacion_dian_api.core.signing.xades import COLOMBIA_TZ, sign_document_xml
from facturacion_dian_api.core.xml.application_response_builder import (
    build_application_response_xml,
)

logger = logging.getLogger(__name__)


def colombia_now() -> datetime:
    """Return the current instant in Colombian time.

    Isolated so tests can freeze it, and so every caller shares one source of
    truth: the event date must match the XAdES signing date (rule AAD09e), and
    both feed the CUDE seed.
    """
    return datetime.now(COLOMBIA_TZ)


def _resolve_event_number(req: EventSubmitRequest) -> str:
    """Resolve ``ApplicationResponse/cbc:ID``.

    DIAN wants a consecutive owned by whoever generates the event, unique per
    event type (rule AAD05b). This service holds no sequence, so the caller
    should send ``event_number``. The fallback derives a stable value from the
    referenced CUFE: unique per (invoice, event type) — the only combination
    DIAN accepts once anyway — and identical across retries of the same event,
    so a retry keeps the same consecutive.

    Note this does not make the *CUDE* stable across retries: the event
    re-stamps its date/time from the clock on each call to satisfy rule AAD09e
    (issue date = signing date), and the timestamp feeds the CUDE seed. A retry
    is a freshly signed document with the same event number but a new CUDE,
    which is correct for RADIAN — events consume no numbering range.
    """
    explicit = (req.event_number or "").strip()
    if explicit:
        return explicit
    return f"{req.event_type}{req.document_cufe[:12]}"


def _validate_event_config(req: EventSubmitRequest) -> None:
    required = {
        "software_id": (req.software_id or settings.dian.software_id).strip(),
        "software_pin": (req.software_pin or settings.dian.software_pin).strip(),
        "company_nit": settings.company.nit.strip(),
        "company_name": settings.company.name.strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        joined = ", ".join(sorted(missing))
        raise ConfigurationError(f"Missing required event settings: {joined}")

    if req.event_type == "031" and not req.claim_cause_code:
        raise ConfigurationError("Event 031 (reclamo) requires claim_cause_code (01-04)")


def _collect_messages(dian_response: DianResponse) -> list[str]:
    if dian_response.error_messages:
        return dian_response.error_messages

    values = [
        dian_response.status_message.strip(),
        dian_response.status_description.strip(),
    ]
    return [value for value in values if value]


class EventSubmissionService:
    """Application service that builds, signs and registers RADIAN events.

    Returns ``ACCEPTED``/``REJECTED`` only: those are DIAN's functional
    verdicts and both travel as HTTP 200 (AGENTS.md § 7). The third status of
    the public contract, ``FAILED``, is what a caller records when the call
    itself fails — this service raises ``DianTimeoutError``/``DianUpstreamError``
    for that and the HTTP layer maps them to 504/502.
    """

    async def emit_event(self, req: EventSubmitRequest) -> EventSubmissionResult:
        _validate_event_config(req)

        # Una sola instancia de fecha/hora alimenta la semilla del CUDE, el XML
        # y (vía datetime.now(COLOMBIA_TZ) en el firmador) la fecha de la firma.
        # La regla AAD09e rechaza el evento si esas fechas no coinciden, por eso
        # el servicio las estampa en vez de aceptarlas del llamador.
        now = colombia_now()
        issue_date = now.date().isoformat()
        issue_time = now.strftime("%H:%M:%S") + "-05:00"
        event_number = _resolve_event_number(req)

        cude = calculate_event_cude(
            EventCudeFields(
                num_de=event_number,
                fec_emi=issue_date,
                hor_emi=issue_time,
                nit_fe=settings.company.nit,
                doc_adq=req.supplier_nit,
                response_code=req.event_type,
                document_id=req.document_number,
                document_type_code=req.document_type_code,
                software_pin=(req.software_pin or settings.dian.software_pin).strip(),
            )
        )

        logger.info(
            "Emitting RADIAN event %s for document %s",
            req.event_type,
            req.document_number,
        )

        xml_root = build_application_response_xml(req, cude, event_number, issue_date, issue_time)

        try:
            bundle = get_certificate_bundle()
            signed_xml = sign_document_xml(xml_root, bundle)
        except FileNotFoundError as exc:
            raise CertificateConfigurationError(str(exc)) from exc
        except ValueError as exc:
            raise CertificateConfigurationError(str(exc)) from exc

        xml_filename = f"ar_{req.event_type}_{req.document_number}.xml"
        _, content_b64 = zip_and_encode(xml_filename, signed_xml)

        environment = req.environment or settings.dian.environment
        client = DianClient(endpoint_url=resolve_wsdl_url(environment))
        dian_response = await client.send_event_update_status(content_b64)

        artifacts = EventArtifacts(
            application_response_xml_base64=base64.b64encode(signed_xml).decode("ascii"),
            application_response_xml_filename=xml_filename,
            dian_response_xml_base64=(
                base64.b64encode(dian_response.xml_bytes).decode("ascii")
                if dian_response.xml_bytes is not None
                else None
            ),
            dian_response_xml_filename=(
                f"dian_{req.event_type}_{req.document_number}.xml"
                if dian_response.xml_bytes is not None
                else None
            ),
        )

        return EventSubmissionResult(
            status="ACCEPTED" if dian_response.is_accepted else "REJECTED",
            cude=cude,
            tracking_id=dian_response.tracking_id,
            messages=_collect_messages(dian_response),
            dian_response=dian_response.to_dict(),
            artifacts=artifacts,
            client_reference=req.client_reference,
        )
