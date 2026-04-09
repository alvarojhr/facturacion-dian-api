# facturacion-dian-kit

Open toolkit for Colombian DIAN electronic invoicing.

`facturacion-dian-kit` starts as a self-hosted HTTP server backed by a reusable Python core. The repository is intentionally structured to evolve into `core + server + SDKs` without renaming the project later.

## What is included

- `packages/core`: DIAN domain logic, UBL builders, CUFE/CUDE, signing, SOAP envelopes, and DIAN response parsing.
- `packages/server`: FastAPI HTTP server exposing the public API contract.
- `packages/sdk-python`: reserved for a future Python SDK.
- `packages/sdk-ts`: reserved for a future TypeScript SDK or generated client.
- `.agents/skills/dian-integration`: skill and agent metadata focused on kit adoption and troubleshooting.

## Current scope

- Public HTTP API for document submission and status lookups
- DIAN buyer lookup and numbering range lookup
- AttachedDocument ZIP generation
- Docker packaging for self-hosting

This repository is not positioned as a ready-made SDK yet. The first public deliverable is the server and its reusable core.

## Quick start

1. Copy the environment template.

```powershell
Copy-Item .env.example .env -Force
```

2. Install the packages in editable mode.

```powershell
python -m pip install -e ./packages/core -e "./packages/server[dev]"
```

3. Run checks.

```powershell
python scripts/validate_skill.py
python -m ruff check .
python -m mypy packages/core/src packages/server/src
python -m pytest
```

4. Start the API.

```powershell
uvicorn facturacion_dian_kit.server.app:app --host 0.0.0.0 --port 8000
```

## Docker

```powershell
docker build -t facturacion-dian-kit .
docker run --rm -p 8000:8000 --env-file .env facturacion-dian-kit
```

## Public API

Initial endpoints:

- `POST /api/v1/documents/submissions`
- `GET /api/v1/documents/submissions/{tracking_id}`
- `POST /api/v1/attached-documents`
- `POST /api/v1/customers/lookup`
- `POST /api/v1/numbering-ranges/lookup`
- `GET /health`

Example submission payload:

```json
{
  "client_reference": "client-ref-001",
  "document": {
    "number": "FDK000001",
    "type": "FACTURA_ELECTRONICA",
    "issue_date": "2026-03-12",
    "issue_time": "14:30:00-05:00",
    "payment_method": "CASH"
  },
  "buyer": {
    "document_number": "800199436",
    "document_type": "NIT",
    "name": "Empresa Ejemplo S.A.S."
  },
  "resolution": {
    "number": "18764000001",
    "prefix": "FDK"
  },
  "totals": {
    "subtotal": 100000,
    "tax_total": 19000,
    "total": 119000
  },
  "line_items": [
    {
      "description": "Tornillo hexagonal 1/4 x 1 zinc",
      "quantity": 100,
      "unit_price": 500,
      "line_total": 50000,
      "tax_type": "IVA_19",
      "tax_amount": 9500
    }
  ],
  "submission_options": {
    "software_id": "software-123",
    "software_pin": "12345",
    "technical_key": "fc8eac422eba16e22ffd8c6f94b3f40a6e38162c",
    "test_set_id": "test-set-123"
  }
}
```

## Operational policy

- `422` for invalid payloads
- `503` for missing or invalid local configuration such as certificate or required DIAN settings
- `502` for non-timeout upstream DIAN transport failures
- `504` for DIAN timeouts
- `200` when DIAN processed the request and returned a functional acceptance or rejection

## Development notes

- Do not commit certificates, private keys, `.env` files, or real DIAN credentials.
- Keep the public API contract stable inside `packages/server`.
- Use `packages/core` for reusable logic and avoid reintroducing ERP-specific terminology there.

## Roadmap

- Harden the server contract toward `1.0.0`
- Extract reusable SDK surfaces from `packages/core`
- Publish Python and TypeScript SDKs once the HTTP and core interfaces stabilize
