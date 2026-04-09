# facturacion-dian-kit

API HTTP de alto nivel para integrar facturacion electronica DIAN en Colombia.

`facturacion-dian-kit` esta pensado para equipos que necesitan conectar un ERP, un POS o cualquier backend propio con DIAN sin depender del lenguaje de programacion del sistema principal. El producto publico es la API HTTP; el resto del repo existe para implementar y operar esa API.

## Que ofrece

- envio de documentos electronicos a DIAN;
- consulta de estado por `tracking_id`;
- construccion de `AttachedDocument` para interoperabilidad por correo;
- lookup de adquiriente;
- lookup de rangos de numeracion autorizados;
- despliegue self-hosted con Docker.

Es una alternativa abierta y self-hosted frente a integraciones DIAN cerradas o administradas por terceros.

## Endpoints oficiales

- `POST /api/v1/documents/submissions`
- `GET /api/v1/documents/submissions/{tracking_id}`
- `POST /api/v1/attached-documents`
- `POST /api/v1/customers/lookup`
- `POST /api/v1/numbering-ranges/lookup`
- `GET /health`

## Documentacion

- [Guia de inicio rapido](docs/guia-inicio-rapido.md)
- [Guia de integracion HTTP](docs/integracion-http.md)
- [Guia de certificados y secretos](docs/guia-certificados-y-secretos.md)
- [Guia de habilitacion](docs/guia-habilitacion.md)
- [Catalogo de errores y rechazos DIAN](docs/catalogo-errores-dian.md)
- [Troubleshooting operativo](docs/troubleshooting-operativo.md)
- [Ejemplos JSON canonicos](docs/examples)

## Inicio rapido

1. Copia la plantilla de entorno.

```powershell
Copy-Item .env.example .env -Force
```

2. Instala los paquetes en modo editable.

```powershell
python -m pip install -e ./packages/core -e "./packages/server[dev]"
```

3. Ejecuta las validaciones locales.

```powershell
python scripts/validate_public_docs.py
python scripts/validate_skill.py
python -m ruff check .
python -m mypy packages/core/src packages/server/src
python -m pytest
```

4. Inicia la API.

```powershell
uvicorn facturacion_dian_kit.server.app:app --host 0.0.0.0 --port 8000
```

## Docker

```powershell
docker build -t facturacion-dian-kit .
docker run --rm -p 8000:8000 --env-file .env facturacion-dian-kit
```

## Ejemplo minimo de envio

Usa uno de los payloads canonicos en [`docs/examples/factura-electronica.json`](docs/examples/factura-electronica.json) y envialo asi:

```powershell
curl --request POST "http://localhost:8000/api/v1/documents/submissions" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/factura-electronica.json"
```

La respuesta publica normaliza estos campos:

- `submission_id`
- `tracking_id`
- `client_reference`
- `document_key`
- `qr_url`
- `status`
- `messages`
- `dian_response`
- `artifacts` opcional

## Politica HTTP

- `422` cuando el payload es invalido.
- `503` cuando falta configuracion local o el certificado es invalido.
- `502` cuando falla la comunicacion con DIAN sin ser timeout.
- `504` cuando DIAN no responde a tiempo.
- `200` cuando DIAN procesa la solicitud y devuelve aceptacion o rechazo funcional.

## Notas de implementacion

- `packages/server` contiene la API HTTP y el contrato OpenAPI.
- `packages/core` contiene la implementacion interna reusable del servicio.
- `packages/core` no se posiciona como superficie publica consumible ni como producto separado en esta etapa.

## Distribucion

- codigo fuente;
- Docker image;
- publicacion en GHCR para releases etiquetadas.

No se publica PyPI ni npm porque el producto publico de `facturacion-dian-kit` es la API HTTP.

## Seguridad y uso responsable

- No subas certificados, llaves privadas, `.env` ni credenciales reales de DIAN.
- No uses los valores demo de la documentacion en ambientes reales.
- Manten el contrato HTTP estable y versionado de forma intencional.

## Contribuir

Revisa [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) y [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) antes de abrir cambios o reportes.
