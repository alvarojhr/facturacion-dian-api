"""Public HTTP contracts exposed by facturacion-dian-kit."""

from __future__ import annotations

from typing import Any, Literal

from facturacion_dian_kit.core.models import (
    CustomerDocumentType,
    DocumentStatus,
    DocumentType,
    Environment,
)
from pydantic import BaseModel, Field


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
    """Optional issuer-specific runtime overrides."""

    nit: str | None = None
    dv: str | None = None
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
    """Opaque artifacts returned by the server when requested."""

    xml_base64: str | None = None
    xml_filename: str | None = None


class DocumentSubmissionResponse(BaseModel):
    """Public response contract for document submission and status lookups."""

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

    xml_filename: str
    zip_filename: str
    content_base64: str


class BuyerLookupRequest(BaseModel):
    """Public buyer lookup request."""

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

    found: bool
    error_message: str | None = None
    customer: BuyerLookupPayload | None = None


class NumberingRangeLookupRequest(BaseModel):
    """Request to look up DIAN numbering ranges."""

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

    ranges: list[NumberingRangePayload] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health probe response."""

    status: str
    version: str
    dian_environment: str
    certificate_loaded: bool
    certificate_valid_until: str | None = None
