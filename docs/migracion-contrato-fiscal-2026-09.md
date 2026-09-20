# Migración del contrato fiscal 0.2.0a0 de septiembre de 2026

La revisión `0.2.0a0` endurece el contrato HTTP para impedir que un payload ambiguo llegue a firma o a DIAN. Cada consumidor debe migrar como una actualización incompatible del contrato.

La imagen se publica en la línea OCI `v2`, separada de la versión Python/HTTP
`0.2.0a0`. Conserva `latest` en la línea anterior. El despliegue automático del
consumidor requiere `DOWNSTREAM_HTTP_CONTRACT` igual a la versión del manifiesto publicado en este repositorio,
únicamente después de validar su migración. Un consumidor puede fijar el digest
de v2 en un servicio separado sin activar ese dispatch global.

## Cambios obligatorios

1. Envíe `submission_options.file_sequence` en documentos y eventos, y `file_sequence` en `AttachedDocument`. Es el consecutivo hexadecimal anual del nombre técnico; el integrador debe reservarlo y persistirlo antes del primer intento.
2. En facturas y documentos equivalentes, envíe la resolución completa: `number`, `prefix`, `date`, `range_from`, `range_to`, `valid_from` y `valid_to`. Las notas con consecutivo interno pueden omitir `resolution`.
3. Use la fecha de Colombia del día para un documento que se firma por primera vez. Para reintentar uno anterior, envíe el XML exacto devuelto por `prepare_only`, junto con su mismo nombre técnico.
4. Incluya `item_code` en cada línea. Los importes usan decimales con máximo dos posiciones y las cantidades admiten hasta seis.
5. En `0.2.0a0` se exigían los cinco campos del perfil identificado. Desde `0.2.0a1` se separa identidad de datos fiscales desconocidos; consulte [la política y la dependencia de entrega AE28](compradores-parciales-020a1.md) y el [candidato actual `0.2.0a2`](despliegue-020a2.md).
6. Si el emisor viaja en el body, envíe su perfil completo. Ya no se mezclan sus datos con defaults de otra empresa.
7. Informe `payment_form=CONTADO|CREDITO`; para crédito, envíe `payment_due_date`.
8. En notas, envíe causal y modalidad en `references.reason` y `references.response_code`, además de una referencia completa o un período completo.

## Impuestos y valores comerciales

### Ampliación local: pagos combinados e IVA en COP enteros

`document.payment_methods` admite varios instrumentos, incluidos `CREDIT_CARD`
(48) y `DEBIT_CARD` (49). Es excluyente con el anterior `payment_method`;
enviar ambos produce `422`. `payment_form` y `payment_due_date` conservan sus
significados. POS exige contado por DEAN02.

La igualdad exacta del IVA se sustituye por una comparación de holgura: 2 COP
en línea y agregado; hasta 5 COP sólo si el IVA informado es su aproximación
al múltiplo de diez más cercano. Se mantienen exactas las sumas contables y se
conservan los importes recibidos. El caso base 2801 / IVA 532 está cubierto.

Consultar la [política completa, ejemplos y cambios del adaptador](pagos-combinados-y-tolerancias-020.md)
antes de retirar los bloqueos del consumidor.

El formato antiguo de un impuesto por línea sigue disponible mediante `tax_type` y `tax_amount`. Para varios tributos use `taxes`:

```json
{
  "taxes": [
    {"tax_type": "IVA_19", "amount": 1900},
    {"tax_type": "RETEFUENTE", "taxable_amount": 10000, "percent": 2.5, "amount": 250}
  ]
}
```

No combine ambos formatos. Un código desconocido produce `422`. La API comprueba cantidad por precio, descuentos y cargos, base por tarifa, sumas tributarias y total pagable.

Los descuentos o cargos se envían en `allowance_charges`, tanto por línea como en `totals`. `allowance_total` y `charge_total` deben coincidir con el detalle. Las líneas gratuitas requieren `reference_price` y `reference_price_type_code`.

## Flujo de persistencia antes de transmitir

Primera llamada:

```json
{
  "submission_options": {
    "file_sequence": 125,
    "prepare_only": true
  }
}
```

La respuesta usa `status=prepared`, deja `tracking_id=null` porque todavía no existe correlación DIAN e incluye el XML firmado y su nombre en `artifacts`. Persístalos de forma atómica con NIT, ambiente, tipo, número, CUFE/CUDE y `client_reference`.

Segunda llamada: repita el mismo payload con `prepare_only=false`, `signed_xml_base64` y `signed_xml_filename`. El servicio verifica ID, clave fiscal y firma contra el certificado del despliegue antes de transmitir esos mismos bytes.

Ante timeout, conserve el intento y consulte primero por el `tracking_id`. No genere otro número, fecha, CUFE/CUDE ni consecutivo de archivo mientras el resultado sea incierto.

## Estados

Los documentos pueden responder `prepared`, `received`, `pending`, `accepted`, `rejected`, `unknown` o `error`. Un `ZipKey` aislado queda `pending`; sólo un resultado funcional definitivo puede quedar `accepted` o `rejected`.

Consulte el ambiente correcto:

```text
GET /api/v1/documents/submissions/{tracking_id}?environment=habilitacion
```

## AttachedDocument

El endpoint exige el XML firmado del emisor y el `ApplicationResponse` firmado por DIAN. El AR debe ser código `02`, referenciar el mismo número y CUFE/CUDE, y contener fecha y hora. El servicio deriva de ese AR el código y el instante de validación; ya no recibe `validation_result_code`, `validation_date` ni `validation_time` del integrador.

## POS, ajustes y contingencias

- `NOTA_AJUSTE_DEE_CREDITO`: `CreditNoteTypeCode=94`.
- `NOTA_AJUSTE_DEE_DEBITO`: documento UBL `CreditNote` con `CreditNoteTypeCode=93`.
- `DOCUMENTO_EQUIVALENTE_POS_CONTINGENCIA_EMISOR`: tipo `07`.
- `DOCUMENTO_EQUIVALENTE_POS_CONTINGENCIA_DIAN`: tipo `08`.
- `FACTURA_CONTINGENCIA_FACTURADOR`: tipo `03`.
- `FACTURA_CONTINGENCIA_DIAN`: tipo `04`.

Los tipos de contingencia requieren `document.contingency` y la referencia al documento expedido durante el incidente. El modo emisor se rechaza si ya vencieron las 48 horas posteriores a la recuperación.

## Eventos del receptor

El evento `032` requiere `receiver_person`. Para reintentar un evento con resultado incierto, envíe su `signed_event_xml_base64` y las fechas originales `event_issue_date` y `event_issue_time`; el servicio verifica y retransmite el mismo CUDE.

El integrador conserva la secuencia `030 -> 032 -> (033 | 031)`, las ventanas aplicables y la reconciliación contra su propia persistencia.
