# HTTP API

Usa esta referencia cuando el usuario necesite el contrato oficial de la API publica de `facturacion-dian-api`.

Endpoints oficiales:

- `POST /api/v1/documents/submissions`
- `GET /api/v1/documents/submissions/{tracking_id}`
- `POST /api/v1/attached-documents`
- `POST /api/v1/customers/lookup`
- `POST /api/v1/numbering-ranges/lookup`
- `POST /api/v1/documents/download-by-key`
- `POST /api/v1/events`
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

La consulta de estado devuelve el mismo modelo: si DIAN ya proceso el documento,
`document_key` trae la clave (CUFE/CUDE) que ella misma reporta y `qr_url` la URL
del catalogo. Reconciliar un envio cuyo acuse se perdio no exige recalcular el
CUFE (recalcularlo daria otra clave si el reintento se firmo con otra hora).

## Eventos RADIAN del receptor

`POST /api/v1/events` registra los eventos que emite quien **recibe** la factura:
`030` acuse de recibo, `032` recibo del bien o servicio, `033` aceptacion
expresa y `031` reclamo (exige `claim_cause_code` 01-04). El `034` (aceptacion
tacita) no se expone: lo registra el emisor.

Campos del request:

- `event_type`, `environment`, `event_number`
- `document_cufe`, `document_number`, `document_issue_date`, `document_type_code`
- `supplier_nit`, `supplier_name`, `supplier_dv`, `total_amount`
- `claim_cause_code`, `claim_description` (solo `031`)
- `receiver_person` (obligatorio ante DIAN para el `032`)
- `submission_options`, `client_reference`

Campos de la respuesta: `status` (`PREPARED`, `RECEIVED`, `PENDING`,
`ACCEPTED`, `REJECTED`, `UNKNOWN` o `ERROR`), `cude`,
`tracking_id`, `client_reference`, `messages`, `dian_response`, `artifacts`.

Reglas que el integrador debe recordar:

- En HTTP `0.2.0a3`, envía `issuer` con NIT, DV, nombre y tipo de persona.
  Omitirlo conserva el fallback histórico `COMPANY_*` del despliegue.
- Prepara con `submission_options.prepare_only=true`, persiste XML/CUDE/nombre
  y transmite con `signed_event_xml_base64` y `signed_event_xml_filename`.
  Ante incertidumbre, `reconcile_only=true` consulta el CUDE sin retransmitir.
- El endpoint es stateless: el orden `030 -> 032 -> (033 | 031)` y la ventana de
  reclamo son responsabilidad del integrador.
- Los eventos no consumen numeracion DIAN. El integrador debe conservar el XML
  firmado y el nombre tecnico devueltos al preparar el evento; un reintento
  reenvia exactamente esos bytes para conservar CUDE, fecha, hora y firma.
- `submission_options.file_sequence` es obligatorio para documentos y eventos.
  El ERP/POS lo administra de forma monotona y reutiliza el mismo valor al
  reintentar el mismo artefacto firmado.

Para la guia completa, lee [`../../../../docs/integracion-http.md`](../../../../docs/integracion-http.md).
