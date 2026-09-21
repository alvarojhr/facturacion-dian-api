# Corrección de base imponible — HTTP 0.2.0a4

## Problema y resultado

Una factura con 22 unidades a 1.850 COP, excluidas de IVA, se generaba con
`TaxExclusiveAmount=40700.00`, aunque sus líneas no emitían `TaxTotal` y la suma
de sus bases tributarias era cero. Esa contradicción produce FAU04.

El generador ahora separa los importes comerciales de las bases tributarias:

| Campo XML | Caso excluido corregido |
| --- | ---: |
| `LineExtensionAmount` | 40700.00 |
| `TaxExclusiveAmount` | 0.00 |
| `TaxInclusiveAmount` | 40700.00 |
| `PayableAmount` | 40700.00 |

Los excluidos siguen sin emitir impuestos. Exentos y gravados a tarifa cero
conservan los nodos y las bases que les corresponden. Una base explícita cero
se conserva; las bases de retención no se suman como bases de `TaxTotal`.

`TaxInclusiveAmount` usa el valor comercial de las líneas más los tributos.
Los descuentos y cargos globales, anticipos, retenciones y redondeo conservan
su efecto en `PayableAmount`, validado por el contrato. No se cambian cantidades,
precios, totales aportados por el integrador ni el cálculo de CUFE/CUDE.

## Regla por familia XML

Se usan las tablas de reglas de validación del
[anexo FEV 1.9](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9.pdf)
y del anexo DEE 1.0 de la Resolución 000165 de 2023:

- `Invoice`: FAU04 (p. 438 FEV) y DEAU04 (p. 728 DEE) suman
  `InvoiceLine/TaxTotal/TaxSubtotal/TaxableAmount`.
- `CreditNote`: CAU04 (pp. 508–509 FEV) y NAAU04 (p. 1278 DEE) suman
  `CreditNoteLine/TaxTotal[1]/TaxSubtotal/TaxableAmount`. La selección del primer
  `TaxTotal` conserva el orden del detalle y omite las retenciones.
- `DebitNote`: DAU04 (pp. 574–575 FEV) suma
  `DebitNoteLine/TaxTotal/TaxSubtotal/TaxableAmount`.
- FAU06/CAU06/DAU06 y sus equivalentes DEE definen el bruto más tributos desde
  `LineExtensionAmount`, independientemente de `TaxExclusiveAmount`.

Las tablas de estructura de `Invoice` contienen `TaxTotal[1]` (p. 86 FEV y
p. 74 DEE), mientras las tablas de validación FAU04/DEAU04 citadas omiten `[1]`.
Se aplica la tabla de validación; no se extiende esa suma a las notas `CreditNote`,
cuya regla sí conserva `[1]`. El caso de exclusión y los documentos con un solo
tributo por línea no dependen de esa diferencia editorial.

## Verificación y adopción

La regresión cubre seis perfiles: factura, POS, nota crédito, nota débito y los
dos ajustes DEE que expone la API. Incluye exclusión total, documentos mixtos,
IVA de 19/5/0, exentos, bases explícitas, varios tributos, retenciones y ajustes
globales. La preparación HTTP usa certificados efímeros y verifica que el
reintento transmita exactamente el XML firmado, con transporte simulado.

El smoke de la imagen comprueba el caso excluido con los wheels instalados.
`release/manifest.json` fija la nueva versión 0.2.0a4 y sus hashes reproducibles.

Los consumidores deben actualizar sus wheels/manifiesto de contrato y el digest
del servicio desplegado, y repetir el caso excluido y mixto antes de activar la
imagen. Cambiar el código de este repositorio no actualiza por sí solo servicios
que están fijados a un digest anterior.

Para documentos ya rechazados, conservar XML, payload, CUFE/CUDE y respuesta
DIAN originales. Reenviar los mismos bytes reproduce el rechazo. La recuperación
requiere confirmar el estado real y un procedimiento explícito del integrador
para preparar la corrección, conservar su trazabilidad y transmitirla. Esta
versión no modifica documentos almacenados ni ejecuta esa recuperación.
