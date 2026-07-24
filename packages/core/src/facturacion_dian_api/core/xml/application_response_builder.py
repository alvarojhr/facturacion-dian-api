"""UBL 2.1 ApplicationResponse XML builder for RADIAN receiver events.

Implements the "estructura común para todos los eventos" (DIAN Anexo Técnico
Factura Electrónica de Venta v1.9, § 6.5.4) plus the per-event detail tables of
§ 6.5.5.3 (030 acuse de recibo), § 6.5.5.4 (031 reclamo), § 6.5.5.5 (032 recibo
del bien) and § 6.5.5.6 (033 aceptación expresa).

The event 034 (aceptación tácita) is deliberately not implemented: the DIAN
registers it on the issuer's side, not the receiver's.

Two traps worth naming, both of which produce a DIAN rejection rather than a
crash:

- ``cbc:IssueDate`` must equal the date of the XAdES signature (rule AAD09e).
  The service stamps both from ``datetime.now(COLOMBIA_TZ)``; a bare UTC
  timestamp flips the date after 19:00 Colombia time and the event bounces.
- ``sts:QRCode`` carries the CUFE of the **referenced invoice**, not the CUDE
  of the event (rule AAB36).
"""

from __future__ import annotations

from facturacion_dian_api.core.config import settings
from facturacion_dian_api.core.cufe.calculator import (
    build_qr_url,
    calculate_software_security_code,
)
from facturacion_dian_api.core.models import EventSubmitRequest
from facturacion_dian_api.core.runtime_config import compute_nit_dv
from facturacion_dian_api.core.xml.namespaces import (
    APPLICATION_RESPONSE_CUSTOMIZATION_ID,
    APPLICATION_RESPONSE_PROFILE_ID,
    CLAIM_CAUSE_NAMES,
    CURRENCY_COP,
    DIAN_AUTHORIZATION_PROVIDER_DV,
    DIAN_AUTHORIZATION_PROVIDER_ID,
    DIAN_SCHEME_AGENCY_ID,
    DIAN_SCHEME_AGENCY_NAME,
    EVENT_DESCRIPTIONS,
    NSMAP_APPLICATION_RESPONSE,
    application_response,
    cac,
    cbc,
    ext,
    sts,
)
from lxml import etree

# Tipo de identificador fiscal: 31 = NIT (tabla 13.2.1 del Anexo Técnico).
SCHEME_NAME_NIT = "31"
# Tipo de organización jurídica (@schemeVersionID): 1 = persona jurídica.
SCHEME_VERSION_LEGAL_ENTITY = "1"


def _sub(parent: etree._Element, tag: str, text: str | None = None, **attrib: str) -> etree._Element:
    el = etree.SubElement(parent, tag, **attrib)
    if text is not None:
        el.text = text
    return el


def _tipo_ambiente(req: EventSubmitRequest) -> str:
    environment = req.environment or settings.dian.environment
    return "1" if environment == "produccion" else "2"


def _party_tax_scheme(
    parent: etree._Element,
    *,
    registration_name: str,
    company_id: str,
    verification_digit: str,
    organization_type: str,
) -> None:
    """Build the cac:PartyTaxScheme block shared by Sender and Receiver.

    ``cac:SenderParty``/``cac:ReceiverParty`` are UBL ``PartyType`` nodes, so
    ``cac:PartyTaxScheme`` hangs directly off them — there is no intermediate
    ``cac:Party`` here, unlike ``cac:AccountingSupplierParty`` on an invoice.
    The annex XPath (``/ApplicationResponse/cac:SenderParty/cac:PartyTaxScheme/
    cbc:CompanyID``) is what feeds the CUDE seed, so an extra level breaks it.
    """
    tax_scheme = _sub(parent, cac("PartyTaxScheme"))
    _sub(tax_scheme, cbc("RegistrationName"), registration_name)
    _sub(
        tax_scheme,
        cbc("CompanyID"),
        company_id,
        schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
        schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
        schemeID=verification_digit,
        schemeName=SCHEME_NAME_NIT,
        schemeVersionID=organization_type,
    )
    scheme = _sub(tax_scheme, cac("TaxScheme"))
    _sub(scheme, cbc("ID"), "01")
    _sub(scheme, cbc("Name"), "IVA")


