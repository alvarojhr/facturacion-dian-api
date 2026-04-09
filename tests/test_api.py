"""Tests for the public FastAPI HTTP API."""

from __future__ import annotations

import base64
import io
import zipfile

import pytest
from facturacion_dian_kit.core.config import settings
from facturacion_dian_kit.core.dian.client import DianClient
from facturacion_dian_kit.core.dian.response_parser import DianResponse
from facturacion_dian_kit.core.errors import DianTimeoutError
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")
        assert data["version"]
        assert data["dian_environment"] in ("habilitacion", "produccion")
        assert isinstance(data["certificate_loaded"], bool)

    def test_root_returns_service_info(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "facturacion-dian-kit API"
        assert data["version"]


class TestDocumentSubmit:
    """Test document submission behavior through the public API."""

    def test_submit_invoice_returns_document_key(
        self,
        client: TestClient,
        sample_invoice_payload: dict,
    ) -> None:
        response = client.post("/api/v1/documents/submissions", json=sample_invoice_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["document_key"] is not None
        assert len(data["document_key"]) == 96
        assert data["qr_url"] is not None
        assert "catalogo-vpfe.dian.gov.co" in data["qr_url"]
        assert data["tracking_id"] is not None
        assert data["artifacts"]["xml_filename"] == "ws_FDK000001.xml"
        assert data["client_reference"] == "client-ref-001"

    def test_submit_pos_document_returns_cude(
        self,
        client: TestClient,
        sample_pos_payload: dict,
    ) -> None:
        response = client.post("/api/v1/documents/submissions", json=sample_pos_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["document_key"] is not None
        assert len(data["document_key"]) == 96

    def test_submit_credit_note_returns_cude(
        self,
        client: TestClient,
        sample_credit_note_payload: dict,
    ) -> None:
        response = client.post("/api/v1/documents/submissions", json=sample_credit_note_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["document_key"] is not None

    def test_submit_debit_note_returns_cude(
        self,
        client: TestClient,
        sample_debit_note_payload: dict,
    ) -> None:
        response = client.post("/api/v1/documents/submissions", json=sample_debit_note_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["document_key"] is not None

    def test_submit_same_payload_returns_same_document_key(
        self,
        client: TestClient,
        sample_invoice_payload: dict,
    ) -> None:
        first = client.post("/api/v1/documents/submissions", json=sample_invoice_payload)
        second = client.post("/api/v1/documents/submissions", json=sample_invoice_payload)
        assert first.json()["document_key"] == second.json()["document_key"]

    def test_submit_invalid_payload_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/v1/documents/submissions", json={"document": {"number": "X"}})
        assert response.status_code == 422

    def test_submit_without_xml_artifact_omits_artifacts(
        self,
        client: TestClient,
        sample_invoice_payload: dict,
    ) -> None:
        sample_invoice_payload["submission_options"]["return_xml_artifact"] = False
        response = client.post("/api/v1/documents/submissions", json=sample_invoice_payload)
        assert response.status_code == 200
        assert response.json()["artifacts"] is None

    def test_submit_returns_503_when_configuration_is_missing(
        self,
        client: TestClient,
        sample_invoice_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings.dian, "software_id", "")
        monkeypatch.setattr(settings.dian, "software_pin", "")
        monkeypatch.setattr(settings.dian, "technical_key", "")
        monkeypatch.setattr(settings.dian, "test_set_id", "")
        payload = sample_invoice_payload.copy()
        payload.pop("submission_options")
        response = client.post("/api/v1/documents/submissions", json=payload)
        assert response.status_code == 503
        assert "Missing required submission settings" in response.json()["detail"]

    def test_submit_returns_504_on_dian_timeout(
        self,
        client: TestClient,
        sample_invoice_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_timeout(
            self: DianClient,
            filename: str,
            content_b64: str,
            test_set_id: str | None = None,
        ) -> DianResponse:
            del self, filename, content_b64, test_set_id
            raise DianTimeoutError("Timeout calling DIAN SendTestSetAsync")

        monkeypatch.setattr(DianClient, "send_test_set_async", fake_timeout)
        response = client.post("/api/v1/documents/submissions", json=sample_invoice_payload)
        assert response.status_code == 504


class TestDocumentStatus:
    """Test status lookups through the public API."""

    def test_status_returns_rejected_payload(self, client: TestClient) -> None:
        response = client.get("/api/v1/documents/submissions/some-tracking-id")
        assert response.status_code == 200
        data = response.json()
        assert data["tracking_id"] == "some-tracking-id"
        assert data["status"] == "rejected"

    def test_status_returns_xml_artifact_when_available(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_status(self: DianClient, tracking_id: str) -> DianResponse:
            del self
            return DianResponse(
                is_valid=True,
                status_code="00",
                status_description="Processed successfully.",
                status_message="Document validated.",
                tracking_id=tracking_id,
                xml_bytes=b"<Invoice>ok</Invoice>",
            )

        monkeypatch.setattr(DianClient, "get_status_zip", fake_status)
        monkeypatch.setattr(DianClient, "get_status", fake_status)
        response = client.get("/api/v1/documents/submissions/track-xml")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert base64.b64decode(data["artifacts"]["xml_base64"]) == b"<Invoice>ok</Invoice>"
        assert data["artifacts"]["xml_filename"] == "status_track-xml.xml"


class TestAttachedDocument:
    """Test AttachedDocument generation endpoint."""

    def test_attached_document_returns_zip_package(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/attached-documents",
            json={
                "document_number": "FDK123",
                "document_type_code": "01",
                "issuer_nit": "900123456",
                "issuer_name": "Example Issuer SAS",
                "receiver_name": "Cliente Demo SAS",
                "receiver_email": "facturas@cliente.test",
                "reply_to_email": "billing@example-issuer.test",
                "company_name": "Example Issuer SAS",
                "invoice_xml_base64": base64.b64encode(b"<Invoice>demo</Invoice>").decode("ascii"),
                "invoice_xml_filename": "ws_FDK123.xml",
                "issue_date": "2026-04-01",
                "cufe": "abc123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["xml_filename"] == "ad_FDK123.xml"
        assert data["zip_filename"] == "ad_FDK123.zip"

        with zipfile.ZipFile(io.BytesIO(base64.b64decode(data["content_base64"]))) as zf:
            assert zf.namelist() == ["ad_FDK123.xml"]
            payload = zf.read("ad_FDK123.xml")
            assert b"AttachedDocument" in payload
            assert b"billing@example-issuer.test" in payload


class TestCustomerLookup:
    """Test buyer lookup endpoint."""

    def test_lookup_customer_returns_prefill(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/customers/lookup",
            json={"document_type": "NIT", "document_number": "900123456"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["customer"]["display_name"] == "Cliente DIAN S.A.S."
        assert data["customer"]["email"] == "contacto@cliente-dian.test"
        assert data["customer"]["country_code"] == "CO"

    def test_lookup_customer_returns_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/customers/lookup",
            json={"document_type": "CC", "document_number": "0000000000"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["customer"] is None
        assert data["error_message"] == "Buyer not found"


class TestNumberingRangeLookup:
    """Test numbering range lookup endpoint."""

    def test_lookup_numbering_ranges_returns_ranges(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/numbering-ranges/lookup",
            json={
                "environment": "produccion",
                "account_code": "901975980",
                "account_code_t": "901975980",
                "software_code": "software-123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["ranges"]) == 2
        assert data["ranges"][0]["prefix"] == "FDK"
