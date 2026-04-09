"""Digital certificate (.p12 / PKCS#12) loading and management."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from cryptography.hazmat.primitives.asymmetric.padding import AsymmetricPadding
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    pkcs12,
)
from cryptography.x509 import Certificate
from facturacion_dian_kit.core.config import WORKING_DIRECTORY, settings


class PrivateKeyLike(Protocol):
    """Subset of private key behavior needed by the kit."""

    def private_bytes(
        self,
        encoding: Encoding,
        format: PrivateFormat,
        encryption_algorithm: NoEncryption,
    ) -> bytes: ...

    def sign(
        self,
        data: bytes,
        padding: AsymmetricPadding,
        algorithm: object,
    ) -> bytes: ...


class CertificateBundle:
    """Holds the private key, certificate, and CA chain from a .p12 file."""

    def __init__(
        self,
        private_key: PrivateKeyLike,
        certificate: Certificate,
        ca_chain: list[Certificate],
    ) -> None:
        self.private_key = private_key
        self.certificate = certificate
        self.ca_chain = ca_chain

    @property
    def cert_pem(self) -> bytes:
        return self.certificate.public_bytes(Encoding.PEM)

    @property
    def cert_der(self) -> bytes:
        return self.certificate.public_bytes(Encoding.DER)

    @property
    def private_key_pem(self) -> bytes:
        return self.private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )

    @property
    def not_valid_after(self) -> datetime:
        return self.certificate.not_valid_after_utc

    @property
    def is_valid(self) -> bool:
        now = datetime.now(UTC)
        return self.certificate.not_valid_before_utc <= now <= self.not_valid_after

    @property
    def issuer_name(self) -> str:
        return self.certificate.issuer.rfc4514_string()

    @property
    def subject_name(self) -> str:
        return self.certificate.subject.rfc4514_string()


def load_certificate(
    cert_path: str | None = None,
    cert_password: str | None = None,
) -> CertificateBundle:
    """Load a PKCS#12 (.p12 or .pfx) certificate file."""

    if cert_path is None:
        path = settings.dian.resolved_cert_path
    else:
        path = Path(cert_path)
        if not path.is_absolute():
            path = (WORKING_DIRECTORY / path).resolve()

    password = (cert_password or settings.dian.cert_password).encode("utf-8")
    if not path.exists():
        raise FileNotFoundError(f"Certificate not found: {path}")

    p12_data = path.read_bytes()
    try:
        private_key, certificate, ca_certs = pkcs12.load_key_and_certificates(
            p12_data,
            password,
        )
    except Exception as exc:
        raise ValueError(f"Failed to load certificate: {exc}") from exc

    if private_key is None or certificate is None:
        raise ValueError("Certificate file must contain a private key and certificate")

    return CertificateBundle(
        private_key=cast(PrivateKeyLike, private_key),
        certificate=certificate,
        ca_chain=list(ca_certs) if ca_certs else [],
    )


_bundle: CertificateBundle | None = None


def get_certificate_bundle() -> CertificateBundle:
    """Get or load the certificate bundle (cached singleton)."""

    global _bundle  # noqa: PLW0603
    if _bundle is None:
        _bundle = load_certificate()
    return _bundle


def reset_certificate_cache() -> None:
    """Clear the cached certificate bundle (for testing)."""

    global _bundle  # noqa: PLW0603
    _bundle = None
