"""Internal models shared by the core and server packages."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

DocumentType = Literal[
    "FACTURA_ELECTRONICA",
    "DOCUMENTO_EQUIVALENTE_POS",
    "NOTA_CREDITO",
    "NOTA_DEBITO",
]
Environment = Literal["habilitacion", "produccion"]
DocumentStatus = Literal["accepted", "rejected", "error"]
CustomerDocumentType = Literal["FINAL_CONSUMER", "NIT", "CC", "CE", "TI", "PASSPORT"]
PaymentForm = Literal["CONTADO", "CREDITO"]
PaymentMeans = Literal["CASH", "CREDIT_CARD", "DEBIT_CARD", "TRANSFER", "UNSPECIFIED"]

# Eventos RADIAN del receptor de la factura. El 034 (aceptación tácita) no se
# implementa: lo registra el emisor, no el adquiriente.
EventType = Literal["030", "031", "032", "033"]
ClaimCauseCode = Literal["01", "02", "03", "04"]
EventStatus = Literal["ACCEPTED", "REJECTED", "FAILED"]


class DocumentLine(BaseModel):
    """A single commercial line item."""

    description: str
    item_name: str | None = None
    item_code: str | None = None
    unit_code: str | None = None
    quantity: float
    unit_price: int = Field(description="COP, tax-exclusive")
    line_total: int = Field(description="COP, tax-exclusive")
    tax_type: str = Field(description="IVA_19 | IVA_5 | EXEMPT | EXCLUDED")
    tax_amount: int = Field(description="COP")


class DocumentSubmitRequest(BaseModel):
    """Flattened submission request used internally by the domain layer."""

    invoice_number: str
    document_type: DocumentType
    environment: Environment | None = None
    software_id: str | None = None
    software_pin: str | None = None
    test_set_id: str | None = None
    issuer_nit: str | None = None
    issuer_dv: str | None = None
    issuer_name: str | None = None
    issuer_additional_account_id: Literal["1", "2"] | None = None
    issuer_address: str | None = None
    issuer_city_code: str | None = None
    issuer_city_name: str | None = None
    issuer_department_code: str | None = None
    issuer_department_name: str | None = None
    issuer_country_code: str | None = None
    issuer_tax_level_code: str | None = None
    issuer_economic_activity: str | None = None
    issuer_phone: str | None = None
    issuer_email: str | None = None
    software_owner_nit: str | None = None
    technical_key: str | None = None
    customer_nit: str | None = None
    customer_document_type: CustomerDocumentType | None = None
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    customer_address: str | None = None
    customer_city_code: str | None = None
    customer_city_name: str | None = None
    customer_department_code: str | None = None
    customer_department_name: str | None = None
    customer_country_code: str | None = None
    issue_date: str = Field(description="YYYY-MM-DD")
    issue_time: str = Field(description="HH:MM:SS-05:00")
    due_date: str | None = Field(default=None, description="YYYY-MM-DD; obligatorio para CREDITO")
    subtotal: int = Field(description="COP integer")
    tax_total: int = Field(description="COP integer")
    total: int = Field(description="COP integer")
    lines: list[DocumentLine]
    payment_form: PaymentForm = "CONTADO"
    payment_means: PaymentMeans | None = None
    # Compatibilidad transitoria con integradores anteriores. El dominio sólo
    # consume payment_form/payment_means después de esta normalización.
    payment_method: str | None = Field(default=None)
    resolution_number: str
    resolution_date: str | None = None
    prefix: str
    resolution_range_from: int | None = None
    resolution_range_to: int | None = None
    resolution_valid_from: str | None = None
    resolution_valid_to: str | None = None
    number_width: int | None = None
    pos_register_plate: str | None = None
    pos_register_location: str | None = None
    cashier_name: str | None = None
    pos_register_type: str | None = None
    sale_code: str | None = None
    buyer_loyalty_points: int | None = None
    client_reference: str | None = None
    credit_note_number: str | None = None
    referenced_invoice_number: str | None = None
    referenced_invoice_cufe: str | None = None
    referenced_invoice_issue_date: str | None = None
    credit_note_reason: str | None = None
    debit_note_number: str | None = None
    debit_note_reason: str | None = None
    debit_note_response_code: str | None = None

    @model_validator(mode="after")
    def normalize_payment_terms(self) -> DocumentSubmitRequest:
        try:
            issue_date = date.fromisoformat(self.issue_date)
            due_date = date.fromisoformat(self.due_date) if self.due_date else None
        except ValueError as exc:
            raise ValueError("issue_date/due_date deben usar una fecha YYYY-MM-DD válida") from exc
        legacy_means = {
            "CASH": "CASH",
            "CARD": "CREDIT_CARD",
            "TRANSFER": "TRANSFER",
            "CHECK": "UNSPECIFIED",
            "CREDIT": "UNSPECIFIED",
        }.get(self.payment_method or "")
        if self.payment_method and legacy_means is None:
            raise ValueError("payment_method legacy no reconocido")
        if self.payment_means is None:
            if legacy_means is None:
                raise ValueError("payment_means es obligatorio")
            self.payment_means = legacy_means  # type: ignore[assignment]
        elif legacy_means is not None and self.payment_means != legacy_means:
            raise ValueError("payment_means contradice payment_method")

        if self.payment_method == "CREDIT" and self.payment_form == "CONTADO":
            self.payment_form = "CREDITO"
        if self.payment_form == "CREDITO":
            if self.document_type != "FACTURA_ELECTRONICA":
                raise ValueError("CREDITO sólo aplica a FACTURA_ELECTRONICA")
            if not self.due_date:
                raise ValueError("due_date es obligatorio para CREDITO")
            assert due_date is not None
            if due_date <= issue_date:
                raise ValueError("due_date debe ser posterior a issue_date")
            if self.customer_document_type == "FINAL_CONSUMER":
                raise ValueError("CREDITO no está permitido para consumidor final")
        elif self.due_date is not None:
            raise ValueError("due_date sólo aplica cuando payment_form es CREDITO")
        return self


class SubmissionArtifacts(BaseModel):
    """Opaque artifacts generated during a successful DIAN interaction.

    ``xml_base64``/``xml_filename`` carry the issuer-signed document XML
    (factura/NC/ND), which is what carries the CUFE.

    ``application_response_xml_base64``/``application_response_xml_filename``
    carry the Application Response signed by the DIAN (the timestamped
    acknowledgement that the document was accepted). The Colombian
    Resolución 165 requires retaining BOTH artifacts for at least five years,
    so the caller is expected to persist each one separately when present.

    For habilitación (test-set submissions), DIAN's flow is asynchronous and
    the AR usually arrives via ``get_status`` rather than on the initial
    submit response — so the AR fields may be ``None`` on a submit but
    populated on a subsequent status lookup.
    """

    xml_base64: str | None = None
    xml_filename: str | None = None
    application_response_xml_base64: str | None = None
    application_response_xml_filename: str | None = None


class DocumentSubmissionResult(BaseModel):
    """Result returned by the document submission and status services."""

    submission_id: str
    tracking_id: str
    document_key: str | None = None
    qr_url: str | None = None
    status: DocumentStatus
    messages: list[str] = Field(default_factory=list)
    dian_response: dict[str, Any] = Field(default_factory=dict)
    artifacts: SubmissionArtifacts | None = None
    client_reference: str | None = None


class AttachedDocumentBuildRequest(BaseModel):
    """Request to build a DIAN-style AttachedDocument ZIP package."""

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


class AttachedDocumentBuildResponse(BaseModel):
    """Result of building the AttachedDocument ZIP package."""

    xml_filename: str
    zip_filename: str
    content_base64: str


class CustomerLookupRequest(BaseModel):
    """Lookup request for DIAN buyer data."""

    environment: Environment | None = None
    document_type: Literal["NIT", "CC", "CE", "TI", "PASSPORT"]
    document_number: str


class CustomerLookupPayload(BaseModel):
    """Normalized buyer data returned from DIAN."""

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


class CustomerLookupResponse(BaseModel):
    """Normalized lookup response."""

    found: bool
    error_message: str | None = None
    customer: CustomerLookupPayload | None = None


class NumberingRangeLookupRequest(BaseModel):
    """Numbering range lookup request."""

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
    """Lookup response for authorized numbering ranges."""

    ranges: list[NumberingRangePayload] = Field(default_factory=list)


class DownloadByKeyResult(BaseModel):
    """Result of downloading a document XML by its CUFE/CUDE."""

    success: bool
    document_key: str
    xml_base64: str | None = None
    xml_filename: str | None = None
    status: str = ""
    error_message: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class EventReceiverPerson(BaseModel):
    """Person who took delivery of the invoice, goods or services.

    Feeds ``cac:DocumentResponse/cac:IssuerParty/cac:Person``. The Anexo
    Técnico v1.9 makes this group mandatory for the 032 event (§6.5.5.5,
    AAH11: "Debe ser obligatorio informar") and validates it on 030/033 too,
    so integrators should always send it.
    """

    document_number: str
    document_type: str = Field(default="13", description="DIAN @schemeName code")
    first_name: str
    family_name: str
    job_title: str | None = None
    organization_department: str | None = None


class EventSubmitRequest(BaseModel):
    """Flattened RADIAN event request used internally by the domain layer."""

    event_type: EventType
    environment: Environment | None = None
    software_id: str | None = None
    software_pin: str | None = None
    # Consecutivo del evento (ApplicationResponse/cbc:ID). Lo genera el
    # llamador: este servicio es stateless y no lleva secuencias.
    event_number: str | None = None
    document_cufe: str
    document_number: str
    document_issue_date: str | None = None
    document_type_code: str = "01"
    supplier_nit: str
    supplier_name: str
    supplier_dv: str | None = None
    total_amount: int | None = None
    claim_cause_code: ClaimCauseCode | None = None
    claim_description: str | None = None
    receiver_person: EventReceiverPerson | None = None
    client_reference: str | None = None


class EventArtifacts(BaseModel):
    """XML artifacts produced while registering a RADIAN event.

    ``application_response_*`` carry the event signed by us (the invoice
    receiver); ``dian_response_*`` carry the ApplicationResponse the DIAN
    signs back when it accepts or rejects the event.
    """

    application_response_xml_base64: str | None = None
    application_response_xml_filename: str | None = None
    dian_response_xml_base64: str | None = None
    dian_response_xml_filename: str | None = None


class EventSubmissionResult(BaseModel):
    """Result returned by the RADIAN event service."""

    status: EventStatus
    cude: str | None = None
    tracking_id: str | None = None
    messages: list[str] = Field(default_factory=list)
    dian_response: dict[str, Any] = Field(default_factory=dict)
    artifacts: EventArtifacts | None = None
    client_reference: str | None = None


class HealthStatus(BaseModel):
    """Health snapshot for the running service."""

    status: str = Field(description="ok | degraded | error")
    version: str
    dian_environment: str
    certificate_loaded: bool
    certificate_valid_until: str | None = None
