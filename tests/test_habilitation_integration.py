"""Opt-in rehearsal against the real DIAN habilitacion endpoints.

The payload files are intentionally external to the repository because they
contain issuer-specific numbering and credentials. Normal CI collects this
test but skips it unless DIAN_LIVE_TESTS=1 is explicit.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from facturacion_dian_api.core.dian.client import DianClient
from facturacion_dian_api.core.dian.response_parser import DianResponse
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[1]


def _external_payload_paths() -> list[Path]:
    if os.getenv("DIAN_LIVE_TESTS") != "1":
        pytest.skip("Set DIAN_LIVE_TESTS=1 to authorize real DIAN habilitacion calls")

    raw_paths = os.getenv("DIAN_INTEGRATION_PAYLOADS", "")
    if not raw_paths:
        pytest.fail("DIAN_INTEGRATION_PAYLOADS must list external JSON payloads")

    paths = [Path(value).expanduser().resolve() for value in raw_paths.split(os.pathsep) if value]
    if not paths:
        pytest.fail("DIAN_INTEGRATION_PAYLOADS did not contain a usable path")

    for path in paths:
        if path.is_relative_to(REPO_ROOT):
            pytest.fail("Live DIAN payloads must stay outside the public repository")
        if not path.is_file():
            pytest.fail(f"Live DIAN payload does not exist: {path.name}")
    return paths


def _load_habilitation_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        pytest.fail(f"Payload {path.name} must be a JSON object")
    if payload.get("environment") != "habilitacion":
        pytest.fail(f"Payload {path.name} must declare environment=habilitacion")
    return payload


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _poll_terminal_status(tracking_id: str) -> DianResponse:
    timeout_seconds = int(os.getenv("DIAN_INTEGRATION_TIMEOUT_SECONDS", "240"))
    deadline = time.monotonic() + timeout_seconds
    last = DianResponse()
    in_progress_codes = {"", "0", "66"}

    while time.monotonic() < deadline:
        last = asyncio.run(DianClient().get_status_zip(tracking_id))
        if last.is_accepted:
            return last
        if last.error_messages:
            pytest.fail(f"DIAN rejected tracking hash {_short_hash(tracking_id)}: {last.error_messages}")
        if last.status_code and last.status_code not in in_progress_codes:
            pytest.fail(
                f"DIAN rejected tracking hash {_short_hash(tracking_id)}: "
                f"code={last.status_code} message={last.status_message}"
            )
        time.sleep(5)

    pytest.fail(
        f"DIAN did not reach a terminal status for tracking hash {_short_hash(tracking_id)}; "
        f"last code={last.status_code or 'unknown'}"
    )


def test_habilitation_document_matrix(client: TestClient) -> None:
    """Submit the externally supplied FE/POS/NC/ND matrix in declared order."""

    for path in _external_payload_paths():
        payload = _load_habilitation_payload(path)
        response = client.post("/api/v1/documents/submissions", json=payload)
        assert response.status_code == 200, response.text
        submitted = response.json()
        assert submitted["status"] == "accepted", submitted.get("messages", [])
        assert submitted["artifacts"]["xml_base64"]
        assert submitted["artifacts"]["xml_filename"]

        tracking_id = submitted["tracking_id"]
        assert isinstance(tracking_id, str) and tracking_id
        _poll_terminal_status(tracking_id)
        status_response = client.get(f"/api/v1/documents/submissions/{tracking_id}")
        assert status_response.status_code == 200, status_response.text
        final = status_response.json()
        assert final["status"] == "accepted", final.get("messages", [])
        document_key = final.get("document_key") or submitted.get("document_key")
        assert isinstance(document_key, str) and len(document_key) == 96
        assert document_key in (final.get("qr_url") or submitted.get("qr_url") or "")

        status_artifacts = final.get("artifacts") or {}
        submit_artifacts = submitted.get("artifacts") or {}
        assert (
            status_artifacts.get("application_response_xml_base64")
            or submit_artifacts.get("application_response_xml_base64")
        ), "DIAN did not return the signed ApplicationResponse"

        print(
            f"habilitacion ok payload={path.name} "
            f"tracking_sha256={_short_hash(tracking_id)} "
            f"document_key_sha256={_short_hash(document_key)}"
        )
