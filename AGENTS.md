# AGENTS.md — Guía para cualquier agente de IA que modifique este repo

> Este archivo está escrito para agentes de cualquier proveedor (Claude Code,
> OpenAI Codex, Cursor, etc.). Es la **memoria persistente** del proyecto: las
> invariantes y trampas propias de este repo que son fáciles de romper. Si vas a
> modificar algo, **léelo primero**. `CLAUDE.md` y `CODEX.md` solo apuntan aquí.
>
> Distinción importante: la skill `dian-integration` (`.agents/skills/`) es para
> **integrar** la API desde un ERP/POS/backend externo. **Este** archivo es para
> desarrollar y mantener el repo. Son complementarios.
>
> **Repo PÚBLICO (OSS).** Nada de marcas de un emisor concreto, defaults privados
> de negocio, ids de proyectos cloud ni secretos. Mantén el contenido genérico y
> autosuficiente.

`facturacion-dian-api` es una **API HTTP de alto nivel** y *stateless* para
facturación electrónica DIAN en Colombia. `packages/core` contiene la lógica
interna reusable (XML, firma, SOAP, CUFE); `packages/server` expone la superficie
HTTP (FastAPI) y el contrato OpenAPI. El producto público es la API HTTP.

---

## 1. La compuerta de validación es ley

Antes de **cualquier** PR corre el set completo (está en `CONTRIBUTING.md`); CI
(`.github/workflows/ci.yml`) lo exige y además corre **Gitleaks** (`--exit-code=2`):

```powershell
python scripts/validate_public_docs.py
python scripts/validate_skill.py
python -m ruff check .
python -m mypy packages/core/src packages/server/src
python -m pytest
docker build -t facturacion-dian-api .
```

Nunca saltes la compuerta ni la "ablandes" para que pase. Si un cambio rompe un
validador, el cambio (o la doc) está mal, no el validador.

---

## 2. Invariantes del contrato público

`scripts/validate_public_docs.py` protege el contrato y CI lo bloquea:

- Los **endpoints oficiales** son canónicos y deben aparecer documentados:
  `POST /api/v1/documents/submissions`,
  `GET /api/v1/documents/submissions/{tracking_id}`,
  `POST /api/v1/attached-documents`, `POST /api/v1/customers/lookup`,
  `POST /api/v1/numbering-ranges/lookup`, `GET /health`.
- Hay **snippets prohibidos** que no pueden reaparecer en los docs públicos: las
  grafías **viejas** de los endpoints (las formas `/submit`, `/status/{id}`,
  `/attached-document` bajo `documents/`) y **cualquier** encuadre de "SDK"
  (PyPI/npm, paquetes `sdk-*`, "futuro SDK"). El producto se distribuye como API
  HTTP + imagen Docker, **no** como SDK.
- `README.md` debe seguir posicionando el proyecto como **"API HTTP de alto
  nivel"** (el validador lo verifica literalmente).
- La skill (`SKILL.md` + `agents/openai.yaml` + las 4 referencias) tiene forma
  validada por `scripts/validate_skill.py`.

> Si renombras/agregas un endpoint o un doc, actualiza **a la vez** los documentos
> **y** las expectativas del validador. No los dejes desincronizados.

`packages/core` **no** es superficie pública consumible ni producto separado: no lo
documentes como tal.

---

## 3. Una sola identidad, un solo certificado

El servicio carga **un único** certificado `.p12` (PKCS#12) al arranque, desde
`DIAN_CERT_PATH` + `DIAN_CERT_PASSWORD`
(`packages/core/src/facturacion_dian_api/core/signing/certificate.py`, con caché
singleton). **No existe** noción de "negocios"/tenants y no debe introducirse: un
despliegue = un emisor. Las credenciales por emisor (software id/pin/clave técnica,
NIT) entran en el **cuerpo de la petición**, no como estado del servicio.

---

## 4. Firma y XML son frágiles a propósito

Estos módulos corren bajo overrides de `mypy` deliberados (ver `pyproject.toml`):
`core.signing.xades` con `ignore_errors`, y `core.dian.envelope`,
`core.signing.ws_security`, `core.xml.*_builder`, `core.xml.common` con códigos de
error desactivados. Es intencional: la firma XAdES, WS-Security y los builders UBL
se ajustan a esquemas externos rígidos.

- Cambios en estos módulos exigen **escrutinio extra de pruebas**:
  `tests/test_signing.py`, `tests/test_envelope.py`, `tests/test_xml_builders.py`.
- **No** "arregles" la config de mypy para forzar `strict` aquí sin entender por
  qué está relajada. Si reduces un override, justifícalo y respáldalo con pruebas.

---

## 5. CUFE/CUDE: corrección crítica

`packages/core/src/facturacion_dian_api/core/cufe/calculator.py` calcula el hash
**SHA-384** sobre una semilla de campos **en orden estricto** (número, fechas,
totales, NIT, `clave_tecnica` para CUFE o `software_pin` para CUDE, ambiente).

- El **orden de los campos** y el formato de los montos (`Decimal` a 2 decimales,
  `ROUND_HALF_UP`, punto decimal, sin miles) son parte del cálculo. Reordenar o
  reformatear rompe el hash y DIAN rechaza el documento.
- Cualquier cambio aquí debe pasar `tests/test_cufe.py` con vectores conocidos.
- **La clave no se recalcula para reconciliar: se lee de DIAN.** La semilla lleva
  `fec_fac`/`hor_fac`, así que un reintento firmado más tarde produce una clave
  **distinta** a la del documento que DIAN ya aceptó. Por eso la consulta de estado
  expone `document_key` (y `qr_url`) desde el `XmlDocumentKey` que reporta DIAN, en
  vez de dejar que el llamador lo derive. `XmlDocumentKey` se parsea aparte del
  `tracking_id` a propósito: la cadena de fallback de éste también lo consume
  cuando no hay `ZipKey`, y ahí se confunden dos identificadores distintos (envío
  vs documento).

---

## 6. `issue_date` / `issue_time` los provee el llamador

Son **strings provistos por quien llama** (`core/models.py`, formato
`HH:MM:SS-05:00`) y alimentan directamente la semilla del CUFE. El servicio **no**
los genera ni los reescribe. No agregues defaults automáticos ni "normalices" la
zona horaria en silencio: el offset Colombia (`-05:00`) correcto es responsabilidad
del integrador, y un offset equivocado cambia el CUFE y provoca rechazo de DIAN.

---

## 7. Semántica de status HTTP (contrato estable)

Mapeada en `packages/server/src/facturacion_dian_api/server/app.py`. Mantenla
estable:

| Status | Significado |
|---|---|
| `422` | Payload inválido (validación Pydantic) |
| `503` | Falta configuración local o el certificado es inválido |
| `502` | Falla de comunicación con DIAN (sin ser timeout) |
| `504` | DIAN no respondió a tiempo |
| `200` | DIAN procesó la solicitud: **aceptación o rechazo funcional** |

Un rechazo **funcional** de DIAN es `200` con `status="rejected"` en el cuerpo, no
un error HTTP. No conviertas rechazos funcionales en 4xx/5xx.

---

## 8. Frontera `core` / `server`

- `packages/core` (`facturacion-dian-api-core`): dominio reusable (XML, firma,
  SOAP, CUFE). Interno; no se publica.
- `packages/server` (`facturacion-dian-api-server`): superficie HTTP + contrato
  OpenAPI; depende de `core`.

Mantén la lógica de dominio en `core` y la traducción HTTP en `server`
(`mappers.py`, `contracts.py`). No filtres detalles internos de `core` al contrato
público.

---

## 9. Sin secretos, sin branding privado

- **Nunca** subas certificados (`.p12`/`.pem`/`.key`), `.env`, ni credenciales
  reales de DIAN. **Gitleaks** corre en CI y bloquea el push.
- **No** introduzcas marca de un emisor específico ni defaults privados de negocio
  (regla de `CONTRIBUTING.md`). No uses los valores **demo** de la documentación en
  ambientes reales.
- Trata la documentación pública y los ejemplos JSON (`docs/examples/`) como parte
  del contrato.

---

## 10. Determinismo + pruebas

El comportamiento DIAN debe ser **determinista** y respaldado por pruebas. Incluye
o actualiza pruebas para payload, XML, firma, parser, transporte o documentación
pública según aplique. Los tests marcados `integration` llaman endpoints DIAN
reales — no los corras como parte del flujo normal.

---

## 11. Eventos RADIAN: la semilla del CUDE es distinta

`core/cufe/calculator.py` tiene **tres** funciones de hash y son incompatibles
entre sí. La del evento (`calculate_event_cude`, Anexo Técnico FEV v1.9 § 11.5,
idéntica al Anexo RADIAN v1.1 § 12.1.1) es:

```text
SHA-384(Num_DE + Fec_Emi + Hor_Emi + NitFE + DocAdq
        + ResponseCode + ID + DocumentTypeCode + SoftwarePIN)
```

- **No lleva `TipoAmbiente` al final** ni montos ni códigos de impuesto, a
  diferencia de CUFE/CUDE de documentos. Reusar `calculate_cude` produce el
  rechazo `Regla: AAD06`.
- `NitFE` es **nuestro** NIT (`SenderParty`, quien genera el evento) y `DocAdq`
  el del proveedor (`ReceiverParty`). Invertirlos también rompe el hash.
- `tests/test_cufe.py::TestEventCudeCalculation` fija el vector oficial del
  anexo. Si un cambio lo rompe, el cambio está mal.

Otras trampas del `ApplicationResponse` (`core/xml/application_response_builder.py`):

- `cac:SenderParty`/`cac:ReceiverParty` son `PartyType`: `cac:PartyTaxScheme`
  cuelga **directo**, sin `cac:Party` intermedio (a diferencia de
  `AccountingSupplierParty` en la factura). El XPath del CUDE depende de eso.
- **Regla AAD09e**: la fecha del evento debe ser igual a la de la firma. Por eso
  `core/events.py` estampa fecha y hora desde `colombia_now()` en vez de pedirlas
  al llamador — es la excepción consciente a la regla del § 6.
- `sts:QRCode` lleva el **CUFE de la factura referenciada**, no el CUDE del
  evento (AAB36).
- El evento no lleva `sts:InvoiceControl`: no consume numeración DIAN. Por lo
  mismo **no aplica la Regla 90** y un reintento reenvía el mismo documento.
- `SendEventUpdateStatus` recibe **solo** `contentFile`; mandarle `fileName`
  como `SendBillSync` falla en el WCF de la DIAN.
- El `034` (aceptación tácita) **no se implementa**: lo registra el emisor.

## 12. Convenciones

- **Idioma.** Documentación, README, `CONTRIBUTING.md` y PRs/commits: **español**
  (la voz pública del repo). Comentarios de código: el inglés es la norma existente
  — mantén la consistencia dentro de cada módulo.
- **Este archivo es memoria persistente.** Cuando descubras un patrón o trampa que
  el siguiente agente deba conocer, **agrégalo aquí**, con base en un hecho real.
