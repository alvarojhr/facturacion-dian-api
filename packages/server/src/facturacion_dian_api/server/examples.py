"""Canonical examples for OpenAPI and public documentation."""

from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

# Los ejemplos usan la misma fecha colombiana que valida el contrato, incluso
# cuando el proceso está en un host UTC y allá ya cambió el día.
TODAY = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()

DOCUMENT_KEY_EXAMPLE = "demo-document-key-not-real"
SIGNED_XML_BASE64 = base64.b64encode(b"<Signed>ok</Signed>").decode("ascii")
INVOICE_XML_BASE64 = base64.b64encode(
    f'''<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
      xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
      xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
      xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
      <cbc:ProfileExecutionID>2</cbc:ProfileExecutionID><cbc:ID>FDK000001</cbc:ID>
      <cbc:UUID schemeName="CUFE-SHA384">{DOCUMENT_KEY_EXAMPLE}</cbc:UUID><cbc:IssueDate>2026-04-01</cbc:IssueDate>
      <cbc:IssueTime>14:30:00-05:00</cbc:IssueTime><cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>
      <cac:AccountingSupplierParty><cac:Party><cac:PartyTaxScheme>
        <cbc:RegistrationName>Example Issuer SAS</cbc:RegistrationName>
        <cbc:CompanyID schemeName="31" schemeID="8">900123456</cbc:CompanyID>
        <cbc:TaxLevelCode>O-47</cbc:TaxLevelCode>
        <cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme>
      </cac:PartyTaxScheme></cac:Party></cac:AccountingSupplierParty>
      <cac:AccountingCustomerParty><cac:Party><cac:PartyTaxScheme>
        <cbc:RegistrationName>Cliente Demo SAS</cbc:RegistrationName>
        <cbc:CompanyID schemeName="31" schemeID="4">800199436</cbc:CompanyID>
        <cbc:TaxLevelCode>R-99-PN</cbc:TaxLevelCode>
        <cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme>
      </cac:PartyTaxScheme></cac:Party></cac:AccountingCustomerParty><ds:Signature/>
    </Invoice>'''.encode()
).decode("ascii")
DIAN_AR_XML_BASE64 = base64.b64encode(
    b'''<ApplicationResponse xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
      xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
      xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
      xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
      <cbc:ID>AR-DEMO-1</cbc:ID><cbc:IssueDate>2026-04-01</cbc:IssueDate>
      <cbc:IssueTime>14:31:00-05:00</cbc:IssueTime><ds:Signature/>
      <cac:DocumentResponse><cac:Response><cbc:ResponseCode>02</cbc:ResponseCode>
      <cbc:Description>Documento Validado por la DIAN</cbc:Description></cac:Response>
      <cac:DocumentReference><cbc:ID>FDK000001</cbc:ID>
      <cbc:UUID>demo-document-key-not-real</cbc:UUID>
      <cbc:DocumentTypeCode>01</cbc:DocumentTypeCode></cac:DocumentReference>
      </cac:DocumentResponse>
    </ApplicationResponse>'''
).decode("ascii")
ZIP_BASE64_EXAMPLE = base64.b64encode(b"zip-demo").decode("ascii")

