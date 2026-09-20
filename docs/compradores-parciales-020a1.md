# Compradores identificados con datos fiscales desconocidos — 0.2.0a1

## Estado y alcance

La API admite compradores identificados sin responsabilidades ni tributo conocidos
en FE, NC, ND y POS. Conserva nombre, documento y tipo de persona. La **entrega
electrónica con AttachedDocument queda bloqueada cuando el XML firmado carece
de TaxLevelCode del comprador**: no se acreditó una representación oficial de
«desconocido» para AE28, que es obligatorio. Este build no resuelve esa dependencia
ni acredita aceptación DIAN real.

La revisión posterior distingue ese bloqueo del contenedor de las modalidades
de entrega por representación gráfica permitidas para adquirentes que no son
facturadores electrónicos. No permite deducir esa condición de un perfil fiscal
incompleto. Véanse el [informe focalizado de AE28](auditorias/2026-09-19-ae28-entrega-comprador.md)
y la [consulta técnica preparada para DIAN](auditorias/2026-09-19-consulta-dian-ae28.md).

Se propone `0.2.0a1`, siguiente alfa de los paquetes core/server. El servidor fija
core exactamente a esa versión. Los artefactos `0.2.0a0` se conservan; la versión
Python es independiente de las etiquetas OCI `v1.*`. No hay publicación ni despliegue.

## Contrato y política por familia

| Familia soportada | Responsabilidad desconocida | Tributo desconocido |
|---|---|---|
| Factura electrónica y sus tipos de contingencia | Omitir TaxLevelCode completo | Serializar ZZ / No aplica |
| Nota crédito FE | Omitir TaxLevelCode completo | Serializar ZZ / No aplica |
| Nota débito FE | Omitir TaxLevelCode completo | Serializar ZZ / No aplica |
| POS electrónico y sus tipos de contingencia | Omitir TaxLevelCode completo | Serializar ZZ / No aplica |
| Ajustes DEE crédito/débito | Requieren responsabilidad conocida para preparar un identificado | Serializar ZZ / No aplica |
| Consumidor final | Regla específica R-99-PN | ZZ / No aplica |
| AttachedDocument | AE28 no permite omisión: error explícito si falta en el original | Copiar el par del XML firmado |

Esta tabla no extiende la política a otras modalidades DEE no implementadas por
la API, ni certifica otras reglas de identificación de las notas DEE.

- `tax_level_code` omitido o `null` es desconocido. `""`, espacios, códigos fuera
  del catálogo y listas mal formadas son errores. Se conservan varios códigos
  separados por `;`. Catálogo: O-13, O-15, O-23, O-47, R-99-PN; máximo 30 caracteres.
- El par `tax_scheme_id` / `tax_scheme_name` puede faltar o ser `null` en ambos
  campos. Si se informa, debe coincidir exactamente con 01/IVA, 04/INC,
  ZA/IVA e INC o ZZ/No aplica. Un campo suelto, vacío o incompatible es error.
- El fallback ZZ/No aplica vive en la serialización. HTTP, mapper y core conservan
  los `None`: no hay actualización ni clasificación del perfil del cliente.
- CC/CE/TI/PASSPORT admiten omitir `additional_account_id`: al serializar corresponde
  persona natural (`2`). No implican ninguna responsabilidad ni tributo.
- NIT exige `additional_account_id` confirmado (`1` o `2`), también en el core.
  Los consumidores directos que antes dependían del NIT para inferir persona
  jurídica deben informar ese dato y el tipo documental.
- Consumidor final se reconoce por `FINAL_CONSUMER`, el identificador DIAN exacto
  `222222222222`, o el caso compatible sin tipo ni número. Su persona debe ser
  natural. Una CC explícita sin número, números en blanco o identificadores
  contradictorios no se transforman en consumidor final. No se usan heurísticas
  de nombre, longitud o prefijo. Los valores explícitos inválidos no se toleran.
- El emisor mantiene su validación completa, DV y configuración. Las reglas de
  importes, pagos, tolerancias, referencias, resolución, ambiente y firma no se
  flexibilizan. No se habilitan eventos.

Ejemplos completos de preparación con datos sintéticos:

- [CC sin responsabilidades ni tributo](examples/comprador-cc-parcial.json).
- [NIT con persona y tributo confirmados](examples/comprador-nit-parcial.json).

## Contenedor y evidencia histórica

`receiver_tax_level_code` es opcional en HTTP/core y funciona como afirmación
contra el original. Si el XML firmado contiene responsabilidades, se copian de
allí; si el request las informa, deben coincidir. Una petición contradictoria se
rechaza. El contenedor también verifica nombre, número, tipo documental y DV de
las partes contra el documento firmado, y copia su tributo en lugar de imponer IVA.

Si el original no contiene responsabilidades del comprador, la respuesta es 422:

```text
ATTACHED_DOCUMENT_BUYER_RESPONSIBILITY_UNRESOLVED
```

