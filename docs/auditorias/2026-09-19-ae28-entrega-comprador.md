# AE28 y entrega a compradores sin responsabilidad fiscal conocida

Fecha de revisión: 19 de septiembre de 2026, Colombia.

## Resultado

**El caso de AttachedDocument sigue sin una representación acreditada para
responsabilidad desconocida. La investigación no permite liberar ese recorrido.**
Se entrega una [consulta técnica lista para radicar](2026-09-19-consulta-dian-ae28.md)
y un [reproductor ejecutable](../../scripts/reproduce_ae28.py) con evidencia
sintética. La consulta no se ha enviado.

La preparación de la factura sin responsabilidad del comprador ya está resuelta
en los wheels locales `0.2.0a1`, commit de implementación
`3b88ff44eff9c865cfffde13a9874499f8ceeb3a`. El error de contenedor es una decisión
local pendiente de aclaración técnica, no un rechazo observado de DIAN ni una
obligación general de pedir responsabilidades al cliente.

**Hay una modalidad de entrega con respaldo independiente de AE28:** la
representación gráfica para adquirentes que no son facturadores electrónicos,
según el medio autorizado. Su aplicación exige establecer ese supuesto; CC,
NIT o perfil fiscal incompleto no permiten deducirlo.

## Evidencia y alcance de las fuentes

