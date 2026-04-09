# HTTP API

Usa esta referencia cuando el usuario necesite el contrato oficial de la API publica de `facturacion-dian-kit`.

Endpoints oficiales:

- `POST /api/v1/documents/submissions`
- `GET /api/v1/documents/submissions/{tracking_id}`
- `POST /api/v1/attached-documents`
- `POST /api/v1/customers/lookup`
- `POST /api/v1/numbering-ranges/lookup`
- `GET /health`

Bloques principales del request de envio:

- `document`
- `issuer`
- `buyer`
- `resolution`
- `totals`
- `line_items`
- `references`
- `submission_options`
- `client_reference`

Campos principales de la respuesta:

- `submission_id`
- `tracking_id`
- `client_reference`
- `document_key`
- `qr_url`
- `status`
- `messages`
- `dian_response`
- `artifacts`

Para la guia completa, lee [`../../../../docs/integracion-http.md`](../../../../docs/integracion-http.md).
