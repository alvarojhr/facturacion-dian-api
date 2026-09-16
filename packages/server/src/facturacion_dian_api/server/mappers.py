"""Mapping helpers between public API contracts and core models."""

from __future__ import annotations

from facturacion_dian_api.core.models import (
    AllowanceCharge,
    AttachedDocumentBuildRequest,
    CustomerLookupPayload,
    DocumentLine,
    DocumentSubmissionResult,
    DocumentSubmitRequest,
    EventReceiverPerson,
    EventSubmissionResult,
    EventSubmitRequest,
)
from facturacion_dian_api.core.models import (
    NumberingRangePayload as CoreNumberingRangePayload,
)
from facturacion_dian_api.server.contracts import (
    AttachedDocumentRequest,
    AttachedDocumentResponse,
    BuyerLookupPayload,
    BuyerLookupResponse,
    DocumentSubmissionRequest,
    DocumentSubmissionResponse,
    EmitEventRequest,
    EmitEventResponse,
    EventArtifactPayload,
    NumberingRangeLookupResponse,
    NumberingRangePayload,
    SubmissionArtifactPayload,
)


def to_core_submission_request(req: DocumentSubmissionRequest) -> DocumentSubmitRequest:
    """Adapt the public nested request to the existing core shape."""

    point_of_sale = req.document.point_of_sale
    contingency = req.document.contingency
    options = req.submission_options
    references = req.references
    buyer = req.buyer
    issuer = req.issuer
    resolution = req.resolution

    return DocumentSubmitRequest(
        invoice_number=req.document.number,
        document_type=req.document.type,
        environment=req.environment,
        software_id=options.software_id,
        software_pin=options.software_pin,
        test_set_id=options.test_set_id,
        issuer_nit=issuer.nit if issuer else None,
        issuer_dv=issuer.dv if issuer else None,
        issuer_name=issuer.name if issuer else None,
        issuer_additional_account_id=issuer.additional_account_id if issuer else None,
        issuer_address=issuer.address if issuer else None,
        issuer_city_code=issuer.city_code if issuer else None,
        issuer_city_name=issuer.city_name if issuer else None,
        issuer_department_code=issuer.department_code if issuer else None,
        issuer_department_name=issuer.department_name if issuer else None,
        issuer_country_code=issuer.country_code if issuer else None,
        issuer_tax_level_code=issuer.tax_level_code if issuer else None,
        issuer_tax_scheme_id=issuer.tax_scheme_id if issuer else None,
        issuer_tax_scheme_name=issuer.tax_scheme_name if issuer else None,
        issuer_economic_activity=issuer.economic_activity if issuer else None,
        issuer_phone=issuer.phone if issuer else None,
        issuer_email=issuer.email if issuer else None,
        software_owner_nit=issuer.software_owner_nit if issuer else None,
        technical_key=options.technical_key,
        customer_nit=buyer.document_number,
        customer_document_type=buyer.document_type,
        customer_name=buyer.name,
        customer_email=buyer.email,
        customer_phone=buyer.phone,
        customer_address=buyer.address,
        customer_city_code=buyer.city_code,
        customer_city_name=buyer.city_name,
        customer_department_code=buyer.department_code,
        customer_department_name=buyer.department_name,
        customer_country_code=buyer.country_code,
        customer_additional_account_id=buyer.additional_account_id,
        customer_tax_level_code=buyer.tax_level_code,
        customer_tax_scheme_id=buyer.tax_scheme_id,
        customer_tax_scheme_name=buyer.tax_scheme_name,
        issue_date=req.document.issue_date,
        issue_time=req.document.issue_time,
        subtotal=req.totals.subtotal,
        tax_total=req.totals.tax_total,
        withholding_total=req.totals.withholding_total,
        total=req.totals.total,
        allowance_total=req.totals.allowance_total,
        charge_total=req.totals.charge_total,
        prepaid_amount=req.totals.prepaid_amount,
        payable_rounding_amount=req.totals.payable_rounding_amount,
        allowance_charges=[
            AllowanceCharge.model_validate(entry.model_dump())
            for entry in req.totals.allowance_charges
        ],
        lines=[DocumentLine.model_validate(item.model_dump()) for item in req.line_items],
        payment_method=req.document.payment_method,
        payment_methods=req.document.payment_methods,
        payment_form=req.document.payment_form,
        payment_due_date=req.document.payment_due_date,
        resolution_number=resolution.number if resolution else "",
        resolution_date=resolution.date if resolution else None,
        prefix=resolution.prefix if resolution else "",
        resolution_range_from=resolution.range_from if resolution else None,
        resolution_range_to=resolution.range_to if resolution else None,
        resolution_valid_from=resolution.valid_from if resolution else None,
        resolution_valid_to=resolution.valid_to if resolution else None,
        number_width=resolution.number_width if resolution else None,
        pos_register_plate=point_of_sale.register_plate if point_of_sale else None,
        pos_register_location=point_of_sale.register_location if point_of_sale else None,
        cashier_name=point_of_sale.cashier_name if point_of_sale else None,
        pos_register_type=point_of_sale.register_type if point_of_sale else None,
        sale_code=point_of_sale.sale_code if point_of_sale else None,
        buyer_loyalty_points=point_of_sale.buyer_loyalty_points if point_of_sale else None,
        client_reference=req.client_reference,
        credit_note_number=(
            req.document.number
            if req.document.type in {"NOTA_CREDITO", "NOTA_AJUSTE_DEE_CREDITO"}
            else None
        ),
        referenced_invoice_number=references.referenced_document_number if references else None,
        referenced_invoice_cufe=references.referenced_document_key if references else None,
        referenced_invoice_issue_date=references.referenced_issue_date if references else None,
        credit_note_reason=(
            references.reason
            if req.document.type in {"NOTA_CREDITO", "NOTA_AJUSTE_DEE_CREDITO"} and references
            else None
        ),
        credit_note_response_code=(
            references.response_code
            if req.document.type in {"NOTA_CREDITO", "NOTA_AJUSTE_DEE_CREDITO"} and references
            else None
        ),
        debit_note_number=(
            req.document.number
            if req.document.type in {"NOTA_DEBITO", "NOTA_AJUSTE_DEE_DEBITO"}
            else None
        ),
        debit_note_reason=(
            references.reason
            if req.document.type in {"NOTA_DEBITO", "NOTA_AJUSTE_DEE_DEBITO"} and references
            else None
        ),
        debit_note_response_code=(
            references.response_code
            if req.document.type in {"NOTA_DEBITO", "NOTA_AJUSTE_DEE_DEBITO"} and references
            else None
        ),
        billing_period_start=references.billing_period_start if references else None,
        billing_period_end=references.billing_period_end if references else None,
        contingency_reference_number=references.contingency_reference_number if references else None,
        contingency_reference_date=references.contingency_reference_date if references else None,
        contingency_incident_id=contingency.incident_id if contingency else None,
        contingency_reason=contingency.reason if contingency else None,
        contingency_started_at=contingency.started_at.isoformat() if contingency else None,
        contingency_recovered_at=contingency.recovered_at.isoformat() if contingency else None,
        file_sequence=options.file_sequence,
        file_provider_code=options.file_provider_code,
        prepare_only=options.prepare_only,
        signed_xml_base64=options.signed_xml_base64,
        signed_xml_filename=options.signed_xml_filename,
    )


