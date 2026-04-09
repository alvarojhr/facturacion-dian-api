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

Guias completas:

- [`../../../../docs/troubleshooting-operativo.md`](../../../../docs/troubleshooting-operativo.md)
- [`../../../../docs/catalogo-errores-dian.md`](../../../../docs/catalogo-errores-dian.md)
