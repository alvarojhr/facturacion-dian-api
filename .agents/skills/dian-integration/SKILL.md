---
name: dian-integration
description: Configure, validate, and adopt facturacion-dian-kit for DIAN electronic invoicing workflows. Use when Codex needs to help a team integrate the public HTTP API, prepare environment variables and certificates, validate submission payloads, explain DIAN rejections, map ERP data into the public contract, or guide habilitacion testing without relying on private production credentials.
---

# DIAN Integration

Read this skill when helping a team adopt `facturacion-dian-kit`.

## Start here

- Read [`references/http-api.md`](references/http-api.md) for the public HTTP contract.
- Read [`references/examples.md`](references/examples.md) when the user needs payload examples or field mapping guidance.
- Read [`references/troubleshooting.md`](references/troubleshooting.md) when the user reports errors or DIAN rejections.
- Read [`references/habilitacion.md`](references/habilitacion.md) when the task is about habilitacion setup or test-set validation.

## Workflow

1. Confirm whether the user is integrating against the HTTP server, not a future SDK.
2. Normalize the user input into the public nested contract:
   `document`, `issuer`, `buyer`, `resolution`, `totals`, `line_items`, `references`, `submission_options`.
3. Check configuration requirements before debugging payloads:
   `DIAN_SOFTWARE_ID`, `DIAN_SOFTWARE_PIN`, certificate path/password, issuer NIT, and `DIAN_TEST_SET_ID` for habilitacion.
4. Distinguish functional DIAN rejection from transport or local configuration failure.
5. Prefer deterministic guidance tied to the documented API and environment variables instead of speculative advice.

## Guardrails

- Do not ask users to paste private certificates or secrets into chat.
- Do not treat the current project as a packaged SDK.
- Do not recommend production use of placeholder technical keys, test-set ids, or example issuer metadata.
- If a rejection depends on DIAN business rules, explain the likely cause and point to the payload fields involved.
