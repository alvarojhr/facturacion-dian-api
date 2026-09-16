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
- si debes retransmitir, usa el XML firmado persistido, su mismo nombre y el mismo `file_sequence`.

## La respuesta sale `rejected`

Checklist:

- lee `messages`;
- inspecciona `dian_response.status_code` y `status_description`;
- revisa `references` en notas;
- valida numeracion y resolucion;
- confirma subtotales, impuestos y total por linea.

## Falta un XML en `artifacts`

Checklist:

- el XML firmado del emisor siempre se devuelve en preparación o envío;
- el AR puede faltar mientras el envío asíncrono siga pendiente;
- consulta el estado en el mismo ambiente hasta obtener el AR definitivo;
- persiste cada artifact por separado y valida su restauración.

## AttachedDocument no sirve para interoperabilidad

Checklist:

- confirma que ambos XML estén firmados;
- valida que el AR sea el resultado `02`, no una respuesta rechazada o pendiente;
- confirma que número, tipo y CUFE/CUDE coincidan entre request, documento y AR;
- usa la fecha y hora del documento firmado; la validación se deriva del AR.

## Un documento histórico devuelve `422`

Un XML nuevo no puede firmarse con fecha de emisión anterior. Recupera el artifact firmado que persististe y envíalo mediante `signed_xml_base64` y `signed_xml_filename`. Si no existe, reconcilia por CUFE/CUDE o tracking antes de decidir el tratamiento contable y fiscal.

## El certificado rotó entre preparación y envío

Completa los envíos preparados antes de retirar el certificado que los firmó. La API verifica los artifacts de reintento contra el certificado del despliegue; conservar la versión anterior durante la reconciliación evita reconstruir el documento.
