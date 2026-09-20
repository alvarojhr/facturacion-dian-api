# Eventos recuperables HTTP 0.2.0a3

La versión separa preparación, transmisión y conciliación de eventos 030/031/032/033.
El integrador conserva su estado y los artefactos; el servicio continúa stateless.
El protocolo y sus límites están en [integración HTTP](integracion-http.md#preparación-recuperable-de-eventos-http-020a3).

El bloque opcional `issuer` elimina la dependencia de identidad de ejemplo en
despliegues que reciben sus perfiles por petición. No altera el certificado.
La primera preparación puede fijar fecha y hora del día colombiano; un XML
persistido conserva las originales. La verificación de reenvíos contrasta
también CUFE referenciado, proveedor, ambiente, persona y causal, campos que
la semilla del CUDE no cubre por completo.

Los documentos FE/NC conservan el contrato anterior. Publicar nuevos wheels y
una imagen por digest siguiendo el [procedimiento de publicación](despliegue-020a2.md);
no sustituir paquetes ni servicios históricos que recuperen documentos pendientes.

Las pruebas usan certificados efímeros y transporte DIAN simulado: comprueban
ausencia de envío durante preparación, igualdad de bytes en reenvío y consulta
del CUDE sin transmisión. No constituyen emisión ni aceptación fiscal real.
