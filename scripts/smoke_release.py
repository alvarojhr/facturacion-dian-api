#!/usr/bin/env python3
"""Offline HTTP smoke against installed wheels; no real certificate or DIAN call."""

from __future__ import annotations

import importlib.metadata
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from facturacion_dian_api.server.app import app
from facturacion_dian_api.server.contracts import DocumentSubmissionRequest
from facturacion_dian_api.server.examples import DOCUMENT_SUBMISSION_INVOICE_EXAMPLE
from fastapi.testclient import TestClient


def main() -> None:
    version = importlib.metadata.version("facturacion-dian-api-server")
    client = TestClient(app)
    for days, expected_status in ((180, "ok"), (3, "degraded")):
        bundle = SimpleNamespace(is_valid=True, not_valid_after=datetime.now(UTC) + timedelta(days=days))
        with patch("facturacion_dian_api.server.api.health.get_certificate_bundle", return_value=bundle):
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["version"] == version
        assert response.json()["status"] == expected_status
    with patch("facturacion_dian_api.server.api.health.get_certificate_bundle", side_effect=FileNotFoundError("offline")):
        response = client.get("/health")
    assert response.json()["certificate_loaded"] is False
    assert response.json()["version"] == version
    payload = deepcopy(DOCUMENT_SUBMISSION_INVOICE_EXAMPLE)
    payload["buyer"] = {"name": "COMPRADOR DE PRUEBA", "document_type": "CC", "document_number": "123456789"}
    request = DocumentSubmissionRequest.model_validate(payload)
    assert request.buyer.tax_level_code is None
    schema = client.get("/openapi.json").json()
    assert schema["info"]["version"] == version
    assert "receiver_tax_level_code" not in schema["components"]["schemas"]["AttachedDocumentRequest"].get("required", [])
    print(json.dumps({"version": version, "health": "valid/expiring/missing OK", "partial_buyer": "OK"}))


if __name__ == "__main__":
    main()
