# Implementación de la auditoría fiscal

Fecha: 15 de septiembre de 2026. Resumen público de los controles incorporados al contrato 0.2.0a0.

## Resultado

Los 14 hallazgos tienen controles implementados en la API y pruebas locales. La validación estructural se ejecutó contra los XSD de las cajas oficiales **FE 1.9 v2026** y **DEE 1.0 V1-3**. Pasaron factura, POS, NC, ND, ajustes DEE 93/94, eventos 030/031/032 y `AttachedDocument`.

Esta implementación no sustituye la habilitación. Antes de producción todavía se deben ejecutar los casos reales con el certificado, software, test set, resoluciones y RUT de cada emisor, y guardar los `ApplicationResponse` de DIAN como evidencia.

La comprobación de firmas fuente del `AttachedDocument` valida integridad con el
certificado X.509 embebido. La confianza de la cadena y la identidad DIAN del
firmante se deben comprobar con la PKI y los artefactos reales del ambiente.

## Trazabilidad

| Hallazgo | Control implementado | Evidencia local |
| --- | --- | --- |
| H01 | Contrato exige XML firmado y AR firmado; verifica criptográficamente su integridad con el certificado X.509 embebido; cruza número, clave, tipo y ambiente; acepta sólo AR `02`; deriva fecha, hora y resultado; firma el contenedor. | XSD `UBL-AttachedDocument-2.1.xsd`, prueba de alteración de firma y AR rechazado. |
| H02 | Estados separados, `ZipKey` pendiente, ambiente en GET y QR por ambiente. | Pruebas del parser y endpoints. |
| H03 | Decimales y validación de líneas, tributos, descuentos, totales y pagable antes de calcular la clave. | Casos adversos de consistencia monetaria. |
| H04 | Catálogo explícito, varios tributos por línea, retenciones, tributos porcentuales y por unidad; códigos desconocidos producen `422`. | Pruebas de typo, IVA + INC y retención. |
| H05 | Forma, medio y vencimiento separados; crédito exige vencimiento. | Prueba de forma `2` y fecha pactada. |
| H06 | Causal, referencia y período explícitos; no se inventan referencias parciales. | Pruebas de builders y contratos de NC/ND. |
| H07 | Ajustes DEE `CreditNote` diferenciados con códigos `94` y `93`, referencia CUDE y nombre `ncs`. | XSD y pruebas de ambos tipos. |
| H08 | Perfil completo por emisor, DV resuelto por NIT, responsabilidades múltiples y tipo de persona independiente. | Pruebas de emisor del body y DV. |
| H09 | Fecha/hora tipadas, firma inicial del día, reintento con XML persistido, artículo obligatorio y resolución completa/rango/vigencia. Las notas pueden usar numeración interna. | Pruebas de fechas, numeración, líneas y notas sin resolución. |
| H10 | Tipos FEV `03/04` y DEE `07/08`, incidente, referencia y plazo de 48 horas. | Pruebas de las modalidades de contingencia. |
| H11 | Persona obligatoria en `032`; fecha original y XML firmado exacto para reintentos; estados de evento ampliados. | Pruebas de contrato y determinismo. |
| H12 | `Decimal`, descuentos, cargos, anticipos, redondeo, retenciones y líneas gratuitas con precio de referencia. | Pruebas monetarias y XSD. |
| H13 | Bloqueo de certificado vencido o aún no válido, validación del uso de clave, recarga de caché al rotar y alerta configurable de vencimiento en `/health`. | Pruebas de firma y certificado. |
| H14 | Nombres `fv/nc/nd/ds/ncs/ar/ars/ad/z` con NIT de 10 dígitos, código de proveedor, año y consecutivo hexadecimal. El consecutivo es obligatorio en la API. | Pruebas de estabilidad, unicidad y nombres de artifacts. |

## Validación reproducible

Ejecutar `python scripts/validate_public_docs.py`, `python scripts/validate_skill.py`, `python -m ruff check .`, `python -m mypy packages/core/src packages/server/src` y `python -m pytest -m "not integration"` con las dependencias de `requirements.lock`. Las pruebas crean certificados efímeros y sustituyen el transporte DIAN.

Para comprobar estructura con las cajas oficiales, ejecutar `python scripts/validate_canonical_xml_xsd.py --xsd-dir "<caja>/XSD/maindoc"`. XSD no acredita aceptación fiscal.

## Migración de consumidores

Cada consumidor debe adoptar el contrato antes de actualizar su servicio: reservar consecutivos de archivo, completar perfiles fiscales, persistir XML firmado y respuestas, reconciliar resultados inciertos y conservar el destino de documentos anteriores. Consultar [la migración](../migracion-contrato-fiscal-2026-09.md) y [pagos y tolerancias](../pagos-combinados-y-tolerancias-020.md).

La habilitación requiere certificado, software, test set y resoluciones del emisor. Conservar request, XML, nombre, tracking, estado y ApplicationResponse de cada caso autorizado.
