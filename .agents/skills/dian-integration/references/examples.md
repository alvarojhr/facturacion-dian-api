# Examples

Payloads JSON canonicos:

- [`../../../../docs/examples/factura-electronica.json`](../../../../docs/examples/factura-electronica.json)
- [`../../../../docs/examples/documento-equivalente-pos.json`](../../../../docs/examples/documento-equivalente-pos.json)
- [`../../../../docs/examples/nota-credito.json`](../../../../docs/examples/nota-credito.json)
- [`../../../../docs/examples/nota-debito.json`](../../../../docs/examples/nota-debito.json)
- [`../../../../docs/examples/attached-document.json`](../../../../docs/examples/attached-document.json)
- [`../../../../docs/examples/customer-lookup.json`](../../../../docs/examples/customer-lookup.json)
- [`../../../../docs/examples/numbering-ranges-lookup.json`](../../../../docs/examples/numbering-ranges-lookup.json)

Hints de mapeo:

- cabecera comercial -> `document`, `resolution`, `totals`
- datos del emisor -> `issuer` cuando deban sobrescribir defaults runtime
- datos del cliente -> `buyer`
- credenciales y parametros DIAN -> `submission_options`
- correlacion del caller -> `client_reference`

Para ejemplos de `curl`, lee [`../../../../docs/integracion-http.md`](../../../../docs/integracion-http.md).