def _build_dian_extensions(root: etree._Element, req: EventSubmitRequest, event_number: str) -> None:
    """Build ext:UBLExtensions: DIAN extensions + the signature placeholder.

    § 6.5.4 (AAC01) requires exactly two UBLExtension nodes for an event: one
    carrying ``sts:DianExtensions`` and one that ``core.signing.xades`` fills
    with ``ds:Signature``. Unlike an invoice, an event carries **no**
    ``sts:InvoiceControl``: events consume no DIAN numbering range.
    """
    extensions = _sub(root, ext("UBLExtensions"))

    dian_extension = _sub(extensions, ext("UBLExtension"))
    content = _sub(dian_extension, ext("ExtensionContent"))
    dian_ext = _sub(content, sts("DianExtensions"))

    invoice_source = _sub(dian_ext, sts("InvoiceSource"))
    _sub(
        invoice_source,
        cbc("IdentificationCode"),
        CURRENCY_COP[:2],
        listAgencyID="6",
        listAgencyName="United Nations Economic Commission for Europe",
        listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1",
    )

    software_owner_nit = settings.company.nit
    software_provider = _sub(dian_ext, sts("SoftwareProvider"))
    _sub(
        software_provider,
        sts("ProviderID"),
        software_owner_nit,
        schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
        schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
        schemeID=compute_nit_dv(software_owner_nit),
        schemeName=SCHEME_NAME_NIT,
    )
    _sub(
        software_provider,
        sts("SoftwareID"),
        (req.software_id or settings.dian.software_id).strip(),
        schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
        schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
    )

    # AAB27: la huella se calcula sobre el número del propio evento
    # (§ 11.8: NroDocumento = ApplicationResponse/cbc:ID), no sobre el número
    # de la factura referenciada.
    _sub(
        dian_ext,
        sts("SoftwareSecurityCode"),
        calculate_software_security_code(
            (req.software_id or settings.dian.software_id).strip(),
            (req.software_pin or settings.dian.software_pin).strip(),
            event_number,
        ),
        schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
        schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
    )

    # Orden AAB30 → AAB36: AuthorizationProvider precede a QRCode en la
    # secuencia de sts:DianExtensions para eventos.
    auth_provider = _sub(dian_ext, sts("AuthorizationProvider"))
    _sub(
        auth_provider,
        sts("AuthorizationProviderID"),
        DIAN_AUTHORIZATION_PROVIDER_ID,
        schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
        schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
        schemeID=DIAN_AUTHORIZATION_PROVIDER_DV,
        schemeName=SCHEME_NAME_NIT,
    )

    _sub(dian_ext, sts("QRCode"), build_qr_url(req.document_cufe))

    signature_extension = _sub(extensions, ext("UBLExtension"))
    _sub(signature_extension, ext("ExtensionContent"))


