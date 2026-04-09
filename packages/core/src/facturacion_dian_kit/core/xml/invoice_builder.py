"""UBL 2.1 Invoice XML builder for DIAN documents."""

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
    build_legal_monetary_total,
    build_payment_means,
    build_supplier_party,
    build_tax_totals,
    build_ubl_extensions,
    resolve_invoice_control,
)
from facturacion_dian_kit.core.xml.namespaces import (
    CURRENCY_COP,
    CUSTOMIZATION_DOC_EQUIVALENTE,
    CUSTOMIZATION_FACTURA,
    INVOICE_TYPE_DOC_EQUIVALENTE_POS,
    INVOICE_TYPE_FACTURA,
    NS_INVOICE,
    NSMAP_INVOICE,
    cbc,
)
from lxml import etree

FACTURA_PROFILE_ID = "DIAN 2.1: Factura ElectrÃ³nica de Venta"
POS_PROFILE_ID = "DIAN 2.1: Documento Equivalente POS"


def build_invoice_xml(
    req: DocumentSubmitRequest,
    cufe: str,
    qr_code: str | None = None,
) -> etree._Element:
    """Build a complete UBL 2.1 Invoice XML for DIAN."""
    is_pos = req.document_type == "DOCUMENTO_EQUIVALENTE_POS"
    root = etree.Element(f"{{{NS_INVOICE}}}Invoice", nsmap=NSMAP_INVOICE)

    software_security_code = calculate_software_security_code(
        resolved_software_id(req),
        resolved_software_pin(req),
        req.invoice_number,
    )

    invoice_control = build_ubl_extensions(
        root,
        req,
        software_security_code,
        qr_code,
        include_software_manufacturer=is_pos,
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
    _sub(
        root,
        cbc("CustomizationID"),
        CUSTOMIZATION_DOC_EQUIVALENTE if is_pos else CUSTOMIZATION_FACTURA,
    )
    _sub(root, cbc("ProfileID"), POS_PROFILE_ID if is_pos else FACTURA_PROFILE_ID)
    _sub(root, cbc("ProfileExecutionID"), resolved_tipo_ambiente(req))
    _sub(root, cbc("ID"), req.invoice_number)

    _sub(
        root,
        cbc("UUID"),
        cufe,
        schemeID=resolved_tipo_ambiente(req),
        schemeName="CUDE-SHA384" if is_pos else "CUFE-SHA384",
    )

    _sub(root, cbc("IssueDate"), req.issue_date)
    _sub(root, cbc("IssueTime"), req.issue_time)
    _sub(root, cbc("DueDate"), req.issue_date)
    _sub(
        root,
        cbc("InvoiceTypeCode"),
        INVOICE_TYPE_DOC_EQUIVALENTE_POS if is_pos else INVOICE_TYPE_FACTURA,
    )
    _sub(root, cbc("Note"), "")
    _sub(
        root,
        cbc("DocumentCurrencyCode"),
        CURRENCY_COP,
        listAgencyID="6",
        listAgencyName="United Nations Economic Commission for Europe",
        listID="ISO 4217 Alpha",
    )
    _sub(root, cbc("LineCountNumeric"), str(len(req.lines)))

    build_supplier_party(root, req.prefix, req)
    build_customer_party(root, req)
    build_payment_means(root, req.payment_method, req.issue_date)
    build_tax_totals(root, req.lines)
    build_legal_monetary_total(root, req.lines, req.total)

    for index, line in enumerate(req.lines, start=1):
        build_invoice_line(root, index, line, tag_name="InvoiceLine")

    return root


def invoice_to_xml_string(root: etree._Element) -> bytes:
    """Serialize the Invoice XML tree to UTF-8 bytes."""
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )

