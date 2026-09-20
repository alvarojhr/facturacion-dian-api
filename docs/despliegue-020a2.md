# Preparación del despliegue HTTP 0.2.0a2

## Qué cambia

`0.2.0a2` integra el contrato de compradores parciales de `0.2.0a1` sobre
`main` (`df6637f`): conserva la recuperación de `document_key`/QR al consultar
estado, la restricción de crédito para consumidor final, las fechas colombianas
en ejemplos y pruebas, y las protecciones de la línea OCI v1. Los wheels `a0`
y `a1` conservan sus bytes y su función para documentos históricos.

La imagen instala exactamente los dos wheels del manifiesto aprobado con
`--no-index --no-deps --require-hashes`. No contiene un checkout editable. El
verificador comprueba los archivos instalados y sus rutas de importación; una
coincidencia de `/health.version` por sí sola no es suficiente.

## Reproducir los artefactos aprobados

Con Python 3.12, checkout limpio y la historia Git completa:

```powershell
python -m pip install --no-deps --require-hashes -r requirements-build.lock
python scripts/build_reproducible_wheels.py
docker build -t facturacion-dian-api:local-020a2 .
docker run --rm --network none facturacion-dian-api:local-020a2 python -I /opt/dian-release/verify_release.py --artifact-dir /opt/dian-release --runtime
```

El script crea `dist/release/` sin sobrescribir artefactos existentes. Para otra
verificación usa `--output-dir` con una carpeta nueva. Reproduce dos veces desde
los bytes de Git del árbol de paquetes del manifiesto, con herramientas y fecha fijadas.
Debe obtener los mismos hashes revisados en `release/manifest.json`. Rechaza
cambios de runtime posteriores a ese manifiesto.
La comprobación del árbol permite integrar mediante squash sin depender de que
el commit original del candidato siga accesible.
El empaquetado fija los permisos y atributos ZIP, usa LF en el `METADATA`
generado y recalcula `RECORD`. Los archivos Python se conservan byte por byte.
Los miembros ZIP se guardan sin compresión para no depender de la versión de
zlib; las capas de la imagen sí se comprimen normalmente.

Para preparar una versión nueva: cambia las versiones de core/server y sus
metadatos, valida y registra el código en Git; ejecuta el script con
`--candidate --output-dir dist/candidate`. Prueba esos wheels y revisa el
manifiesto antes de copiarlo a `release/manifest.json`. Registra el manifiesto y
repite el modo normal. No cambies el contenido de paquetes aprobados conservando
su número de versión. Los wheels son artefactos internos del servidor y de sus
pruebas; la integración del consumidor continúa siendo HTTP.

## Publicación y adopción coordinada

1. Integrar la rama preparada tras revisión y CI. La automatización de `main`
   crea un tag OCI `v2.x.y`: ese tag y la versión HTTP `0.2.0a2` son distintos.
2. `release.yml` reproduce los paquetes, construye la imagen, comprueba sus bytes
   y el contrato HTTP sin red, y publica la misma imagen comprobada. Adjunta los
   wheels, el manifiesto, el lock y `image-digest.txt` como artefactos del workflow.
3. Usar el digest OCI publicado para desplegar una instancia candidata. El ID
   local de Docker no sustituye ese digest. Conservar v1 y los servicios de
   contratos históricos. El build no demuestra habilitación real ante DIAN.
4. El consumidor debe incorporar los dos wheels y el lock de `dist/release/` en
   sus pruebas de contrato, actualizar hashes, verificador y versión esperada a
   `0.2.0a2`, y probar la imagen por digest. Conservar los artefactos y las rutas
   asociadas a documentos `a0`/`a1`. Validar sus payloads contra los paquetes
   instalados y las modalidades de entrega implementadas.
5. Desplegar las migraciones aditivas y el backend del consumidor antes de
   activar la nueva ruta HTTP. Comprobar `/health`, carga del certificado, perfil
   del emisor, resolución vigente, preparación, consulta/reconciliación y entrega
   con datos de habilitación autorizados. Los certificados y secretos permanecen
   fuera del repositorio.
6. Activar el consumidor progresivamente con rollback de configuración y sin
   reinterpretar snapshots históricos. Solo entonces confirmar
   `DOWNSTREAM_HTTP_CONTRACT=0.2.0a2`; un valor anterior no habilita el dispatch
   automático de esta versión. La variable es una confirmación operativa, no
   una prueba automática de migración.

## Dependencia fiscal todavía abierta: AE28

La aceptación de FE/NC/ND con comprador parcial está implementada. Si el XML
original carece de responsabilidad fiscal, crear su AttachedDocument sigue
devolviendo `ATTACHED_DOCUMENT_BUYER_RESPONSIBILITY_UNRESOLVED`. Es un control
local, no evidencia de rechazo de DIAN. No insertar `R-99-PN` ni otro dato
inventado; tampoco alterar un XML firmado histórico.

El consumidor debe mantener el documento aceptado y gestionar la entrega
pendiente por separado. La representación gráfica requiere que sea aplicable al
comprador y que se registre la modalidad elegida; no es un reemplazo universal
del contenedor electrónico. El POS debe impedir previamente operaciones que su
flujo de ajustes no pueda soportar con el perfil disponible.

La [consulta técnica AE28](auditorias/2026-09-19-consulta-dian-ae28.md) está
preparada, **no radicada**. Una respuesta oficial sobre ese caso sigue siendo
necesaria para habilitar la entrega electrónica universal de compradores sin
responsabilidad informada. Véase la [evidencia normativa y técnica](auditorias/2026-09-19-ae28-entrega-comprador.md).
