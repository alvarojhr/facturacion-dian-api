"""DIAN technical filenames, independent from fiscal document numbering."""

from __future__ import annotations

import hashlib
import re
from datetime import date

from facturacion_dian_api.core.models import DocumentType

FAMILY_PREFIX: dict[DocumentType, str] = {
    "FACTURA_ELECTRONICA": "fv",
    "FACTURA_CONTINGENCIA_FACTURADOR": "fv",
    "FACTURA_CONTINGENCIA_DIAN": "fv",
    "DOCUMENTO_EQUIVALENTE_POS": "ds",
    "DOCUMENTO_EQUIVALENTE_POS_CONTINGENCIA_EMISOR": "ds",
    "DOCUMENTO_EQUIVALENTE_POS_CONTINGENCIA_DIAN": "ds",
    "NOTA_CREDITO": "nc",
    "NOTA_DEBITO": "nd",
    # El anexo DEE usa una sola familia para ambas modalidades de la nota de
    # ajuste. El tipo fiscal 93/94 vive en CreditNoteTypeCode.
    "NOTA_AJUSTE_DEE_CREDITO": "ncs",
    "NOTA_AJUSTE_DEE_DEBITO": "ncs",
}


def _nit10(issuer_nit: str) -> str:
    digits = re.sub(r"\D", "", issuer_nit)
    if not digits or len(digits) > 10:
        raise ValueError("issuer NIT must contain between 1 and 10 digits for DIAN filenames")
    return digits.zfill(10)


def _sequence(
    explicit_sequence: int | None,
    *,
    family: str,
    issuer_nit: str,
    document_number: str,
    issue_year: int,
) -> int:
    if explicit_sequence is not None:
        if not 1 <= explicit_sequence <= 0xFFFFFFFF:
            raise ValueError("file_sequence must be between 1 and FFFFFFFF")
        return explicit_sequence
    # Compatibility fallback. It is stable across a retry and varies with the
    # fiscal identity. Integrators that need a strictly consecutive series send
    # file_sequence from their durable reservation.
    seed = f"{family}|{issuer_nit}|{document_number}|{issue_year}".encode()
    value = int.from_bytes(hashlib.sha256(seed).digest()[:4], "big")
    return value or 1


def build_dian_filename(
    *,
    family: str,
    issuer_nit: str,
    provider_code: str,
    document_number: str,
    issue_date: str,
    sequence: int | None,
    extension: str = "xml",
) -> str:
    """Build ``family + NIT10 + provider3 + year2 + hex8`` filename."""
    if not re.fullmatch(r"[a-z]{1,3}", family):
        raise ValueError("file family must contain one to three lowercase letters")
    if not re.fullmatch(r"\d{3}", provider_code):
        raise ValueError("provider_code must contain exactly three digits")
    year = date.fromisoformat(issue_date).year
    counter = _sequence(
        sequence,
        family=family,
        issuer_nit=issuer_nit,
        document_number=document_number,
        issue_year=year,
    )
    return f"{family}{_nit10(issuer_nit)}{provider_code}{year % 100:02d}{counter:08x}.{extension}"


def build_document_filename(
    document_type: DocumentType,
    *,
    issuer_nit: str,
    provider_code: str,
    document_number: str,
    issue_date: str,
    sequence: int | None,
) -> str:
    return build_dian_filename(
        family=FAMILY_PREFIX[document_type],
        issuer_nit=issuer_nit,
        provider_code=provider_code,
        document_number=document_number,
        issue_date=issue_date,
        sequence=sequence,
    )
