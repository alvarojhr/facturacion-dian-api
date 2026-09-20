# Consulta técnica: AE28 cuando la factura omite la responsabilidad del comprador

**Borrador listo para radicar. No enviado.**

**Destinatario:** DIAN, equipo competente de facturación electrónica.

**Asunto:** Representación de `ReceiverParty/PartyTaxScheme/TaxLevelCode` en
AttachedDocument para un adquirente identificado cuya responsabilidad fiscal no se conoce.

## Situación que se solicita aclarar

Un facturador expide una factura electrónica de venta a nombre de un adquirente
identificado. Conoce su nombre, tipo y número de documento y el medio de entrega.
No dispone de sus responsabilidades fiscales. El comprador conserva su identidad;
no se sustituye por la identificación genérica de consumidor final.

El anexo técnico de factura electrónica 1.9 permite omitir `TaxLevelCode` del
comprador en la factura (FAK26, ocurrencia 0..1, página 54 de la copia de 753
páginas). En cambio, en el contenedor AttachedDocument, AE28 tiene ocurrencia
1..1 (página 265). AE29 regula el atributo `listName`, no el valor de AE28.

La Resolución 000227 de 2025, artículo 1.5.1.12.3, limita los datos exigibles al
adquirente y no incluye sus responsabilidades fiscales. Se busca cumplir la
entrega sin solicitar datos adicionales ni atribuirle una condición fiscal desconocida.

El catálogo vigente incluye `R-99-PN`, con descripción «No aplica – Otros *».
No hemos identificado una instrucción vigente que lo defina como valor técnico
para responsabilidad desconocida exclusivamente en el contenedor. Solicitamos
aclarar ese supuesto, distinto de conocer que al adquirente no le corresponden
las otras responsabilidades del catálogo.

## Preguntas concretas

1. ¿Qué contenido debe tener AE28 cuando la factura firmada y validada omite
   legítimamente FAK26 y el emisor desconoce las responsabilidades del adquirente?
2. ¿Está autorizado usar `R-99-PN` exclusivamente en el contenedor en ese supuesto,
   sin modificar la factura firmada y sin registrarlo como clasificación fiscal
   confirmada del adquirente? En caso afirmativo, ¿qué disposición o instrucción
   técnica lo establece y cuáles son sus condiciones?
3. Si ese valor no procede, ¿se permite omitir AE28, dejarlo vacío o utilizar otra
   representación? Agradecemos un ejemplo XML mínimo y la referencia oficial
   aplicable, incluyendo si corresponde ajustar o aclarar la ocurrencia 1..1.
4. ¿La solución aplica por igual a receptor identificado con CC y con NIT, y a
   contenedores de factura, nota crédito y nota débito? ¿Tiene condiciones distintas
   según el receptor sea o no facturador electrónico?
5. Mientras se aclara AE28, para el adquirente que no es facturador electrónico y
   autoriza recibir la representación gráfica digital, ¿es correcto aplicar el
   artículo 1.5.1.5.5.1, numeral 2.1, conservando internamente el XML y su validación?
   ¿Existe alguna condición técnica adicional relevante para ese caso?

## Ejemplo mínimo del problema

Los siguientes son **fragmentos ilustrativos**, no documentos completos ni
facturas aceptadas por DIAN. Todos los datos del paquete adjunto son sintéticos.

Parte del comprador en la factura:

```xml
<cac:PartyTaxScheme
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:RegistrationName>COMPRADOR SINTETICO AE28</cbc:RegistrationName>
  <cbc:CompanyID schemeName="13">123456789</cbc:CompanyID>
  <cac:TaxScheme>
    <cbc:ID>ZZ</cbc:ID>
    <cbc:Name>No aplica</cbc:Name>
  </cac:TaxScheme>
</cac:PartyTaxScheme>
```

En el contenedor debe representarse a esa misma persona en
`/AttachedDocument/cac:ReceiverParty/cac:PartyTaxScheme`. La consulta es cómo
informar su `cbc:TaxLevelCode` cuando no aparece en el original.

La implementación conserva intactos el XML firmado y la respuesta de validación.
La respuesta de aceptación incluida en el ejemplo es **simulada y firmada con
un certificado efímero de prueba**. No es una respuesta emitida por DIAN.

El error HTTP 422 adjunto se genera en nuestra implementación. No se afirma
que DIAN haya rechazado una factura o un contenedor por este motivo. La
validación XSD por sí sola tampoco determina la solución fiscal.

## Referencias

- [Resolución 000227 de 2025, arts. 1.5.1.12.3 y 1.5.1.5.5.1](https://normograma.dian.gov.co/dian/compilacion/docs/resolucion_dian_0227_2025.htm).
- [Anexo FE 1.9, apartados 6.1, 6.4, 8.5, 9.3 y 13.2.7.6](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9.pdf).
- [Caja de herramientas FE 1.9, versión 2026](https://www.dian.gov.co/impuestos/factura-electronica/Documents/Caja-de-herramientas-FE_V19_v2026.zip),
  tabla `13.2.6.1 Responsabilidades fiscales.xlsx`.

La identificación y los datos de contacto del solicitante se diligenciarán al
radicar en el [canal oficial PQSRD de DIAN](https://www.dian.gov.co/atencionciudadano/PQSRD/Paginas/Inicio.aspx).
