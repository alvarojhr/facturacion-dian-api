# Pagos combinados y tolerancias monetarias en 0.2.0a0

Implementación local del 15 de septiembre de 2026. Conserva `/api/v1` y los
importes del consumidor. El servicio no convierte el ledger del ERP a centavos.

## Medios de pago

Enviar **una** representación con valor no nulo:

- Anterior: `document.payment_method`, un instrumento.
- Nueva: `document.payment_methods`, lista no vacía de instrumentos en el orden
  suministrado. Se genera un `cac:PaymentMeans` por entrada, sin seleccionar el
  principal ni descartar entradas repetidas.

Enviar ambas produce `422`, incluso si contienen el mismo instrumento. También
se rechazan la ausencia de ambas, la lista vacía, los códigos desconocidos y
objetos con importes dentro de la lista. `null` equivale a no aportar esa
representación. La exclusión aparece en OpenAPI mediante `oneOf`.

| Literal API | Código DIAN | Significado en la lista oficial |
| --- | --- | --- |
| `CASH` | 10 | Efectivo |
| `CHECK` | 20 | Cheque |
| `CREDIT` | 30 | Transferencia crédito; literal anterior conservado |
| `TRANSFER` | 31 | Transferencia débito; literal anterior conservado |
| `CREDIT_CARD` | 48 | Tarjeta crédito |
| `CARD` | 48 | Alias anterior de tarjeta crédito |
| `DEBIT_CARD` | 49 | Tarjeta débito |

`CREDIT` y `TRANSFER` conservan sus códigos anteriores; el adaptador debe conocer
el instrumento real. `CARD` no representa una tarjeta genérica.

`payment_form` sigue siendo `CONTADO` por defecto o `CREDITO`; se repite como
`PaymentMeans/ID` 1 o 2 en todos los bloques. Una tarjeta de crédito no cambia esa
forma. Una venta a crédito exige `payment_due_date` ISO, igual o posterior a la
emisión; el vencimiento se conserva en cada bloque. **POS exige `CONTADO`**, por
DEAN02, incluida su contingencia. FEV y notas conservan las formas de sus tablas.

La extensión no recibe importes por instrumento ni calcula pagos efectivos,
anticipos o cartera. `totals.prepaid_amount` conserva su significado de anticipo
deducible del pagable. El ERP mantiene el detalle de abonos y el saldo; la lista
de medios no representa una suma contra el valor de la factura.

Fragmentos para `document` (mantener número, tipo y fechas):

```json
{"payment_methods": ["CASH", "DEBIT_CARD"], "payment_form": "CONTADO"}
```

```json
{"payment_methods": ["CASH", "TRANSFER"], "payment_form": "CONTADO"}
```

```json
{"payment_methods": ["DEBIT_CARD", "CREDIT_CARD"], "payment_form": "CONTADO"}
```

Peticiones completas: [efectivo/débito](examples/pagos-efectivo-debito.json),
[efectivo/transferencia](examples/pagos-efectivo-transferencia.json) y
[débito/crédito](examples/pagos-debito-credito.json). Actualizar la fecha a la del
día de Colombia antes de preparar un documento nuevo.

## Política monetaria implementada

El cálculo de referencia usa `Decimal`, precisión de trabajo explícita y
`ROUND_HALF_EVEN`, con dos decimales para los importes del contrato. La holgura
es una comparación, sin reemplazar el valor recibido. Se mantienen hasta dos
decimales en importes y seis en cantidades; las tarifas aceptadas se serializan
sin truncarlas a dos decimales.

| Control | Política local |
| --- | --- |
| `line_total` frente a cantidad × precio neto − descuentos + cargos | Diferencia absoluta ≤ 2.00 COP. Una base calculada negativa se rechaza. |
| IVA 19/5 de línea frente a base × tarifa / 100 | Diferencia ≤ 2.00 COP; alternativamente, el importe debe ser el múltiplo de diez más cercano y distar ≤ 5.00 COP. |
| `TaxSubtotal/TaxAmount` por impuesto/tarifa | Comparación entre la suma recibida y el cálculo de las bases acumuladas: ≤ 2.00 COP; excepción del múltiplo de diez sólo para IVA. |
| IVA cero, exento y excluido | Importe exactamente cero. |
| Líneas gratuitas | Base de línea exactamente cero; la holgura no crea valor comercial. |
| Otros impuestos de línea y descuentos/cargos porcentuales | Se mantiene igualdad exacta con su cálculo redondeado. No se amplía su tolerancia individual en esta corrección. |
| Subtotal, tributos, retenciones, descuentos y cargos del documento | Igualdad exacta con su detalle. |
| Total pagable | Igualdad exacta con la ecuación siguiente. |

```text
total = subtotal - allowance_total + charge_total + tax_total
        - withholding_total - prepaid_amount + payable_rounding_amount
```

Los márgenes de 2 y 5 COP son alternativos: nunca se suman. El múltiplo de diez
usa HALF_EVEN, incluidos empates. IVA calculado 95 puede aproximarse a 100; 99
no supera la validación por diferir cuatro pesos. IVA 105 puede aproximarse a
100. El servicio no aproxima de oficio todos los IVA a decenas.

La política se comparte entre HTTP y core para FEV, POS, contingencias y notas
soportadas. La regla específica de forma de pago POS se valida aparte.

Cada grupo usa impuesto y tarifa numérica: `19` y `19.00` no dividen un mismo
agregado. Se suma el cálculo sin redondear de base por tarifa y después se
redondea la referencia agregada. Las tarifas diferentes no compensan entre sí
una diferencia inválida. `TaxTotal/TaxAmount` es la suma exacta de los subtotales
informados; no se aplica otra holgura contra esa suma. Las bases explícitas de
valor cero se conservan.

