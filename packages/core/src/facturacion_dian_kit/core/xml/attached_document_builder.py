"""Build DIAN-style AttachedDocument payloads for interoperable email delivery."""

from __future__ import annotations

import base64
from datetime import date

from facturacion_dian_kit.core.models import AttachedDocumentBuildRequest
from facturacion_dian_kit.core.xml.namespaces import NSMAP_ATTACHED_DOCUMENT, attached, cac, cbc
from lxml import etree

DIAN_VALIDATOR_ID = "800197268"


def _sub(parent: etree._Element, tag: str, text: str | None = None, **attrib: str) -> etree._Element:
    el = etree.SubElement(parent, tag, **attrib)
    if text is not None:
        el.text = text
    return el


def build_attached_document_xml(req: AttachedDocumentBuildRequest) -> bytes:
    """Build an AttachedDocument XML that embeds the invoice XML as CDATA."""

    try:
        embedded_xml = base64.b64decode(req.invoice_xml_base64).decode("utf-8")
    except Exception as exc:  # pragma: no cover - pydantic validates shape, not base64 content
        raise ValueError("invoice_xml_base64 is not valid base64-encoded XML") from exc

    root = etree.Element(attached("AttachedDocument"), nsmap=NSMAP_ATTACHED_DOCUMENT)
    _sub(root, cbc("UBLVersionID"), "UBL 2.1")
    _sub(root, cbc("CustomizationID"), "Documento adjunto")
    _sub(root, cbc("ProfileID"), "DIAN 2.1: AttachedDocument")
    _sub(root, cbc("ProfileExecutionID"), "1")
    _sub(root, cbc("ID"), req.document_number)
    _sub(root, cbc("IssueDate"), req.issue_date or date.today().isoformat())
    _sub(root, cbc("DocumentTypeCode"), req.document_type_code)
    _sub(root, cbc("ParentDocumentID"), req.document_number)
    if req.cufe:
        _sub(root, cbc("UUID"), req.cufe, schemeName="CUFE-SHA384")

    sender = _sub(root, cac("SenderParty"))
    sender_tax = _sub(sender, cac("PartyTaxScheme"))
    _sub(sender_tax, cbc("RegistrationName"), req.issuer_name)
    _sub(sender_tax, cbc("CompanyID"), req.issuer_nit, schemeName="31")

    receiver = _sub(root, cac("ReceiverParty"))
    receiver_tax = _sub(receiver, cac("PartyTaxScheme"))
    _sub(receiver_tax, cbc("RegistrationName"), req.receiver_name)
    if req.receiver_email:
        contact = _sub(receiver, cac("Contact"))
        _sub(contact, cbc("ElectronicMail"), req.receiver_email)

    attachment = _sub(root, cac("Attachment"))
    external_reference = _sub(attachment, cac("ExternalReference"))
    _sub(external_reference, cbc("MimeCode"), "text/xml")
    _sub(external_reference, cbc("FileName"), req.invoice_xml_filename)
    description = _sub(external_reference, cbc("Description"))
    description.text = etree.CDATA(embedded_xml)

    verification = _sub(root, cac("ParentDocumentLineReference"))
    _sub(verification, cbc("LineID"), "1")
    document_reference = _sub(verification, cac("DocumentReference"))
    _sub(document_reference, cbc("ID"), req.document_number)
    result = _sub(verification, cac("ResultOfVerification"))
    _sub(result, cbc("ValidatorID"), DIAN_VALIDATOR_ID)
    _sub(result, cbc("ValidationResultCode"), req.validation_result_code or "00")
    _sub(result, cbc("ValidationDate"), req.issue_date or date.today().isoformat())
    _sub(result, cbc("ValidationTime"), "00:00:00-05:00")

    note_parts = [f"Correo autorrespuesta: {req.reply_to_email}"]
    if req.company_name:
        note_parts.append(f"Empresa: {req.company_name}")
    if req.business_line:
        note_parts.append(f"Linea de negocio: {req.business_line}")
    _sub(root, cbc("Note"), " | ".join(note_parts))

    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True)

