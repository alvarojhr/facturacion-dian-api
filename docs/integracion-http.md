# Guia de integracion HTTP

La versión candidata `0.2.0a1` admite [compradores con datos fiscales desconocidos](compradores-parciales-020a1.md). Revise la política por familia y la dependencia pendiente de AE28 antes de activar la entrega electrónica.

La ampliación local de `0.2.0a0` incorpora `document.payment_methods` y conserva
el IVA informado dentro de las tolerancias fiscales. Consulte la
[política de pagos y redondeos](pagos-combinados-y-tolerancias-020.md), sus
ejemplos y la exclusión entre `payment_method` y `payment_methods`.

`facturacion-dian-api` expone una API HTTP estable para integrarse desde ERP, POS y backends.

Base URL local por defecto:

```text
http://localhost:8000
```

## Endpoints oficiales

| Metodo | Ruta | Proposito |
| --- | --- | --- |
| `POST` | `/api/v1/documents/submissions` | Preparar o enviar factura, POS, notas, ajustes DEE y contingencias |
| `GET` | `/api/v1/documents/submissions/{tracking_id}` | Consultar estado funcional en DIAN |
| `POST` | `/api/v1/attached-documents` | Construir ZIP interoperable AttachedDocument |
| `POST` | `/api/v1/customers/lookup` | Consultar adquiriente en DIAN |
| `POST` | `/api/v1/numbering-ranges/lookup` | Consultar rangos de numeracion autorizados |
| `POST` | `/api/v1/documents/download-by-key` | Descargar el XML de un documento por CUFE/CUDE |
| `POST` | `/api/v1/events` | Emitir un evento RADIAN del receptor (030/031/032/033) |
| `GET` | `/health` | Verificar estado del runtime |

## Envio de documentos

Usa siempre `POST /api/v1/documents/submissions`. El tipo documental cambia dentro de `document.type`.

La fecha de un documento nuevo debe ser la fecha actual de Colombia. Facturas y documentos equivalentes requieren resolución completa y vigente. Las notas pueden omitirla cuando usan su consecutivo interno. Revisa la [migración fiscal de septiembre de 2026](migracion-contrato-fiscal-2026-09.md).

Ejemplos canonicos:

- [Factura electronica](examples/factura-electronica.json)
- [Documento equivalente POS](examples/documento-equivalente-pos.json)
- [Nota credito](examples/nota-credito.json)
- [Nota debito](examples/nota-debito.json)

### Curl: factura electronica

```powershell
curl --request POST "http://localhost:8000/api/v1/documents/submissions" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/factura-electronica.json"
```

### Curl: documento equivalente POS

```powershell
curl --request POST "http://localhost:8000/api/v1/documents/submissions" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/documento-equivalente-pos.json"
```

### Curl: nota credito

```powershell
curl --request POST "http://localhost:8000/api/v1/documents/submissions" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/nota-credito.json"
```

### Curl: nota debito

```powershell
curl --request POST "http://localhost:8000/api/v1/documents/submissions" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/nota-debito.json"
```

## Consulta de estado

```powershell
curl "http://localhost:8000/api/v1/documents/submissions/2c6c3df3-6301-4170-9e1e-a2441a8b5d5e?environment=habilitacion"
```

Un `ZipKey` confirma recepción, no aceptación. Continúa consultando mientras el estado sea `received` o `pending`. Los estados finales fiscales son `accepted` y `rejected`; `unknown` y `error` requieren reconciliación operativa.

## Preparar, persistir y transmitir

En la primera llamada usa `submission_options.prepare_only=true`. Persiste `artifacts.xml_base64`, `artifacts.xml_filename`, CUFE/CUDE, ambiente y `file_sequence`. Repite el mismo payload con esos dos campos como `signed_xml_base64` y `signed_xml_filename` para transmitir exactamente el XML persistido.

Este flujo evita reconstruir otro documento después de un timeout. La API verifica la firma, el número y la clave fiscal antes de reutilizar el artifact.

## AttachedDocument

El request recibe el documento firmado por el emisor y el `ApplicationResponse` firmado por DIAN. El AR debe contener respuesta `02` y referenciar el mismo número y CUFE/CUDE. El servicio toma del AR el resultado, fecha y hora de validación, construye el contenedor y lo firma.

Payload canonico:

- [AttachedDocument](examples/attached-document.json)

```powershell
curl --request POST "http://localhost:8000/api/v1/attached-documents" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/attached-document.json"
```

## Lookup de adquiriente

Payload canonico:

- [Customer lookup](examples/customer-lookup.json)

```powershell
curl --request POST "http://localhost:8000/api/v1/customers/lookup" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/customer-lookup.json"
```

## Lookup de rangos de numeracion

Payload canonico:

- [Numbering ranges lookup](examples/numbering-ranges-lookup.json)

