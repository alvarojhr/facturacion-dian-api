"""Public HTTP contracts exposed by facturacion-dian-api."""

from __future__ import annotations

from typing import Any, Literal, cast

from facturacion_dian_api.core.models import (
    ClaimCauseCode,
    CustomerDocumentType,
    DocumentStatus,
    DocumentType,
    Environment,
    EventStatus,
    EventType,
)
from facturacion_dian_api.server.examples import (
    ATTACHED_DOCUMENT_REQUEST_EXAMPLE,
    ATTACHED_DOCUMENT_RESPONSE_EXAMPLE,
    BUYER_LOOKUP_REQUEST_EXAMPLE,
    BUYER_LOOKUP_RESPONSE_EXAMPLE,
    DOCUMENT_STATUS_RESPONSE_EXAMPLE,
    DOCUMENT_SUBMISSION_REQUEST_EXAMPLES,
    DOCUMENT_SUBMISSION_RESPONSE_EXAMPLE,
    DOWNLOAD_BY_KEY_REQUEST_EXAMPLE,
    DOWNLOAD_BY_KEY_RESPONSE_EXAMPLE,
    EMIT_EVENT_ACKNOWLEDGEMENT_EXAMPLE,
    EMIT_EVENT_CLAIM_EXAMPLE,
    EMIT_EVENT_GOODS_RECEIPT_EXAMPLE,
    EMIT_EVENT_RESPONSE_EXAMPLE,
    HEALTH_RESPONSE_EXAMPLE,
    NUMBERING_RANGE_LOOKUP_REQUEST_EXAMPLE,
    NUMBERING_RANGE_LOOKUP_RESPONSE_EXAMPLE,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator


class LineItemInput(BaseModel):
    """Public line item shape for document submissions."""

    description: str
    item_name: str | None = None
    item_code: str | None = None
    unit_code: str | None = None
    quantity: float
    unit_price: int
    line_total: int
    tax_type: str
    tax_amount: int


class PointOfSaleInput(BaseModel):
    """Optional point-of-sale metadata for POS-equivalent documents."""

    register_plate: str | None = None
    register_location: str | None = None
    cashier_name: str | None = None
    register_type: str | None = None
    sale_code: str | None = None
    buyer_loyalty_points: int | None = None


class DocumentInput(BaseModel):
    """Document-level metadata."""

    number: str
    type: DocumentType
    issue_date: str = Field(description="YYYY-MM-DD")
    issue_time: str = Field(description="HH:MM:SS-05:00")
    payment_method: str = Field(description="CASH | CARD | TRANSFER")
    point_of_sale: PointOfSaleInput | None = None


class IssuerInput(BaseModel):
    """Optional issuer identity; ``name`` enables the body-owned contract."""

    nit: str | None = None
    dv: str | None = None
    name: str | None = None
    additional_account_id: Literal["1", "2"] | None = None
    address: str | None = None
    city_code: str | None = None
    city_name: str | None = None
    department_code: str | None = None
    department_name: str | None = None
    country_code: str | None = None
    tax_level_code: str | None = None
    economic_activity: str | None = None
    phone: str | None = None
    email: str | None = None
    software_owner_nit: str | None = None


class BuyerInput(BaseModel):
    """Buyer data required to render the DIAN UBL payload."""

    name: str
    document_number: str | None = None
    document_type: CustomerDocumentType | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city_code: str | None = None
    city_name: str | None = None
    department_code: str | None = None
    department_name: str | None = None
    country_code: str | None = None


class ResolutionInput(BaseModel):
    """Authorized numbering resolution data."""

    number: str
    prefix: str
    date: str | None = None
    range_from: int | None = None
    range_to: int | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    number_width: int | None = None


class TotalsInput(BaseModel):
    """Monetary totals reported to DIAN."""

    subtotal: int
    tax_total: int
    total: int


class ReferenceInput(BaseModel):
    """Reference metadata used by note documents."""

    referenced_document_number: str | None = None
    referenced_document_key: str | None = None
    referenced_issue_date: str | None = None
    reason: str | None = None
    response_code: str | None = None


class SubmissionOptionsInput(BaseModel):
    """Runtime-only options that should not be persisted as business data."""

    software_id: str | None = None
    software_pin: str | None = None
    test_set_id: str | None = None
    technical_key: str | None = None
    return_xml_artifact: bool = True


class DocumentSubmissionRequest(BaseModel):
    """Public request contract for document submission."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"examples": DOCUMENT_SUBMISSION_REQUEST_EXAMPLES})
    )

    document: DocumentInput
    issuer: IssuerInput | None = None
    buyer: BuyerInput
    resolution: ResolutionInput
    totals: TotalsInput
    line_items: list[LineItemInput]
    references: ReferenceInput | None = None
    environment: Environment | None = None
    submission_options: SubmissionOptionsInput | None = None
    client_reference: str | None = None


class SubmissionArtifactPayload(BaseModel):
    """Opaque artifacts returned by the server when requested.

    ``xml_base64``/``xml_filename`` exponen el documento firmado por el
    emisor (carga el CUFE). ``application_response_xml_base64``/
    ``application_response_xml_filename`` exponen el Application Response
    firmado por la DIAN — comprobante con timestamp oficial que la
    Resolución 165 colombiana exige retener por separado del documento
    original. Cuando un canal asíncrono (habilitación, GetStatus posterior)
    aún no devuelve uno de los dos, el campo queda en ``None``.
    """

    xml_base64: str | None = None
    xml_filename: str | None = None
    application_response_xml_base64: str | None = None
    application_response_xml_filename: str | None = None


class DocumentSubmissionResponse(BaseModel):
    """Public response contract for document submission and status lookups."""

    model_config = ConfigDict(
        json_schema_extra=cast(
            dict[str, Any],
            {
                "examples": [
                    DOCUMENT_SUBMISSION_RESPONSE_EXAMPLE,
                    DOCUMENT_STATUS_RESPONSE_EXAMPLE,
                ]
            },
        )
    )

    submission_id: str
    tracking_id: str
    client_reference: str | None = None
    document_key: str | None = None
    qr_url: str | None = None
    status: DocumentStatus
    messages: list[str] = Field(default_factory=list)
    dian_response: dict[str, Any] = Field(default_factory=dict)
    artifacts: SubmissionArtifactPayload | None = None


class AttachedDocumentRequest(BaseModel):
    """Public request to build an AttachedDocument ZIP payload."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": ATTACHED_DOCUMENT_REQUEST_EXAMPLE})
    )

    document_number: str
    document_type_code: str
    issuer_nit: str
    issuer_name: str
    receiver_name: str
    receiver_email: str | None = None
    reply_to_email: str
    company_name: str | None = None
    business_line: str | None = None
    invoice_xml_base64: str
    invoice_xml_filename: str
    issue_date: str | None = None
    cufe: str | None = None
    validation_result_code: str | None = None


