"""Mapping helpers between public API contracts and core models."""

from __future__ import annotations

from facturacion_dian_kit.core.models import (
    AttachedDocumentBuildRequest,
    CustomerLookupPayload,
    DocumentLine,
    DocumentSubmissionResult,
    DocumentSubmitRequest,
)
from facturacion_dian_kit.core.models import (
    NumberingRangePayload as CoreNumberingRangePayload,
)
from facturacion_dian_kit.server.contracts import (
    AttachedDocumentRequest,
    AttachedDocumentResponse,
    BuyerLookupPayload,
    BuyerLookupResponse,
    DocumentSubmissionRequest,
    DocumentSubmissionResponse,
    NumberingRangeLookupResponse,
    NumberingRangePayload,
    SubmissionArtifactPayload,
)


def to_core_submission_request(req: DocumentSubmissionRequest) -> DocumentSubmitRequest:
    """Adapt the public nested request to the existing core shape."""

    point_of_sale = req.document.point_of_sale
    options = req.submission_options
    references = req.references
    buyer = req.buyer
    issuer = req.issuer

    return DocumentSubmitRequest(
        invoice_number=req.document.number,
        document_type=req.document.type,
        environment=req.environment,
        software_id=options.software_id if options else None,
        software_pin=options.software_pin if options else None,
        test_set_id=options.test_set_id if options else None,
        issuer_nit=issuer.nit if issuer else None,
        issuer_dv=issuer.dv if issuer else None,
        software_owner_nit=issuer.software_owner_nit if issuer else None,
        technical_key=options.technical_key if options else None,
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
        issue_date=req.document.issue_date,
        issue_time=req.document.issue_time,
        subtotal=req.totals.subtotal,
        tax_total=req.totals.tax_total,
        total=req.totals.total,
        lines=[DocumentLine.model_validate(item.model_dump()) for item in req.line_items],
        payment_method=req.document.payment_method,
        resolution_number=req.resolution.number,
        resolution_date=req.resolution.date,
        prefix=req.resolution.prefix,
        resolution_range_from=req.resolution.range_from,
        resolution_range_to=req.resolution.range_to,
        resolution_valid_from=req.resolution.valid_from,
        resolution_valid_to=req.resolution.valid_to,
        number_width=req.resolution.number_width,
        pos_register_plate=point_of_sale.register_plate if point_of_sale else None,
        pos_register_location=point_of_sale.register_location if point_of_sale else None,
        cashier_name=point_of_sale.cashier_name if point_of_sale else None,
        pos_register_type=point_of_sale.register_type if point_of_sale else None,
        sale_code=point_of_sale.sale_code if point_of_sale else None,
        buyer_loyalty_points=point_of_sale.buyer_loyalty_points if point_of_sale else None,
        client_reference=req.client_reference,
        credit_note_number=req.document.number if req.document.type == "NOTA_CREDITO" else None,
        referenced_invoice_number=references.referenced_document_number if references else None,
        referenced_invoice_cufe=references.referenced_document_key if references else None,
        referenced_invoice_issue_date=references.referenced_issue_date if references else None,
        credit_note_reason=references.reason if req.document.type == "NOTA_CREDITO" and references else None,
        debit_note_number=req.document.number if req.document.type == "NOTA_DEBITO" else None,
        debit_note_reason=references.reason if req.document.type == "NOTA_DEBITO" and references else None,
        debit_note_response_code=(
            references.response_code if req.document.type == "NOTA_DEBITO" and references else None
        ),
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
