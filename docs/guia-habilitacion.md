# Guia de habilitacion

Usa esta guia para validar la conectividad y el flujo funcional con DIAN antes de pasar a produccion.

## Requisitos minimos

- `DIAN_ENVIRONMENT=habilitacion`
- `DIAN_LOOKUP_ENVIRONMENT=produccion`
- `DIAN_SOFTWARE_ID`
- `DIAN_SOFTWARE_PIN`
- `DIAN_TEST_SET_ID`
- certificado y password
- datos del emisor y resolucion consistentes

`DIAN_LOOKUP_ENVIRONMENT` es la excepcion deliberada: el registro de
adquirientes (`GetAcquirer`) solo responde en produccion. Si lo dejas caer a
`habilitacion`, vpfe-hab devuelve el sobre `GetAcquirerResponse` con HTTP 404 y
`POST /api/v1/customers/lookup` falla con 502 para cualquier documento. Firmar y
enviar siguen usando `DIAN_ENVIRONMENT`.

## Flujo recomendado

1. Verifica que `/health` responda y que el certificado cargue correctamente.
2. Envia un payload conocido y valido, por ejemplo [`examples/factura-electronica.json`](examples/factura-electronica.json).
3. Primero usa `prepare_only=true`, reserva `file_sequence` y guarda el XML firmado.
4. Transmite ese XML y guarda `tracking_id`, `submission_id`, CUFE/CUDE y nombre técnico.
5. Consulta `GET /api/v1/documents/submissions/{tracking_id}?environment=habilitacion` hasta recibir resultado funcional.
6. Guarda el `ApplicationResponse` DIAN y construye el `AttachedDocument` para los casos de entrega.
7. Repite la matriz descrita en [implementación de la auditoría fiscal](auditorias/2026-09-15-implementacion-auditoria-fiscal.md).
8. Solo después de corridas estables cambia secretos y endpoints a producción.

## Que revisar si falla

- `messages`
- `dian_response.status_code`
- `dian_response.status_description`
- variables `DIAN_*`
- consistencia entre resolucion, prefijo y numeracion

## Criterios practicos para pasar a produccion

- la API carga certificado sin degradacion;
- los payloads base pasan sin ajustes manuales;
- el polling de estado devuelve resultados coherentes;
- factura, notas, ajustes DEE y contingencias usadas tienen AR aceptado y evidencia restaurable;
- los XML canónicos pasan el XSD de la caja DIAN que se desplegará;
- el equipo ya tiene definidos procedimientos de rotacion de secretos y monitoreo.
