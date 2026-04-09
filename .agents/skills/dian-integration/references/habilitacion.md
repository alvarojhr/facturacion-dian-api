# Habilitacion

Usa habilitacion para validar conectividad DIAN y cumplimiento del test set antes de pasar a produccion.

Inputs runtime minimos:

- `DIAN_ENVIRONMENT=habilitacion`
- `DIAN_SOFTWARE_ID`
- `DIAN_SOFTWARE_PIN`
- `DIAN_TEST_SET_ID`
- certificado y password

Secuencia recomendada:

1. Verifica carga local del certificado.
2. Envia un payload conocido y valido.
3. Guarda el `tracking_id`.
4. Consulta `GET /api/v1/documents/submissions/{tracking_id}` hasta obtener resultado funcional.
5. Solo despues de una corrida estable, mueve credenciales y endpoints a produccion.

Lee tambien:

- [`../../../../docs/guia-habilitacion.md`](../../../../docs/guia-habilitacion.md)
- [`../../../../docs/guia-certificados-y-secretos.md`](../../../../docs/guia-certificados-y-secretos.md)