```powershell
curl --request POST "http://localhost:8000/api/v1/numbering-ranges/lookup" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/numbering-ranges-lookup.json"
```

## Descarga de XML por CUFE/CUDE

`POST /api/v1/documents/download-by-key` recupera de DIAN el XML de un documento
ya emitido, a partir de su CUFE (factura) o CUDE (nota / documento equivalente).
Sirve para reconstruir un archivo perdido sin reenviar el documento.

Payloads canonicos:

- [Download by key](examples/download-by-key.json)
- [Respuesta](examples/respuesta-download-by-key.json)

```powershell
curl --request POST "http://localhost:8000/api/v1/documents/download-by-key" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/download-by-key.json"
```

El XML llega en `xml_base64`. Si DIAN no tiene el documento, la respuesta sigue
siendo `200` con `success: false` y `error_message` diligenciado: es un resultado
funcional, no un fallo de transporte (ver [Politica HTTP](#politica-http)).

## Eventos RADIAN del receptor

`POST /api/v1/events` registra ante DIAN los eventos que emite quien **recibe**
una factura de un proveedor. El servicio construye el `ApplicationResponse`
UBL 2.1, calcula su CUDE, lo firma con XAdES y lo transmite por
`SendEventUpdateStatus`.

| `event_type` | Evento |
| --- | --- |
| `030` | Acuse de recibo de la factura |
| `032` | Recibo del bien o prestacion del servicio |
| `033` | Aceptacion expresa |
| `031` | Reclamo (requiere `claim_cause_code` 01-04) |

El evento `034` (aceptacion tacita) **no** se expone: lo registra el emisor.

Payloads canonicos:

- [Acuse de recibo 030](examples/evento-acuse-recibo.json)
- [Reclamo 031](examples/evento-reclamo.json)
- [Respuesta](examples/respuesta-evento.json)

```powershell
curl --request POST "http://localhost:8000/api/v1/events" `
  --header "Content-Type: application/json" `
  --data "@docs/examples/evento-acuse-recibo.json"
```

Puntos a tener en cuenta:

- **La identidad de quien emite el evento sale de las variables `COMPANY_*` del
  despliegue**, no del request: un despliegue = un emisor. En el cuerpo solo
  viaja la contraparte (`supplier_nit`, `supplier_name`).
- **El endpoint es stateless.** El orden obligatorio `030 -> 032 -> (033 | 031)`
  y la ventana de reclamo los controla el integrador.
- **Los eventos no consumen numeracion DIAN.** Reserva `event_number` y
  `file_sequence` antes del intento. Ante un resultado incierto, reenvia
  `signed_event_xml_base64`, `event_issue_date` y `event_issue_time` para
  conservar exactamente el mismo XML y CUDE.
- **`receiver_person`**: DIAN lo exige para el evento `032` y lo valida en
  `030`/`033`. Envialo siempre que conozcas a la persona que recibio.
- `status` distingue `RECEIVED`, `PENDING`, `ACCEPTED`, `REJECTED`, `UNKNOWN`
  y `ERROR`. Los resultados funcionales llegan como `200`; los fallos de
  transporte salen como `502`/`504`.
- `artifacts` trae dos XML que hay que retener por separado: el
  `ApplicationResponse` firmado por ti y la respuesta firmada por DIAN.

## Politica HTTP

- `422`: el request no cumple el contrato HTTP.
- `503`: falta configuracion local o el certificado no esta disponible o es invalido.
- `502`: DIAN o el transporte devolvieron una falla upstream.
- `504`: DIAN no respondio a tiempo.
- `200`: la respuesta incluye el estado real de preparación, recepción, proceso o resultado fiscal.

## Campos clave del request

- `document`: identifica el documento y su tipo.
- `issuer`: si incluye `name`, la identidad completa del body tiene prioridad;
  cada campo ausente cae al `COMPANY_*` equivalente. Sin `name` se conserva el
  contrato legacy (`nit`, `dv`, `software_owner_nit`).
- `buyer`: datos del adquiriente.
- `resolution`: numeracion autorizada completa en factura y documento equivalente; opcional en notas.
- `totals`: subtotal, impuestos, retenciones, descuentos/cargos, anticipos, redondeo y pagable.
- `line_items`: lineas comerciales con código, valores y uno o varios tributos explícitos.
- `references`: requerido para notas.
- `submission_options`: credenciales, consecutivo técnico anual y control de preparación/reintento.
- `client_reference`: correlacion opaca del caller.

## Campos clave de la respuesta

- `submission_id`
- `tracking_id`
- `client_reference`
- `document_key`
- `qr_url`
- `status`
- `messages`
- `dian_response`
- `artifacts`

`artifacts` es evidencia fiscal, no telemetría. Persiste el XML firmado del emisor y el AR firmado por DIAN en campos separados.
