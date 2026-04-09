"""Shared UBL 2.1 XML element builders."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from facturacion_dian_kit.core.config import settings
from facturacion_dian_kit.core.models import DocumentLine, DocumentSubmitRequest
from facturacion_dian_kit.core.runtime_config import (
    resolved_issuer_dv,
    resolved_issuer_nit,
    resolved_software_id,
    resolved_software_owner_dv,
    resolved_software_owner_nit,
)
from facturacion_dian_kit.core.xml.namespaces import (
    CURRENCY_COP,
    DIAN_SCHEME_AGENCY_ID,
    DIAN_SCHEME_AGENCY_NAME,
    PAYMENT_MEANS,
    TAX_TYPE_TO_DIAN,
    cac,
    cbc,
    ext,
    sts,
)
from lxml import etree

FINAL_CONSUMER_ID = "222222222222"
FINAL_CONSUMER_TAX_LEVEL_CODE = "R-99-PN"
VALID_TAX_LEVEL_CODES = {"O-13", "O-15", "O-23", "O-47", FINAL_CONSUMER_TAX_LEVEL_CODE}
CUSTOMER_DOCUMENT_SCHEME_NAMES = {
    "FINAL_CONSUMER": "13",
    "NIT": "31",
    "CC": "13",
    "CE": "22",
    "TI": "12",
    "PASSPORT": "41",
}
CUSTOMER_ADDITIONAL_ACCOUNT_IDS = {
    "FINAL_CONSUMER": "2",
    "NIT": "1",
    "CC": "2",
    "CE": "2",
    "TI": "2",
    "PASSPORT": "2",
}


def _money(value_cop: int) -> str:
    """Format COP integer to string with 2 decimal places."""
    return str(Decimal(value_cop).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _sub(parent: etree._Element, tag: str, text: str | None = None, **attrib: str) -> etree._Element:
    """Create a sub-element with optional text and attributes."""
    el = etree.SubElement(parent, tag, **attrib)
    if text is not None:
        el.text = text
    return el


def _normalize_tax_level_code(value: str | None, *, default: str) -> str:
    if value is None:
        return default

    normalized = value.strip().upper()
    if not normalized:
        return default

    compact = normalized.replace("-", "")
    numeric_map = {
        "13": "O-13",
        "15": "O-15",
        "23": "O-23",
        "47": "O-47",
        "99PN": FINAL_CONSUMER_TAX_LEVEL_CODE,
        "R99PN": FINAL_CONSUMER_TAX_LEVEL_CODE,
    }
    normalized = numeric_map.get(compact, normalized)
    return normalized if normalized in VALID_TAX_LEVEL_CODES else default


def _compute_nit_dv(identifier: str | None) -> str | None:
    if not identifier:
        return None

    digits = "".join(ch for ch in identifier if ch.isdigit())
    if not digits:
        return None

    digits = digits[-15:]
    weights = [71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]
    weighted_digits = digits.rjust(len(weights), "0")
    total = sum(int(digit) * weight for digit, weight in zip(weighted_digits, weights, strict=True))
    remainder = total % 11
    verification_digit = 11 - remainder

    if verification_digit == 11:
        return "0"
    if verification_digit == 10:
        return "1"
    return str(verification_digit)


def _company_id_attrs(identifier_type: str, verification_digit: str | None) -> dict[str, str]:
    attrs = {
        "schemeAgencyID": DIAN_SCHEME_AGENCY_ID,
        "schemeAgencyName": DIAN_SCHEME_AGENCY_NAME,
        "schemeName": identifier_type,
    }
    if verification_digit is not None:
        attrs["schemeID"] = verification_digit
    return attrs


def _normalize_customer_document_type(req: DocumentSubmitRequest) -> str:
    raw_value = (req.customer_document_type or "").strip().upper()
    if raw_value in CUSTOMER_DOCUMENT_SCHEME_NAMES:
        return raw_value
    return "NIT" if req.customer_nit else "FINAL_CONSUMER"


def _country_name(country_code: str) -> str:
    return "Colombia" if country_code.upper() == "CO" else country_code.upper()


def _truncate(value: str | None, max_length: int, fallback: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        normalized = fallback
    return normalized[:max_length]


def _build_named_value_extension(
    parent: etree._Element,
    group_tag: str,
    info_tag: str,
    rows: list[tuple[str, str]],
) -> None:
    group = _sub(parent, group_tag)
    for name, value in rows:
        info = _sub(group, info_tag)
        _sub(info, "Name", name)
        _sub(info, "Value", value)


def _build_customer_address(parent: etree._Element, req: DocumentSubmitRequest) -> None:
    city_code = req.customer_city_code or settings.company.city_code
    city_name = req.customer_city_name or settings.company.city_name
    department_name = req.customer_department_name or settings.company.department_name
    department_code = req.customer_department_code or settings.company.department_code
    address_line = req.customer_address or "N/A"
    country_code = (req.customer_country_code or settings.company.country_code).upper()

    _sub(parent, cbc("ID"), city_code)
    _sub(parent, cbc("CityName"), city_name)
    _sub(parent, cbc("PostalZone"), city_code)
    _sub(parent, cbc("CountrySubentity"), department_name)
    _sub(parent, cbc("CountrySubentityCode"), department_code)
    addr_line = _sub(parent, cac("AddressLine"))
    _sub(addr_line, cbc("Line"), address_line)
    country = _sub(parent, cac("Country"))
    _sub(country, cbc("IdentificationCode"), country_code)
    _sub(country, cbc("Name"), _country_name(country_code), languageID="es")


def build_ubl_extensions(
    root: etree._Element,
    req: DocumentSubmitRequest,
    software_security_code: str,
    qr_code: str | None = None,
    *,
    include_software_manufacturer: bool = False,
) -> etree._Element:
    """Build ext:UBLExtensions and return sts:InvoiceControl."""
    extensions = _sub(root, ext("UBLExtensions"))

    ext1 = _sub(extensions, ext("UBLExtension"))
    content1 = _sub(ext1, ext("ExtensionContent"))
    dian_ext = _sub(content1, sts("DianExtensions"))

    invoice_control = _sub(dian_ext, sts("InvoiceControl"))

    invoice_source = _sub(dian_ext, sts("InvoiceSource"))
    _sub(
        invoice_source,
        cbc("IdentificationCode"),
        CURRENCY_COP[:2],
        listAgencyID="6",
        listAgencyName="United Nations Economic Commission for Europe",
        listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1",
    )

    software_provider = _sub(dian_ext, sts("SoftwareProvider"))
    _sub(
        software_provider,
        sts("ProviderID"),
        resolved_software_owner_nit(req),
        schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
        schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
        schemeID=resolved_software_owner_dv(req),
        schemeName="31",
    )
    _sub(
        software_provider,
        sts("SoftwareID"),
        resolved_software_id(req),
        schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
        schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
    )

    _sub(
        dian_ext,
        sts("SoftwareSecurityCode"),
        software_security_code,
        schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
        schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
    )
    if qr_code:
        _sub(dian_ext, sts("QRCode"), qr_code)

    auth_provider = _sub(dian_ext, sts("AuthorizationProvider"))
    _sub(
        auth_provider,
        sts("AuthorizationProviderID"),
        "800197268",
        schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
        schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
        schemeID="4",
        schemeName="31",
    )

    if include_software_manufacturer:
        manufacturer_extension = _sub(extensions, ext("UBLExtension"))
        manufacturer_content = _sub(manufacturer_extension, ext("ExtensionContent"))
        manufacturer_name = (
            settings.dian.software_manufacturer_name.strip()
            or settings.company.name
        )
        manufacturer_company_name = (
            settings.dian.software_manufacturer_company_name.strip()
            or settings.company.name
        )
        software_name = settings.dian.software_name.strip() or "Facturacion DIAN Kit"
        _build_named_value_extension(
            manufacturer_content,
            "FabricanteSoftware",
            "InformacionDelFabricanteDelSoftware",
            [
                ("NombreApellido", _truncate(manufacturer_name, 100, settings.company.name)),
                ("RazonSocial", _truncate(manufacturer_company_name, 100, settings.company.name)),
                ("NombreSoftware", _truncate(software_name, 100, "Facturacion DIAN Kit")),
            ],
        )

        benefits_extension = _sub(extensions, ext("UBLExtension"))
        benefits_content = _sub(benefits_extension, ext("ExtensionContent"))
        buyer_code = req.customer_nit or FINAL_CONSUMER_ID
        buyer_name = _truncate(req.customer_name, 100, "Consumidor Final")
        buyer_points = str(req.buyer_loyalty_points if req.buyer_loyalty_points is not None else 0)
        _build_named_value_extension(
            benefits_content,
            "BeneficiosComprador",
            "InformacionBeneficiosComprador",
            [
                ("Codigo", _truncate(buyer_code, 100, FINAL_CONSUMER_ID)),
                ("NombresApellidos", buyer_name),
                ("Puntos", _truncate(buyer_points, 100, "0")),
            ],
        )

        point_of_sale_extension = _sub(extensions, ext("UBLExtension"))
        point_of_sale_content = _sub(point_of_sale_extension, ext("ExtensionContent"))
        _build_named_value_extension(
            point_of_sale_content,
            "PuntoVenta",
            "InformacionCajaVenta",
            [
                ("PlacaCaja", _truncate(req.pos_register_plate, 100, "POS-1")),
                ("Ubicaci\u00f3nCaja", _truncate(req.pos_register_location, 100, settings.company.address or "Punto de venta")),
                ("Cajero", _truncate(req.cashier_name, 100, "Cajero POS")),
                ("TipoCaja", _truncate(req.pos_register_type, 100, "POS")),
                ("C\u00f3digoVenta", _truncate(req.sale_code, 100, req.invoice_number)),
                ("SubTotal", _truncate(str(req.subtotal), 100, "0")),
            ],
        )

    signature_extension = _sub(extensions, ext("UBLExtension"))
    _sub(signature_extension, ext("ExtensionContent"))
    return invoice_control


def build_invoice_control(
    parent: etree._Element,
    resolution_number: str,
    prefix: str,
    range_from: int,
    range_to: int,
    valid_from: str,
    valid_to: str,
) -> None:
    """Populate sts:InvoiceControl with numbering resolution data."""
    _sub(parent, sts("InvoiceAuthorization"), resolution_number)
    authorization_period = _sub(parent, sts("AuthorizationPeriod"))
    _sub(authorization_period, cbc("StartDate"), valid_from)
    _sub(authorization_period, cbc("EndDate"), valid_to)

    authorized_invoices = _sub(parent, sts("AuthorizedInvoices"))
    _sub(authorized_invoices, sts("Prefix"), prefix)
    _sub(authorized_invoices, sts("From"), str(range_from))
    _sub(authorized_invoices, sts("To"), str(range_to))


def resolve_invoice_control(req: DocumentSubmitRequest) -> tuple[int, int, str, str]:
    """Resolve resolution range and validity, preferring request-specific data."""
    valid_from = req.resolution_valid_from.strip() if req.resolution_valid_from else settings.dian.resolution_valid_from
    valid_to = req.resolution_valid_to.strip() if req.resolution_valid_to else settings.dian.resolution_valid_to

    return (
        req.resolution_range_from if req.resolution_range_from is not None else settings.dian.resolution_range_from,
        req.resolution_range_to if req.resolution_range_to is not None else settings.dian.resolution_range_to,
        valid_from,
        valid_to,
    )


def build_supplier_party(parent: etree._Element, prefix: str, req: DocumentSubmitRequest) -> None:
    """Build cac:AccountingSupplierParty from company config."""
    supplier = _sub(parent, cac("AccountingSupplierParty"))
    _sub(supplier, cbc("AdditionalAccountID"), "1")

    party = _sub(supplier, cac("Party"))

    party_name = _sub(party, cac("PartyName"))
    _sub(party_name, cbc("Name"), settings.company.name)

    location = _sub(party, cac("PhysicalLocation"))
    address = _sub(location, cac("Address"))
    _sub(address, cbc("ID"), settings.company.city_code)
    _sub(address, cbc("CityName"), settings.company.city_name)
    _sub(address, cbc("PostalZone"), settings.company.city_code)
    _sub(address, cbc("CountrySubentity"), settings.company.department_name)
    _sub(address, cbc("CountrySubentityCode"), settings.company.department_code)
    addr_line = _sub(address, cac("AddressLine"))
    _sub(addr_line, cbc("Line"), settings.company.address)
    country = _sub(address, cac("Country"))
    _sub(country, cbc("IdentificationCode"), settings.company.country_code)
    _sub(country, cbc("Name"), "Colombia", languageID="es")

    tax_scheme_elem = _sub(party, cac("PartyTaxScheme"))
    _sub(tax_scheme_elem, cbc("RegistrationName"), settings.company.name)
    _sub(
        tax_scheme_elem,
        cbc("CompanyID"),
        resolved_issuer_nit(req),
        **_company_id_attrs("31", resolved_issuer_dv(req)),
    )
    _sub(
        tax_scheme_elem,
        cbc("TaxLevelCode"),
        _normalize_tax_level_code(settings.company.tax_scheme, default="O-47"),
        listName="05",
    )

    tax_address = _sub(tax_scheme_elem, cac("RegistrationAddress"))
    _sub(tax_address, cbc("ID"), settings.company.city_code)
    _sub(tax_address, cbc("CityName"), settings.company.city_name)
    _sub(tax_address, cbc("PostalZone"), settings.company.city_code)
    _sub(tax_address, cbc("CountrySubentity"), settings.company.department_name)
    _sub(tax_address, cbc("CountrySubentityCode"), settings.company.department_code)
    ta_line = _sub(tax_address, cac("AddressLine"))
    _sub(ta_line, cbc("Line"), settings.company.address)
    ta_country = _sub(tax_address, cac("Country"))
    _sub(ta_country, cbc("IdentificationCode"), settings.company.country_code)
    _sub(ta_country, cbc("Name"), "Colombia", languageID="es")
    scheme = _sub(tax_scheme_elem, cac("TaxScheme"))
    _sub(scheme, cbc("ID"), "01")
    _sub(scheme, cbc("Name"), "IVA")

    legal = _sub(party, cac("PartyLegalEntity"))
    _sub(legal, cbc("RegistrationName"), settings.company.name)
    _sub(
        legal,
        cbc("CompanyID"),
        resolved_issuer_nit(req),
        **_company_id_attrs("31", resolved_issuer_dv(req)),
    )
    corp_reg = _sub(legal, cac("CorporateRegistrationScheme"))
    _sub(corp_reg, cbc("ID"), prefix)
    _sub(corp_reg, cbc("Name"), resolved_issuer_nit(req))

    contact = _sub(party, cac("Contact"))
    _sub(contact, cbc("Telephone"), settings.company.phone)
    _sub(contact, cbc("ElectronicMail"), settings.company.email)


def build_customer_party(parent: etree._Element, req: DocumentSubmitRequest) -> None:
    """Build cac:AccountingCustomerParty from request data."""
    customer = _sub(parent, cac("AccountingCustomerParty"))
    customer_document_type = _normalize_customer_document_type(req)
    is_final_consumer = customer_document_type == "FINAL_CONSUMER" or not req.customer_nit
    buyer_identifier = req.customer_nit or FINAL_CONSUMER_ID
    buyer_identifier_type = CUSTOMER_DOCUMENT_SCHEME_NAMES[customer_document_type]
    buyer_verification_digit = _compute_nit_dv(req.customer_nit) if customer_document_type == "NIT" else None

    _sub(customer, cbc("AdditionalAccountID"), CUSTOMER_ADDITIONAL_ACCOUNT_IDS[customer_document_type])

    party = _sub(customer, cac("Party"))
    party_identification = _sub(party, cac("PartyIdentification"))
    _sub(
        party_identification,
        cbc("ID"),
        buyer_identifier,
        schemeName=buyer_identifier_type,
    )

    party_name = _sub(party, cac("PartyName"))
    _sub(party_name, cbc("Name"), req.customer_name)

    if is_final_consumer:
        tax_scheme_elem = _sub(party, cac("PartyTaxScheme"))
        _sub(tax_scheme_elem, cbc("RegistrationName"), req.customer_name)
        _sub(
            tax_scheme_elem,
            cbc("CompanyID"),
            buyer_identifier,
            schemeAgencyID=DIAN_SCHEME_AGENCY_ID,
            schemeAgencyName=DIAN_SCHEME_AGENCY_NAME,
            schemeName=buyer_identifier_type,
        )
        _sub(tax_scheme_elem, cbc("TaxLevelCode"), FINAL_CONSUMER_TAX_LEVEL_CODE)
        scheme = _sub(tax_scheme_elem, cac("TaxScheme"))
        _sub(scheme, cbc("ID"), "ZZ")
        _sub(scheme, cbc("Name"), "No aplica")
        return

    location = _sub(party, cac("PhysicalLocation"))
    address = _sub(location, cac("Address"))
    _build_customer_address(address, req)

    tax_scheme_elem = _sub(party, cac("PartyTaxScheme"))
    _sub(tax_scheme_elem, cbc("RegistrationName"), req.customer_name)
    _sub(
        tax_scheme_elem,
        cbc("CompanyID"),
        buyer_identifier,
        **_company_id_attrs(buyer_identifier_type, buyer_verification_digit),
    )
    _sub(
        tax_scheme_elem,
        cbc("TaxLevelCode"),
        FINAL_CONSUMER_TAX_LEVEL_CODE,
        listName="05",
    )

    tax_address = _sub(tax_scheme_elem, cac("RegistrationAddress"))
    _build_customer_address(tax_address, req)
    scheme = _sub(tax_scheme_elem, cac("TaxScheme"))
    _sub(scheme, cbc("ID"), "ZZ")
    _sub(scheme, cbc("Name"), "No aplica")

    legal = _sub(party, cac("PartyLegalEntity"))
    _sub(legal, cbc("RegistrationName"), req.customer_name)
    _sub(
        legal,
        cbc("CompanyID"),
        buyer_identifier,
        **_company_id_attrs(buyer_identifier_type, buyer_verification_digit),
    )

    if req.customer_phone or req.customer_email:
        contact = _sub(party, cac("Contact"))
        if req.customer_phone:
            _sub(contact, cbc("Telephone"), req.customer_phone)
        if req.customer_email:
            _sub(contact, cbc("ElectronicMail"), req.customer_email)


def build_payment_means(parent: etree._Element, payment_method: str, due_date: str) -> None:
    """Build cac:PaymentMeans element."""
    pm = _sub(parent, cac("PaymentMeans"))
    code = PAYMENT_MEANS.get(payment_method, "10")
    _sub(pm, cbc("ID"), "1")
    _sub(pm, cbc("PaymentMeansCode"), code)
    _sub(pm, cbc("PaymentDueDate"), due_date)


def build_tax_totals(parent: etree._Element, lines: list[DocumentLine]) -> None:
    """Build document-level cac:TaxTotal blocks.

    DIAN requires one ``cac:TaxTotal`` per tax scheme (FAS01) and one
    ``cac:TaxSubtotal`` per tariff within that scheme (FAS04). Excluded items
    must not emit taxes at either header or line level, so ``EXCLUDED`` lines
    are skipped entirely here.
    """
    tax_totals: dict[str, dict[str, object]] = {}

    for line in lines:
        dian_tax = TAX_TYPE_TO_DIAN.get(line.tax_type, TAX_TYPE_TO_DIAN["EXCLUDED"])
        if str(dian_tax["code"]) == "ZZ":
            continue

        code = str(dian_tax["code"])
        percent = str(dian_tax["percent"])
        tax_total = tax_totals.setdefault(
            code,
            {
                "code": code,
                "name": str(dian_tax["name"]),
                "tax_amount": 0,
                "subtotals": {},
            },
        )
        subtotals = tax_total["subtotals"]
        assert isinstance(subtotals, dict)
        subtotal = subtotals.setdefault(
            percent,
            {
                "percent": percent,
                "taxable_amount": 0,
                "tax_amount": 0,
            },
        )
        subtotal["taxable_amount"] += line.line_total  # type: ignore[operator]
        subtotal["tax_amount"] += line.tax_amount  # type: ignore[operator]
        tax_total["tax_amount"] += line.tax_amount  # type: ignore[operator]

    for group in tax_totals.values():
        tax_total = _sub(parent, cac("TaxTotal"))
        _sub(
            tax_total,
            cbc("TaxAmount"),
            _money(int(group["tax_amount"])),
            currencyID=CURRENCY_COP,
        )

        subtotals = group["subtotals"]
        assert isinstance(subtotals, dict)
        for subtotal_group in subtotals.values():
            subtotal = _sub(tax_total, cac("TaxSubtotal"))
            _sub(
                subtotal,
                cbc("TaxableAmount"),
                _money(int(subtotal_group["taxable_amount"])),
                currencyID=CURRENCY_COP,
            )
            _sub(
                subtotal,
                cbc("TaxAmount"),
                _money(int(subtotal_group["tax_amount"])),
                currencyID=CURRENCY_COP,
            )
            tax_cat = _sub(subtotal, cac("TaxCategory"))
            _sub(tax_cat, cbc("Percent"), str(subtotal_group["percent"]))
            scheme = _sub(tax_cat, cac("TaxScheme"))
            _sub(scheme, cbc("ID"), str(group["code"]))
            _sub(scheme, cbc("Name"), str(group["name"]))


def _line_extension_amount(lines: list[DocumentLine]) -> int:
    """Return the commercial value before taxes for all lines."""
    return sum(line.line_total for line in lines)


def _tax_exclusive_amount(lines: list[DocumentLine]) -> int:
    """Return the taxable base reported at line level.

    DIAN FAU04 / CAU04 / DAU04 validates this against the sum of
    ``InvoiceLine|CreditNoteLine|DebitNoteLine/TaxTotal/TaxSubtotal/TaxableAmount``.
    Excluded items do not emit ``TaxTotal``, so they must not contribute here.
    """
    total = 0
    for line in lines:
        dian_tax = TAX_TYPE_TO_DIAN.get(line.tax_type, TAX_TYPE_TO_DIAN["EXCLUDED"])
        if str(dian_tax["code"]) == "ZZ":
            continue
        total += line.line_total
    return total


def build_legal_monetary_total(
    parent: etree._Element,
    lines: list[DocumentLine],
    total: int,
) -> None:
    """Build cac:LegalMonetaryTotal element."""
    line_extension_amount = _line_extension_amount(lines)
    tax_exclusive_amount = _tax_exclusive_amount(lines)
    lmt = _sub(parent, cac("LegalMonetaryTotal"))
    _sub(
        lmt,
        cbc("LineExtensionAmount"),
        _money(line_extension_amount),
        currencyID=CURRENCY_COP,
    )
    _sub(
        lmt,
        cbc("TaxExclusiveAmount"),
        _money(tax_exclusive_amount),
        currencyID=CURRENCY_COP,
    )
    _sub(lmt, cbc("TaxInclusiveAmount"), _money(total), currencyID=CURRENCY_COP)
    _sub(lmt, cbc("AllowanceTotalAmount"), "0.00", currencyID=CURRENCY_COP)
    _sub(lmt, cbc("ChargeTotalAmount"), "0.00", currencyID=CURRENCY_COP)
    _sub(lmt, cbc("PayableAmount"), _money(total), currencyID=CURRENCY_COP)


def build_requested_monetary_total(
    parent: etree._Element,
    lines: list[DocumentLine],
    total: int,
) -> None:
    """Build cac:RequestedMonetaryTotal for DebitNote documents."""
    line_extension_amount = _line_extension_amount(lines)
    tax_exclusive_amount = _tax_exclusive_amount(lines)
    rmt = _sub(parent, cac("RequestedMonetaryTotal"))
    _sub(
        rmt,
        cbc("LineExtensionAmount"),
        _money(line_extension_amount),
        currencyID=CURRENCY_COP,
    )
    _sub(
        rmt,
        cbc("TaxExclusiveAmount"),
        _money(tax_exclusive_amount),
        currencyID=CURRENCY_COP,
    )
    _sub(rmt, cbc("TaxInclusiveAmount"), _money(total), currencyID=CURRENCY_COP)
    _sub(rmt, cbc("AllowanceTotalAmount"), "0.00", currencyID=CURRENCY_COP)
    _sub(rmt, cbc("ChargeTotalAmount"), "0.00", currencyID=CURRENCY_COP)
    _sub(rmt, cbc("PayableAmount"), _money(total), currencyID=CURRENCY_COP)


def build_invoice_line(
    parent: etree._Element,
    line_number: int,
    line: DocumentLine,
    tag_name: str = "InvoiceLine",
) -> None:
    """Build a single InvoiceLine, CreditNoteLine, or DebitNoteLine element."""
    if tag_name == "CreditNoteLine":
        inv_line = _sub(parent, cac("CreditNoteLine"))
    elif tag_name == "DebitNoteLine":
        inv_line = _sub(parent, cac("DebitNoteLine"))
    else:
        inv_line = _sub(parent, cac("InvoiceLine"))

    _sub(inv_line, cbc("ID"), str(line_number))

    if tag_name == "CreditNoteLine":
        qty_tag = "CreditedQuantity"
    elif tag_name == "DebitNoteLine":
        qty_tag = "DebitedQuantity"
    else:
        qty_tag = "InvoicedQuantity"
    unit_code = line.unit_code or "94"
    _sub(inv_line, cbc(qty_tag), str(line.quantity), unitCode=unit_code)

    _sub(inv_line, cbc("LineExtensionAmount"), _money(line.line_total), currencyID=CURRENCY_COP)

    dian_tax = TAX_TYPE_TO_DIAN.get(line.tax_type, TAX_TYPE_TO_DIAN["EXCLUDED"])
    if str(dian_tax["code"]) != "ZZ":
        line_tax = _sub(inv_line, cac("TaxTotal"))
        _sub(line_tax, cbc("TaxAmount"), _money(line.tax_amount), currencyID=CURRENCY_COP)
        line_subtotal = _sub(line_tax, cac("TaxSubtotal"))
        _sub(line_subtotal, cbc("TaxableAmount"), _money(line.line_total), currencyID=CURRENCY_COP)
        _sub(line_subtotal, cbc("TaxAmount"), _money(line.tax_amount), currencyID=CURRENCY_COP)
        tax_cat = _sub(line_subtotal, cac("TaxCategory"))
        _sub(tax_cat, cbc("Percent"), str(dian_tax["percent"]))
        scheme = _sub(tax_cat, cac("TaxScheme"))
        _sub(scheme, cbc("ID"), str(dian_tax["code"]))
        _sub(scheme, cbc("Name"), str(dian_tax["name"]))

    item = _sub(inv_line, cac("Item"))
    _sub(item, cbc("Description"), line.description)
    _sub(item, cbc("Name"), line.item_name or line.description)
    if line.item_code:
        sellers_item = _sub(item, cac("SellersItemIdentification"))
        _sub(sellers_item, cbc("ID"), line.item_code)
        standard_item = _sub(item, cac("StandardItemIdentification"))
        _sub(
            standard_item,
            cbc("ID"),
            line.item_code,
            schemeID="999",
            schemeName="EstÃ¡ndar de adopciÃ³n del contribuyente",
        )

    price = _sub(inv_line, cac("Price"))
    _sub(price, cbc("PriceAmount"), _money(line.unit_price), currencyID=CURRENCY_COP)
    _sub(price, cbc("BaseQuantity"), "1.00", unitCode=unit_code)

