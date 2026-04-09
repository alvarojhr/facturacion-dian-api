"""UBL 2.1 DebitNote XML builder for DIAN."""

from __future__ import annotations

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
    build_payment_means,
    build_requested_monetary_total,
    build_supplier_party,
    build_tax_totals,
    build_ubl_extensions,
    resolve_invoice_control,
)
from facturacion_dian_kit.core.xml.namespaces import (
    CURRENCY_COP,
    CUSTOMIZATION_DEBIT_NOTE,
    NS_DEBIT_NOTE,
    NSMAP_DEBIT_NOTE,
    cac,
    cbc,
)
from lxml import etree

DEFAULT_DEBIT_NOTE_RESPONSE_CODE = "1"
DEFAULT_DEBIT_NOTE_REASON = "Intereses"
DEBIT_NOTE_PROFILE_ID = "DIAN 2.1: Nota DÃ©bito de Factura ElectrÃ³nica de Venta"


def build_debit_note_xml(
    req: DocumentSubmitRequest,
    cude: str,
    qr_code: str | None = None,
) -> etree._Element:
    """Build a complete UBL 2.1 DebitNote XML for DIAN."""
    debit_note_number = req.debit_note_number or req.invoice_number
    response_code = req.debit_note_response_code or DEFAULT_DEBIT_NOTE_RESPONSE_CODE
    reason = req.debit_note_reason or DEFAULT_DEBIT_NOTE_REASON
    referenced_issue_date = req.referenced_invoice_issue_date or req.issue_date

    root = etree.Element(f"{{{NS_DEBIT_NOTE}}}DebitNote", nsmap=NSMAP_DEBIT_NOTE)

    software_security_code = calculate_software_security_code(
        resolved_software_id(req),
        resolved_software_pin(req),
        debit_note_number,
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

    _sub(root, cbc("UBLVersionID"), "UBL 2.1")
    _sub(root, cbc("CustomizationID"), CUSTOMIZATION_DEBIT_NOTE)
    _sub(root, cbc("ProfileID"), DEBIT_NOTE_PROFILE_ID)
    _sub(root, cbc("ProfileExecutionID"), resolved_tipo_ambiente(req))
    _sub(root, cbc("ID"), debit_note_number)
    _sub(
        root,
        cbc("UUID"),
        cude,
        schemeID=resolved_tipo_ambiente(req),
        schemeName="CUDE-SHA384",
    )
    _sub(root, cbc("IssueDate"), req.issue_date)
    _sub(root, cbc("IssueTime"), req.issue_time)
    _sub(root, cbc("Note"), reason)
    _sub(
        root,
        cbc("DocumentCurrencyCode"),
        CURRENCY_COP,
        listAgencyID="6",
        listAgencyName="United Nations Economic Commission for Europe",
        listID="ISO 4217 Alpha",
    )
    _sub(root, cbc("LineCountNumeric"), str(len(req.lines)))

    discrepancy = _sub(root, cac("DiscrepancyResponse"))
    _sub(discrepancy, cbc("ReferenceID"), req.referenced_invoice_number or "")
    _sub(discrepancy, cbc("ResponseCode"), response_code)
    _sub(discrepancy, cbc("Description"), reason)

    billing_ref = _sub(root, cac("BillingReference"))
    invoice_ref = _sub(billing_ref, cac("InvoiceDocumentReference"))
    _sub(invoice_ref, cbc("ID"), req.referenced_invoice_number or "")
    _sub(invoice_ref, cbc("UUID"), req.referenced_invoice_cufe or "", schemeName="CUFE-SHA384")
    _sub(invoice_ref, cbc("IssueDate"), referenced_issue_date)

    build_supplier_party(root, req.prefix, req)
    build_customer_party(root, req)
    build_payment_means(root, req.payment_method, req.issue_date)
    build_tax_totals(root, req.lines)
    build_requested_monetary_total(root, req.lines, req.total)

    for index, line in enumerate(req.lines, start=1):
        build_invoice_line(root, index, line, tag_name="DebitNoteLine")

    return root


def debit_note_to_xml_string(root: etree._Element) -> bytes:
    """Serialize the DebitNote XML tree to UTF-8 bytes."""
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )

