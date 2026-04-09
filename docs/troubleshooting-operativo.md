# Troubleshooting operativo

## La API responde `503`

Checklist:

- confirma que `DIAN_CERT_PATH` apunta al archivo correcto;
- valida el password del certificado;
- revisa `DIAN_SOFTWARE_ID`, `DIAN_SOFTWARE_PIN` y `DIAN_TEST_SET_ID`;
- confirma si el request depende de `DIAN_TECHNICAL_KEY`.

## La API responde `502`

Checklist:

- revisa si DIAN esta disponible;
- confirma conectividad saliente desde el runtime;
- vuelve a intentar si el error fue intermitente;
- conserva logs del request y del response SOAP para soporte.

## La API responde `504`

Checklist:

- trata el evento como timeout upstream;
- evita marcar el documento como rechazado de negocio;
- repite consulta de estado si ya tenias `tracking_id`;
- reintenta envio solo si el flujo de negocio lo permite.

## La respuesta sale `rejected`

Checklist:

- lee `messages`;
- inspecciona `dian_response.status_code` y `status_description`;
- revisa `references` en notas;
- valida numeracion y resolucion;
- confirma subtotales, impuestos y total por linea.

## No aparece XML en `artifacts`

Checklist:

- revisa si el caller envio `submission_options.return_xml_artifact=false`;
- para status, valida si DIAN devolvio XML en la consulta;
- confirma que el flujo aceptado persista los artifacts requeridos aguas abajo.

## AttachedDocument no sirve para interoperabilidad

Checklist:

- revisa `document_type_code`;
- valida `reply_to_email` y `receiver_email`;
- confirma que el XML base64 corresponde al documento firmado esperado;
- revisa `cufe` y fecha de emision.
