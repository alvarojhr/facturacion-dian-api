"""Domain exceptions raised by facturacion-dian-kit."""

from __future__ import annotations


class FacturacionDianKitError(Exception):
    """Base exception for recoverable kit errors."""


class ConfigurationError(FacturacionDianKitError):
    """Required local configuration is missing or invalid."""


class CertificateConfigurationError(ConfigurationError):
    """Certificate loading or validation failed."""


class DianTransportError(FacturacionDianKitError):
    """A network or HTTP transport error happened while calling DIAN."""


class DianTimeoutError(DianTransportError):
    """DIAN did not answer within the configured timeout."""


class DianUpstreamError(DianTransportError):
    """DIAN returned a non-success HTTP response."""

    def __init__(self, status_code: int, body_excerpt: str) -> None:
        self.status_code = status_code
        self.body_excerpt = body_excerpt
        super().__init__(f"DIAN upstream returned HTTP {status_code}: {body_excerpt}")
