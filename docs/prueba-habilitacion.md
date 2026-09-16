# Prueba controlada en habilitacion

La suite normal no llama a DIAN. La prueba `integration` sólo se habilita de
forma explícita y exige que los payloads reales vivan fuera del repositorio
público.

Prepara, en orden, los JSON de factura electrónica, documento equivalente POS,
nota crédito y nota débito. Cada archivo debe usar el contrato canónico, declarar
`"environment": "habilitacion"` y contener numeración/credenciales válidas del
emisor. No reutilices los valores demo de `docs/examples`.

```powershell
$env:DIAN_LIVE_TESTS = "1"
$env:DIAN_INTEGRATION_PAYLOADS = @(
  "C:\ruta-privada\01-factura.json",
  "C:\ruta-privada\02-pos.json",
  "C:\ruta-privada\03-nota-credito.json",
  "C:\ruta-privada\04-nota-debito.json"
) -join [IO.Path]::PathSeparator
$env:DIAN_INTEGRATION_TIMEOUT_SECONDS = "240"
python -m pytest tests/test_habilitation_integration.py -m integration -s
```

La prueba valida submit, consulta de estado, CUFE/CUDE reportado por DIAN, QR,
XML firmado y `ApplicationResponse`. La salida sólo muestra nombre del archivo
y hashes cortos de los identificadores; no guarda payloads, tokens ni XML.

Ejecuta esta matriz con autorización del responsable operativo: consume
numeración/test set y produce efectos externos. Un rechazo funcional de DIAN
falla el gate aunque llegue por HTTP 200.