DOCUMENT_SUBMISSION_INVOICE_EXAMPLE = {
    "client_reference": "pedido-erp-1001",
    "document": {
        "number": "FDK000001",
        "type": "FACTURA_ELECTRONICA",
        "issue_date": TODAY,
        "issue_time": "14:30:00-05:00",
        "payment_method": "CASH",
    },
    "issuer": {
        "nit": "900123456",
        "dv": "8",
        "name": "Example Issuer SAS",
        "additional_account_id": "1",
        "address": "Street 10 #20-30",
        "city_code": "11001",
        "city_name": "Bogota",
        "department_code": "11",
        "department_name": "Bogota D.C.",
        "country_code": "CO",
        "tax_level_code": "O-47",
        "tax_scheme_id": "01",
        "tax_scheme_name": "IVA",
        "economic_activity": "4752",
        "phone": "3001234567",
        "email": "billing@example-issuer.test",
    },
    "buyer": {
        "document_number": "800199436",
        "document_type": "NIT",
        "name": "Empresa Ejemplo S.A.S.",
        "email": "compras@ejemplo.com",
        "phone": "3001234567",
        "address": "Calle 10 # 5-11",
        "city_code": "11001",
        "city_name": "Bogota",
        "department_code": "11",
        "department_name": "Bogota D.C.",
        "country_code": "CO",
        "additional_account_id": "1",
        "tax_level_code": "R-99-PN",
        "tax_scheme_id": "01",
        "tax_scheme_name": "IVA",
    },
    "resolution": {
        "number": "18764000001",
        "prefix": "FDK",
        "date": "2026-01-01",
        "range_from": 1,
        "range_to": 999999,
        "valid_from": "2026-01-01",
        "valid_to": "2027-12-31",
    },
    "totals": {
        "subtotal": 100000,
        "tax_total": 19000,
        "total": 119000,
    },
    "line_items": [
        {
            "description": "Tornillo hexagonal 1/4 x 1 zinc",
            "item_name": "Tornillo hexagonal 1/4 x 1 zinc",
            "item_code": "TOR-001",
            "unit_code": "94",
            "quantity": 100,
            "unit_price": 500,
            "line_total": 50000,
            "tax_type": "IVA_19",
            "tax_amount": 9500,
        },
        {
            "description": "Tuerca hexagonal 1/4 zinc",
            "item_name": "Tuerca hexagonal 1/4 zinc",
            "item_code": "TUE-001",
            "unit_code": "94",
            "quantity": 100,
            "unit_price": 500,
            "line_total": 50000,
            "tax_type": "IVA_19",
            "tax_amount": 9500,
        },
    ],
    "submission_options": {
        "software_id": "software-demo-id",
        "software_pin": "pin-demo-001",
        "technical_key": "technical-key-demo-001",
        "test_set_id": "test-set-demo-001",
        "return_xml_artifact": True,
        "file_sequence": 1,
    },
}

DOCUMENT_SUBMISSION_POS_EXAMPLE = {
    "client_reference": "venta-pos-2001",
    "document": {
        "number": "POS000001",
        "type": "DOCUMENTO_EQUIVALENTE_POS",
        "issue_date": TODAY,
        "issue_time": "10:15:30-05:00",
        "payment_method": "CARD",
        "point_of_sale": {
            "register_plate": "POS-1",
            "register_location": "Mostrador principal",
            "cashier_name": "Ana Perez",
            "register_type": "POS",
            "sale_code": "SALE-100",
            "buyer_loyalty_points": 10,
        },
    },
    "buyer": {
        "name": "Consumidor Final",
        "document_type": "FINAL_CONSUMER",
    },
    "resolution": {
        "number": "18764000002",
        "prefix": "POS",
        "date": "2026-01-01",
        "range_from": 1,
        "range_to": 999999,
        "valid_from": "2026-01-01",
        "valid_to": "2027-12-31",
    },
    "totals": {
        "subtotal": 42000,
        "tax_total": 7980,
        "total": 49980,
    },
    "line_items": [
        {
            "description": "Martillo carpintero 16oz",
            "item_name": "Martillo carpintero 16oz",
            "item_code": "MAR-016",
            "unit_code": "94",
            "quantity": 1,
            "unit_price": 42000,
            "line_total": 42000,
            "tax_type": "IVA_19",
            "tax_amount": 7980,
        }
    ],
    "submission_options": {
        "software_id": "software-demo-id",
        "software_pin": "pin-demo-001",
        "test_set_id": "test-set-demo-001",
        "file_sequence": 1,
    },
}

