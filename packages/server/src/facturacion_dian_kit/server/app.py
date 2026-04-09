"""FastAPI application entry point for facturacion-dian-kit."""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version

from facturacion_dian_kit.core.config import settings
from facturacion_dian_kit.core.errors import (
    CertificateConfigurationError,
    ConfigurationError,
    DianTimeoutError,
    DianTransportError,
    DianUpstreamError,
)
from facturacion_dian_kit.server.api.customers import router as customers_router
from facturacion_dian_kit.server.api.documents import router as documents_router
from facturacion_dian_kit.server.api.health import router as health_router
from facturacion_dian_kit.server.api.numbering_ranges import router as numbering_ranges_router
from facturacion_dian_kit.server.settings import server_settings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=getattr(logging, settings.runtime.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)


def _package_version() -> str:
    try:
        return version("facturacion-dian-kit-server")
    except PackageNotFoundError:
        return "0.1.0a0"


app = FastAPI(
    title="facturacion-dian-kit API",
    description=(
        "API HTTP de alto nivel para integrar facturacion electronica DIAN desde ERP, POS "
        "y backends sin depender del lenguaje de programacion. Expone envio de documentos, "
        "consulta de estado, AttachedDocument y lookups DIAN operativos."
    ),
    version=_package_version(),
)

if server_settings.allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=server_settings.allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health_router)
app.include_router(customers_router)
app.include_router(documents_router)
app.include_router(numbering_ranges_router)


@app.exception_handler(ConfigurationError)
async def handle_configuration_error(
    request: Request,
    exc: ConfigurationError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(CertificateConfigurationError)
async def handle_certificate_error(
    request: Request,
    exc: CertificateConfigurationError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(DianTimeoutError)
async def handle_dian_timeout(
    request: Request,
    exc: DianTimeoutError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=504, content={"detail": str(exc)})


@app.exception_handler(DianUpstreamError)
async def handle_dian_upstream_error(
    request: Request,
    exc: DianUpstreamError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(DianTransportError)
async def handle_dian_transport_error(
    request: Request,
    exc: DianTransportError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/")
async def root() -> dict[str, str]:
    """Return the service identity."""

    return {
        "service": "facturacion-dian-kit API",
        "version": _package_version(),
        "environment": settings.dian.environment,
    }