def to_public_submission_response(result: DocumentSubmissionResult) -> DocumentSubmissionResponse:
    """Convert a core submission result into the public response model."""

    artifacts = None
    if result.artifacts is not None:
        artifacts = SubmissionArtifactPayload.model_validate(result.artifacts.model_dump())

    return DocumentSubmissionResponse(
        submission_id=result.submission_id,
        tracking_id=result.tracking_id,
        client_reference=result.client_reference,
        document_key=result.document_key,
        qr_url=result.qr_url,
        status=result.status,
        messages=result.messages,
        dian_response=result.dian_response,
        artifacts=artifacts,
    )


def to_core_event_request(req: EmitEventRequest) -> EventSubmitRequest:
    """Adapt the public event contract to the core shape."""

    options = req.submission_options
    person = req.receiver_person

    return EventSubmitRequest(
        event_type=req.event_type,
        environment=req.environment,
        software_id=options.software_id,
        software_pin=options.software_pin,
        event_number=req.event_number,
        event_issue_date=req.event_issue_date,
        event_issue_time=req.event_issue_time,
        signed_event_xml_base64=options.signed_event_xml_base64,
        file_sequence=options.file_sequence,
        file_provider_code=options.file_provider_code,
        document_cufe=req.document_cufe,
        document_number=req.document_number,
        document_issue_date=req.document_issue_date,
        document_type_code=req.document_type_code,
        supplier_nit=req.supplier_nit,
        supplier_name=req.supplier_name,
        supplier_dv=req.supplier_dv,
        total_amount=req.total_amount,
        claim_cause_code=req.claim_cause_code,
        claim_description=req.claim_description,
        receiver_person=(
            EventReceiverPerson.model_validate(person.model_dump()) if person is not None else None
        ),
        client_reference=req.client_reference,
    )


def to_public_event_response(result: EventSubmissionResult) -> EmitEventResponse:
    """Convert a core event result into the public response model."""

    artifacts = None
    if result.artifacts is not None:
        artifacts = EventArtifactPayload.model_validate(result.artifacts.model_dump())

    return EmitEventResponse(
        status=result.status,
        cude=result.cude,
        tracking_id=result.tracking_id,
        client_reference=result.client_reference,
        messages=result.messages,
        dian_response=result.dian_response,
        artifacts=artifacts,
    )


def to_core_attached_document_request(req: AttachedDocumentRequest) -> AttachedDocumentBuildRequest:
    """Convert the public AttachedDocument contract to the core model."""

    return AttachedDocumentBuildRequest.model_validate(req.model_dump())


def to_public_attached_document_response(
    xml_filename: str,
    zip_filename: str,
    content_base64: str,
) -> AttachedDocumentResponse:
    """Build the public AttachedDocument response."""

    return AttachedDocumentResponse(
        xml_filename=xml_filename,
        zip_filename=zip_filename,
        content_base64=content_base64,
    )


def to_public_buyer_response(
    *,
    found: bool,
    error_message: str | None,
    customer: CustomerLookupPayload | None,
) -> BuyerLookupResponse:
    """Convert the normalized core payload to the public buyer response."""

    payload = None
    if customer is not None:
        payload = BuyerLookupPayload.model_validate(customer.model_dump())
    return BuyerLookupResponse(
        found=found,
        error_message=error_message,
        customer=payload,
    )


def to_public_numbering_ranges(ranges: list[CoreNumberingRangePayload]) -> NumberingRangeLookupResponse:
    """Convert normalized numbering ranges to the public response model."""

    return NumberingRangeLookupResponse(
        ranges=[NumberingRangePayload.model_validate(item.model_dump()) for item in ranges]
    )
