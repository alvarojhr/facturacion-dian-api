# StatusCode 98 "En Proceso" — HTTP 0.2.0a5

## Problema y resultado

La DIAN responde `SendBillSync` con `StatusCode 98`, `StatusDescription "En Proceso"`
e `IsValid=false` cuando recibió el documento pero todavía no terminó de
validarlo. El dictamen (00 aceptado o 99 rechazado) se consulta después con
GetStatus.

`DianResponse.is_rejected` sólo miraba `IsValid` y reportaba esa respuesta como
`status="rejected"`. Desde las 21:20 del 2026-09-22 la DIAN respondió 98 a todo
envío: un consumidor mostró 34 facturas como rechazo definitivo aunque sólo
traían notificaciones (FAK26, RUT01).

Ahora `DianResponse.is_in_process` identifica el 98, `is_rejected` lo excluye y
`processing_status` devuelve `"pending"`. Un 99 con `IsValid=false` sigue siendo
`"rejected"`. No cambian el XML, la firma, el CUFE/CUDE ni el contrato HTTP.

## Consumidores

Tratar `pending` como documento transmitido sin dictamen: consultar el estado con
el tracking o la clave original, sin volver a firmar ni renumerar. Documentos ya
almacenados como `rejected` con `dian_response.status_code = "98"` no tienen
dictamen y deben consultarse; esta versión no modifica datos almacenados.

`release/manifest.json` fija la nueva versión 0.2.0a5 y sus hashes reproducibles.
Cambiar el código de este repositorio no actualiza por sí solo servicios fijados
a un digest anterior.