El error se mantiene aunque el caller envíe R-99-PN: un catálogo actual del ERP no
puede completar silenciosamente un documento histórico. No se genera un ZIP que
aparente estar listo para entregar. Hace falta una aclaración oficial aplicable a
AE28 o una representación respaldada por DIAN; R-99-PN, un elemento vacío y la
omisión no se aceptan como soluciones inferidas.

Con responsabilidades conocidas se genera y firma el contenedor y se empaqueta
en ZIP. La factura y el AR se verifican criptográficamente y se conservan byte a
byte, incluidas firma, huella y referencias. La información del contenedor se
extrae sin reescribir ni volver a firmar el original. Se conserva BOM UTF-8;
si hay CR se usan referencias de carácter para evitar la normalización de XML 1.0.
Los documentos habituales se embeben en CDATA. AE17/AE29, si se informan, usan
`listName="No aplica"`; ese atributo no es un sustituto del valor de AE28.

`signed_xml_base64` y `signed_xml_filename` siguen reutilizando el artefacto
preparado. Las nuevas exigencias de responsabilidad DEE se aplican a preparación,
sin reconstruir un reintento firmado. El caller conserva el snapshot original.

## Evidencia oficial consultada el 19 de septiembre de 2026

1. [Resolución 000227 de 2025, artículo 1.5.1.12.3](https://normograma.dian.gov.co/dian/compilacion/docs/resolucion_dian_0227_2025.htm):
   limita los datos exigibles al comprador a nombre, identificación y correo
   para entrega electrónica. No establece una codificación de desconocido en AE28.
2. [Anexo FE 1.9, 753 páginas](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9.pdf):
   FAK26, CAK26 y DAK26 son 0..1 en páginas 54, 137 y 211. La regla FAK26 es
   notificación (406), mientras CAK26 y DAK26 rechazan valores informados inválidos
   (483 y 550). La ausencia estructuralmente permitida no autoriza valores inválidos.
   TaxScheme/ID/Name son obligatorios (57); FAK39/40/41 (408) no permiten suprimirlos.
   AE28 es 1..1 (265). AE29 regula sólo su atributo opcional listName.
   La nota de la tabla PartyTaxScheme (687) permite ZZ cuando el emisor/adquiriente
   no cuenta con los detalles de los tres códigos tributarios precedentes.
3. [Anexo DEE 1.0, 1546 páginas](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Anexo-Tecnico-Documento-Equivalente-Electronico-V1-0-final.pdf),
   enlazado por el [micrositio oficial y caja 1.3](https://micrositios.dian.gov.co/sistema-de-facturacion-electronica/marco-normativo-y-documentacion-tecnica-del-doc-equivalente-electronico/):
   POS DEAK26 es 0..1 (52); NAAK26 y NADAK26 son 1..1 (582 y 623).
   La tabla 16.5.5 (1452) respalda ZZ/No aplica cuando no se conocen detalles
   tributarios, para personas naturales o jurídicas. La tabla de responsabilidades
   16.5.4.1 (1451–1452) no define R-99-PN como «desconocido».

Se descargaron nuevamente ambos PDF; las tablas AE28 y NAAK26 se verificaron
también visualmente. No se encontró en las fuentes consultadas una modificación
que autorice omitir AE28 o trasladar automáticamente la opcionalidad de FE a DEE.

| PDF | SHA-256 |
|---|---|
| FE 1.9 | `1b4022ac112232cd525a455432b2bdfc977d2edcf14c1c7aa26f8ba93fe47ded` |
| DEE 1.0 | `127058a6c3ef94d74de9b5c3773891941fdc3f96f028eee28f9a07827dd1d13d` |

## Compatibilidad y preparación de consumidores

Los perfiles completos mantienen sus datos; se añaden fixtures de factura y NC
generados por los mappers reales de FE y 34 requests sintéticos aprobados de
Pinki (29 positivos, cinco negativos). Sólo se actualiza la fecha de emisión al
ejecutar las pruebas. Los datos comerciales de esos casos no se alteran.

La validación XSD de la NC parcial de Pinki detectó un defecto previo: el helper
compartido ordenaba AllowanceCharge antes de TaxTotal en todas las líneas. UBL
exige ese orden para factura y el inverso para líneas de NC/ND. Se corrige sólo
el orden de nodos; no cambian descuentos, impuestos, cantidades ni totales.
Los reintentos firmados mantienen sus bytes anteriores.

FE conserva en su prueba de contrato una expectativa que rechaza el perfil sin
responsabilidades: debe actualizarla. Su expectativa antigua sobre tarjeta débito
también pertenece a otra revisión del contrato. Esta tarea no modifica los ERP
ni afirma que todas sus suites o despliegues estén listos.

Procedencia de los fixtures revisados (ambos checkouts tenían cambios locales):

- FE HEAD `1d662beea956cbaea5cf2a2dcc7392fbb2a46ef8`; fixture fiscal SHA-256
  `d48044f1606e216f3519ea62d9262be78ad6ad39e93ca4644a72e3e18b87e5e0`.
- Pinki HEAD `46d49f5806d14321280cef7b24973e2289e97602`; requests.json SHA-256
  `28f4c8b70c15f0f5732b0f26a1233c12c90c877447a69a80bdad176ee74efcc5`.

Para preparar el despliegue posterior en la tarea de Pinki:

1. Revisar el commit y el manifest del build, incluida la dependencia pendiente de
   AE28. No activar indiscriminadamente la entrega de compradores sin responsabilidad.
2. Incorporar los dos wheels `0.2.0a1` aprobados en `scripts/canonical-artifact/`;
   actualizar sus requirements y hashes con `requirements-wheels.txt` y manifest.
   Conservar `0.2.0a0` y su configuración para recuperación de documentos anteriores.
3. Actualizar fixtures y expectativas: CC parcial, NIT con persona confirmada,
   pares inválidos, omisión/null, responsabilidades múltiples, ajustes DEE,
   contenedor conocido y error explícito de AE28. No guardar ZZ/R-99-PN como perfil
   deducido del cliente. No habilitar eventos al actualizar esta dependencia.
4. Repetir las pruebas de contrato contra los wheels instalados, sin editable ni
   checkout inyectado. Verificar `/health.version=0.2.0a1` y las capacidades mediante
   preparación real con certificado efímero, firma, XSD y reintentos sin transporte real.
5. Construir la imagen candidata y registrar su ID/digest real. Ejecutar smoke de
   esa imagen para preparación, contenedor conocido, bloqueo AE28 y ZIP. La imagen
   de esta tarea es sólo local y no constituye un digest publicado para Cloud Run.
6. Revisar snapshots históricos y los metadatos que se derivan del XML firmado.
   Coordinar publicación y activación canónica en una tarea posterior, una vez
   resueltas las dependencias de entrega y las verificaciones de habilitación.

## Build y verificación reproducibles

Se trabaja en un checkout aislado, rama `codex/optional-buyer-fiscal-profile`.
Su base `25a6adc` es una instantánea explícita del trabajo local anterior sobre
`020c6206ea2764c00e9a62562ff39a12a6270e50`; no representa cambios nuevos de esta tarea.
El checkout original, FE y Pinki se conservan. No había AGENTS.md en este repositorio
ni en sus directorios padre consultados. Se siguieron los checks de CI existentes.

Comandos, desde el checkout aislado (Python 3.12 y dependencias instaladas):

```powershell
python -m ruff check .
python -m mypy packages/core/src packages/server/src
python scripts/validate_public_docs.py
python scripts/validate_skill.py
# Rutas locales de XSD/maindoc de las cajas oficiales verificadas:
$env:DIAN_FE_XSD_DIR = '<caja FE>/XSD/maindoc'
$env:DIAN_DEE_XSD_DIR = '<caja DEE>/XSD/maindoc'
python -m pytest
python scripts/validate_canonical_xml_xsd.py --xsd-dir $env:DIAN_FE_XSD_DIR
python scripts/validate_canonical_xml_xsd.py --xsd-dir $env:DIAN_DEE_XSD_DIR
# Requiere árbol limpio y setuptools>=75 + wheel, instalados previamente:
python scripts/build_reproducible_wheels.py
```

El script usa `git archive HEAD`, dos directorios de construcción limpios y
`SOURCE_DATE_EPOCH` del commit. Exige wheels idénticos entre ambos builds; nunca
sobrescribe un directorio anterior. Genera `dist/buyer-profile-<commit>/manifest.json`
con commit/tree, versión de herramientas, versiones de paquetes, hashes del
código comprometido y SHA-256 de ambos wheels, más requirements con hashes.

El control pip-audit detectó dos vulnerabilidades previas en AnyIO 4.13.0
([CVE-2026-63374](https://github.com/agronholm/anyio/security/advisories/GHSA-82r6-8w77-94w6)
y [CVE-2026-64847](https://github.com/agronholm/anyio/security/advisories/GHSA-5p39-cfhj-2xmp)).
Se actualiza únicamente AnyIO a 4.14.2 en requirements.lock, con hashes oficiales
de PyPI. Pinki debe incorporar también este lockfile aprobado en la imagen candidata.

Instalar en un venv nuevo las dependencias runtime/dev, después ambos wheels
con `--no-deps --no-index --require-hashes -r requirements-wheels.txt`. Ejecutar:

```powershell
<venv>/Scripts/python.exe -I scripts/validate_installed_wheels.py `
  --artifact-dir dist/buyer-profile-<commit> `
  --fe-xsd-dir $env:DIAN_FE_XSD_DIR --dee-xsd-dir $env:DIAN_DEE_XSD_DIR
```

Este smoke confirma ubicación y versión de los módulos realmente instalados,
prohíbe red externa, valida health, ejecuta la suite sin `pythonpath` del checkout
y registra `installed-qa.json`. Las pruebas usan certificados efímeros y un AR
sintético; ningún resultado de mocks, firmas o XSD se presenta como aceptación DIAN.
Los resultados finales, hashes, commit e ID local de imagen se entregan juntos
en el reporte de artefactos del build. La entrega electrónica sin AE28 permanece
pendiente aunque los checks técnicos resulten satisfactorios.
