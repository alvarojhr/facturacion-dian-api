---
name: dian-integration
description: Configura, valida y adopta facturacion-dian-api como API HTTP de alto nivel para facturacion electronica DIAN. Use when Codex needs to help a team integrate the public API from an ERP, POS or backend, prepare environment variables and certificates, validate request payloads, explain DIAN rejections, or guide habilitacion without using production secrets.
---

# DIAN Integration

Read this skill when helping a team integrate the public API of `facturacion-dian-api`.

## Start here

- Read [`references/http-api.md`](references/http-api.md) for the official HTTP endpoints and request blocks.
- Read [`references/examples.md`](references/examples.md) when the task needs canonical JSON examples or ERP/POS mapping guidance.
- Read [`references/troubleshooting.md`](references/troubleshooting.md) when the issue is operational, transport-related, or a DIAN rejection.
- Read [`references/habilitacion.md`](references/habilitacion.md) when the task is about test-set setup or habilitacion flow.

## Workflow

1. Confirm the caller will integrate against the public HTTP API of `facturacion-dian-api`.
2. Normalize business data into the official blocks:
   `document`, `issuer`, `buyer`, `resolution`, `totals`, `line_items`, `references`, `submission_options`.
   For RADIAN receiver events (`POST /api/v1/events`) the blocks are flat instead:
   `event_type`, the referenced document, the supplier, and `submission_options`.
3. Validate runtime DIAN inputs before debugging payload semantics:
   `DIAN_SOFTWARE_ID`, `DIAN_SOFTWARE_PIN`, certificate path/password, issuer NIT, and `DIAN_TEST_SET_ID` in habilitacion.
4. Distinguish HTTP contract errors from local configuration failures and from functional DIAN rejections.
5. Prefer deterministic guidance grounded in the documented API, official endpoints, and canonical example payloads.

## Guardrails

- Do not ask users to paste private certificates or secrets into chat.
- Do not present `facturacion-dian-api` as an SDK or language-specific library.
- Do not recommend production use of demo identifiers, test-set ids, or placeholder issuer metadata.
- If DIAN rejects a document functionally, explain the likely payload area involved and the next verification step.
- Do not offer event `034` (aceptacion tacita): the issuer registers it, and the API does not expose it.
- Do not tell callers the API enforces the event order `030 -> 032 -> (033 | 031)`; that belongs to the integrator.
