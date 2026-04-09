#!/usr/bin/env python3
"""Lightweight validation for public docs and canonical examples."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "guia-inicio-rapido.md",
    REPO_ROOT / "docs" / "integracion-http.md",
    REPO_ROOT / "docs" / "guia-certificados-y-secretos.md",
    REPO_ROOT / "docs" / "guia-habilitacion.md",
    REPO_ROOT / "docs" / "catalogo-errores-dian.md",
    REPO_ROOT / "docs" / "troubleshooting-operativo.md",
)

REQUIRED_EXAMPLES = (
    REPO_ROOT / "docs" / "examples" / "factura-electronica.json",
    REPO_ROOT / "docs" / "examples" / "documento-equivalente-pos.json",
    REPO_ROOT / "docs" / "examples" / "nota-credito.json",
    REPO_ROOT / "docs" / "examples" / "nota-debito.json",
    REPO_ROOT / "docs" / "examples" / "attached-document.json",
    REPO_ROOT / "docs" / "examples" / "customer-lookup.json",
    REPO_ROOT / "docs" / "examples" / "numbering-ranges-lookup.json",
    REPO_ROOT / "docs" / "examples" / "respuesta-envio-aceptado.json",
    REPO_ROOT / "docs" / "examples" / "respuesta-lookup-cliente.json",
    REPO_ROOT / "docs" / "examples" / "respuesta-rangos-numeracion.json",
    REPO_ROOT / "docs" / "examples" / "respuesta-health.json",
)

PUBLIC_TEXT_FILES = (
    *REQUIRED_DOCS,
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "agents" / "openai.yaml",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "references" / "http-api.md",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "references" / "examples.md",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "references" / "troubleshooting.md",
    REPO_ROOT / ".agents" / "skills" / "dian-integration" / "references" / "habilitacion.md",
)

OFFICIAL_ENDPOINTS = (
    "POST /api/v1/documents/submissions",
    "GET /api/v1/documents/submissions/{tracking_id}",
    "POST /api/v1/attached-documents",
    "POST /api/v1/customers/lookup",
    "POST /api/v1/numbering-ranges/lookup",
    "GET /health",
)

FORBIDDEN_SNIPPETS = (
    "/api/v1/documents/submit",
    "/api/v1/documents/status/",
    "/api/v1/documents/attached-document",
    "packages/sdk-python",
    "packages/sdk-ts",
    "future Python SDK",
    "future TypeScript SDK",
    "core + server + SDKs",
)


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def validate_files_exist() -> None:
    for path in (*REQUIRED_DOCS, *REQUIRED_EXAMPLES):
        if not path.is_file():
            raise ValueError(f"Missing required public artifact: {path}")


def validate_json_examples() -> None:
    for path in REQUIRED_EXAMPLES:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON example {path}: {exc}") from exc


def validate_text_content() -> None:
    corpus = {path: _read_text(path) for path in PUBLIC_TEXT_FILES}

    for snippet in FORBIDDEN_SNIPPETS:
        offenders = [str(path.relative_to(REPO_ROOT)) for path, text in corpus.items() if snippet in text]
        if offenders:
            joined = ", ".join(offenders)
            raise ValueError(f"Forbidden public snippet {snippet!r} found in: {joined}")

    combined = "\n".join(corpus.values())
    for endpoint in OFFICIAL_ENDPOINTS:
        if endpoint not in combined:
            raise ValueError(f"Official endpoint not documented in public docs: {endpoint}")

    readme = corpus[REPO_ROOT / "README.md"]
    if "API HTTP de alto nivel" not in readme:
        raise ValueError("README.md must position facturacion-dian-kit as an API HTTP de alto nivel")


def main() -> int:
    try:
        validate_files_exist()
        validate_json_examples()
        validate_text_content()
    except ValueError as exc:
        print(f"Public docs validation failed: {exc}", file=sys.stderr)
        return 1

    print("Public docs validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
