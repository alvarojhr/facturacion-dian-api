# Contexto del proyecto

Antes de modificar cualquier cosa, lee **[`AGENTS.md`](AGENTS.md)** en la raíz: es
la guía multi-proveedor de las invariantes de este repo (la compuerta de validación
+ Gitleaks, el contrato público de endpoints y los snippets prohibidos, la fragilidad
de firma/XML, la corrección del CUFE, la semántica de status HTTP, y la regla de
"sin secretos ni branding privado"). Este archivo solo apunta allí.

Para **integrar** la API desde un ERP/POS/backend externo, usa la skill
`dian-integration` (`.claude/skills/dian-integration`), no este archivo.
