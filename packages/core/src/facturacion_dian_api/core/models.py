"""Internal models shared by the core and server packages."""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any, Literal, cast

from facturacion_dian_api.core.buyer import (
    resolve_buyer_identity,
    validate_buyer_family,
    validate_responsibilities,
    validate_tax_scheme,
)
from facturacion_dian_api.core.monetary import (
    IVA_TYPES,
    money,
    percentage_amount,
    validate_calculated_amount,
)
from facturacion_dian_api.core.payments import PaymentDetails
from facturacion_dian_api.core.payments import PaymentForm as PaymentForm
from facturacion_dian_api.core.payments import PaymentMethod as PaymentMethod
from facturacion_dian_api.core.xml.namespaces import TAX_TYPE_TO_DIAN
from pydantic import BaseModel, Field, field_validator, model_validator

DocumentType = Literal[
    "FACTURA_ELECTRONICA",
    "DOCUMENTO_EQUIVALENTE_POS",
    "DOCUMENTO_EQUIVALENTE_POS_CONTINGENCIA_EMISOR",
    "DOCUMENTO_EQUIVALENTE_POS_CONTINGENCIA_DIAN",
    "NOTA_CREDITO",
    "NOTA_DEBITO",
    "NOTA_AJUSTE_DEE_CREDITO",
    "NOTA_AJUSTE_DEE_DEBITO",
    "FACTURA_CONTINGENCIA_FACTURADOR",
    "FACTURA_CONTINGENCIA_DIAN",
]
Environment = Literal["habilitacion", "produccion"]
DocumentStatus = Literal[
    "prepared", "received", "pending", "accepted", "rejected", "unknown", "error"
]
CustomerDocumentType = Literal["FINAL_CONSUMER", "NIT", "CC", "CE", "TI", "PASSPORT"]
TaxType = Literal[
    "IVA_19", "IVA_5", "IVA_0", "EXEMPT", "EXCLUDED", "INC", "ICA",
    "RETEIVA", "RETEFUENTE", "RETEICA", "RETECREE", "IC_PORCENTUAL",
    "FONDO_HORTIFRUTICOLA", "TIMBRE", "INC_BOLSAS", "IMPUESTO_CARBONO",
    "INC_COMBUSTIBLES", "SOBRETASA_COMBUSTIBLES", "SORDICOM", "IC_DATOS",
    "ICL", "INPP", "IBUA", "ICUI", "AD_VALOREM", "OTHER",
]

# Eventos RADIAN del receptor de la factura. El 034 (aceptación tácita) no se
# implementa: lo registra el emisor, no el adquiriente.
EventType = Literal["030", "031", "032", "033"]
ClaimCauseCode = Literal["01", "02", "03", "04"]
EventStatus = Literal["PREPARED", "RECEIVED", "PENDING", "ACCEPTED", "REJECTED", "UNKNOWN", "ERROR"]


class AllowanceCharge(BaseModel):
    """Discount or charge that changes a line or document monetary base."""

    charge_indicator: bool
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    base_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    percentage: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=4)
    reason_code: str | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_amount(self) -> AllowanceCharge:
        if (self.base_amount is None) != (self.percentage is None):
            raise ValueError("base_amount and percentage must be provided together")
        if self.base_amount is not None and self.percentage is not None:
            expected = money(percentage_amount(self.base_amount, self.percentage))
            if self.amount != expected:
                raise ValueError(f"amount must equal base_amount * percentage ({expected})")
        return self


class LineTax(BaseModel):
    """Tax reported for a line, including percentage and per-unit taxes."""

    tax_type: TaxType
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    taxable_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    percent: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=4)
    per_unit_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    base_unit_measure: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    scheme_id: str | None = None
    scheme_name: str | None = None

    @model_validator(mode="after")
    def validate_tax_definition(self) -> LineTax:
        fixed_rates = {"IVA_19": Decimal("19"), "IVA_5": Decimal("5")}
        if self.tax_type in fixed_rates:
            expected = fixed_rates[self.tax_type]
            if self.percent is None:
                self.percent = expected
            elif self.percent != expected:
                raise ValueError(f"{self.tax_type} requires percent={expected}")
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


