# Contenedor con responsabilidad del comprador respaldada por RUT — HTTP 0.2.0a6

## Problema

FAK26 (responsabilidades del comprador) es opcional en la factura, mientras que
AE28 del AttachedDocument tiene ocurrencia 1..1. Si una factura se firmó y validó
sin FAK26, el servicio responde 422
`ATTACHED_DOCUMENT_BUYER_RESPONSIBILITY_UNRESOLVED` y no construye el contenedor.
En 0.2.0a6 ese límite seguía vigente para responsabilidades **desconocidas** (ver
la [auditoría AE28](auditorias/2026-09-19-ae28-entrega-comprador.md)). La DIAN
respondió después y 0.2.0a7 las representa con R-99-PN sólo en el contenedor:
ver [contenedor con responsabilidad desconocida](contenedor-responsabilidad-desconocida-020a7.md).

Hay un caso distinto. Después de firmar, el emisor obtiene el RUT del comprador y
conoce sus responsabilidades reales, pero la factura validada ya no se puede
modificar. Sin una vía explícita, ese comprador facturador electrónico no recibe el
XML hasta anular y volver a expedir cada factura.

## Contrato

`POST /api/v1/attached-documents` acepta un campo opcional:

| Campo | Valores | Por defecto |
|---|---|---|
| `receiver_tax_level_source` | `SIGNED_DOCUMENT`, `BUYER_RUT` | `SIGNED_DOCUMENT` |

- `SIGNED_DOCUMENT` conserva el comportamiento anterior: AE28 se copia del XML
  firmado y `receiver_tax_level_code`, si llega, sólo se contrasta con él.
- `BUYER_RUT` es una declaración explícita del emisor: el XML firmado omitió las
  responsabilidades del comprador y el emisor cuenta con su RUT. AE28 lleva
  `receiver_tax_level_code`, que es obligatorio y se valida contra el catálogo
  (O-13, O-15, O-23, O-47, R-99-PN).

Garantías con `BUYER_RUT`:

1. Sólo completa un AE28 ausente. Si el XML firmado ya trae TaxLevelCode del
   comprador, la respuesta es 422 `ATTACHED_DOCUMENT_BUYER_RUT_NOT_APPLICABLE`: un
   hecho firmado nunca se reemplaza.
2. La factura y el AR se embeben byte a byte, con firma y huella intactas. La
   factura embebida sigue sin FAK26.
3. El tributo (TaxScheme) del comprador se copia del XML firmado, no del RUT.
4. Identidad, DV, número, fechas y CUFE/CUDE se siguen contrastando contra el
   documento firmado.

## Responsabilidades del consumidor

- Usar `BUYER_RUT` sólo con el RUT del comprador en la mano. Transcribir sus
  responsabilidades al catálogo: casillas 13, 15, 23 o 47 del RUT a O-13, O-15,
  O-23 u O-47; si no tiene ninguna, R-99-PN. No usarlo para suponer valores.
- Conservar la evidencia (número de formulario y fecha del RUT, quién lo
  registró). El servicio es *stateless* y no la almacena.
- Esta declaración se limita al contenedor de entrega. La DIAN no valida el
  AttachedDocument y la decisión de usar esta vía corresponde al emisor. La
  consulta sobre AE28 ya tiene respuesta (2026-10-27, ver 0.2.0a7).

## Versión

`release/manifest.json` fija la nueva versión 0.2.0a6 y sus hashes
reproducibles. El XML de facturas, notas, eventos y su firma no cambian respecto a
0.2.0a5. Los servicios fijados a un digest anterior no adquieren este
comportamiento: un consumidor que lo necesite despliega la nueva versión y
la comprueba con `/health`.