`PayableRoundingAmount` informa un ajuste de redondeo del pagable, explícito y
con signo, debido a la diferencia entre el total calculado y la suma de
parciales. No modifica base ni IVA ni evita sus validaciones. No se crea para
compensar un IVA rechazado, un descuento o un cargo comercial.

## Ejemplo de venta en pesos enteros

Precio comercial con IVA incluido: 1.000 COP; cantidad: 3.333; cobro: 3.333 COP.
El contrato recibe precio **neto**, base e IVA separados:

```json
{
  "line_items": [{
    "description": "Material por metro", "item_code": "MT-1", "unit_code": "MTR",
    "quantity": "3.333", "unit_price": "840.34", "line_total": "2801.00",
    "taxes": [{"tax_type": "IVA_19", "taxable_amount": "2801.00", "amount": "532.00"}]
  }],
  "totals": {"subtotal": "2801.00", "tax_total": "532.00", "total": "3333.00"}
}
```

Cantidad × precio neto = 2800.85322; referencia a dos decimales = 2800.85;
diferencia de base = +0.15 COP. IVA de referencia = 532.19; diferencia = −0.19
COP. Ambos pasan la holgura general. Se emiten base `2801.00`, IVA `532.00` y
pagable `3333.00`, sin descuentos/cargos ni redondeo pagable ficticios.
`840.34` es la extracción a dos decimales que ya hace el adaptador desde
1.000 / 1.19; no cambia el precio de venta ni el ledger.

Diez líneas iguales acumulan −1.90 COP de IVA y pasan. Once acumulan −2.09 COP
y fallan en el agregado, aunque cada línea pase. No se redistribuye la
diferencia: corresponde diagnosticar el caso fiscal conservando la operación.

Los XML de factura, POS y notas, CUFE/CUDE y artefactos de respuesta usan los
importes aprobados. La preparación no transmite. Los reintentos entregan los
bytes firmados persistidos, sin nueva firma.

## Migración de adaptadores

Un adaptador anterior debe revisar estos puntos:

La etiqueta `0.2.0a0` ya existía antes de esta ampliación local. Verificar las
huellas de los wheels del informe y ejecutar los ejemplos nuevos contra el
servicio de destino; la versión por sí sola no demuestra estas capacidades.

1. En `dian/http.adapter.ts`, trasladar todos los `paymentMethods` a
   `document.payment_methods` y omitir `payment_method` cuando se use la lista.
   Mapear `CREDIT_CARD` y `DEBIT_CARD` a los mismos literales. Retirar los
   bloqueos de débito y combinación; mantener el de `VOUCHER` y otros sin mapeo.
2. Mantener `dian-payment.utils.ts` como origen de forma y vencimiento según la
   operación. No inferir CxC desde tarjeta crédito. POS debe llegar contado;
   la emisión de CxC usa el tipo documental permitido.
3. En `dian/canonical-line.ts`, reemplazar la igualdad exacta de IVA por esta
   comparación o delegar la validación fiscal a la API. Conservar cantidades,
   bases, IVA y extracción de precio neto con enteros escalados y HALF_EVEN.
   Si se valida localmente, comprobar también los agregados por tarifa.
4. No convertir automáticamente `base - cantidad × precio` en
   `AllowanceCharge`. El mapper actual lo hace para toda diferencia. Enviar
   sólo descuentos/cargos comerciales identificados. Para los 0.15 COP del
   caso, omitir el ajuste; una diferencia fuera de tolerancia sin causa
   comercial debe continuar bloqueada.
5. Actualizar `canonical-contract.test.ts`: IVA 532, débito y combinación deben
   pasar. Mantener pruebas de medios desconocidos, límites, acumulación,
   descuentos reales y notas parciales; comparar los XML completos.
6. Persistir la lista en snapshots nuevos; conservar payload y XML ya firmados.
   No reconstruir históricos ni recontabilizar. Mantener el bloqueo de cantidad
   cero con residuo y las restricciones de eventos pendientes de otra tarea.

## Fuentes oficiales comprobadas

- [Anexo FEV 1.9](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9.pdf):
  pp.14–15, §5.2.1, HALF_EVEN y tolerancias; FAN01 p.70, CAN01 p.153 y DAN01
  p.233, `1..N`; FAS07 pp.78–79 y FAX07 p.97, cálculo de base/tarifa.
- [Anexo DEE 1.0](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Anexo-Tecnico-Documento-Equivalente-Electronico-V1-0-final.pdf):
  pp.19–20, reglas monetarias; POS DEAN01/02 p.110, `1..N` y forma 1;
  NAAN01 p.591 y NADAN01 p.636, `1..N` en notas de ajuste.
- [Caja FEV 1.9 v2026](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Caja-de-herramientas-FE_V19_v2026.zip)
  y [caja DEE V1-3](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Caja-de-herramientas-Doc-Equivalentes-V1-3.zip):
  se compararon 10/20/30/31/48/49 de ambos `MediosPago-2.1.gc`; coinciden.
  Huellas de los ZIP en el informe de auditoría.
- [Concepto DIAN 3550 de 2026](https://normograma.dian.gov.co/dian/compilacion/docs/oficio_dian_3550_2026.htm):
  confirma la aproximación de IVA por operación al múltiplo de diez del artículo
  1.3.1.1.1 del Decreto 1625 de 2016. El control XML no redefine el registro
  contable del consumidor.

Las pruebas offline y XSD acreditan controles locales y estructura UBL. La
aceptación funcional de DIAN se verifica posteriormente en habilitación.
