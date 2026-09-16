# Troubleshooting

Clasifica el problema primero:

- `422`: request invalido respecto al contrato HTTP.
- `503`: configuracion local incompleta o certificado invalido.
- `502`: falla upstream o de transporte con DIAN.
- `504`: timeout DIAN.
- `200` + `status=REJECTED`: rechazo funcional de DIAN.
- `200` + `status=RECEIVED|PENDING`: DIAN recibio el ZIP, pero aun no emitio un
  resultado definitivo; consulta por `tracking_id` y no generes otra firma.
- `200` + `status=UNKNOWN|ERROR`: la respuesta no permite afirmar aceptacion;
  conserva el artefacto y resuelve el estado antes de emitir otro documento.

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
- ante timeout o transporte incierto, reintenta con `signed_xml_base64` y
  `technical_filename` persistidos; no reconstruyas ni vuelvas a firmar.

Guias completas:

- [`../../../../docs/troubleshooting-operativo.md`](../../../../docs/troubleshooting-operativo.md)
- [`../../../../docs/catalogo-errores-dian.md`](../../../../docs/catalogo-errores-dian.md)
