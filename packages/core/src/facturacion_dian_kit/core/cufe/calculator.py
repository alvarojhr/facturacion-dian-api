"""CUFE, CUDE, and Software Security Code calculation.

Implements SHA-384 hashing per DIAN Anexo Técnico v1.9:
- Section 11.1.2: CUFE generation (Factura Electrónica)
- Section 11.1.4: CUDE generation (Doc. Equivalente POS, Nota Crédito)
- Software Security Code

Reference: https://www.dian.gov.co/impuestos/factura-electronica/Documents/
           Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9.pdf
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def _fmt_money(value_cop: int) -> str:
    """Format COP integer as string with 2 decimal places.

    DIAN requires monetary values with dot decimal separator, 2 digits,
    no thousands separator.

    Examples:
        1785000 → "1785000.00"
        0       → "0.00"
    """
    d = Decimal(value_cop).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(d)


# ─── DIAN Tax Codes ──────────────────────────────────────────
# Maps our internal tax_type codes to DIAN tax scheme codes

DIAN_TAX_CODE_IVA = "01"   # IVA (Impuesto al Valor Agregado)
DIAN_TAX_CODE_IC = "04"    # INC (Impuesto Nacional al Consumo)
DIAN_TAX_CODE_ICA = "03"   # ICA (Impuesto de Industria y Comercio)


@dataclass(frozen=True)
class CufeFields:
    """Fields required for CUFE calculation (Factura Electrónica).

    Per DIAN Anexo Técnico v1.9, Section 11.1.2:
    CUFE = SHA-384(NumFac + FecFac + HorFac + ValFac
                   + CodImp1 + ValImp1 + CodImp2 + ValImp2 + CodImp3 + ValImp3
                   + ValTotFac + NitOFE + NumAdq + ClTec + TipoAmbiente)
    """

    num_fac: str        # Invoice number (e.g., "SETT000001")
    fec_fac: str        # Issue date "YYYY-MM-DD"
    hor_fac: str        # Issue time "HH:MM:SS-05:00"
    val_fac: int        # Subtotal (COP, tax-exclusive)
    val_iva: int        # IVA total (COP)
    val_inc: int        # INC total (COP) — typically 0 for hardware store
    val_ica: int        # ICA total (COP) — typically 0
    val_tot_fac: int    # Grand total payable (COP)
    nit_ofe: str        # Issuer NIT (no dots, dashes, or DV)
    num_adq: str        # Buyer identification (no dots, dashes, or DV)
    clave_tecnica: str  # Technical key from DIAN resolution
    tipo_ambiente: str  # "1" = production, "2" = test


@dataclass(frozen=True)
class CudeFields:
    """Fields required for CUDE calculation (Doc. Equivalente POS, Nota Crédito).

    Per DIAN Anexo Técnico v1.9, Section 11.1.4:
    CUDE = SHA-384(NumFac + FecFac + HorFac + ValFac
                   + CodImp1 + ValImp1 + CodImp2 + ValImp2 + CodImp3 + ValImp3
                   + ValTotFac + NitOFE + NumAdq + SoftwarePIN + TipoAmbiente)

    Same as CUFE but uses SoftwarePIN instead of ClTec (Technical Key).
    """

    num_fac: str
    fec_fac: str
    hor_fac: str
    val_fac: int
    val_iva: int
    val_inc: int
    val_ica: int
    val_tot_fac: int
    nit_ofe: str
    num_adq: str
    software_pin: str  # Software PIN instead of Technical Key
    tipo_ambiente: str


def calculate_cufe(fields: CufeFields) -> str:
    """Calculate CUFE (Código Único de Factura Electrónica).

    Used for: FACTURA_ELECTRONICA documents.

    Returns:
        96-character lowercase hex string (SHA-384 digest).
    """
    seed = (
        fields.num_fac
        + fields.fec_fac
        + fields.hor_fac
        + _fmt_money(fields.val_fac)
        + DIAN_TAX_CODE_IVA + _fmt_money(fields.val_iva)
        + DIAN_TAX_CODE_IC + _fmt_money(fields.val_inc)
        + DIAN_TAX_CODE_ICA + _fmt_money(fields.val_ica)
        + _fmt_money(fields.val_tot_fac)
        + fields.nit_ofe
        + fields.num_adq
        + fields.clave_tecnica
        + fields.tipo_ambiente
    )
    return hashlib.sha384(seed.encode("utf-8")).hexdigest()


def calculate_cude(fields: CudeFields) -> str:
    """Calculate CUDE (Código Único de Documento Electrónico).

    Used for: DOCUMENTO_EQUIVALENTE_POS and NOTA_CREDITO documents.

    Returns:
        96-character lowercase hex string (SHA-384 digest).
    """
    seed = (
        fields.num_fac
        + fields.fec_fac
        + fields.hor_fac
        + _fmt_money(fields.val_fac)
        + DIAN_TAX_CODE_IVA + _fmt_money(fields.val_iva)
        + DIAN_TAX_CODE_IC + _fmt_money(fields.val_inc)
        + DIAN_TAX_CODE_ICA + _fmt_money(fields.val_ica)
        + _fmt_money(fields.val_tot_fac)
        + fields.nit_ofe
        + fields.num_adq
        + fields.software_pin
        + fields.tipo_ambiente
    )
    return hashlib.sha384(seed.encode("utf-8")).hexdigest()


def calculate_software_security_code(
    software_id: str,
    software_pin: str,
    invoice_number: str,
) -> str:
    """Calculate the Software Security Code for DIAN.

    Formula: SHA-384(SoftwareID + PIN + InvoiceNumber)

    This code authenticates the software with DIAN and must be
    included in the UBL XML.

    Returns:
        96-character lowercase hex string (SHA-384 digest).
    """
    seed = software_id + software_pin + invoice_number
    return hashlib.sha384(seed.encode("utf-8")).hexdigest()


def build_qr_url(document_key: str) -> str:
    """Build the DIAN catalog QR verification URL.

    Args:
        document_key: The CUFE or CUDE of the document.

    Returns:
        Full URL for DIAN catalog QR code verification.
    """
    return f"https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={document_key}"
