"""Health endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version

from facturacion_dian_api.core.config import settings
from facturacion_dian_api.core.models import HealthStatus
from facturacion_dian_api.core.signing.certificate import get_certificate_bundle
from facturacion_dian_api.server.contracts import HealthResponse
from facturacion_dian_api.server.examples import HEALTH_RESPONSE_EXAMPLE
from fastapi import APIRouter

router = APIRouter(tags=["Operacion"])


def _package_version() -> str:
    try:
        return version("facturacion-dian-api-server")
    except PackageNotFoundError:
        return "0.2.0a5"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado operativo del servicio",
    responses={
        200: {
            "description": "Snapshot del runtime y del certificado cargado.",
            "content": {"application/json": {"example": HEALTH_RESPONSE_EXAMPLE}},
        }
    },
)
async def health_check() -> HealthResponse:
    """Return the runtime health snapshot for the server."""

    try:
        bundle = get_certificate_bundle()
        remaining = bundle.not_valid_after - datetime.now(UTC)
        days_remaining = max(0, int(remaining.total_seconds() // 86400))
        expiring_soon = days_remaining <= settings.dian.cert_expiry_warning_days
        status = HealthStatus(
            status="ok" if bundle.is_valid and not expiring_soon else "degraded",
            version=_package_version(),
            dian_environment=settings.dian.environment,
            certificate_loaded=True,
            certificate_valid_until=bundle.not_valid_after.isoformat(),
            certificate_days_remaining=days_remaining,
            certificate_expiring_soon=expiring_soon,
        )
    except Exception:
        status = HealthStatus(
            status="degraded",
            version=_package_version(),
            dian_environment=settings.dian.environment,
            certificate_loaded=False,
            certificate_valid_until=None,
            certificate_days_remaining=None,
            certificate_expiring_soon=False,
        )
    return HealthResponse.model_validate(status.model_dump())
