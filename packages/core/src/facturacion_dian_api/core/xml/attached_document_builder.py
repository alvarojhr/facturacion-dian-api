"""Build the signed UBL AttachedDocument delivered to an invoice buyer."""

from __future__ import annotations

import base64
from typing import cast

from facturacion_dian_api.core.buyer import validate_responsibilities, validate_tax_scheme
from facturacion_dian_api.core.models import AttachedDocumentBuildRequest
from facturacion_dian_api.core.signing.xades import verify_embedded_document_signature
from facturacion_dian_api.core.xml.namespaces import (
    DIAN_SCHEME_AGENCY_ID,
    DIAN_SCHEME_AGENCY_NAME,
    NS_DS,
    NSMAP_ATTACHED_DOCUMENT,
    attached,
    cac,
    cbc,
    ext,
)
from lxml import etree

DIAN_VALIDATOR_ID = "800197268"


def _sub(parent: etree._Element, tag: str, text: str | None = None, **attrib: str) -> etree._Element:
    el = etree.SubElement(parent, tag, **attrib)
    if text is not None:
        el.text = text
    return el


def _decode_xml(value: str, label: str) -> tuple[bytes, etree._Element]:
    try:
        payload = base64.b64decode(value, validate=True)
        root = etree.fromstring(payload, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    except (ValueError, etree.XMLSyntaxError) as exc:
        raise ValueError(f"{label} must be valid base64-encoded XML") from exc
    return payload, root


def _text(root: etree._Element, xpath: str) -> str:
    return str(root.xpath(f"string({xpath})")).strip()


def _validate_sources(
    req: AttachedDocumentBuildRequest,
) -> tuple[str, str, str, str, str, str, etree._Element]:
    _, invoice = _decode_xml(req.invoice_xml_base64, "invoice_xml_base64")
    _, response = _decode_xml(
        req.application_response_xml_base64,
        "application_response_xml_base64",
    )
    if etree.QName(invoice).localname not in {"Invoice", "CreditNote", "DebitNote"}:
        raise ValueError("invoice_xml_base64 must contain a UBL Invoice, CreditNote or DebitNote")
    if etree.QName(response).localname != "ApplicationResponse":
        raise ValueError("application_response_xml_base64 must contain a UBL ApplicationResponse")
    if invoice.find(f".//{{{NS_DS}}}Signature") is None:
        raise ValueError("invoice XML must carry the issuer ds:Signature")
    if response.find(f".//{{{NS_DS}}}Signature") is None:
        raise ValueError("DIAN ApplicationResponse must carry ds:Signature")
    verify_embedded_document_signature(invoice)
    verify_embedded_document_signature(response)

    metadata = (
        _text(invoice, "/*/*[local-name()='ID'][1]"),
        _text(invoice, "/*/*[local-name()='UUID'][1]"),
        _text(invoice, "/*/*[local-name()='IssueDate'][1]"),
        _text(invoice, "/*/*[local-name()='IssueTime'][1]"),
    )
    if metadata != (req.document_number, req.cufe, req.issue_date, req.issue_time):
        raise ValueError("AttachedDocument metadata does not match the signed source document")
    type_code = _text(invoice, "/*/*[local-name()='InvoiceTypeCode' or "
                      "local-name()='CreditNoteTypeCode' or local-name()='DebitNoteTypeCode'][1]")
    if type_code != req.document_type_code:
        raise ValueError("AttachedDocument document type does not match the signed source document")

    response_code = _text(
        response,
        "/*/*[local-name()='DocumentResponse']/*[local-name()='Response']"
        "/*[local-name()='ResponseCode'][1]",
    )
    if response_code != "02":
        raise ValueError("ApplicationResponse is not a DIAN validated-document response (code 02)")
    reference_xpath = (
        "/*/*[local-name()='DocumentResponse']/*[local-name()='DocumentReference']"
    )
    referenced_number = _text(response, reference_xpath + "/*[local-name()='ID'][1]")
    referenced_key = _text(response, reference_xpath + "/*[local-name()='UUID'][1]")
    referenced_type = _text(
        response,
        reference_xpath + "/*[local-name()='DocumentTypeCode'][1]",
    )
    if (referenced_number, referenced_key) != (req.document_number, req.cufe):
        raise ValueError("DIAN ApplicationResponse references a different document or CUFE/CUDE")
    if referenced_type and referenced_type != req.document_type_code:
        raise ValueError("DIAN ApplicationResponse references a different document type")
    response_id = _text(response, "/*/*[local-name()='ID'][1]")
    response_date = _text(response, "/*/*[local-name()='IssueDate'][1]")
    response_time = _text(response, "/*/*[local-name()='IssueTime'][1]")
    if not response_id or not response_date or not response_time:
        raise ValueError("DIAN ApplicationResponse is missing ID, IssueDate or IssueTime")
    environment = _text(invoice, "/*/*[local-name()='ProfileExecutionID'][1]")
    if environment not in {"1", "2"}:
        raise ValueError("signed source document has an invalid ProfileExecutionID")
    key_scheme = _text(invoice, "/*/*[local-name()='UUID'][1]/@schemeName")
    if key_scheme not in {"CUFE-SHA384", "CUDE-SHA384"}:
        raise ValueError("Signed source document has an invalid CUFE/CUDE scheme")
    return response_id, response_date, response_time, response_code, environment, key_scheme, invoice


def _source_party(
    invoice: etree._Element, *, role: str, name: str, identifier: str,
    document_type: str, dv: str | None, responsibility: str | None,
) -> tuple[str, str, str]:
    path = (f"/*/*[local-name()='Accounting{role}Party']/*[local-name()='Party']"
            "/*[local-name()='PartyTaxScheme']")
    parties = cast(list[etree._Element], invoice.xpath(path))
    if len(parties) != 1:
        raise ValueError(f"Signed source must contain exactly one {role} PartyTaxScheme")
    party = parties[0]
    source_identity = (
        _text(party, "*[local-name()='RegistrationName']"),
        _text(party, "*[local-name()='CompanyID']"),
        _text(party, "*[local-name()='CompanyID']/@schemeName"),
    )
    if source_identity != (name, identifier, document_type):
        raise ValueError(f"AttachedDocument {role} identity contradicts the signed source")
    if (dv is not None or document_type == "31") and (
        _text(party, "*[local-name()='CompanyID']/@schemeID") != (dv or "")
    ):
        raise ValueError(f"AttachedDocument {role} DV contradicts the signed source")
    nodes = party.findall(cbc("TaxLevelCode"))
    if len(nodes) > 1:
        raise ValueError(f"Signed {role} has multiple TaxLevelCode elements")
    if not nodes:
        if role == "Customer":
            raise ValueError(
                "ATTACHED_DOCUMENT_BUYER_RESPONSIBILITY_UNRESOLVED: signed source has no "
                "buyer TaxLevelCode; AE28 requires it. No officially supported unknown-value "
                "representation has been established. Electronic delivery is blocked; "
                "do not invent R-99-PN or rewrite the signed document."
            )
        raise ValueError("Signed source is missing issuer TaxLevelCode")
    source_level = validate_responsibilities(nodes[0].text or "")
    asserted_level = validate_responsibilities(responsibility)
    if asserted_level is not None and asserted_level != source_level:
        raise ValueError(f"AttachedDocument {role} tax_level_code contradicts the signed source")
    scheme_id = _text(party, "*[local-name()='TaxScheme']/*[local-name()='ID']")
    scheme_name = _text(party, "*[local-name()='TaxScheme']/*[local-name()='Name']")
    validate_tax_scheme(scheme_id, scheme_name)
    assert source_level is not None
    return source_level, scheme_id, scheme_name


def _party(
    parent: etree._Element,
    *,
    name: str,
    nit: str,
    dv: str | None,
    document_type: str,
    tax_level: str,
    tax_scheme_id: str,
    tax_scheme_name: str,
    email: str | None = None,
) -> None:
    tax = _sub(parent, cac("PartyTaxScheme"))
    _sub(tax, cbc("RegistrationName"), name)
    attrs = {
        "schemeAgencyID": DIAN_SCHEME_AGENCY_ID,
        "schemeAgencyName": DIAN_SCHEME_AGENCY_NAME,
        "schemeName": document_type,
    }
    if dv:
        attrs["schemeID"] = dv
    _sub(tax, cbc("CompanyID"), nit, **attrs)
    _sub(tax, cbc("TaxLevelCode"), tax_level, listName="No aplica")
    scheme = _sub(tax, cac("TaxScheme"))
    _sub(scheme, cbc("ID"), tax_scheme_id)
    _sub(scheme, cbc("Name"), tax_scheme_name)
    if email:
        contact = _sub(parent, cac("Contact"))
        _sub(contact, cbc("ElectronicMail"), email)


def _embedded_attachment(parent: etree._Element, filename: str, payload_base64: str) -> None:
    attachment = _sub(parent, cac("Attachment"))
    external = _sub(attachment, cac("ExternalReference"))
    _sub(external, cbc("MimeCode"), "text/xml")
    _sub(external, cbc("EncodingCode"), "UTF-8")
    _sub(external, cbc("FileName"), filename)
    description = _sub(external, cbc("Description"))
    original = base64.b64decode(payload_base64, validate=True)
    text = original.decode("utf-8")  # Preserve an original UTF-8 BOM, if present.
    # XML 1.0 normalizes literal CR inside CDATA. Character references preserve
    # those bytes through parsing/signing; ordinary UTF-8 documents use CDATA.
    description.text = text if "\r" in text else etree.CDATA(text)


def build_attached_document_xml(req: AttachedDocumentBuildRequest) -> bytes:
    """Build a complete AttachedDocument containing both mandatory XML artifacts."""
    (
        response_id,
        response_date,
        response_time,
        response_code,
        environment,
        key_scheme,
        invoice,
    ) = _validate_sources(req)
    issuer_level, issuer_scheme_id, issuer_scheme_name = _source_party(
        invoice, role="Supplier", name=req.issuer_name, identifier=req.issuer_nit,
        document_type="31", dv=req.issuer_dv, responsibility=req.issuer_tax_level_code,
    )
    receiver_level, receiver_scheme_id, receiver_scheme_name = _source_party(
        invoice, role="Customer", name=req.receiver_name, identifier=req.receiver_nit,
        document_type=req.receiver_document_type, dv=req.receiver_dv,
        responsibility=req.receiver_tax_level_code,
    )

    root = etree.Element(attached("AttachedDocument"), nsmap=NSMAP_ATTACHED_DOCUMENT)
    extensions = _sub(root, ext("UBLExtensions"))
    extension = _sub(extensions, ext("UBLExtension"))
    _sub(extension, ext("ExtensionContent"))

    _sub(root, cbc("UBLVersionID"), "UBL 2.1")
    _sub(root, cbc("CustomizationID"), "Documentos adjuntos")
    _sub(root, cbc("ProfileID"), "Factura Electrónica de Venta")
    _sub(root, cbc("ProfileExecutionID"), environment)
    _sub(root, cbc("ID"), req.document_number)
    _sub(root, cbc("IssueDate"), req.issue_date)
    _sub(root, cbc("IssueTime"), req.issue_time)
    _sub(root, cbc("DocumentType"), "Contenedor de Factura Electrónica")
    _sub(root, cbc("ParentDocumentID"), req.document_number)

    sender = _sub(root, cac("SenderParty"))
    _party(
        sender,
        name=req.issuer_name,
        nit=req.issuer_nit,
        dv=req.issuer_dv,
        document_type="31",
        tax_level=issuer_level,
        tax_scheme_id=issuer_scheme_id,
        tax_scheme_name=issuer_scheme_name,
    )
    receiver = _sub(root, cac("ReceiverParty"))
    _party(
        receiver,
        name=req.receiver_name,
        nit=req.receiver_nit,
        dv=req.receiver_dv,
        document_type=req.receiver_document_type,
        tax_level=receiver_level,
        tax_scheme_id=receiver_scheme_id,
        tax_scheme_name=receiver_scheme_name,
        email=req.receiver_email,
    )

    _embedded_attachment(root, req.invoice_xml_filename, req.invoice_xml_base64)

    line_reference = _sub(root, cac("ParentDocumentLineReference"))
    _sub(line_reference, cbc("LineID"), "1")
    document_reference = _sub(line_reference, cac("DocumentReference"))
    _sub(document_reference, cbc("ID"), response_id)
    _sub(document_reference, cbc("UUID"), req.cufe, schemeName=key_scheme)
    _sub(document_reference, cbc("IssueDate"), response_date)
    _sub(document_reference, cbc("DocumentType"), "ApplicationResponse")
    _embedded_attachment(
        document_reference,
        req.application_response_xml_filename,
        req.application_response_xml_base64,
    )
    verification = _sub(document_reference, cac("ResultOfVerification"))
    _sub(verification, cbc("ValidatorID"), DIAN_VALIDATOR_ID)
    _sub(verification, cbc("ValidationResultCode"), response_code)
    _sub(verification, cbc("ValidationDate"), response_date)
    _sub(verification, cbc("ValidationTime"), response_time)

    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=False)
