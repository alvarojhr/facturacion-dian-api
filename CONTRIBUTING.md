# Contributing

## Development setup

```powershell
Copy-Item .env.example .env -Force
python -m pip install -e ./packages/core -e "./packages/server[dev]"
```

Run the full validation set before opening a pull request:

```powershell
python -m ruff check .
python -m mypy packages/core/src packages/server/src
python -m pytest
docker build -t facturacion-dian-kit .
```

## Contribution rules

- Keep DIAN behavior deterministic and test-backed.
- Do not introduce issuer-specific branding or private business defaults.
- Do not commit certificates, `.env` files, or live DIAN credentials.
- Prefer changes in `packages/core` when the behavior is reusable across transports.
- Keep the public HTTP contract in `packages/server` documented and intentionally versioned.

## Pull requests

- Describe the user-visible effect and the DIAN scenario impacted.
- Call out any normative DIAN reference or validation rule affected.
- Include or update tests for payload shape, XML output, signing, parser behavior, or transport handling as applicable.
