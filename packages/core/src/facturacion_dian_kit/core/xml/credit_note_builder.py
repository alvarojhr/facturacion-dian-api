"""UBL 2.1 CreditNote XML builder for DIAN."""

from __future__ import annotations

import calendar
from datetime import date

from facturacion_dian_kit.core.cufe.calculator import calculate_software_security_code
from facturacion_dian_kit.core.models import DocumentSubmitRequest
from facturacion_dian_kit.core.runtime_config import (
    resolved_software_id,
    resolved_software_pin,
    resolved_tipo_ambiente,
)
from facturacion_dian_kit.core.xml.common import (
    _sub,
    build_customer_party,
    build_invoice_control,
    build_invoice_line,
    build_legal_monetary_total,
    build_payment_means,
    build_supplier_party,
    build_tax_totals,
    build_ubl_extensions,
    resolve_invoice_control,
)
from facturacion_dian_kit.core.xml.namespaces import (
    CREDIT_NOTE_TYPE,
    CURRENCY_COP,
    CUSTOMIZATION_CREDIT_NOTE,
    CUSTOMIZATION_CREDIT_NOTE_NO_ASOCIADA,
    NS_CREDIT_NOTE,
    NSMAP_CREDIT_NOTE,
    cac,
    cbc,
)
from lxml import etree

CREDIT_NOTE_PROFILE_ID = "DIAN 2.1: Nota CrÃ©dito de Factura ElectrÃ³nica de Venta"


def build_credit_note_xml(
    req: DocumentSubmitRequest,
    cude: str,
    qr_code: str | None = None,
) -> etree._Element:
    """Build a complete UBL 2.1 CreditNote XML for DIAN."""
    credit_note_number = req.credit_note_number or req.invoice_number
    referenced_issue_date = req.referenced_invoice_issue_date or req.issue_date

    root = etree.Element(f"{{{NS_CREDIT_NOTE}}}CreditNote", nsmap=NSMAP_CREDIT_NOTE)

    software_security_code = calculate_software_security_code(
        resolved_software_id(req),
        resolved_software_pin(req),
        credit_note_number,
    )

    invoice_control = build_ubl_extensions(
        root,
        req,
        software_security_code,
        qr_code,
    )
    range_from, range_to, valid_from, valid_to = resolve_invoice_control(req)
    build_invoice_control(
        invoice_control,
        req.resolution_number,
        req.prefix,
        range_from,
        range_to,
        valid_from,
        valid_to,
    )

    has_reference = bool(req.referenced_invoice_number)
    customization_id = CUSTOMIZATION_CREDIT_NOTE if has_reference else CUSTOMIZATION_CREDIT_NOTE_NO_ASOCIADA

    _sub(root, cbc("UBLVersionID"), "UBL 2.1")
    _sub(root, cbc("CustomizationID"), customization_id)
    _sub(root, cbc("ProfileID"), CREDIT_NOTE_PROFILE_ID)
    _sub(root, cbc("ProfileExecutionID"), resolved_tipo_ambiente(req))
    _sub(root, cbc("ID"), credit_note_number)
    _sub(
        root,
        cbc("UUID"),
        cude,
        schemeID=resolved_tipo_ambiente(req),
        schemeName="CUDE-SHA384",
    )
    _sub(root, cbc("IssueDate"), req.issue_date)
    _sub(root, cbc("IssueTime"), req.issue_time)
    _sub(root, cbc("CreditNoteTypeCode"), CREDIT_NOTE_TYPE)
    _sub(root, cbc("Note"), req.credit_note_reason or "Nota CrÃ©dito")
    _sub(
        root,
        cbc("DocumentCurrencyCode"),
        CURRENCY_COP,
        listAgencyID="6",
        listAgencyName="United Nations Economic Commission for Europe",
        listID="ISO 4217 Alpha",
    )
    _sub(root, cbc("LineCountNumeric"), str(len(req.lines)))

    # Tipo 22 (no reference): ResponseCode "1" (devoluciÃ³n parcial) â€” annulment forbidden
    # Tipo 1 (with reference): ResponseCode "1" as well â€” safer and accurate for POS returns
    response_code = "1"

    if not has_reference:
        # CAE02/CAE04: Tipo 22 requires InvoicePeriod covering the billing month
        year, month, _ = (int(p) for p in req.issue_date.split("-"))
        period_start = date(year, month, 1).isoformat()
        period_end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        invoice_period = _sub(root, cac("InvoicePeriod"))
        _sub(invoice_period, cbc("StartDate"), period_start)
        _sub(invoice_period, cbc("EndDate"), period_end)

    discrepancy = _sub(root, cac("DiscrepancyResponse"))
    if has_reference:
        _sub(discrepancy, cbc("ReferenceID"), req.referenced_invoice_number)
    _sub(discrepancy, cbc("ResponseCode"), response_code)
    _sub(discrepancy, cbc("Description"), req.credit_note_reason or "DevoluciÃ³n parcial")

    if has_reference:
        billing_ref = _sub(root, cac("BillingReference"))
        invoice_ref = _sub(billing_ref, cac("InvoiceDocumentReference"))
        _sub(invoice_ref, cbc("ID"), req.referenced_invoice_number)
        _sub(invoice_ref, cbc("UUID"), req.referenced_invoice_cufe or "", schemeName="CUFE-SHA384")
        _sub(invoice_ref, cbc("IssueDate"), referenced_issue_date)

    build_supplier_party(root, req.prefix, req)
    build_customer_party(root, req)
    build_payment_means(root, req.payment_method, req.issue_date)
    build_tax_totals(root, req.lines)
    build_legal_monetary_total(root, req.lines, req.total)

    for index, line in enumerate(req.lines, start=1):
        build_invoice_line(root, index, line, tag_name="CreditNoteLine")

    return root


def credit_note_to_xml_string(root: etree._Element) -> bytes:
    """Serialize the CreditNote XML tree to UTF-8 bytes."""
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )

