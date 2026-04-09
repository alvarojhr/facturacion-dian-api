# Guia de inicio rapido

Esta guia te deja con `facturacion-dian-kit` corriendo localmente como API HTTP.

## Requisitos

- Python 3.12+
- Docker opcional si prefieres correr el servicio en contenedor
- certificado `.p12` o `.pfx`
- credenciales DIAN de habilitacion o produccion

## 1. Preparar entorno

```powershell
Copy-Item .env.example .env -Force
```

Completa al menos:

- `DIAN_ENVIRONMENT`
- `DIAN_SOFTWARE_ID`
- `DIAN_SOFTWARE_PIN`
- `DIAN_TEST_SET_ID` cuando uses habilitacion
- `DIAN_CERT_PATH`
- `DIAN_CERT_PASSWORD`
- `COMPANY_*`

## 2. Instalar dependencias

```powershell
python -m pip install -e ./packages/core -e "./packages/server[dev]"
```

## 3. Validar repo

```powershell
python scripts/validate_public_docs.py
python scripts/validate_skill.py
python -m ruff check .
python -m mypy packages/core/src packages/server/src
python -m pytest
```

## 4. Levantar la API

```powershell
uvicorn facturacion_dian_kit.server.app:app --host 0.0.0.0 --port 8000
```

## 5. Smoke tests

Verifica salud:

```powershell
curl http://localhost:8000/health
```

Envia un ejemplo de lookup:

```powershell
curl --request POST "http://localhost:8000/api/v1/customers/lookup" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/customer-lookup.json"
```

## Docker

```powershell
docker build -t facturacion-dian-kit .
docker run --rm -p 8000:8000 --env-file .env facturacion-dian-kit
```

## Siguientes pasos

- Lee la [guia de integracion HTTP](integracion-http.md).
- Revisa la [guia de certificados y secretos](guia-certificados-y-secretos.md).
- Si vas a DIAN habilitacion, usa la [guia de habilitacion](guia-habilitacion.md).
