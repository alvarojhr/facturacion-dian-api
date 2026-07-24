"""Tests for the public FastAPI HTTP API."""

from __future__ import annotations

import base64
import io
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from facturacion_dian_api.core.config import resolve_wsdl_url, settings
from facturacion_dian_api.core.cufe.calculator import EventCudeFields, calculate_event_cude
from facturacion_dian_api.core.dian.client import DianClient
from facturacion_dian_api.core.dian.response_parser import DianResponse
from facturacion_dian_api.core.errors import DianTimeoutError
from facturacion_dian_api.server.contracts import DocumentSubmissionRequest
from facturacion_dian_api.server.mappers import to_core_submission_request
from fastapi.testclient import TestClient
from lxml import etree

from tests.conftest import DOWNLOADED_XML_BYTES, KNOWN_DOCUMENT_KEY, UNKNOWN_DOCUMENT_KEY


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
            "nit": "12345678",
            "dv": "8",
            "name": "PEREZ GOMEZ ANA LUCIA",
            "additional_account_id": "2",
            "address": "CL 100 # 15-20 BRR EJEMPLO",
            "city_code": "68276",
            "city_name": "Floridablanca",
            "department_code": "68",
            "department_name": "Santander",
            "country_code": "CO",
            "tax_level_code": "R-99-PN",
            "economic_activity": "4752",
            "phone": "3001234567",
            "email": "ana.perez@example.com",
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


