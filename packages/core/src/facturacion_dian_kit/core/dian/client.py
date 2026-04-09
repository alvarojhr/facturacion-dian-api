"""DIAN SOAP client using httpx."""

from __future__ import annotations

import logging

import httpx
from facturacion_dian_kit.core.config import settings
from facturacion_dian_kit.core.dian.envelope import (
    build_get_acquirer_envelope,
    build_get_numbering_range_envelope,
    build_get_status_envelope,
    build_get_status_zip_envelope,
    build_send_bill_sync_envelope,
    build_send_test_set_async_envelope,
)
from facturacion_dian_kit.core.dian.response_parser import (
    AcquirerResponse,
    DianResponse,
    NumberingRangeResponse,
    parse_get_acquirer_response,
    parse_get_numbering_range_response,
    parse_send_bill_response,
)
from facturacion_dian_kit.core.errors import DianTimeoutError, DianTransportError, DianUpstreamError
from facturacion_dian_kit.core.signing.certificate import CertificateBundle, get_certificate_bundle
from facturacion_dian_kit.core.signing.ws_security import sign_soap_envelope

logger = logging.getLogger(__name__)

SOAP_CONTENT_TYPE = "application/soap+xml; charset=utf-8"
DIAN_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class DianClient:
    """HTTP client for DIAN Web Services."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        bundle: CertificateBundle | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url or settings.dian.wsdl_url
        self._bundle = bundle

    async def send_bill_sync(self, filename: str, content_b64: str) -> DianResponse:
        envelope = build_send_bill_sync_envelope(self.endpoint_url, filename, content_b64)
        return await self._send_soap(envelope, "SendBillSync")

    async def send_test_set_async(
        self,
        filename: str,
        content_b64: str,
        test_set_id: str | None = None,
    ) -> DianResponse:
        ts_id = test_set_id or settings.dian.test_set_id
        envelope = build_send_test_set_async_envelope(
            self.endpoint_url,
            filename,
            content_b64,
            ts_id,
        )
        return await self._send_soap(envelope, "SendTestSetAsync")

    async def get_status(self, tracking_id: str) -> DianResponse:
        envelope = build_get_status_envelope(self.endpoint_url, tracking_id)
        return await self._send_soap(envelope, "GetStatus")

    async def get_status_zip(self, tracking_id: str) -> DianResponse:
        envelope = build_get_status_zip_envelope(self.endpoint_url, tracking_id)
        return await self._send_soap(envelope, "GetStatusZip")

    async def get_acquirer(
        self,
        identification_type: str,
        identification_number: str,
    ) -> AcquirerResponse:
        envelope = build_get_acquirer_envelope(
            self.endpoint_url,
            identification_type,
            identification_number,
        )
        response = await self._post_signed_envelope(envelope, "GetAcquirer")
        if response.status_code != 200:
            raise DianUpstreamError(response.status_code, response.text[:500])
        return parse_get_acquirer_response(response.content)

    async def get_numbering_range(
        self,
        account_code: str,
        account_code_t: str,
        software_code: str,
    ) -> NumberingRangeResponse:
        envelope = build_get_numbering_range_envelope(
            self.endpoint_url,
            account_code,
            account_code_t,
            software_code,
        )
        response = await self._post_signed_envelope(envelope, "GetNumberingRange")
        if response.status_code != 200:
            raise DianUpstreamError(response.status_code, response.text[:500])
        return parse_get_numbering_range_response(response.content)

    def _get_bundle(self) -> CertificateBundle:
        if self._bundle is None:
            self._bundle = get_certificate_bundle()
        return self._bundle

    async def _send_soap(self, envelope: bytes, operation: str) -> DianResponse:
        response = await self._post_signed_envelope(envelope, operation)
        if response.status_code != 200:
            raise DianUpstreamError(response.status_code, response.text[:500])
        return parse_send_bill_response(response.content)

    async def _post_signed_envelope(self, envelope: bytes, operation: str) -> httpx.Response:
        bundle = self._get_bundle()
        signed_envelope = sign_soap_envelope(envelope, bundle)

        try:
            async with httpx.AsyncClient(timeout=DIAN_TIMEOUT) as client:
                response = await client.post(
                    self.endpoint_url,
                    content=signed_envelope,
                    headers={"Content-Type": SOAP_CONTENT_TYPE},
                )
        except httpx.TimeoutException as exc:
            logger.error("DIAN %s timed out", operation)
            raise DianTimeoutError(f"Timeout calling DIAN {operation}") from exc
        except httpx.HTTPError as exc:
            logger.error("DIAN %s transport error: %s", operation, exc)
            raise DianTransportError(f"HTTP error calling DIAN {operation}: {exc}") from exc

        logger.info(
            "DIAN %s <- HTTP %d (%d bytes)",
            operation,
            response.status_code,
            len(response.content),
        )
        return response