class AttachedDocumentResponse(BaseModel):
    """ZIP build response for AttachedDocument payloads."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": ATTACHED_DOCUMENT_RESPONSE_EXAMPLE})
    )

    xml_filename: str
    zip_filename: str
    content_base64: str


class BuyerLookupRequest(BaseModel):
    """Public buyer lookup request."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": BUYER_LOOKUP_REQUEST_EXAMPLE})
    )

    environment: Environment | None = None
    document_type: Literal["NIT", "CC", "CE", "TI", "PASSPORT"]
    document_number: str


class BuyerLookupPayload(BaseModel):
    """Normalized DIAN buyer information."""

    display_name: str
    document_type: Literal["NIT", "CC", "CE", "TI", "PASSPORT"]
    document_number: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city_code: str | None = None
    city_name: str | None = None
    department_code: str | None = None
    department_name: str | None = None
    country_code: str = "CO"


class BuyerLookupResponse(BaseModel):
    """Buyer lookup response."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": BUYER_LOOKUP_RESPONSE_EXAMPLE})
    )

    found: bool
    error_message: str | None = None
    customer: BuyerLookupPayload | None = None


class NumberingRangeLookupRequest(BaseModel):
    """Request to look up DIAN numbering ranges."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": NUMBERING_RANGE_LOOKUP_REQUEST_EXAMPLE})
    )

    environment: Environment | None = None
    account_code: str
    account_code_t: str
    software_code: str


class NumberingRangePayload(BaseModel):
    """Authorized numbering range returned by DIAN."""

    resolution_number: str
    resolution_date: str | None = None
    prefix: str
    from_number: int
    to_number: int
    valid_date_from: str | None = None
    valid_date_to: str | None = None
    technical_key: str | None = None


class NumberingRangeLookupResponse(BaseModel):
    """Numbering range lookup response."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": NUMBERING_RANGE_LOOKUP_RESPONSE_EXAMPLE})
    )

    ranges: list[NumberingRangePayload] = Field(default_factory=list)


class DownloadByKeyRequest(BaseModel):
    """Request to download a document XML by its CUFE/CUDE."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": DOWNLOAD_BY_KEY_REQUEST_EXAMPLE})
    )

    environment: Environment | None = None
    document_key: str = Field(description="CUFE or CUDE of the document")


