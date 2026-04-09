"""Tests that keep the public API docs aligned with the real contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from facturacion_dian_kit.server.contracts import (
    AttachedDocumentRequest,
    AttachedDocumentResponse,
    BuyerLookupRequest,
    BuyerLookupResponse,
    DocumentSubmissionRequest,
    DocumentSubmissionResponse,
    HealthResponse,
    NumberingRangeLookupRequest,
    NumberingRangeLookupResponse,
)
from facturacion_dian_kit.server.examples import (
    ATTACHED_DOCUMENT_REQUEST_EXAMPLE,
    ATTACHED_DOCUMENT_RESPONSE_EXAMPLE,
    BUYER_LOOKUP_REQUEST_EXAMPLE,
    BUYER_LOOKUP_RESPONSE_EXAMPLE,
    DOCUMENT_STATUS_RESPONSE_EXAMPLE,
    DOCUMENT_SUBMISSION_REQUEST_EXAMPLES,
    DOCUMENT_SUBMISSION_RESPONSE_EXAMPLE,
    HEALTH_RESPONSE_EXAMPLE,
    NUMBERING_RANGE_LOOKUP_REQUEST_EXAMPLE,
    NUMBERING_RANGE_LOOKUP_RESPONSE_EXAMPLE,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_EXAMPLES_DIR = REPO_ROOT / "docs" / "examples"

REQUEST_MODELS = {
    "factura-electronica.json": DocumentSubmissionRequest,
    "documento-equivalente-pos.json": DocumentSubmissionRequest,
    "nota-credito.json": DocumentSubmissionRequest,
    "nota-debito.json": DocumentSubmissionRequest,
    "attached-document.json": AttachedDocumentRequest,
    "customer-lookup.json": BuyerLookupRequest,
    "numbering-ranges-lookup.json": NumberingRangeLookupRequest,
}

RESPONSE_MODELS = {
    "respuesta-envio-aceptado.json": DocumentSubmissionResponse,
    "respuesta-lookup-cliente.json": BuyerLookupResponse,
    "respuesta-rangos-numeracion.json": NumberingRangeLookupResponse,
    "respuesta-health.json": HealthResponse,
}

PUBLIC_DOC_FILES = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "guia-inicio-rapido.md",
    REPO_ROOT / "docs" / "integracion-http.md",
    REPO_ROOT / "docs" / "guia-certificados-y-secretos.md",
    REPO_ROOT / "docs" / "guia-habilitacion.md",
    REPO_ROOT / "docs" / "catalogo-errores-dian.md",
    REPO_ROOT / "docs" / "troubleshooting-operativo.md",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "references" / "http-api.md",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "references" / "examples.md",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "references" / "troubleshooting.md",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "references" / "habilitacion.md",
]

FORBIDDEN_PUBLIC_SNIPPETS = (
    "/api/v1/documents/submit",
    "/api/v1/documents/status/",
    "/api/v1/documents/attached-document",
    "packages/sdk-python",
    "packages/sdk-ts",
    "future Python SDK",
    "future TypeScript SDK",
    "core + server + SDKs",
)


def _load_json(name: str) -> dict:
    return json.loads((DOCS_EXAMPLES_DIR / name).read_text(encoding="utf-8"))


class TestPublicExamples:
    """Public JSON examples should always match the real request/response models."""

    def test_request_examples_validate_against_models(self) -> None:
        for filename, model in REQUEST_MODELS.items():
            model.model_validate(_load_json(filename))

    def test_response_examples_validate_against_models(self) -> None:
        for filename, model in RESPONSE_MODELS.items():
            model.model_validate(_load_json(filename))

    def test_openapi_examples_validate_against_models(self) -> None:
        for payload in DOCUMENT_SUBMISSION_REQUEST_EXAMPLES:
            DocumentSubmissionRequest.model_validate(payload)

        DocumentSubmissionResponse.model_validate(DOCUMENT_SUBMISSION_RESPONSE_EXAMPLE)
        DocumentSubmissionResponse.model_validate(DOCUMENT_STATUS_RESPONSE_EXAMPLE)
        AttachedDocumentRequest.model_validate(ATTACHED_DOCUMENT_REQUEST_EXAMPLE)
        AttachedDocumentResponse.model_validate(ATTACHED_DOCUMENT_RESPONSE_EXAMPLE)
        BuyerLookupRequest.model_validate(BUYER_LOOKUP_REQUEST_EXAMPLE)
        BuyerLookupResponse.model_validate(BUYER_LOOKUP_RESPONSE_EXAMPLE)
        NumberingRangeLookupRequest.model_validate(NUMBERING_RANGE_LOOKUP_REQUEST_EXAMPLE)
        NumberingRangeLookupResponse.model_validate(NUMBERING_RANGE_LOOKUP_RESPONSE_EXAMPLE)
        HealthResponse.model_validate(HEALTH_RESPONSE_EXAMPLE)


class TestPublicDocs:
    """Public docs should stay API-first and free of legacy routes."""

    def test_public_docs_do_not_reference_legacy_routes(self) -> None:
        for path in PUBLIC_DOC_FILES:
            text = path.read_text(encoding="utf-8")
            for snippet in FORBIDDEN_PUBLIC_SNIPPETS:
                assert snippet not in text, f"{snippet!r} found in {path}"

    def test_readme_positions_project_as_api(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "API HTTP de alto nivel" in readme
        assert "No se publica PyPI ni npm" in readme
        assert "POST /api/v1/documents/submissions" in readme

    def test_sdk_placeholder_files_are_gone(self) -> None:
        assert not (REPO_ROOT / "packages" / "sdk-python" / "README.md").exists()
        assert not (REPO_ROOT / "packages" / "sdk-ts" / "README.md").exists()

    def test_lightweight_public_docs_validator_passes(self) -> None:
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "validate_public_docs.py")],
            check=True,
            cwd=REPO_ROOT,
        )