class DocumentLine(BaseModel):
    """A single commercial line item."""

    description: str = Field(min_length=1)
    item_name: str | None = None
    item_code: str | None = None
    unit_code: str = Field(default="94", min_length=1)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    line_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    tax_type: TaxType | None = None
    tax_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    taxes: list[LineTax] = Field(default_factory=list)
    allowance_charges: list[AllowanceCharge] = Field(default_factory=list)
    reference_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    reference_price_type_code: Literal["01", "02", "03"] | None = None

    @model_validator(mode="after")
    def normalize_and_validate(self) -> DocumentLine:
        if self.taxes and (self.tax_type is not None or self.tax_amount is not None):
            legacy_matches_normalized = (
                len(self.taxes) == 1
                and self.tax_type == self.taxes[0].tax_type
                and self.tax_amount == self.taxes[0].amount
            )
            if not legacy_matches_normalized:
                raise ValueError("Use taxes or legacy tax_type/tax_amount, not both")
        if not self.taxes:
            if self.tax_type is None or self.tax_amount is None:
                raise ValueError("Provide taxes or both tax_type and tax_amount")
            self.taxes = [LineTax(tax_type=self.tax_type, amount=self.tax_amount)]

        allowances = sum(
            (entry.amount for entry in self.allowance_charges if not entry.charge_indicator),
            Decimal("0"),
        )
        charges = sum(
            (entry.amount for entry in self.allowance_charges if entry.charge_indicator),
            Decimal("0"),
        )
        with localcontext() as ctx:
            ctx.prec = 50
            expected = self.quantity * self.unit_price - allowances + charges
        if expected < 0:
            raise ValueError("Line allowances cannot exceed quantity * unit_price + charges")
        if self.unit_price == 0 and self.line_total != 0:
            raise ValueError("Free lines require line_total=0; monetary tolerance cannot create a sale")
        validate_calculated_amount(self.line_total, expected, label="line_total")
        if self.unit_price == 0 and (
            self.reference_price is None or self.reference_price_type_code is None
        ):
            raise ValueError("Free lines require reference_price and reference_price_type_code")
        for tax in self.taxes:
            base = tax.taxable_amount if tax.taxable_amount is not None else self.line_total
            if tax.per_unit_amount is not None and tax.base_unit_measure is not None:
                expected_tax = money(tax.per_unit_amount * tax.base_unit_measure)
            elif tax.percent is not None:
                expected_tax = money(percentage_amount(base, tax.percent))
            elif tax.amount:
                raise ValueError(f"{tax.tax_type} requires percent or per-unit data")
            else:
                expected_tax = Decimal("0")
            if tax.tax_type in {"IVA_19", "IVA_5"}:
                validate_calculated_amount(tax.amount, expected_tax, label=f"{tax.tax_type} amount", iva=True)
            elif tax.amount != expected_tax:
                raise ValueError(f"{tax.tax_type} amount must equal its base/rate calculation ({expected_tax})")
        return self


class DocumentAmounts(BaseModel):
    """Exact ledger equations and validation of the emitted IVA subtotals."""

    subtotal: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    tax_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    withholding_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    allowance_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    charge_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    prepaid_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    payable_rounding_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    allowance_charges: list[AllowanceCharge] = Field(default_factory=list)

    def validate_lines(self, lines: list[DocumentLine]) -> None:
        with localcontext() as ctx:
            ctx.prec = 50
            self._validate_lines(lines)

    def _validate_lines(self, lines: list[DocumentLine]) -> None:
        withholding = {"RETEIVA", "RETEFUENTE", "RETEICA", "RETECREE"}
        taxes = [tax for line in lines for tax in line.taxes]
        sums = {
            "subtotal": sum((line.line_total for line in lines), Decimal("0")),
            "tax_total": sum((tax.amount for tax in taxes if tax.tax_type not in withholding | {"EXCLUDED"}), Decimal("0")),
            "withholding_total": sum((tax.amount for tax in taxes if tax.tax_type in withholding), Decimal("0")),
            "allowance_total": sum((entry.amount for entry in self.allowance_charges if not entry.charge_indicator), Decimal("0")),
            "charge_total": sum((entry.amount for entry in self.allowance_charges if entry.charge_indicator), Decimal("0")),
        }
        for name, expected in sums.items():
            if getattr(self, name) != expected:
                raise ValueError(f"totals.{name} must equal its detail sum ({expected})")
        expected_total = (
            self.subtotal - self.allowance_total + self.charge_total + self.tax_total
            - self.withholding_total - self.prepaid_amount + self.payable_rounding_amount
        )
        if self.total != expected_total:
            raise ValueError(f"totals.total must equal the payable calculation ({expected_total})")

        # Compare every tax/rate group's supplied sum with its unrounded
        # calculation. Individual allowances must not multiply header tolerance.
        groups: dict[tuple[str, Decimal | None, Decimal | None, str | None], tuple[Decimal, Decimal]] = {}
        labels: dict[tuple[str, Decimal | None, Decimal | None, str | None], str] = {}
        for line in lines:
            for tax in line.taxes:
                if tax.tax_type == "EXCLUDED":
                    continue
                base = tax.taxable_amount if tax.taxable_amount is not None else line.line_total
                kind: str = "IVA" if tax.tax_type in IVA_TYPES else tax.tax_type
                code = tax.scheme_id if tax.tax_type == "OTHER" else str(cast(dict[str, object], TAX_TYPE_TO_DIAN[tax.tax_type])["code"])
                assert code is not None
                key = (code, tax.percent, tax.per_unit_amount, line.unit_code if tax.per_unit_amount is not None else None)
                labels.setdefault(key, kind)
                amount, expected = groups.get(key, (Decimal("0"), Decimal("0")))
                if tax.per_unit_amount is not None and tax.base_unit_measure is not None:
                    calculated = tax.per_unit_amount * tax.base_unit_measure
                else:
                    calculated = percentage_amount(base, tax.percent or Decimal("0"))
                groups[key] = (
                    amount + tax.amount, expected + calculated,
                )
        for key, (actual, expected) in groups.items():
            code, rate, _, _unit = key
            validate_calculated_amount(actual, expected, label=f"{labels[key]} aggregate rate {rate}", iva=code == "01")