class DownloadByKeyResponse(BaseModel):
    """Response with the downloaded XML."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": DOWNLOAD_BY_KEY_RESPONSE_EXAMPLE})
    )

    success: bool
    document_key: str
    xml_base64: str | None = None
    xml_filename: str | None = None
    status: str = ""
    error_message: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class EventOptionsInput(BaseModel):
    """Runtime-only credentials for a RADIAN event submission."""

    software_id: str | None = None
    software_pin: str | None = None


class EventReceiverPersonInput(BaseModel):
    """Person who took delivery of the invoice, goods or services.

    Maps to ``cac:DocumentResponse/cac:IssuerParty/cac:Person``. DIAN makes
    this group mandatory for the 032 event and validates it on 030/033, so
    send it whenever the receiving person is known.
    """

    document_number: str
    document_type: str = Field(default="13", description="Codigo DIAN @schemeName (13 = CC, 31 = NIT)")
    first_name: str
    family_name: str
    job_title: str | None = None
    organization_department: str | None = None


class EmitEventRequest(BaseModel):
    """Public request contract to register a RADIAN receiver event.

    The identity of whoever emits the event (the invoice receiver) comes from
    the deployment's ``COMPANY_*`` configuration, never from the body: one
    deployment = one issuer (AGENTS.md § 3). Only the counterpart — the
    supplier that issued the referenced invoice — travels in the request.
    """

    model_config = ConfigDict(
        json_schema_extra=cast(
            dict[str, Any],
            {
                "examples": [
                    EMIT_EVENT_ACKNOWLEDGEMENT_EXAMPLE,
                    EMIT_EVENT_GOODS_RECEIPT_EXAMPLE,
                    EMIT_EVENT_CLAIM_EXAMPLE,
                ]
            },
        )
    )

    event_type: EventType = Field(
        description="030 acuse | 031 reclamo | 032 recibo del bien | 033 aceptacion expresa"
    )
    environment: Environment | None = None
    event_number: str | None = Field(
        default=None,
        description=(
            "Consecutivo propio del receptor para ApplicationResponse/cbc:ID. "
            "Si se omite se deriva del CUFE referenciado, lo que mantiene "
            "estable el CUDE entre reintentos."
        ),
    )
    document_cufe: str = Field(description="CUFE de la factura del proveedor")
    document_number: str
    document_issue_date: str | None = Field(default=None, description="YYYY-MM-DD")
    document_type_code: str = Field(default="01", description="Tipo del documento referenciado")
    supplier_nit: str
    supplier_name: str
    supplier_dv: str | None = None
    total_amount: int | None = None
    claim_cause_code: ClaimCauseCode | None = Field(default=None, description="Solo evento 031")
    claim_description: str | None = Field(default=None, description="Solo evento 031")
    receiver_person: EventReceiverPersonInput | None = None
    submission_options: EventOptionsInput | None = None
    client_reference: str | None = None

    @model_validator(mode="after")
    def _require_claim_fields(self) -> EmitEventRequest:
        if self.event_type == "031" and not self.claim_cause_code:
            raise ValueError("El evento 031 (reclamo) requiere claim_cause_code (01-04)")
        if self.event_type != "031" and self.claim_cause_code:
            raise ValueError("claim_cause_code solo aplica al evento 031 (reclamo)")
        return self


class EventArtifactPayload(BaseModel):
    """XML artifacts returned after registering a RADIAN event.

    ``application_response_*`` is the event signed by the receiver;
    ``dian_response_*`` is the ApplicationResponse the DIAN signs back. The
    Resolucion 165 requires retaining both, so persist them separately.
    """

    application_response_xml_base64: str | None = None
    application_response_xml_filename: str | None = None
    dian_response_xml_base64: str | None = None
    dian_response_xml_filename: str | None = None


class EmitEventResponse(BaseModel):
    """Public response contract for a RADIAN event submission.

    ``FAILED`` is never returned by this endpoint: a transport failure surfaces
    as 502/504 and only the caller records it as such. A functional rejection
    from DIAN is ``200`` with ``status="REJECTED"`` (AGENTS.md § 7).
    """

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": EMIT_EVENT_RESPONSE_EXAMPLE})
    )

    status: EventStatus
    cude: str | None = None
    tracking_id: str | None = None
    client_reference: str | None = None
    messages: list[str] = Field(default_factory=list)
    dian_response: dict[str, Any] = Field(default_factory=dict)
    artifacts: EventArtifactPayload | None = None


class HealthResponse(BaseModel):
    """Health probe response."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"example": HEALTH_RESPONSE_EXAMPLE})
    )

    status: str
    version: str
    dian_environment: str
    certificate_loaded: bool
    certificate_valid_until: str | None = None
