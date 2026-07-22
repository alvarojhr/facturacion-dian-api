"""Helpers to resolve request-specific DIAN config with env fallback."""

from __future__ import annotations

from typing import Literal

from facturacion_dian_api.core.config import settings
from facturacion_dian_api.core.models import DocumentSubmitRequest


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


def uses_body_owned_issuer(req: DocumentSubmitRequest) -> bool:
    """Use the complete request identity only when ``issuer.name`` is present."""
    return bool((req.issuer_name or "").strip())


def _resolved_issuer_text(
    req: DocumentSubmitRequest,
    explicit: str | None,
    fallback: str,
) -> str:
    if not uses_body_owned_issuer(req):
        return fallback
    return (explicit or "").strip() or fallback


def resolved_issuer_name(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(req, req.issuer_name, settings.company.name)


def resolved_issuer_additional_account_id(
    req: DocumentSubmitRequest,
) -> Literal["1", "2"]:
    if uses_body_owned_issuer(req) and req.issuer_additional_account_id is not None:
        return req.issuer_additional_account_id
    return settings.company.additional_account_id


def resolved_issuer_address(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(req, req.issuer_address, settings.company.address)


def resolved_issuer_city_code(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(req, req.issuer_city_code, settings.company.city_code)


def resolved_issuer_city_name(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(req, req.issuer_city_name, settings.company.city_name)


def resolved_issuer_department_code(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(
        req,
        req.issuer_department_code,
        settings.company.department_code,
    )


def resolved_issuer_department_name(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(
        req,
        req.issuer_department_name,
        settings.company.department_name,
    )


def resolved_issuer_country_code(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(
        req,
        req.issuer_country_code,
        settings.company.country_code,
    ).upper()


def resolved_issuer_tax_level_code(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(
        req,
        req.issuer_tax_level_code,
        settings.company.tax_scheme,
    )


def resolved_issuer_economic_activity(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(
        req,
        req.issuer_economic_activity,
        settings.company.economic_activity,
    )


def resolved_issuer_phone(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(req, req.issuer_phone, settings.company.phone)


def resolved_issuer_email(req: DocumentSubmitRequest) -> str:
    return _resolved_issuer_text(req, req.issuer_email, settings.company.email)


def resolved_software_owner_nit(req: DocumentSubmitRequest) -> str:
    return _digits(req.software_owner_nit) or resolved_issuer_nit(req)


def resolved_software_owner_dv(req: DocumentSubmitRequest) -> str:
    return compute_nit_dv(resolved_software_owner_nit(req))


def resolved_technical_key(req: DocumentSubmitRequest) -> str:
    return (req.technical_key or settings.dian.technical_key).strip()
