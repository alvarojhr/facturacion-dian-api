"""Internal models shared by the core and server packages."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DocumentType = Literal[
    "FACTURA_ELECTRONICA",
    "DOCUMENTO_EQUIVALENTE_POS",
    "NOTA_CREDITO",
    "NOTA_DEBITO",
]
Environment = Literal["habilitacion", "produccion"]
DocumentStatus = Literal["accepted", "rejected", "error"]
CustomerDocumentType = Literal["FINAL_CONSUMER", "NIT", "CC", "CE", "TI", "PASSPORT"]


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
    subtotal: int = Field(description="COP integer")
    tax_total: int = Field(description="COP integer")
    total: int = Field(description="COP integer")
    lines: list[DocumentLine]
    payment_method: str = Field(description="CASH | CARD | TRANSFER")
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


class SubmissionArtifacts(BaseModel):
    """Opaque artifacts generated during a successful DIAN interaction."""

    xml_base64: str | None = None
    xml_filename: str | None = None


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


class HealthStatus(BaseModel):
    """Health snapshot for the running service."""

    status: str = Field(description="ok | degraded | error")
    version: str
    dian_environment: str
    certificate_loaded: bool
    certificate_valid_until: str | None = None
