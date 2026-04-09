"""Helpers to resolve request-specific DIAN config with env fallback."""

from __future__ import annotations

from typing import Literal

from facturacion_dian_kit.core.config import settings
from facturacion_dian_kit.core.models import DocumentSubmitRequest


def _digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def compute_nit_dv(identifier: str | None) -> str:
    digits = _digits(identifier)
    if not digits:
        return ""

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


def resolved_environment(req: DocumentSubmitRequest | None = None) -> Literal["habilitacion", "produccion"]:
    if req and req.environment in ("habilitacion", "produccion"):
        return req.environment
    return settings.dian.environment


def resolved_tipo_ambiente(req: DocumentSubmitRequest | None = None) -> str:
    return "1" if resolved_environment(req) == "produccion" else "2"


def resolved_software_id(req: DocumentSubmitRequest) -> str:
    return (req.software_id or settings.dian.software_id).strip()


def resolved_software_pin(req: DocumentSubmitRequest) -> str:
    return (req.software_pin or settings.dian.software_pin).strip()


def resolved_test_set_id(req: DocumentSubmitRequest) -> str:
    return (req.test_set_id or settings.dian.test_set_id).strip()


def resolved_issuer_nit(req: DocumentSubmitRequest) -> str:
    return _digits(req.issuer_nit) or settings.company.nit


def resolved_issuer_dv(req: DocumentSubmitRequest) -> str:
    explicit = (req.issuer_dv or "").strip()
    return explicit or settings.company.dv or compute_nit_dv(resolved_issuer_nit(req))


def resolved_software_owner_nit(req: DocumentSubmitRequest) -> str:
    return _digits(req.software_owner_nit) or resolved_issuer_nit(req)


def resolved_software_owner_dv(req: DocumentSubmitRequest) -> str:
    return compute_nit_dv(resolved_software_owner_nit(req))


def resolved_technical_key(req: DocumentSubmitRequest) -> str:
    return (req.technical_key or settings.dian.technical_key).strip()

