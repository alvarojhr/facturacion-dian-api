"""Real signatures, persisted replay and lost-response recovery without DIAN calls."""
from __future__ import annotations

import base64
import copy
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from facturacion_dian_api.core.dian.client import DianClient
from facturacion_dian_api.core.dian.response_parser import DianResponse
from facturacion_dian_api.core.runtime_config import compute_nit_dv
from facturacion_dian_api.core.signing.certificate import CertificateBundle
from facturacion_dian_api.core.signing.xades import sign_document_xml
from lxml import etree


@pytest.fixture(params=["030", "031", "032", "033"])
def prepared(client, sample_event_payload, monkeypatch, request):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic event test")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(UTC) - timedelta(days=1))
            .not_valid_after(datetime.now(UTC) + timedelta(days=2)).sign(key, hashes.SHA256()))
    monkeypatch.setattr("facturacion_dian_api.core.events.get_certificate_bundle", lambda: CertificateBundle(key, cert, []))
    monkeypatch.setattr("facturacion_dian_api.core.events.sign_document_xml", sign_document_xml)
    send = AsyncMock(return_value=DianResponse(is_valid=True, validation_result_present=True, status_code="00"))
    monkeypatch.setattr(DianClient, "send_event_update_status", send)
    payload = copy.deepcopy(sample_event_payload)
    payload["event_type"] = request.param
    payload["receiver_person"] = {"document_number": "123456789", "document_type": "13", "first_name": "Test", "family_name": "Receiver"}
    if request.param == "031":
        payload.update(claim_cause_code="01", claim_description="Synthetic claim")
    payload["issuer"] = {"nit": "800199436", "dv": compute_nit_dv("800199436"), "name": "Synthetic receiver", "additional_account_id": "2"}
    payload["submission_options"]["prepare_only"] = True
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "PREPARED"
    send.assert_not_called()
    root = etree.fromstring(base64.b64decode(data["artifacts"]["application_response_xml_base64"]))
    payload["event_issue_date"] = root.xpath("string(/*/*[local-name()='IssueDate'])")
    payload["event_issue_time"] = root.xpath("string(/*/*[local-name()='IssueTime'])")
    payload["submission_options"].update(prepare_only=False,
        signed_event_xml_base64=data["artifacts"]["application_response_xml_base64"],
        signed_event_xml_filename=data["artifacts"]["application_response_xml_filename"])
    return payload, data, send


def test_preparation_and_replay_preserve_exact_signed_bytes(client, prepared, monkeypatch):
    payload, data, send = prepared
    monkeypatch.setattr("facturacion_dian_api.core.events.sign_document_xml", lambda *args: pytest.fail("must not sign again"))
    result = client.post("/api/v1/events", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "ACCEPTED"
    assert result.json()["artifacts"]["application_response_xml_base64"] == data["artifacts"]["application_response_xml_base64"]
    assert result.json()["cude"] == data["cude"]
    send.assert_awaited_once()


@pytest.mark.parametrize("field,value", [("environment", "produccion"), ("document_cufe", "f" * 96), ("supplier_name", "different"), ("event_issue_time", "00:00:00-05:00")])
def test_replay_rejects_different_identity(client, prepared, field, value):
    payload, _, send = prepared
    payload[field] = value
    assert client.post("/api/v1/events", json=payload).status_code == 503
    send.assert_not_called()


def test_replay_rejects_different_filename(client, prepared):
    payload, _, send = prepared
    payload["submission_options"]["signed_event_xml_filename"] = "another.xml"
    assert client.post("/api/v1/events", json=payload).status_code == 503
    send.assert_not_called()


@pytest.mark.parametrize("matching", [True, False])
def test_reconcile_queries_original_cude_and_never_sends(client, prepared, monkeypatch, matching):
    payload, data, send = prepared
    query = AsyncMock(return_value=DianResponse(is_valid=True, validation_result_present=True, status_code="00", document_key=data["cude"] if matching else "f" * 96))
    monkeypatch.setattr(DianClient, "get_status", query)
    payload["submission_options"]["reconcile_only"] = True
    result = client.post("/api/v1/events", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == ("ACCEPTED" if matching else "UNKNOWN")
    query.assert_awaited_once_with(data["cude"])
    send.assert_not_called()


def test_preparation_rejects_old_date_before_signing(client, sample_event_payload):
    sample_event_payload.update(event_issue_date="2000-01-01", event_issue_time="12:00:00-05:00")
    sample_event_payload["submission_options"]["prepare_only"] = True
    assert client.post("/api/v1/events", json=sample_event_payload).status_code == 503