class TestEmitEvent:
    """RADIAN receiver events through the public API."""

    def test_emit_acknowledgement_returns_cude_and_artifacts(
        self,
        client: TestClient,
        sample_event_payload: dict,
    ) -> None:
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ACCEPTED"
        assert len(data["cude"]) == 96
        assert data["tracking_id"] == "event-track-123"
        assert data["client_reference"] == "acuse-erp-1001"
        artifacts = data["artifacts"]
        assert artifacts["application_response_xml_filename"] == "ar_030_SETP990000123.xml"
        assert base64.b64decode(artifacts["application_response_xml_base64"]) == b"<Signed>ok</Signed>"
        # DIAN no devolvio XML en el stub, asi que el artefacto propio queda nulo.
        assert artifacts["dian_response_xml_base64"] is None

    def test_emit_event_is_deterministic_for_fixed_inputs(
        self,
        client: TestClient,
        sample_event_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same inputs + same instant → same CUDE.

        The event's date/time are re-stamped from the clock on every call
        (rule AAD09e forces issue date = signing date), so two calls at
        different times legitimately yield different CUDEs. Determinism is a
        property of the *inputs*, so the clock is frozen to isolate it.
        """
        frozen = datetime(2026, 7, 23, 9, 15, 0, tzinfo=timezone(timedelta(hours=-5)))
        monkeypatch.setattr("facturacion_dian_api.core.events.colombia_now", lambda: frozen)

        first = client.post("/api/v1/events", json=sample_event_payload)
        second = client.post("/api/v1/events", json=sample_event_payload)
        assert first.json()["cude"] == second.json()["cude"]

    def test_derived_event_number_is_stable_across_calls(
        self,
        client: TestClient,
        sample_event_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Omitting event_number derives it from the CUFE, deterministically.

        With the clock frozen, the only field that could vary between two calls
        is the derived consecutive; an equal CUDE proves it is stable.
        """
        frozen = datetime(2026, 7, 23, 9, 15, 0, tzinfo=timezone(timedelta(hours=-5)))
        monkeypatch.setattr("facturacion_dian_api.core.events.colombia_now", lambda: frozen)

        sample_event_payload.pop("event_number")
        first = client.post("/api/v1/events", json=sample_event_payload)
        second = client.post("/api/v1/events", json=sample_event_payload)
        assert first.status_code == 200
        assert first.json()["cude"] == second.json()["cude"]

    def test_event_date_and_cude_come_from_the_colombian_clock(
        self,
        client: TestClient,
        sample_event_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rule AAD09e: the stamped date must be the Colombian calendar day.

        20:30 in Bogota is already the next day in UTC, so a naive
        ``utcnow()`` would stamp 2026-07-24 and DIAN would reject the event.
        """
        frozen = datetime(2026, 7, 23, 20, 30, 15, tzinfo=timezone(timedelta(hours=-5)))
        monkeypatch.setattr("facturacion_dian_api.core.events.colombia_now", lambda: frozen)

        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 200

        expected_cude = calculate_event_cude(
            EventCudeFields(
                num_de="EV000001",
                fec_emi="2026-07-23",
                hor_emi="20:30:15-05:00",
                nit_fe=settings.company.nit,
                doc_adq="800199436",
                response_code="030",
                document_id="SETP990000123",
                document_type_code="01",
                software_pin="12345",
            )
        )
        assert response.json()["cude"] == expected_cude

    def test_claim_without_cause_returns_422(
        self,
        client: TestClient,
        sample_event_payload: dict,
    ) -> None:
        sample_event_payload["event_type"] = "031"
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 422

    def test_claim_with_cause_is_accepted(
        self,
        client: TestClient,
        sample_event_payload: dict,
    ) -> None:
        sample_event_payload["event_type"] = "031"
        sample_event_payload["claim_cause_code"] = "03"
        sample_event_payload["claim_description"] = "Faltaron 20 unidades."
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ACCEPTED"

    def test_claim_cause_rejected_on_non_claim_event(
        self,
        client: TestClient,
        sample_event_payload: dict,
    ) -> None:
        sample_event_payload["claim_cause_code"] = "01"
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 422

    def test_tacit_acceptance_event_is_not_accepted(
        self,
        client: TestClient,
        sample_event_payload: dict,
    ) -> None:
        """034 is registered by the issuer, so this API must not accept it."""
        sample_event_payload["event_type"] = "034"
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 422

    def test_environment_uses_the_canonical_spelling(
        self,
        client: TestClient,
        sample_event_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Events use the same environment literals as every other endpoint."""
        seen: dict[str, str] = {}
        original_init = DianClient.__init__

        def spy_init(
            self: DianClient,
            endpoint_url: str | None = None,
            bundle: object | None = None,
        ) -> None:
            original_init(self, endpoint_url, bundle)  # type: ignore[arg-type]
            seen["endpoint_url"] = self.endpoint_url

        monkeypatch.setattr(DianClient, "__init__", spy_init)
        sample_event_payload["environment"] = "produccion"
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 200
        assert seen["endpoint_url"] == resolve_wsdl_url("produccion")

    def test_uppercase_environment_is_rejected(
        self,
        client: TestClient,
        sample_event_payload: dict,
    ) -> None:
        # El endpoint usa una sola grafia canonica (habilitacion/produccion),
        # como el resto de la API; no hay normalizador. El ERP ya mapea
        # dian_config.environment (PRUEBA/PRODUCCION) antes de llamar, igual que
        # en el envio de documentos. Este test guarda el contrato contra la
        # reintroduccion de un alias permisivo.
        sample_event_payload["environment"] = "PRUEBA"
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 422

    def test_functional_rejection_is_200_with_rejected_status(
        self,
        client: TestClient,
        sample_event_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_rejection(self: DianClient, content_b64: str) -> DianResponse:
            del self, content_b64
            return DianResponse(
                is_valid=False,
                status_code="99",
                status_description="Documento con errores",
                error_messages=["Regla: AAD06, Rechazo: el valor UUID no esta correctamente calculado"],
                tracking_id="event-track-err",
                xml_bytes=b"<ApplicationResponse>dian</ApplicationResponse>",
            )

        monkeypatch.setattr(DianClient, "send_event_update_status", fake_rejection)
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"
        assert "AAD06" in data["messages"][0]
        artifacts = data["artifacts"]
        assert artifacts["dian_response_xml_filename"] == "dian_030_SETP990000123.xml"
        assert (
            base64.b64decode(artifacts["dian_response_xml_base64"])
            == b"<ApplicationResponse>dian</ApplicationResponse>"
        )

    def test_emit_event_returns_503_when_credentials_are_missing(
        self,
        client: TestClient,
        sample_event_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings.dian, "software_id", "")
        monkeypatch.setattr(settings.dian, "software_pin", "")
        sample_event_payload.pop("submission_options")
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 503
        assert "Missing required event settings" in response.json()["detail"]

    def test_emit_event_returns_504_on_dian_timeout(
        self,
        client: TestClient,
        sample_event_payload: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_timeout(self: DianClient, content_b64: str) -> DianResponse:
            del self, content_b64
            raise DianTimeoutError("Timeout calling DIAN SendEventUpdateStatus")

        monkeypatch.setattr(DianClient, "send_event_update_status", fake_timeout)
        response = client.post("/api/v1/events", json=sample_event_payload)
        assert response.status_code == 504


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


class TestDownloadByKey:
    """Test XML download by CUFE/CUDE through the public API."""

    def test_download_returns_xml_base64(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/documents/download-by-key",
            json={"document_key": KNOWN_DOCUMENT_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document_key"] == KNOWN_DOCUMENT_KEY
        assert base64.b64decode(data["xml_base64"]) == DOWNLOADED_XML_BYTES
        assert data["xml_filename"]
        assert data["status"] == "DOWNLOADED"
        assert data["error_message"] is None

    def test_download_unknown_key_returns_200_with_failure(self, client: TestClient) -> None:
        # Un documento inexistente es un resultado funcional de DIAN, no un
        # fallo de transporte: se responde 200 con success=False, igual que el
        # lookup de adquiriente.
        response = client.post(
            "/api/v1/documents/download-by-key",
            json={"document_key": UNKNOWN_DOCUMENT_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["xml_base64"] is None
        assert data["xml_filename"] is None
        assert data["error_message"]

    def test_download_honors_requested_environment(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seen: dict[str, str] = {}
        original_init = DianClient.__init__

        def spy_init(
            self: DianClient,
            endpoint_url: str | None = None,
            bundle: object | None = None,
        ) -> None:
            original_init(self, endpoint_url, bundle)  # type: ignore[arg-type]
            seen["endpoint_url"] = self.endpoint_url

        monkeypatch.setattr(DianClient, "__init__", spy_init)

        response = client.post(
            "/api/v1/documents/download-by-key",
            json={"environment": "produccion", "document_key": KNOWN_DOCUMENT_KEY},
        )

        assert response.status_code == 200
        assert seen["endpoint_url"] == resolve_wsdl_url("produccion")

    def test_download_requires_document_key(self, client: TestClient) -> None:
        response = client.post("/api/v1/documents/download-by-key", json={})
        assert response.status_code == 422
