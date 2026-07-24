# Troubleshooting

Clasifica el problema primero:

- `422`: request invalido respecto al contrato HTTP.
- `503`: configuracion local incompleta o certificado invalido.
- `502`: falla upstream o de transporte con DIAN.
- `504`: timeout DIAN.
- `200` + `status=rejected`: rechazo funcional de DIAN.

Checks rapidos:

- confirma endpoint y nombres de campo del contrato oficial;
- revisa `messages` y `dian_response`;
- valida certificado, password y variables `DIAN_*`;
- verifica si el error pertenece a negocio DIAN o a operacion local.

Eventos RADIAN (`POST /api/v1/events`):

- el rechazo llega como `200` + `status=REJECTED`; las reglas fallidas vienen en
  `messages` con el prefijo `Regla: <ID>`;
- `Regla: AAD06` (UUID mal calculado) apunta al CUDE del evento: revisa que
  `event_number`, fecha/hora y NITs sean los mismos que quedaron en el XML;
- `Regla: AAD09e` significa que la fecha del evento no coincide con la de la
  firma: revisa el reloj y la zona horaria del despliegue (`-05:00`);
- `Regla: AAH11`/`AAH12`/`AAH15` piden `receiver_person`;
- un rechazo por orden de eventos indica que falta el `030` o el `032` previo:
  esa secuencia la controla el integrador, no la API.

Guias completas:

- [`../../../../docs/troubleshooting-operativo.md`](../../../../docs/troubleshooting-operativo.md)
- [`../../../../docs/catalogo-errores-dian.md`](../../../../docs/catalogo-errores-dian.md)
