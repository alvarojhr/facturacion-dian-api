"""Public HTTP contracts exposed by facturacion-dian-kit."""

from __future__ import annotations

from typing import Any, Literal, cast

from facturacion_dian_kit.core.models import (
    CustomerDocumentType,
    DocumentStatus,
    DocumentType,
    Environment,
)
from facturacion_dian_kit.server.examples import (
    ATTACHED_DOCUMENT_REQUEST_EXAMPLE,
    ATTACHED_DOCUMENT_RESPONSE_EXAMPLE,
    BUYER_LOOKUP_REQUEST_EXAMPLE,
    BUYER_LOOKUP_RESPONSE_EXAMPLE,
    DOCUMENT_STATUS_RESPONSE_EXAMPLE,
    DOCUMENT_SUBMISSION_REQUEST_EXAMPLES,
    DOCUMENT_SUBMISSION_RESPONSE_EXAMPLE,
    HEALTH_RESPONSE_EXAMPLE,
    NUMBERING_RANGE_LOOKUP_REQUEST_EXAMPLE,
    NUMBERING_RANGE_LOOKUP_RESPONSE_EXAMPLE,
)
from pydantic import BaseModel, ConfigDict, Field


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
    """Opaque artifacts returned by the server when requested."""

    xml_base64: str | None = None
    xml_filename: str | None = None


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
