"""Public HTTP contracts exposed by facturacion-dian-api."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal, cast

from facturacion_dian_api.core.models import (
    ClaimCauseCode,
    CustomerDocumentType,
    DocumentAmounts,
    DocumentLine,
    DocumentStatus,
    DocumentType,
    Environment,
    EventStatus,
    EventType,
    TaxType,
)
from facturacion_dian_api.core.monetary import money, percentage_amount
from facturacion_dian_api.core.payments import PaymentDetails
from facturacion_dian_api.core.runtime_config import compute_nit_dv
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
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ISSUE_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d:[0-5]\d-05:00$")


def _validate_iso_date(value: str, field_name: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD") from exc
    return value


class AllowanceChargeInput(BaseModel):
    """Discount or charge applied to a line or document."""

    charge_indicator: bool
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    base_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    percentage: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=4)
    reason_code: str | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_amount(self) -> AllowanceChargeInput:
        if (self.base_amount is None) != (self.percentage is None):
            raise ValueError("base_amount and percentage must be provided together")
        if self.base_amount is not None and self.percentage is not None:
            expected = money(percentage_amount(self.base_amount, self.percentage))
            if self.amount != expected:
                raise ValueError(f"amount must equal base_amount * percentage ({expected})")
        return self


class LineTaxInput(BaseModel):
    """One DIAN tax for a line."""

    tax_type: TaxType
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    taxable_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    percent: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=4)
    per_unit_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    base_unit_measure: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    scheme_id: str | None = None
    scheme_name: str | None = None

    @model_validator(mode="after")
    def validate_tax(self) -> LineTaxInput:
        fixed = {"IVA_19": Decimal("19"), "IVA_5": Decimal("5")}
        if self.tax_type in fixed:
            if self.percent is None:
                self.percent = fixed[self.tax_type]
            elif self.percent != fixed[self.tax_type]:
                raise ValueError(f"{self.tax_type} has a fixed rate of {fixed[self.tax_type]}")
        if self.tax_type in {"IVA_0", "EXEMPT", "EXCLUDED"}:
            if self.amount != 0:
                raise ValueError(f"{self.tax_type} requires amount=0")
            self.percent = Decimal("0")
        if self.tax_type == "IBUA" and (
            self.per_unit_amount is None or self.base_unit_measure is None
        ):
            raise ValueError("IBUA requires per_unit_amount and base_unit_measure")
        if self.tax_type == "OTHER" and (not self.scheme_id or not self.scheme_name):
            raise ValueError("OTHER requires scheme_id and scheme_name")
        return self


class LineItemInput(BaseModel):
    """Public line item shape for document submissions."""

    description: str
    item_name: str | None = None
    item_code: str = Field(min_length=1)
    unit_code: str = Field(default="94", min_length=1)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    line_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    tax_type: TaxType | None = None
    tax_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    taxes: list[LineTaxInput] = Field(default_factory=list)
    allowance_charges: list[AllowanceChargeInput] = Field(default_factory=list)
    reference_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    reference_price_type_code: Literal["01", "02", "03"] | None = None

    @model_validator(mode="after")
    def validate_line(self) -> LineItemInput:
        if self.taxes and (self.tax_type is not None or self.tax_amount is not None):
            raise ValueError("Use taxes or legacy tax_type/tax_amount, not both")
        if not self.taxes and (self.tax_type is None or self.tax_amount is None):
            raise ValueError("Provide taxes or both tax_type and tax_amount")
        DocumentLine.model_validate(self.model_dump())
        return self


class PointOfSaleInput(BaseModel):
    """Optional point-of-sale metadata for POS-equivalent documents."""

    register_plate: str | None = None
    register_location: str | None = None
    cashier_name: str | None = None
    register_type: str | None = None
    sale_code: str | None = None
    buyer_loyalty_points: int | None = None


class ContingencyInput(BaseModel):
    """Incident lifecycle that authorizes a later contingency transmission."""

    incident_id: str = Field(min_length=1)
    mode: Literal["EMISOR", "DIAN"]
    reason: str = Field(min_length=1)
    started_at: datetime
    recovered_at: datetime

    @model_validator(mode="after")
    def validate_lifecycle(self) -> ContingencyInput:
        if self.recovered_at < self.started_at:
            raise ValueError("recovered_at cannot precede started_at")
        return self


class DocumentInput(PaymentDetails):
    """Document-level metadata."""

    number: str
    type: DocumentType
    issue_date: str = Field(description="YYYY-MM-DD")
    issue_time: str = Field(description="HH:MM:SS-05:00")
    point_of_sale: PointOfSaleInput | None = None
    contingency: ContingencyInput | None = None

    @field_validator("issue_date")
    @classmethod
    def validate_issue_date(cls, value: str) -> str:
        return _validate_iso_date(value, "issue_date")

    @field_validator("issue_time")
    @classmethod
    def validate_issue_time(cls, value: str) -> str:
        if not ISSUE_TIME_PATTERN.fullmatch(value):
            raise ValueError("issue_time must use HH:MM:SS-05:00")
        return value

    @model_validator(mode="after")
    def validate_payment(self) -> DocumentInput:
        self.validate_payment_context(self.issue_date, self.type)
        is_contingency = "CONTINGENCIA" in self.type
        if is_contingency and self.contingency is None:
            raise ValueError("Contingency document types require document.contingency")
        if not is_contingency and self.contingency is not None:
            raise ValueError("document.contingency only applies to contingency document types")
        if self.contingency:
            expected_mode = "DIAN" if self.type.endswith("_DIAN") else "EMISOR"
            if self.contingency.mode != expected_mode:
                raise ValueError(f"contingency.mode must be {expected_mode} for {self.type}")
            if self.contingency.mode == "EMISOR":
                deadline = self.contingency.recovered_at + timedelta(hours=48)
                if datetime.now(deadline.tzinfo) > deadline:
                    raise ValueError("The 48-hour post-recovery contingency transmission window expired")
        return self


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
    tax_scheme_id: str | None = None
    tax_scheme_name: str | None = None
    economic_activity: str | None = None
    phone: str | None = None
    email: str | None = None
    software_owner_nit: str | None = None

    @field_validator("tax_level_code")
    @classmethod
    def validate_responsibilities(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {"O-13", "O-15", "O-23", "O-47", "R-99-PN"}
        values = [part.strip().upper() for part in value.split(";")]
        invalid = [part for part in values if part not in allowed]
        if invalid:
            raise ValueError("Unknown DIAN fiscal responsibility: " + ", ".join(invalid))
        return ";".join(values)

    @model_validator(mode="after")
    def validate_nit_dv(self) -> IssuerInput:
        if self.nit and self.dv and self.dv != compute_nit_dv(self.nit):
            raise ValueError("issuer.dv does not match issuer.nit")
        return self


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
    additional_account_id: Literal["1", "2"] | None = None
    tax_level_code: str | None = None
    tax_scheme_id: str | None = None
    tax_scheme_name: str | None = None

    @field_validator("tax_level_code")
    @classmethod
    def validate_responsibilities(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {"O-13", "O-15", "O-23", "O-47", "R-99-PN"}
        values = [part.strip().upper() for part in value.split(";")]
        invalid = [part for part in values if part not in allowed]
        if invalid:
            raise ValueError("Unknown DIAN fiscal responsibility: " + ", ".join(invalid))
        return ";".join(values)

    @model_validator(mode="after")
    def validate_fiscal_identity(self) -> BuyerInput:
        final_consumer = self.document_type == "FINAL_CONSUMER" or not self.document_number
        if not final_consumer:
            required = {
                "document_type": self.document_type,
                "additional_account_id": self.additional_account_id,
                "tax_level_code": self.tax_level_code,
                "tax_scheme_id": self.tax_scheme_id,
                "tax_scheme_name": self.tax_scheme_name,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError("Identified buyer fiscal identity is incomplete: " + ", ".join(missing))
        return self


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

    @model_validator(mode="after")
    def validate_resolution(self) -> ResolutionInput:
        for field_name in ("date", "valid_from", "valid_to"):
            value = getattr(self, field_name)
            if value is not None:
                _validate_iso_date(value, f"resolution.{field_name}")
        if (self.range_from is None) != (self.range_to is None):
            raise ValueError("resolution.range_from and range_to must be provided together")
        if self.range_from is not None and self.range_to is not None:
            if self.range_from <= 0 or self.range_from > self.range_to:
                raise ValueError("resolution range is invalid")
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("resolution validity period is invalid")
        return self


class TotalsInput(DocumentAmounts):
    """Monetary totals reported to DIAN; exact equations shared with the core."""


class ReferenceInput(BaseModel):
    """Reference metadata used by note documents."""

    referenced_document_number: str | None = None
    referenced_document_key: str | None = None
    referenced_issue_date: str | None = None
    reason: str | None = None
    response_code: str | None = None
    billing_period_start: str | None = None
    billing_period_end: str | None = None
    contingency_reference_number: str | None = None
    contingency_reference_date: str | None = None


class SubmissionOptionsInput(BaseModel):
    """Runtime-only options that should not be persisted as business data."""

    software_id: str | None = None
    software_pin: str | None = None
    test_set_id: str | None = None
    technical_key: str | None = None
    return_xml_artifact: Literal[True] = True
    file_sequence: int = Field(ge=1, le=0xFFFFFFFF)
    file_provider_code: str = Field(default="000", pattern=r"^\d{3}$")
    prepare_only: bool = False
    signed_xml_base64: str | None = Field(
        default=None,
        description="Exact signed XML returned by a prior prepare_only call",
    )
    signed_xml_filename: str | None = None

    @model_validator(mode="after")
    def validate_two_phase_options(self) -> SubmissionOptionsInput:
        if (self.signed_xml_base64 is None) != (self.signed_xml_filename is None):
            raise ValueError("signed_xml_base64 and signed_xml_filename must be provided together")
        if self.prepare_only and self.signed_xml_base64:
            raise ValueError("prepare_only cannot receive an already signed XML")
        return self


class DocumentSubmissionRequest(BaseModel):
    """Public request contract for document submission."""

    model_config = ConfigDict(
        json_schema_extra=cast(dict[str, Any], {"examples": DOCUMENT_SUBMISSION_REQUEST_EXAMPLES})
    )

    document: DocumentInput
    issuer: IssuerInput | None = None
    buyer: BuyerInput
    resolution: ResolutionInput | None = None
    totals: TotalsInput
    line_items: list[LineItemInput] = Field(min_length=1)
    references: ReferenceInput | None = None
    environment: Environment | None = None
    submission_options: SubmissionOptionsInput
    client_reference: str | None = None

    @model_validator(mode="after")
    def validate_fiscal_consistency(self) -> DocumentSubmissionRequest:
        if self.document.payment_form == "CREDITO" and self.buyer.document_type == "FINAL_CONSUMER":
            raise ValueError("CREDITO no está permitido para consumidor final")
        note_types = {
            "NOTA_CREDITO",
            "NOTA_DEBITO",
            "NOTA_AJUSTE_DEE_CREDITO",
            "NOTA_AJUSTE_DEE_DEBITO",
        }
        today = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
        if self.document.issue_date > today:
            raise ValueError("document.issue_date cannot be in the future")
        options = self.submission_options
        is_reusing_signed_xml = bool(options.signed_xml_base64)
        if (
            self.document.issue_date != today
            and "CONTINGENCIA" not in self.document.type
            and not is_reusing_signed_xml
        ):
            raise ValueError(
                "A newly signed document must use today's Colombia issue_date; "
                "retries must provide the persisted signed XML"
            )
        if self.resolution is None:
            if self.document.type not in note_types:
                raise ValueError("resolution is required for invoices and equivalent documents")
        else:
            if self.document.type not in note_types:
                required_resolution = {
                    "date": self.resolution.date,
                    "range_from": self.resolution.range_from,
                    "range_to": self.resolution.range_to,
                    "valid_from": self.resolution.valid_from,
                    "valid_to": self.resolution.valid_to,
                }
                missing = [
                    name for name, value in required_resolution.items() if value is None
                ]
                if missing:
                    raise ValueError(
                        "Authorized resolution is incomplete: " + ", ".join(missing)
                    )
            if not self.document.number.startswith(self.resolution.prefix):
                raise ValueError("document.number must start with resolution.prefix")
            suffix = self.document.number[len(self.resolution.prefix) :]
            if not suffix.isdigit():
                raise ValueError("document.number must end in a numeric consecutive")
            consecutive = int(suffix)
            if (
                self.resolution.number_width is not None
                and len(suffix) != self.resolution.number_width
            ):
                raise ValueError(
                    "document.number numeric part does not match resolution.number_width"
                )
            if self.resolution.range_from is not None and not (
                self.resolution.range_from <= consecutive <= (self.resolution.range_to or 0)
            ):
                raise ValueError("document.number is outside the authorized resolution range")
            if self.resolution.valid_from and self.document.issue_date < self.resolution.valid_from:
                raise ValueError("document.issue_date is before resolution.valid_from")
            if self.resolution.valid_to and self.document.issue_date > self.resolution.valid_to:
                raise ValueError("document.issue_date is after resolution.valid_to")
            if self.resolution.date and self.document.issue_date < self.resolution.date:
                raise ValueError("document.issue_date is before the resolution date")

        self.totals.validate_lines([DocumentLine.model_validate(line.model_dump()) for line in self.line_items])

        if self.issuer is not None:
            required = {
                "nit": self.issuer.nit,
                "dv": self.issuer.dv,
                "additional_account_id": self.issuer.additional_account_id,
                "address": self.issuer.address,
                "city_code": self.issuer.city_code,
                "city_name": self.issuer.city_name,
                "department_code": self.issuer.department_code,
                "department_name": self.issuer.department_name,
                "country_code": self.issuer.country_code,
                "tax_level_code": self.issuer.tax_level_code,
                "tax_scheme_id": self.issuer.tax_scheme_id,
                "tax_scheme_name": self.issuer.tax_scheme_name,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError("Body-owned issuer is incomplete: " + ", ".join(missing))

        refs = self.references
        if refs:
            for field_name in (
                "referenced_issue_date",
                "billing_period_start",
                "billing_period_end",
                "contingency_reference_date",
            ):
                value = getattr(refs, field_name)
                if value is not None:
                    _validate_iso_date(value, f"references.{field_name}")
            if refs.referenced_issue_date and refs.referenced_issue_date > self.document.issue_date:
                raise ValueError("referenced document date cannot be after note issue date")
            if refs.billing_period_start and refs.billing_period_end:
                if refs.billing_period_start > refs.billing_period_end:
                    raise ValueError("billing period is invalid")
        if self.document.type in note_types:
            if refs is None or not refs.reason or not refs.response_code:
                raise ValueError("Notes require references.reason and references.response_code")
            reference_values = (
                refs.referenced_document_number,
                refs.referenced_document_key,
                refs.referenced_issue_date,
            )
            if any(reference_values) and not all(reference_values):
                raise ValueError(
                    "A referenced note requires document number, key and issue date"
                )
            period_values = (refs.billing_period_start, refs.billing_period_end)
            if any(period_values) and not all(period_values):
                raise ValueError("A note billing period requires start and end dates")
            associated = all(reference_values)
            period = all(period_values)
            if not associated and not period:
                raise ValueError("Notes require a referenced document or a billing period")
            if self.document.type.startswith("NOTA_AJUSTE_DEE") and not associated:
                raise ValueError("DEE adjustment notes require a complete referenced document")
        if "CONTINGENCIA" in self.document.type:
            if refs is None or not refs.contingency_reference_number or not refs.contingency_reference_date:
                raise ValueError("Contingency documents require contingency reference number and date")
            assert self.document.contingency is not None
            reference_date = date.fromisoformat(refs.contingency_reference_date)
            incident = self.document.contingency
            if not incident.started_at.date() <= reference_date <= incident.recovered_at.date():
                raise ValueError("contingency reference date must fall within the incident")
            if date.fromisoformat(self.document.issue_date) < incident.recovered_at.date():
                raise ValueError("contingency transcription cannot precede recovery")
        return self


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
    tracking_id: str | None = None
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
    issuer_dv: str
    issuer_name: str
    issuer_tax_level_code: str
    receiver_name: str
    receiver_nit: str
    receiver_dv: str | None = None
    receiver_document_type: str
    receiver_tax_level_code: str
    receiver_email: str | None = None
    reply_to_email: str
    company_name: str | None = None
    business_line: str | None = None
    invoice_xml_base64: str
    invoice_xml_filename: str
    application_response_xml_base64: str
    application_response_xml_filename: str
    issue_date: str
    issue_time: str
    cufe: str
    file_sequence: int = Field(ge=1, le=0xFFFFFFFF)
    file_provider_code: str = Field(default="000", pattern=r"^\d{3}$")

    @model_validator(mode="after")
    def validate_attached_metadata(self) -> AttachedDocumentRequest:
        _validate_iso_date(self.issue_date, "issue_date")
        if not ISSUE_TIME_PATTERN.fullmatch(self.issue_time):
            raise ValueError("issue_time must use HH:MM:SS-05:00")
        if self.issuer_dv != compute_nit_dv(self.issuer_nit):
            raise ValueError("issuer_dv does not match issuer_nit")
        if self.receiver_document_type == "31":
            if self.receiver_dv is None:
                raise ValueError("receiver_dv is required for a NIT receiver")
            if self.receiver_dv != compute_nit_dv(self.receiver_nit):
                raise ValueError("receiver_dv does not match receiver_nit")
        return self


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
    signed_event_xml_base64: str | None = Field(
        default=None,
        description="Exact signed event XML returned by a prior uncertain attempt",
    )
    file_sequence: int = Field(ge=1, le=0xFFFFFFFF)
    file_provider_code: str = Field(default="000", pattern=r"^\d{3}$")


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
            "Si se omite se deriva del CUFE referenciado."
        ),
    )
    event_issue_date: str | None = Field(default=None, description="YYYY-MM-DD; persist for retry")
    event_issue_time: str | None = Field(default=None, description="HH:MM:SS-05:00; persist for retry")
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
    submission_options: EventOptionsInput
    client_reference: str | None = None

    @model_validator(mode="after")
    def _require_claim_fields(self) -> EmitEventRequest:
        if self.event_type == "031" and not self.claim_cause_code:
            raise ValueError("El evento 031 (reclamo) requiere claim_cause_code (01-04)")
        if self.event_type != "031" and self.claim_cause_code:
            raise ValueError("claim_cause_code solo aplica al evento 031 (reclamo)")
        if self.event_type == "032" and self.receiver_person is None:
            raise ValueError("El evento 032 requiere receiver_person")
        if (self.event_issue_date is None) != (self.event_issue_time is None):
            raise ValueError("event_issue_date and event_issue_time must be provided together")
        if self.event_issue_date is not None:
            _validate_iso_date(self.event_issue_date, "event_issue_date")
        if self.event_issue_time is not None and not ISSUE_TIME_PATTERN.fullmatch(self.event_issue_time):
            raise ValueError("event_issue_time must use HH:MM:SS-05:00")
        if self.event_issue_date is not None and not self.submission_options.signed_event_xml_base64:
            raise ValueError(
                "event_issue_date and event_issue_time are only permitted for a signed event retry"
            )
        if (
            self.submission_options.signed_event_xml_base64
            and self.event_issue_date is None
        ):
            raise ValueError(
                "A signed event retry requires its original event_issue_date and event_issue_time"
            )
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

    A transport failure surfaces as 502/504. A functional rejection from DIAN
    is ``200`` with ``status="REJECTED"``; a technical DIAN response without a
    fiscal verdict is ``ERROR``.
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
    certificate_days_remaining: int | None = None
    certificate_expiring_soon: bool = False
