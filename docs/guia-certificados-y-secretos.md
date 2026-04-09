# Guia de certificados y secretos

La API necesita secretos y material criptografico para firmar y hablar con DIAN. Mantenlos fuera del repositorio.

## Que debes aportar

- certificado `.p12` o `.pfx`
- password del certificado
- `DIAN_SOFTWARE_ID`
- `DIAN_SOFTWARE_PIN`
- `DIAN_TEST_SET_ID` en habilitacion
- `DIAN_TECHNICAL_KEY` cuando aplique

## Reglas basicas

- No subas certificados ni passwords al repo.
- No hardcodees secretos en ejemplos, tests ni docs.
- Usa rutas montadas por volumen o secretos del orquestador.
- Manten separados secretos de habilitacion y produccion.

## Variables relevantes

- `DIAN_CERT_PATH`
- `DIAN_CERT_PASSWORD`
- `DIAN_SOFTWARE_ID`
- `DIAN_SOFTWARE_PIN`
- `DIAN_TEST_SET_ID`
- `DIAN_TECHNICAL_KEY`

## Recomendaciones operativas

- monta el certificado con permisos minimos;
- rota credenciales si un `.env` se expone;
- evita compartir el mismo secreto entre ambientes;
- valida localmente que la API cargue el certificado antes de enviar documentos.

## Pitfalls comunes

- ruta relativa del certificado distinta entre local y contenedor;
- password incorrecto;
- certificado vencido;
- olvidar `DIAN_TEST_SET_ID` en habilitacion;
- usar un `technical_key` demo en ambiente real.
