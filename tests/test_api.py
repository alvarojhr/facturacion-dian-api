"""Tests for the public FastAPI HTTP API."""

from __future__ import annotations

import base64
import io
import zipfile

import pytest
from facturacion_dian_api.core.config import settings
from facturacion_dian_api.core.dian.client import DianClient
from facturacion_dian_api.core.dian.response_parser import DianResponse
from facturacion_dian_api.core.errors import DianTimeoutError
from facturacion_dian_api.server.contracts import DocumentSubmissionRequest
from facturacion_dian_api.server.mappers import to_core_submission_request
from fastapi.testclient import TestClient
from lxml import etree


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
        assert data["service"] == "facturacion-dian-api"
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

    def test_submit_accepts_and_maps_complete_body_owned_issuer(
        self,
        client: TestClient,
        sample_invoice_payload: dict,
    ) -> None:
        issuer = {
            "nit": "49656271",
            "dv": "3",
            "name": "RUEDA CARREÑO OLGA LUCIA",
            "additional_account_id": "2",
            "address": "CR 6 # 8-66 BRR SANTA ANA",
            "city_code": "68276",
            "city_name": "Floridablanca",
            "department_code": "68",
            "department_name": "Santander",
            "country_code": "CO",
            "tax_level_code": "R-99-PN",
            "economic_activity": "4752",
            "phone": "3174283330",
            "email": "olga@example.com",
        }
        sample_invoice_payload["issuer"] = issuer

        request = DocumentSubmissionRequest.model_validate(sample_invoice_payload)
        core = to_core_submission_request(request)

        assert core.model_dump(
            include={
                "issuer_nit",
                "issuer_dv",
                "issuer_name",
                "issuer_additional_account_id",
                "issuer_address",
                "issuer_city_code",
                "issuer_city_name",
                "issuer_department_code",
                "issuer_department_name",
                "issuer_country_code",
                "issuer_tax_level_code",
                "issuer_economic_activity",
                "issuer_phone",
                "issuer_email",
            }
        ) == {
            "issuer_nit": issuer["nit"],
            "issuer_dv": issuer["dv"],
            "issuer_name": issuer["name"],
            "issuer_additional_account_id": issuer["additional_account_id"],
            "issuer_address": issuer["address"],
            "issuer_city_code": issuer["city_code"],
            "issuer_city_name": issuer["city_name"],
            "issuer_department_code": issuer["department_code"],
            "issuer_department_name": issuer["department_name"],
            "issuer_country_code": issuer["country_code"],
            "issuer_tax_level_code": issuer["tax_level_code"],
            "issuer_economic_activity": issuer["economic_activity"],
            "issuer_phone": issuer["phone"],
            "issuer_email": issuer["email"],
        }
        assert client.post("/api/v1/documents/submissions", json=sample_invoice_payload).status_code == 200

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

    def test_submit_returns_application_response_when_dian_attaches_xml_bytes(
        self,
        client: TestClient,
        sample_invoice_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        En producción, send_bill_sync devuelve el Application Response
        firmado por DIAN en XmlBase64Bytes. El microservicio debe exponerlo
        en application_response_xml_base64 (Resolución 165), junto con el
        XML firmado por el emisor en xml_base64.
        """
        ar_payload = b"<AppResponse>signed-by-dian</AppResponse>"

        async def fake_submit_with_ar(
            self: DianClient,
            filename: str,
            content_b64: str,
            test_set_id: str | None = None,
        ) -> DianResponse:
            del self, filename, content_b64, test_set_id
            return DianResponse(
                is_valid=True,
                status_code="00",
                status_description="Procesado Correctamente",
                status_message="Documento aceptado",
                tracking_id="track-with-ar",
                xml_bytes=ar_payload,
            )

        monkeypatch.setattr(DianClient, "send_test_set_async", fake_submit_with_ar)
        monkeypatch.setattr(DianClient, "send_bill_sync", fake_submit_with_ar)

        response = client.post(
            "/api/v1/documents/submissions", json=sample_invoice_payload
        )
        assert response.status_code == 200
        artifacts = response.json()["artifacts"]
        # Ambos artefactos presentes: emisor + DIAN
        assert artifacts["xml_filename"] == "ws_FDK000001.xml"
        assert artifacts["xml_base64"] is not None
        assert base64.b64decode(artifacts["application_response_xml_base64"]) == ar_payload
        assert artifacts["application_response_xml_filename"] == "ar_FDK000001.xml"

    def test_submit_leaves_application_response_null_when_dian_omits_xml_bytes(
        self,
        client: TestClient,
        sample_invoice_payload: dict,
    ) -> None:
        """
        En habilitación (send_test_set_async) DIAN responde sin el AR — éste
        llega via GetStatus después. El campo application_response_xml_base64
        debe quedar en None para que el consumer no persista basura.
        """
        # La fixture global stub_live_dian_calls devuelve una DianResponse sin
        # xml_bytes, lo cual representa el escenario de habilitación asíncrona.
        response = client.post(
            "/api/v1/documents/submissions", json=sample_invoice_payload
        )
        assert response.status_code == 200
        artifacts = response.json()["artifacts"]
        assert artifacts["xml_base64"] is not None  # XML del emisor siempre
        assert artifacts["xml_filename"] == "ws_FDK000001.xml"
        assert artifacts["application_response_xml_base64"] is None
        assert artifacts["application_response_xml_filename"] is None

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

    def test_status_returns_application_response_when_available(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        El XML que devuelve DIAN en GetStatus es el Application Response
        firmado por la DIAN, no la factura original. Se expone en
        application_response_xml_base64 (no en xml_base64), para que el
        consumer lo persista como kind=APPLICATION_RESPONSE alineado con
        la Resolución 165.
        """

        async def fake_status(self: DianClient, tracking_id: str) -> DianResponse:
            del self
            return DianResponse(
                is_valid=True,
                status_code="00",
                status_description="Processed successfully.",
                status_message="Document validated.",
                tracking_id=tracking_id,
                xml_bytes=b"<AppResponse>ok</AppResponse>",
            )

        monkeypatch.setattr(DianClient, "get_status_zip", fake_status)
        monkeypatch.setattr(DianClient, "get_status", fake_status)
        response = client.get("/api/v1/documents/submissions/track-xml")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        # El AR llega en su propio campo; xml_base64 queda en None porque
        # no tenemos el documento original del emisor desde GetStatus.
        assert data["artifacts"]["xml_base64"] is None
        assert data["artifacts"]["xml_filename"] is None
        assert (
            base64.b64decode(data["artifacts"]["application_response_xml_base64"])
            == b"<AppResponse>ok</AppResponse>"
        )
        assert data["artifacts"]["application_response_xml_filename"] == "ar_track-xml.xml"


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
            # La DIAN exige el literal "ApplicationResponse" dentro del
            # DocumentReference del ParentDocumentLineReference, y que el
            # ResultOfVerification cuelgue de ese DocumentReference (UBL 2.1).
            root = etree.fromstring(payload)
            ns = {
                "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
                "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            }
            doc_ref = root.find(
                "cac:ParentDocumentLineReference/cac:DocumentReference", ns
            )
            assert doc_ref is not None
            assert doc_ref.findtext("cbc:DocumentType", namespaces=ns) == "ApplicationResponse"
            assert doc_ref.find("cac:ResultOfVerification", ns) is not None


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
