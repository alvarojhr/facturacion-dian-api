# Catalogo de errores y rechazos DIAN

Esta guia no intenta cubrir todo el anexo tecnico. Resume las clases de error que mas impactan integraciones reales.

## Errores del contrato HTTP

### `422`

La API rechazo el request antes de hablar con DIAN.

Senales tipicas:

- falta un bloque como `document`, `buyer` o `line_items`;
- un nombre de campo no coincide con el contrato;
- el tipo documental no corresponde al shape enviado.

## Errores de configuracion local

### `503`

La API no pudo operar localmente.

Causas frecuentes:

- certificado ausente;
- password invalido;
- `DIAN_SOFTWARE_ID` faltante;
- `DIAN_SOFTWARE_PIN` faltante;
- `DIAN_TEST_SET_ID` faltante en habilitacion;
- `DIAN_TECHNICAL_KEY` faltante cuando aplica.

## Errores upstream

### `502`

Hubo falla de transporte o DIAN devolvio una respuesta no funcionalizable.

Causas frecuentes:

- indisponibilidad del servicio DIAN;
- corte de red;
- respuesta SOAP inesperada;
- falla WS-Security o de certificado en el intercambio.

### `504`

DIAN no respondio a tiempo. Tratalo como indisponibilidad upstream, no como rechazo de negocio.

## Rechazos funcionales de DIAN

### `200` con `status=rejected`

DIAN recibio y proceso el documento, pero lo rechazo funcionalmente.

Patrones comunes:

- numeracion ya procesada o inconsistente;
- referencias incompletas en notas;
- adquiriente insuficiente o inconsistente;
- totales e impuestos que no cuadran;
- datos del emisor o resolucion incoherentes.

Cuando ocurra:

1. revisa `messages`;
2. inspecciona `dian_response`;
3. identifica el bloque implicado (`document`, `resolution`, `buyer`, `references`, `totals`, `line_items`);
4. corrige el payload y reintenta con un numero nuevo si el error ya consumio numeracion.
