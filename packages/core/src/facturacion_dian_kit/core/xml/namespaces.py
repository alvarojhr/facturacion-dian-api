"""UBL 2.1 and DIAN XML namespace constants."""

from __future__ import annotations

NS_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_CREDIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
NS_DEBIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2"
NS_ATTACHED_DOCUMENT = "urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"

NS_STS = "dian:gov:co:facturaelectronica:Structures-2-1"

NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_XADES = "http://uri.etsi.org/01903/v1.3.2#"
NS_XADES141 = "http://uri.etsi.org/01903/v1.4.1#"

NSMAP_INVOICE: dict[str | None, str] = {
    None: NS_INVOICE,
    "cac": NS_CAC,
    "cbc": NS_CBC,
    "ext": NS_EXT,
    "sts": NS_STS,
    "ds": NS_DS,
    "xades": NS_XADES,
    "xades141": NS_XADES141,
}

NSMAP_CREDIT_NOTE: dict[str | None, str] = {
    None: NS_CREDIT_NOTE,
    "cac": NS_CAC,
    "cbc": NS_CBC,
    "ext": NS_EXT,
    "sts": NS_STS,
    "ds": NS_DS,
    "xades": NS_XADES,
    "xades141": NS_XADES141,
}

NSMAP_DEBIT_NOTE: dict[str | None, str] = {
    None: NS_DEBIT_NOTE,
    "cac": NS_CAC,
    "cbc": NS_CBC,
    "ext": NS_EXT,
    "sts": NS_STS,
    "ds": NS_DS,
    "xades": NS_XADES,
    "xades141": NS_XADES141,
}

NSMAP_ATTACHED_DOCUMENT: dict[str | None, str] = {
    None: NS_ATTACHED_DOCUMENT,
    "cac": NS_CAC,
    "cbc": NS_CBC,
}


def _qn(ns: str, tag: str) -> str:
    """Build a Clark notation qualified name: {namespace}tag."""
    return f"{{{ns}}}{tag}"


def cbc(tag: str) -> str:
    """Qualified name in CommonBasicComponents namespace."""
    return _qn(NS_CBC, tag)


def cac(tag: str) -> str:
    """Qualified name in CommonAggregateComponents namespace."""
    return _qn(NS_CAC, tag)


def ext(tag: str) -> str:
    """Qualified name in CommonExtensionComponents namespace."""
    return _qn(NS_EXT, tag)


def sts(tag: str) -> str:
    """Qualified name in DIAN Structures namespace."""
    return _qn(NS_STS, tag)


def attached(tag: str) -> str:
    """Qualified name in AttachedDocument namespace."""
    return _qn(NS_ATTACHED_DOCUMENT, tag)


INVOICE_TYPE_FACTURA = "01"
INVOICE_TYPE_FACTURA_EXPORTACION = "02"
INVOICE_TYPE_DOC_CONTINGENCIA = "03"
INVOICE_TYPE_DOC_EQUIVALENTE_POS = "20"

CREDIT_NOTE_TYPE = "91"

CUSTOMIZATION_CREDIT_NOTE = "20"          # NC asociada (referencia FE conocida)
CUSTOMIZATION_CREDIT_NOTE_NO_ASOCIADA = "22"  # NC no asociada (Res. 42/2020 Art. 30 §1)
CUSTOMIZATION_DEBIT_NOTE = "30"
CUSTOMIZATION_DEBIT_NOTE_PERIOD = "32"
CUSTOMIZATION_FACTURA = "10"
CUSTOMIZATION_DOC_EQUIVALENTE = "10"

PAYMENT_MEANS = {
    "CASH": "10",
    "CARD": "48",
    "TRANSFER": "31",
    "CHECK": "20",
    "CREDIT": "30",
}

DIAN_TAX_SCHEME_IVA = "01"
DIAN_TAX_SCHEME_IC = "04"
DIAN_TAX_SCHEME_ICA = "03"

TAX_TYPE_TO_DIAN = {
    "IVA_19": {"code": "01", "name": "IVA", "percent": "19.00"},
    "IVA_5": {"code": "01", "name": "IVA", "percent": "5.00"},
    "EXEMPT": {"code": "01", "name": "IVA", "percent": "0.00"},
    "EXCLUDED": {"code": "ZZ", "name": "No aplica", "percent": "0.00"},
}

DIAN_SCHEME_AGENCY_ID = "195"
DIAN_SCHEME_AGENCY_NAME = "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)"

CURRENCY_COP = "COP"
COUNTRY_CODE_CO = "CO"