DOCUMENT_SUBMISSION_CREDIT_NOTE_EXAMPLE = {
    "client_reference": "nc-1001",
    "document": {
        "number": "NC000001",
        "type": "NOTA_CREDITO",
        "issue_date": TODAY,
        "issue_time": "09:00:00-05:00",
        "payment_method": "CASH",
    },
    "buyer": {
        "document_number": "800199436",
        "document_type": "NIT",
        "name": "Empresa Ejemplo S.A.S.",
        "additional_account_id": "1",
        "tax_level_code": "R-99-PN",
        "tax_scheme_id": "01",
        "tax_scheme_name": "IVA",
    },
    "totals": {
        "subtotal": 50000,
        "tax_total": 9500,
        "total": 59500,
    },
    "line_items": [
        {
            "description": "Tornillo hexagonal 1/4 x 1 zinc",
            "item_code": "TOR-001",
            "quantity": 100,
            "unit_price": 500,
            "line_total": 50000,
            "tax_type": "IVA_19",
            "tax_amount": 9500,
        }
    ],
    "references": {
        "referenced_document_number": "FDK000001",
        "referenced_document_key": "ref-doc-key-demo",
        "referenced_issue_date": "2026-03-12",
        "reason": "Devolucion parcial",
        "response_code": "1",
    },
    "submission_options": {
        "software_id": "software-demo-id",
        "software_pin": "pin-demo-001",
        "test_set_id": "test-set-demo-001",
        "file_sequence": 1,
    },
}

DOCUMENT_SUBMISSION_DEBIT_NOTE_EXAMPLE = {
    "client_reference": "nd-1001",
    "document": {
        "number": "ND000001",
        "type": "NOTA_DEBITO",
        "issue_date": TODAY,
        "issue_time": "11:00:00-05:00",
        "payment_method": "CASH",
    },
    "buyer": {
        "document_number": "800199436",
        "document_type": "NIT",
        "name": "Empresa Ejemplo S.A.S.",
        "additional_account_id": "1",
        "tax_level_code": "R-99-PN",
        "tax_scheme_id": "01",
        "tax_scheme_name": "IVA",
    },
    "totals": {
        "subtotal": 10000,
        "tax_total": 1900,
        "total": 11900,
    },
    "line_items": [
        {
            "description": "Ajuste por intereses",
            "item_code": "AJU-001",
            "quantity": 1,
            "unit_price": 10000,
            "line_total": 10000,
            "tax_type": "IVA_19",
            "tax_amount": 1900,
        }
    ],
    "references": {
        "referenced_document_number": "FDK000001",
        "referenced_document_key": "ref-doc-key-demo",
        "referenced_issue_date": "2026-03-12",
        "reason": "Cobro de intereses",
        "response_code": "1",
    },
    "submission_options": {
        "software_id": "software-demo-id",
        "software_pin": "pin-demo-001",
        "test_set_id": "test-set-demo-001",
        "file_sequence": 1,
    },
}

