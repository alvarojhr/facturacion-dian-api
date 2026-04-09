"""Health endpoint."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from facturacion_dian_kit.core.config import settings
from facturacion_dian_kit.core.models import HealthStatus
from facturacion_dian_kit.core.signing.certificate import get_certificate_bundle
from facturacion_dian_kit.server.contracts import HealthResponse
from fastapi import APIRouter

router = APIRouter()


def _package_version() -> str:
    try:
        return version("facturacion-dian-kit-server")
    except PackageNotFoundError:
        return "0.1.0a0"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return the runtime health snapshot for the server."""

    try:
        bundle = get_certificate_bundle()
        status = HealthStatus(
            status="ok" if bundle.is_valid else "degraded",
            version=_package_version(),
            dian_environment=settings.dian.environment,
            certificate_loaded=True,
            certificate_valid_until=bundle.not_valid_after.isoformat(),
        )
    except Exception:
        status = HealthStatus(
            status="degraded",
            version=_package_version(),
            dian_environment=settings.dian.environment,
            certificate_loaded=False,
            certificate_valid_until=None,
        )
    return HealthResponse.model_validate(status.model_dump())
