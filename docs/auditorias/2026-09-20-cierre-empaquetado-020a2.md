# Cierre local del empaquetado 0.2.0a2 — 20 de septiembre de 2026

## Resultado

Se corrigió la diferencia entre los paquetes aprobados y la imagen instalada.
El candidato `0.2.0a2` integra la política de comprador parcial sobre `main`
`df6637f`, conserva las correcciones de reconciliación de CUFE, crédito a
consumidor final y calendario colombiano, y usa wheels internos verificables.
No se publicaron imágenes ni se activaron servicios o consumidores.

Se eligió una versión nueva porque los wheels históricos `0.2.0a1` procedían de
una base anterior a esas correcciones. Los artefactos `a0`/`a1` se conservaron.

## Artefacto final

El manifiesto versionado es [`release/manifest.json`](../../release/manifest.json).
Registra el commit de construcción `6d9d486a79b78066b3189e91582f3f8438e2ca9c`,
el árbol de paquetes, el lock, herramientas, fecha y hashes de los 41 archivos.

| Wheel interno | SHA-256 |
|---|---|
| `facturacion_dian_api_core-0.2.0a2-py3-none-any.whl` | `8e09f8eefb981296f325803d9238ba6735d6456d5041bcecb2bc2e0e327f2ba4` |
| `facturacion_dian_api_server-0.2.0a2-py3-none-any.whl` | `2f0bdc11af98550ca6e824e0f86fe4181759e3dde80f02fc5f1e9c76c726fdc0` |

Imagen local: `facturacion-dian-api:verified-020a2-6d9d486a`.
ID local: `sha256:3f953b18d3ba53c04ff6d42379d8bc3333589984ad06fada63874d91631bb389`.
`RepoDigests=[]`: **todavía no hay digest publicado**. Ese ID no es una referencia
de registro utilizable para desplegar en otro entorno.

## Validaciones realizadas

- Dos construcciones repetidas con iguales hashes; reproducción independiente
  en Linux y Windows con coincidencia exacta de los wheels finales.
- La imagen instala desde hashes y verifica 41 archivos, rutas de importación,
  versiones y ausencia de instalación editable. `pip check` pasa.
- **541 pruebas pasadas** con los wheels finales instalados en un entorno
  limpio y el runtime del lock. Se proporcionaron los XSD oficiales FE/DEE;
  el transporte externo quedó bloqueado. Una prueba de integración real quedó
  excluida. Advertencia de pytest por AnyIO previamente importado, sin fallos.
- **42 casos del consumidor pasados contra la imagen final** con `--network none`:
  preparación HTTP, firmas, pagos, totales, notas, compradores parciales,
  errores esperados y contenedores. Para eventos se validó el modelo/mapeo;
  no se emitieron eventos reales. El verificador temporal solo cambió la versión,
  hashes y ruta del artefacto; conservó los payloads y expectativas del consumidor.
- Health con certificado sintético vigente, próximo a vencer y ausente; OpenAPI
  y versión HTTP coherentes. Esto no acredita carga de un certificado productivo.
- Validadores de documentación y skill, Ruff, Mypy (41 archivos), actionlint y
  `pip-audit` del lock sin vulnerabilidades conocidas a la fecha de ejecución.
- Gitleaks sobre los seis commits nuevos respecto de `df6637f`: sin hallazgos.
  El escaneo adicional del árbol completo produjo seis alertas sobre valores de
  ejemplo preexistentes en `.env.example`, `tests/conftest.py` y
  `tests/test_cufe.py`, archivos sin cambios respecto de esa base. No se
  introdujeron exclusiones ni se alteró el escáner para ocultarlas.

Los reportes locales están en `dist/release/installed-qa.json` y
`tmp/fiscal-020/` (`linux-reproducibility.json`, `image-runtime.json`,
`image-health.json`, `pinki/results-final.txt`, `pip-audit.json`,
`gitleaks-branch.json`). Las copias experimentales anteriores de `a2` no son el
artefacto final: los hashes de la tabla y el manifiesto lo identifican.

## Cambios de publicación

El Dockerfile recibe un bundle reproducido y aprobado, instala wheels con hashes
y verifica el runtime. La imagen base está fijada por digest. CI reproduce el
manifiesto; release construye y verifica la imagen antes de publicar esa misma
imagen, adjunta los artefactos y registra el digest OCI. Esta rama rechaza tags
OCI de la línea v1 y mantiene la protección de `latest` vigente en `main`.
El dispatch automático requiere confirmación de la versión HTTP exacta del
manifiesto; una confirmación anterior de `0.2.0a0` no activa `0.2.0a2`.

Los workflows se validaron localmente; todavía no se ejecutaron en GitHub para
esta rama. El [procedimiento de despliegue](../despliegue-020a2.md) contiene la
secuencia de revisión, publicación, adopción y activación.

## Pendientes para activar

1. Integrar y publicar la rama revisada; obtener el digest real de la imagen.
2. En el consumidor, incorporar estos wheels, lock y hashes; agregar `a2` a las
   versiones aceptadas y capturarla en decisiones nuevas. Conservar snapshots,
   URLs, colas y artefactos de contratos anteriores. Repetir sus compuertas.
3. Desplegar sus migraciones y cambios de entrega, comprobar configuración real
   y certificado en una instancia candidata y activar progresivamente. La
   verificación local no permite afirmar que esos pasos ya ocurrieron.
4. Mantener el límite AE28 mientras se tramita la consulta oficial: cuando el
   XML original carece de responsabilidad fiscal, el contenedor falla con el
   diagnóstico explícito. Usar la modalidad gráfica solo cuando corresponde y
   con elección/evidencia del consumidor. No sustituirla silenciosamente ni
   inventar una responsabilidad. La [consulta](2026-09-19-consulta-dian-ae28.md)
   está preparada, no radicada.