| Fuente revisada | Resultado relevante |
|---|---|
| [Micrositio de documentación técnica DIAN](https://micrositios.dian.gov.co/sistema-de-facturacion-electronica/documentacion-tecnica/) | Continúa enlazando el anexo FE 1.9 y la caja de herramientas v2026. |
| [Anexo FE 1.9](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9.pdf), pp. 54 y 265 | FAK26 opcional; AE28 obligatorio. AE29 no proporciona un valor sustituto. |
| Mismo anexo, apartado 8.5, p. 598 | AttachedDocument es un tipo de documento no validado. No cabe presentar la aceptación de la factura como aprobación del contenedor. |
| Mismo anexo, apartado 9.1, p. 635 | El recorrido de interoperabilidad descrito incluye el contenedor en ZIP. Un ZIP de XML sueltos no acredita ese cumplimiento. |
| Mismo anexo, apartado 9.3, p. 638 | Regula otras modalidades para adquirentes que no son facturadores electrónicos. |
| [Caja v2026 descargada nuevamente](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Caja-de-herramientas-FE_V19_v2026.zip) | El PDF incluido coincide byte por byte con el ya revisado. Los 44 XML de ejemplificación no contienen un documento raíz AttachedDocument. |
| Catálogo `13.2.6.1`, celda C7 | Describe R-99-PN como «No aplica – Otros *». No contiene una instrucción sobre AE28 desconocido. Se revisaron celdas, comentarios y textos auxiliares del archivo. |
| [Control de cambios 1.8](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Control-de-Cambios-Anexo-Tecnico-1-8-DIAN.pdf), p. 10 | La explicación histórica de R-99-PN corresponde a no tener las otras cuatro responsabilidades; no declara equivalencia con desconocerlas. No se usa este documento anterior para sustituir reglas actuales. |
| [Resolución 227 compilada](https://normograma.dian.gov.co/dian/compilacion/docs/resolucion_dian_0227_2025.htm), arts. 1.5.1.12.3 y 1.5.1.5.5.1 | Limita los datos exigibles al comprador y distingue las modalidades de entrega según el adquirente. |

Las búsquedas oficiales por AE28, TaxLevelCode, responsabilidades desconocidas y
AttachedDocument no localizaron una aclaración que resuelva el supuesto. Eso no
prueba que tal aclaración no exista. No se adoptaron implementaciones de terceros,
proyectos de resolución ni usos de códigos antiguos como autorización normativa.

### Huellas de las fuentes descargadas

| Archivo | SHA-256 |
|---|---|
| Caja FE v2026 ZIP | `22705b20c8478485d956cb61476b0743bb5d16e45c4e5bed11023fc1e04adfea` |
| Anexo FE 1.9 PDF dentro de la caja | `1b4022ac112232cd525a455432b2bdfc977d2edcf14c1c7aa26f8ba93fe47ded` |
| Tabla 13.2.6.1 responsabilidades XLSX | `fa53659acdada05d610df028018f6458f9a745039da2f03475acb3b1a2348dfc` |
| Tabla 13.2.6.2 tributos XLSX | `17180fc5142ced3f3342050b7cbbc4524b2c0502d1b08b6e93f2fd05dcb88d9f` |

## Verificación con los wheels instalados

Se ejecutó `scripts/reproduce_ae28.py` usando Python aislado (`-I`), paquetes
instalados no editables `core/server 0.2.0a1`, certificado RSA efímero y XSD de la
caja oficial. La configuración se aisló de `.env` e identidades de despliegue.
Las conexiones externas se bloquearon; el transporte DIAN fue simulado.

| Caso | Preparación y firma | Aceptación simulada y reintento | Contenedor |
|---|---|---|---|
| CC sin responsabilidad ni tributo | HTTP 200, firma y XSD correctos | Estado `accepted`; mismos bytes del original, sin reconstruir ni firmar otra vez | HTTP 422 local; no se devuelve ZIP |
| Misma identidad con O-13;O-15 informadas | HTTP 200, firma y XSD correctos | Estado `accepted`; mismos bytes del original | HTTP 200; ZIP, firma y XSD correctos; XML y AR embebidos idénticos |

Se hicieron además cuatro experimentos **de esquema, en memoria, no entregables**:
AE28 omitido, vacío, R-99-PN y un código inventado. Todos pasan el XSD UBL incluido
en la caja. Por tanto, un test XSD verde no decide la cardinalidad ni el catálogo
del perfil DIAN. Los experimentos no se habilitan como comportamiento del servicio.

Los archivos de la reproducción final, con hashes individuales, se encuentran en
`tmp/fiscal-020/ae28-investigation/reproduction-final/results.json`. No se exportaron claves
privadas. Los XML tienen identificadores y certificados sintéticos; el AR no
procede de DIAN. Las firmas demuestran integridad local, no aceptación tributaria
ni confianza en una identidad DIAN real.

Para repetir con un venv que tenga los wheels y las dependencias de prueba:

```powershell
& '<venv>\Scripts\python.exe' -I scripts/reproduce_ae28.py `
  --output '<directorio-nuevo-de-evidencia>' `
  --fe-xsd-dir '<caja-oficial>\XSD\maindoc'
```

El comando exige una carpeta de salida nueva para conservar evidencia previa.
Genera firmas nuevas en cada ejecución; sus bytes no se anuncian como reproducibles.
Lo reproducible es el procedimiento y sus resultados de validación.

La suite completa volvió a pasar contra los wheels instalados: **524 pruebas**,
20,82 segundos, sin omisiones; un aviso de pytest sobre reescritura de asserts
de AnyIO ya importado. También pasaron Ruff, mypy (41 archivos), el validador de
documentación pública, el de la habilidad y `git diff --check`. Los 20 archivos
XSD usados coinciden con la caja descargada en esta revisión. No se reconstruyó
la imagen ni se repitió la auditoría de dependencias porque el runtime y sus
dependencias no cambiaron.

## Modalidades de entrega: decisión para Pinki

Esta matriz es una propuesta de integración fundamentada en el artículo
1.5.1.5.5.1. No está implementada ni desplegada en Pinki en esta tarea.

| Supuesto acreditado | Recorrido |
|---|---|
| Adquirente facturador electrónico | Aplicar el numeral 1: XML y validación en contenedor, con representación gráfica. Si AE28 no puede resolverse, registrar el pendiente de entrega. |
| Adquirente no facturador electrónico que autoriza representación gráfica digital | Aplicar el numeral 2.1: entregar por el medio autorizado. Esta modalidad no exige convertir el PDF en un AttachedDocument. |
| Adquirente no facturador electrónico, entrega impresa o sin medio señalado | Aplicar numerales 2.3 y 2.5. Registrar la entrega material; generar un PDF no equivale a haberlo entregado. |
| Adquirente no facturador electrónico que elige XML y validación | Aplicar numerales 2.2 o 2.4: se mantiene el contenedor y su pendiente AE28. |
| Condición del adquirente desconocida | No inferirla de CC, NIT, ausencia de responsabilidades ni tributo ZZ. La falta de AE28 no activa automáticamente una entrega sólo PDF. |

Para llevar esta matriz al ERP hacen falta datos de modalidad elegida y su
evidencia, separar aceptación DIAN de entrega, conservar el XML/AR original y
evitar que un error al empaquetar cause reemisión o duplicación de correo.
La representación gráfica debe cumplir los requisitos del parágrafo 1 del mismo
artículo, incluido QR cuando corresponde. Esta revisión no certifica el PDF actual
de Pinki ni cambia su protocolo de envío.

La modalidad de representación gráfica cubre los supuestos indicados; no cierra
la compatibilidad universal con AttachedDocument ni se extiende automáticamente
a notas y otros documentos con reglas propias.

## Decisión y trabajo pendiente

1. Radicar la consulta y conservar número de radicado y respuesta oficial.
   El borrador no solicita datos personales ni fiscales de clientes reales.
2. Con la respuesta, implementar la representación de AE28 que proceda, limitada
   al contenedor si corresponde, y añadir la prueba completa del caso desconocido.
3. Si Pinki adopta la modalidad gráfica para los casos permitidos, implementar
   expresamente selección, evidencia y estado de entrega en su propia tarea.
4. Construir una nueva versión sólo cuando cambie el comportamiento del servicio;
   integrar wheels/hashes y verificar la imagen y las pruebas del ERP antes del corte.

No se modificó el runtime de los paquetes, no se regeneraron wheels ni se
movieron etiquetas. Este avance agrega diagnóstico y documentación al checkout
aislado. FE, Pinki y el workspace original se conservan. No hubo publicación,
despliegue, radicación, envío de correo ni transmisión real a DIAN.