def _build_document_response(root: etree._Element, req: EventSubmitRequest) -> None:
    document_response = _sub(root, cac("DocumentResponse"))

    response = _sub(document_response, cac("Response"))
    if req.event_type == "031":
        # AAH10/AAH92: la causal del reclamo viaja como atributos del propio
        # ResponseCode, no como un elemento aparte.
        cause_code = req.claim_cause_code or "01"
        _sub(
            response,
            cbc("ResponseCode"),
            req.event_type,
            listID=cause_code,
            name=CLAIM_CAUSE_NAMES[cause_code],
        )
    else:
        _sub(response, cbc("ResponseCode"), req.event_type)
    _sub(response, cbc("Description"), EVENT_DESCRIPTIONS[req.event_type])

    # AAH05–AAH09. La tabla del anexo no lista cbc:IssueDate dentro del
    # DocumentReference de estos eventos, así que no se emite aunque el
    # llamador envíe document_issue_date (lo usa el ERP para su propio
    # registro, no la DIAN).
    reference = _sub(document_response, cac("DocumentReference"))
    _sub(reference, cbc("ID"), req.document_number)
    _sub(reference, cbc("UUID"), req.document_cufe, schemeName="CUFE-SHA384")
    _sub(reference, cbc("DocumentTypeCode"), req.document_type_code)

    person_data = req.receiver_person
    if person_data is not None:
        issuer_party = _sub(document_response, cac("IssuerParty"))
        person = _sub(issuer_party, cac("Person"))
        # AAH14: @schemeID sólo aplica cuando la persona se identifica por NIT
        # (@schemeName=31); para cédula y demás documentos no hay dígito de
        # verificación que informar.
        person_id_attrs = {"schemeName": person_data.document_type}
        if person_data.document_type == SCHEME_NAME_NIT:
            person_id_attrs["schemeID"] = compute_nit_dv(person_data.document_number)
        _sub(person, cbc("ID"), person_data.document_number, **person_id_attrs)
        _sub(person, cbc("FirstName"), person_data.first_name)
        _sub(person, cbc("FamilyName"), person_data.family_name)
        if person_data.job_title:
            _sub(person, cbc("JobTitle"), person_data.job_title)
        if person_data.organization_department:
            _sub(person, cbc("OrganizationDepartment"), person_data.organization_department)


def build_application_response_xml(
    req: EventSubmitRequest,
    cude: str,
    event_number: str,
    issue_date: str,
    issue_time: str,
) -> etree._Element:
    """Build a complete UBL 2.1 ApplicationResponse for a RADIAN event.

    Args:
        req: Resolved event request.
        cude: Event CUDE, already computed from the very same
            ``event_number``/``issue_date``/``issue_time`` passed here — the
            seed and the XML must agree or DIAN rejects with rule AAD06.
        event_number: Value for ``cbc:ID`` (the receiver's own consecutive).
        issue_date: ``YYYY-MM-DD`` in Colombian time.
        issue_time: ``HH:MM:SS-05:00``.
    """
    root = etree.Element(application_response("ApplicationResponse"), nsmap=NSMAP_APPLICATION_RESPONSE)

    _build_dian_extensions(root, req, event_number)

    tipo_ambiente = _tipo_ambiente(req)
    _sub(root, cbc("UBLVersionID"), "UBL 2.1")
    _sub(root, cbc("CustomizationID"), APPLICATION_RESPONSE_CUSTOMIZATION_ID)
    _sub(root, cbc("ProfileID"), APPLICATION_RESPONSE_PROFILE_ID)
    _sub(root, cbc("ProfileExecutionID"), tipo_ambiente)
    _sub(root, cbc("ID"), event_number)
    _sub(
        root,
        cbc("UUID"),
        cude,
        schemeID=tipo_ambiente,
        schemeName="CUDE-SHA384",
    )
    _sub(root, cbc("IssueDate"), issue_date)
    _sub(root, cbc("IssueTime"), issue_time)
    if req.event_type == "031" and req.claim_description:
        _sub(root, cbc("Note"), req.claim_description)

    # SenderParty = quien genera el evento (nosotros, el adquiriente).
    # ReceiverParty = quien lo recibe (el emisor de la factura, el proveedor).
    # Ese es también el orden de los NITs en la semilla del CUDE.
    sender = _sub(root, cac("SenderParty"))
    _party_tax_scheme(
        sender,
        registration_name=settings.company.name,
        company_id=settings.company.nit,
        verification_digit=settings.company.dv or compute_nit_dv(settings.company.nit),
        organization_type=settings.company.additional_account_id,
    )

    receiver = _sub(root, cac("ReceiverParty"))
    _party_tax_scheme(
        receiver,
        registration_name=req.supplier_name,
        company_id=req.supplier_nit,
        verification_digit=(req.supplier_dv or "").strip() or compute_nit_dv(req.supplier_nit),
        organization_type=SCHEME_VERSION_LEGAL_ENTITY,
    )

    _build_document_response(root, req)

    return root


def application_response_to_xml_string(root: etree._Element) -> bytes:
    """Serialize the ApplicationResponse XML tree to UTF-8 bytes."""
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )
