# Guia de integracion HTTP

`facturacion-dian-kit` expone una API HTTP estable para integrarse desde ERP, POS y backends.

Base URL local por defecto:

```text
http://localhost:8000
```

## Endpoints oficiales

| Metodo | Ruta | Proposito |
| --- | --- | --- |
| `POST` | `/api/v1/documents/submissions` | Enviar factura, POS, nota credito o nota debito |
| `GET` | `/api/v1/documents/submissions/{tracking_id}` | Consultar estado funcional en DIAN |
| `POST` | `/api/v1/attached-documents` | Construir ZIP interoperable AttachedDocument |
| `POST` | `/api/v1/customers/lookup` | Consultar adquiriente en DIAN |
| `POST` | `/api/v1/numbering-ranges/lookup` | Consultar rangos de numeracion autorizados |
| `GET` | `/health` | Verificar estado del runtime |

## Envio de documentos

Usa siempre `POST /api/v1/documents/submissions`. El tipo documental cambia dentro de `document.type`.

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
curl "http://localhost:8000/api/v1/documents/submissions/2c6c3df3-6301-4170-9e1e-a2441a8b5d5e"
```

## AttachedDocument

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

## Politica HTTP

- `422`: el request no cumple el contrato HTTP.
- `503`: falta configuracion local o el certificado no esta disponible o es invalido.
- `502`: DIAN o el transporte devolvieron una falla upstream.
- `504`: DIAN no respondio a tiempo.
- `200` con `status=accepted|rejected`: DIAN proceso la solicitud y devolvio resultado funcional.

## Campos clave del request

- `document`: identifica el documento y su tipo.
- `issuer`: sobrescribe datos del emisor si hace falta.
- `buyer`: datos del adquiriente.
- `resolution`: numeracion autorizada.
- `totals`: subtotal, impuestos y total.
- `line_items`: lineas comerciales.
- `references`: requerido para notas.
- `submission_options`: credenciales y parametros runtime DIAN.
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