def _combined_payment_example(methods: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = deepcopy(DOCUMENT_SUBMISSION_INVOICE_EXAMPLE)
    payload["document"].pop("payment_method")
    payload["document"].update(payment_methods=methods, payment_form="CONTADO")
    payload["line_items"] = [{
        "description": "Material vendido por metro", "item_code": "MT-1", "unit_code": "MTR",
        "quantity": "3.333", "unit_price": "840.34", "line_total": "2801.00",
        "taxes": [{"tax_type": "IVA_19", "taxable_amount": "2801.00", "amount": "532.00"}],
    }]
    payload["totals"] = {"subtotal": "2801.00", "tax_total": "532.00", "total": "3333.00"}
    payload["submission_options"]["prepare_only"] = True
    return payload


COMBINED_CASH_DEBIT_EXAMPLE = _combined_payment_example(["CASH", "DEBIT_CARD"])
COMBINED_CASH_TRANSFER_EXAMPLE = _combined_payment_example(["CASH", "TRANSFER"])
COMBINED_DEBIT_CREDIT_EXAMPLE = _combined_payment_example(["DEBIT_CARD", "CREDIT_CARD"])

DOCUMENT_SUBMISSION_REQUEST_EXAMPLES = [
    DOCUMENT_SUBMISSION_INVOICE_EXAMPLE,
    DOCUMENT_SUBMISSION_POS_EXAMPLE,
    DOCUMENT_SUBMISSION_CREDIT_NOTE_EXAMPLE,
    DOCUMENT_SUBMISSION_DEBIT_NOTE_EXAMPLE,
    COMBINED_CASH_DEBIT_EXAMPLE,
    COMBINED_CASH_TRANSFER_EXAMPLE,
    COMBINED_DEBIT_CREDIT_EXAMPLE,
]

DOCUMENT_SUBMISSION_OPENAPI_EXAMPLES = {
    "efectivo_debito_iva_cop": {
        "summary": "Efectivo y tarjeta debito; IVA conservado en COP enteros",
        "value": COMBINED_CASH_DEBIT_EXAMPLE,
    },
    "efectivo_transferencia": {
        "summary": "Efectivo y transferencia",
        "value": COMBINED_CASH_TRANSFER_EXAMPLE,
    },
    "debito_credito": {
        "summary": "Dos tarjetas; venta de contado",
        "value": COMBINED_DEBIT_CREDIT_EXAMPLE,
    },
    "factura_electronica": {
        "summary": "Factura electronica de venta",
        "description": "Ejemplo completo para FE con cliente identificado.",
        "value": DOCUMENT_SUBMISSION_INVOICE_EXAMPLE,
    },
    "documento_equivalente_pos": {
        "summary": "Documento equivalente POS",
        "description": "Ejemplo para venta POS con metadata de caja.",
        "value": DOCUMENT_SUBMISSION_POS_EXAMPLE,
    },
    "nota_credito": {
        "summary": "Nota credito",
        "description": "Ejemplo con referencias hacia la factura original.",
        "value": DOCUMENT_SUBMISSION_CREDIT_NOTE_EXAMPLE,
    },
    "nota_debito": {
        "summary": "Nota debito",
        "description": "Ejemplo con response code y referencia al documento base.",
        "value": DOCUMENT_SUBMISSION_DEBIT_NOTE_EXAMPLE,
    },
}

DOCUMENT_SUBMISSION_RESPONSE_EXAMPLE = {
    "submission_id": "5c314980-5ec3-4af7-98d3-6bf0b9081010",
    "tracking_id": "2c6c3df3-6301-4170-9e1e-a2441a8b5d5e",
    "client_reference": "pedido-erp-1001",
    "document_key": DOCUMENT_KEY_EXAMPLE,
    "qr_url": f"https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={DOCUMENT_KEY_EXAMPLE}",
    "status": "accepted",
    "messages": [
        "Document received successfully.",
        "Processed successfully.",
    ],
    "dian_response": {
        "is_valid": True,
        "status_code": "00",
        "status_description": "Processed successfully.",
        "status_message": "Document received successfully.",
        "tracking_id": "2c6c3df3-6301-4170-9e1e-a2441a8b5d5e",
        "error_messages": [],
    },
    "artifacts": {
        "xml_base64": SIGNED_XML_BASE64,
        "xml_filename": "fv09001234560002600000001.xml",
    },
}

DOCUMENT_STATUS_RESPONSE_EXAMPLE = {
    "submission_id": "2c6c3df3-6301-4170-9e1e-a2441a8b5d5e",
    "tracking_id": "2c6c3df3-6301-4170-9e1e-a2441a8b5d5e",
    "client_reference": None,
    "document_key": None,
    "qr_url": None,
    "status": "rejected",
    "messages": [
        "Tracking ID not found.",
        "Document not found.",
    ],
    "dian_response": {
        "is_valid": False,
        "status_code": "99",
        "status_description": "Document not found.",
        "status_message": "Tracking ID not found.",
        "tracking_id": "2c6c3df3-6301-4170-9e1e-a2441a8b5d5e",
        "error_messages": [],
    },
    "artifacts": None,
}

ATTACHED_DOCUMENT_REQUEST_EXAMPLE = {
    "document_number": "FDK000001",
    "document_type_code": "01",
    "issuer_nit": "900123456",
    "issuer_dv": "8",
    "issuer_name": "Example Issuer SAS",
    "issuer_tax_level_code": "O-47",
    "receiver_name": "Cliente Demo SAS",
    "receiver_nit": "800199436",
    "receiver_dv": "4",
    "receiver_document_type": "31",
    "receiver_tax_level_code": "R-99-PN",
    "receiver_email": "facturas@cliente.test",
    "reply_to_email": "billing@example-issuer.test",
    "company_name": "Example Issuer SAS",
    "business_line": "Ferreteria y materiales",
    "invoice_xml_base64": INVOICE_XML_BASE64,
    "invoice_xml_filename": "fv09001234560002600000001.xml",
    "application_response_xml_base64": DIAN_AR_XML_BASE64,
    "application_response_xml_filename": "ar09001234560002600000001.xml",
    "issue_date": "2026-04-01",
    "issue_time": "14:30:00-05:00",
    "cufe": DOCUMENT_KEY_EXAMPLE,
    "file_sequence": 1,
}

ATTACHED_DOCUMENT_RESPONSE_EXAMPLE = {
    "xml_filename": "ad09001234560002600000001.xml",
    "zip_filename": "ad09001234560002600000001.zip",
    "content_base64": ZIP_BASE64_EXAMPLE,
}

BUYER_LOOKUP_REQUEST_EXAMPLE = {
    "document_type": "NIT",
    "document_number": "900123456",
}

BUYER_LOOKUP_RESPONSE_EXAMPLE = {
    "found": True,
    "error_message": None,
    "customer": {
        "display_name": "Cliente DIAN S.A.S.",
        "document_type": "NIT",
        "document_number": "900123456",
        "email": "contacto@cliente-dian.test",
        "phone": None,
        "address": None,
        "city_code": None,
        "city_name": None,
        "department_code": None,
        "department_name": None,
        "country_code": "CO",
    },
}

NUMBERING_RANGE_LOOKUP_REQUEST_EXAMPLE = {
    "environment": "produccion",
    "account_code": "901975980",
    "account_code_t": "901975980",
    "software_code": "software-demo-id",
}

NUMBERING_RANGE_LOOKUP_RESPONSE_EXAMPLE = {
    "ranges": [
        {
            "resolution_number": "18764107158626",
            "resolution_date": "2026-03-13",
            "prefix": "FDK",
            "from_number": 1,
            "to_number": 99999,
            "valid_date_from": "2026-03-13",
            "valid_date_to": "2028-03-13",
            "technical_key": "technical-key-demo-001",
        }
    ]
}

HEALTH_RESPONSE_EXAMPLE = {
    "status": "ok",
    "version": "0.2.0a3",
    "dian_environment": "habilitacion",
    "certificate_loaded": True,
    "certificate_valid_until": "2027-12-31T23:59:59+00:00",
    "certificate_days_remaining": 472,
    "certificate_expiring_soon": False,
}

ERROR_503_EXAMPLE = {
    "detail": "Missing required submission settings: software_id, software_pin, technical_key, test_set_id"
}

ERROR_502_EXAMPLE = {
    "detail": "HTTP error calling DIAN GetStatus: Server disconnected without sending a response"
}

ERROR_504_EXAMPLE = {
    "detail": "Timeout calling DIAN SendTestSetAsync"
}

EVENT_CUDE_EXAMPLE = "demo-event-cude-not-real"
APPLICATION_RESPONSE_XML_BASE64 = base64.b64encode(
    b"<ApplicationResponse>demo</ApplicationResponse>"
).decode("ascii")
DIAN_EVENT_RESPONSE_XML_BASE64 = base64.b64encode(
    b"<ApplicationResponse>dian</ApplicationResponse>"
).decode("ascii")

EMIT_EVENT_ACKNOWLEDGEMENT_EXAMPLE = {
    "event_type": "030",
    "environment": "habilitacion",
    "event_number": "EV000001",
    "document_cufe": "b" * 96,
    "document_number": "SETP990000123",
    "document_issue_date": "2026-07-10",
    "supplier_nit": "800199436",
    "supplier_name": "Proveedor Ejemplo S.A.S.",
    "total_amount": 119000,
    "submission_options": {
        "software_id": "software-demo-id",
        "software_pin": "pin-demo-001",
        "file_sequence": 1,
    },
}

EMIT_EVENT_GOODS_RECEIPT_EXAMPLE = {
    "event_type": "032",
    "event_number": "EV000002",
    "document_cufe": "b" * 96,
    "document_number": "SETP990000123",
    "document_issue_date": "2026-07-10",
    "supplier_nit": "800199436",
    "supplier_name": "Proveedor Ejemplo S.A.S.",
    "receiver_person": {
        "document_number": "1098765432",
        "document_type": "13",
        "first_name": "Ana",
        "family_name": "Perez",
        "job_title": "Jefe de bodega",
        "organization_department": "Almacen",
    },
    "submission_options": {
        "software_id": "software-demo-id",
        "software_pin": "pin-demo-001",
        "file_sequence": 2,
    },
}

EMIT_EVENT_CLAIM_EXAMPLE = {
    "event_type": "031",
    "event_number": "EV000003",
    "document_cufe": "b" * 96,
    "document_number": "SETP990000123",
    "document_issue_date": "2026-07-10",
    "supplier_nit": "800199436",
    "supplier_name": "Proveedor Ejemplo S.A.S.",
    "claim_cause_code": "03",
    "claim_description": "Se recibieron 80 de las 100 unidades facturadas.",
    "submission_options": {
        "software_id": "software-demo-id",
        "software_pin": "pin-demo-001",
        "file_sequence": 3,
    },
}

EMIT_EVENT_OPENAPI_EXAMPLES = {
    "acuse_de_recibo": {
        "summary": "030 Acuse de recibo",
        "description": "Primer evento de la secuencia; solo requiere los datos de la factura.",
        "value": EMIT_EVENT_ACKNOWLEDGEMENT_EXAMPLE,
    },
    "recibo_del_bien": {
        "summary": "032 Recibo del bien o servicio",
        "description": "La DIAN exige receiver_person para este evento.",
        "value": EMIT_EVENT_GOODS_RECEIPT_EXAMPLE,
    },
    "reclamo": {
        "summary": "031 Reclamo",
        "description": "Requiere causal 01-04 y descripcion.",
        "value": EMIT_EVENT_CLAIM_EXAMPLE,
    },
}

EMIT_EVENT_RESPONSE_EXAMPLE = {
    "status": "ACCEPTED",
    "cude": EVENT_CUDE_EXAMPLE,
    "tracking_id": "f8809b485030d5f0548451f0f5562649936c45aba286819c052d8dfa432dcb7ed",
    "messages": ["Procesado Correctamente."],
    "client_reference": "acuse-erp-1001",
    "dian_response": {
        "is_valid": True,
        "status_code": "00",
        "status_description": "Procesado Correctamente.",
        "status_message": "",
        "tracking_id": "f8809b485030d5f0548451f0f5562649936c45aba286819c052d8dfa432dcb7ed",
        "error_messages": [],
    },
    "artifacts": {
        "application_response_xml_base64": APPLICATION_RESPONSE_XML_BASE64,
        "application_response_xml_filename": "ar09001234560002600000001.xml",
        "dian_response_xml_base64": DIAN_EVENT_RESPONSE_XML_BASE64,
        "dian_response_xml_filename": "dian_ar09001234560002600000001.xml",
    },
}

DOWNLOAD_BY_KEY_REQUEST_EXAMPLE = {
    "environment": "produccion",
    "document_key": "a" * 96,
}

DOWNLOAD_BY_KEY_RESPONSE_EXAMPLE = {
    "success": True,
    "document_key": "a" * 96,
    "xml_base64": "PEludm9pY2U+ZGVtbzwvSW52b2ljZT4=",
    "xml_filename": "dian_aaaaaaaaaaaaaaaaaaaa.xml",
    "status": "DOWNLOADED",
    "error_message": None,
    "raw_response": {
        "success": True,
        "xml_filename": None,
        "status": "DOWNLOADED",
        "error_message": "",
        "raw_xml": "<s:Envelope>...</s:Envelope>",
    },
}
