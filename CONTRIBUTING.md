# Contribuir

## Setup de desarrollo

```powershell
Copy-Item .env.example .env -Force
python -m pip install -e ./packages/core -e "./packages/server[dev]"
```

Ejecuta este set antes de abrir un pull request:

```powershell
python scripts/validate_public_docs.py
python scripts/validate_skill.py
python -m ruff check .
python -m mypy packages/core/src packages/server/src
python -m pytest
docker build -t facturacion-dian-kit .
```

## Reglas de contribucion

- Manten el comportamiento DIAN determinista y respaldado por pruebas.
- No introduzcas branding especifico de un emisor ni defaults privados de negocio.
- No subas certificados, `.env` ni credenciales reales de DIAN.
- Trata la API HTTP como contrato publico principal del proyecto.
- Considera la documentacion publica y los ejemplos JSON como parte del contrato.
- Usa `packages/core` para comportamiento reusable del servicio y `packages/server` para la superficie HTTP.

## Pull requests

- Describe el efecto visible para integradores y el escenario DIAN afectado.
- Explica cualquier referencia normativa o regla de validacion que cambie.
- Incluye o actualiza pruebas para payload, XML, firma, parser, transporte o documentacion publica segun aplique.
