# Contenedor con responsabilidad del comprador desconocida — HTTP 0.2.0a7

## Respuesta DIAN

La [consulta técnica sobre AE28](auditorias/2026-09-19-consulta-dian-ae28.md) se
radicó y la Subdirección de Factura Electrónica y Soluciones Operativas de la DIAN
la respondió en dos oficios:

- **Oficio 100153157-15391 (2026-10-05).** AE28 conserva su ocurrencia 1..1 y
  lleva un valor de la tabla 13.2.6.1 que determina el facturador. No resolvió el
  caso de la responsabilidad desconocida.
- **Oficio 100153157-16972 (2026-10-27)**, respuesta a la solicitud de aclaración:
  - En el `TaxLevelCode` del AttachedDocument se puede informar `R-99-PN`
    («No aplica – Otros») cuando la responsabilidad no aplica o no está entre las
    opciones disponibles. La pregunta planteaba expresamente la responsabilidad
    desconocida, y ante la alternativa de omitir AE28, dejarlo vacío u otro valor,
    la respuesta fue que procede R-99-PN.
  - Usarlo en el contenedor no modifica la factura ni la clasificación del
    comprador: el contenedor registra la factura validada y sus eventos, desde el
    `ApplicationResponse` 02.
  - El AttachedDocument no está sometido a la validación previa de la DIAN.
  - El Anexo 1.9 no distingue este elemento por tipo de documento (factura, nota
    crédito, nota débito) ni por tipo de identificación del receptor.
  - Si el adquirente suministró correo u otro medio electrónico, el facturador
    envía el contenedor con la representación gráfica.

Ambos oficios son orientaciones de carácter general, no doctrina. La DIAN precisó
que el tema es técnico y que la dependencia competente es esa Subdirección, no la
de Normativa y Doctrina.

## Contrato

`POST /api/v1/attached-documents` acepta un tercer valor de
`receiver_tax_level_source`:

| Valor | AE28 | Cuándo |
|---|---|---|
| `SIGNED_DOCUMENT` (por defecto) | Copia del XML firmado | El original trae la responsabilidad |
| `BUYER_RUT` (0.2.0a6) | `receiver_tax_level_code`, transcrito del RUT | El emisor tiene el RUT del comprador |
| `UNKNOWN_RESPONSIBILITY` (0.2.0a7) | `R-99-PN` | El emisor no conoce la responsabilidad |

Garantías con `UNKNOWN_RESPONSIBILITY`:

1. `receiver_tax_level_code` es obligatorio y debe ser exactamente `R-99-PN`.
   Otro valor responde 422: este origen no transporta responsabilidades conocidas;
   para eso está `BUYER_RUT`.
2. Sólo completa un AE28 ausente. Si el XML firmado ya trae TaxLevelCode del
   comprador, la respuesta es 422
   `ATTACHED_DOCUMENT_UNKNOWN_RESPONSIBILITY_NOT_APPLICABLE`.
3. El documento y el AR se embeben byte a byte, con firma y huella intactas. El
   documento embebido sigue sin FAK26.
4. El tributo (TaxScheme) del comprador se copia del XML firmado; si no lo traía,
   sale `ZZ` «No aplica».
5. Identidad, DV, número, fechas y CUFE/CUDE se siguen contrastando contra el
   documento firmado.

`SIGNED_DOCUMENT` no cambia: si el original no trae TaxLevelCode del comprador,
sigue respondiendo `ATTACHED_DOCUMENT_BUYER_RESPONSIBILITY_UNRESOLVED`, aunque el
llamador envíe R-99-PN. El servicio nunca elige el origen por el llamador.

## Responsabilidades del consumidor

- Declarar `UNKNOWN_RESPONSIBILITY` sólo cuando no conoce la responsabilidad. Si
  tiene el RUT del comprador, `BUYER_RUT` con el valor real es preferible (por
  ejemplo, O-13).
- R-99-PN en el contenedor no es un dato del comprador. No lo guarde como su
  perfil fiscal ni lo use en FAK26 de documentos nuevos.
- Conservar la decisión (origen, fundamento y fecha). El servicio es *stateless* y
  no la almacena.
- Por correo, entregar un único ZIP con el AttachedDocument y la representación
  gráfica.

## Versión

`release/manifest.json` fija la versión 0.2.0a7 y sus hashes reproducibles. El XML
de facturas, notas, eventos y su firma no cambian respecto a 0.2.0a6. Un servicio
fijado a un digest anterior responde 422 a este origen: el consumidor comprueba la
versión con `/health` antes de declararlo.