class DocumentSubmitRequest(PaymentDetails, DocumentAmounts):
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
    issuer_tax_scheme_id: str | None = None
    issuer_tax_scheme_name: str | None = None
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
    customer_additional_account_id: Literal["1", "2"] | None = None
    customer_tax_level_code: str | None = None
    customer_tax_scheme_id: str | None = None
    customer_tax_scheme_name: str | None = None
    issue_date: str = Field(description="YYYY-MM-DD")
    issue_time: str = Field(description="HH:MM:SS-05:00")
    lines: list[DocumentLine] = Field(min_length=1)
    resolution_number: str = ""
    resolution_date: str | None = None
    prefix: str = ""
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
    credit_note_response_code: str | None = None
    debit_note_number: str | None = None
    debit_note_reason: str | None = None
    debit_note_response_code: str | None = None
    billing_period_start: str | None = None
    billing_period_end: str | None = None
    contingency_reference_number: str | None = None
    contingency_reference_date: str | None = None
    contingency_incident_id: str | None = None
    contingency_reason: str | None = None
    contingency_started_at: str | None = None
    contingency_recovered_at: str | None = None
    file_sequence: int | None = Field(default=None, ge=1, le=0xFFFFFFFF)
    file_provider_code: str = Field(default="000", pattern=r"^\d{3}$")
    prepare_only: bool = False
    signed_xml_base64: str | None = None
    signed_xml_filename: str | None = None

    @field_validator("customer_tax_level_code")
    @classmethod
    def validate_customer_responsibilities(cls, value: str | None) -> str | None:
        return validate_responsibilities(value)

    @model_validator(mode="after")
    def validate_customer(self) -> DocumentSubmitRequest:
        document_type, _ = resolve_buyer_identity(
            self.customer_document_type, self.customer_nit,
            self.customer_name, self.customer_additional_account_id,
        )
        validate_tax_scheme(self.customer_tax_scheme_id, self.customer_tax_scheme_name)
        if not self.signed_xml_base64:
            validate_buyer_family(self.document_type, document_type, self.customer_tax_level_code)
        return self

    @model_validator(mode="after")
    def validate_amounts_and_payments(self) -> DocumentSubmitRequest:
        self.validate_payment_context(self.issue_date, self.document_type)
        self.validate_lines(self.lines)
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
    tracking_id: str | None = None
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
    issuer_dv: str
    issuer_name: str
    issuer_tax_level_code: str
    receiver_name: str
    receiver_nit: str
    receiver_dv: str | None = None
    receiver_document_type: str
    receiver_tax_level_code: str | None = Field(
        default=None,
        description="Optional assertion against the signed source. AE28 requires a known source value.",
    )
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
    file_sequence: int | None = Field(default=None, ge=1, le=0xFFFFFFFF)
    file_provider_code: str = Field(default="000", pattern=r"^\d{3}$")

    @field_validator("receiver_tax_level_code")
    @classmethod
    def validate_receiver_responsibilities(cls, value: str | None) -> str | None:
        return validate_responsibilities(value)


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


class EventIssuer(BaseModel):
    """Complete sender identity used by the event builder, owned by the caller."""

    nit: str = Field(pattern=r"^\d{1,15}$")
    dv: str = Field(pattern=r"^\d$")
    name: str = Field(min_length=1)
    additional_account_id: Literal["1", "2"]


class EventSubmitRequest(BaseModel):
    """Flattened RADIAN event request used internally by the domain layer."""

    event_type: EventType
    issuer: EventIssuer | None = None
    prepare_only: bool = False
    reconcile_only: bool = False
    signed_event_xml_filename: str | None = None
    environment: Environment | None = None
    software_id: str | None = None
    software_pin: str | None = None
    # Consecutivo del evento (ApplicationResponse/cbc:ID). Lo genera el
    # llamador: este servicio es stateless y no lleva secuencias.
    event_number: str | None = None
    event_issue_date: str | None = None
    event_issue_time: str | None = None
    signed_event_xml_base64: str | None = None
    file_sequence: int | None = Field(default=None, ge=1, le=0xFFFFFFFF)
    file_provider_code: str = Field(default="000", pattern=r"^\d{3}$")
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
    certificate_days_remaining: int | None = None
    certificate_expiring_soon: bool = False
