"""Canonical examples for OpenAPI and public documentation."""

from __future__ import annotations

import base64
from typing import Any

DOCUMENT_KEY_EXAMPLE = "demo-document-key-not-real"
SIGNED_XML_BASE64 = base64.b64encode(b"<Signed>ok</Signed>").decode("ascii")
INVOICE_XML_BASE64 = base64.b64encode(b"<Invoice>demo</Invoice>").decode("ascii")
ZIP_BASE64_EXAMPLE = base64.b64encode(b"zip-demo").decode("ascii")

DOCUMENT_SUBMISSION_INVOICE_EXAMPLE = {
    "client_reference": "pedido-erp-1001",
    "document": {
        "number": "FDK000001",
        "type": "FACTURA_ELECTRONICA",
        "issue_date": "2026-03-12",
        "issue_time": "14:30:00-05:00",
        "payment_method": "CASH",
    },
    "issuer": {
        "nit": "900123456",
        "dv": "7",
        "name": "Example Issuer SAS",
        "additional_account_id": "1",
        "address": "Street 10 #20-30",
        "city_code": "11001",
        "city_name": "Bogota",
        "department_code": "11",
        "department_name": "Bogota D.C.",
        "country_code": "CO",
        "tax_level_code": "O-47",
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
    },
    "resolution": {
        "number": "18764000001",
        "prefix": "FDK",
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
    },
}

DOCUMENT_SUBMISSION_POS_EXAMPLE = {
    "client_reference": "venta-pos-2001",
    "document": {
        "number": "POS000001",
        "type": "DOCUMENTO_EQUIVALENTE_POS",
        "issue_date": "2026-03-12",
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
    },
}

DOCUMENT_SUBMISSION_CREDIT_NOTE_EXAMPLE = {
    "client_reference": "nc-1001",
    "document": {
        "number": "NC000001",
        "type": "NOTA_CREDITO",
        "issue_date": "2026-03-13",
        "issue_time": "09:00:00-05:00",
        "payment_method": "CASH",
    },
    "buyer": {
        "document_number": "800199436",
        "document_type": "NIT",
        "name": "Empresa Ejemplo S.A.S.",
    },
    "resolution": {
        "number": "18764000001",
        "prefix": "NC",
    },
    "totals": {
        "subtotal": 50000,
        "tax_total": 9500,
        "total": 59500,
    },
    "line_items": [
        {
            "description": "Tornillo hexagonal 1/4 x 1 zinc",
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
    },
    "submission_options": {
        "software_id": "software-demo-id",
        "software_pin": "pin-demo-001",
        "test_set_id": "test-set-demo-001",
    },
}

DOCUMENT_SUBMISSION_DEBIT_NOTE_EXAMPLE = {
    "client_reference": "nd-1001",
    "document": {
        "number": "ND000001",
        "type": "NOTA_DEBITO",
        "issue_date": "2026-03-13",
        "issue_time": "11:00:00-05:00",
        "payment_method": "CASH",
    },
    "buyer": {
        "document_number": "800199436",
        "document_type": "NIT",
        "name": "Empresa Ejemplo S.A.S.",
    },
    "resolution": {
        "number": "18764000001",
        "prefix": "ND",
    },
    "totals": {
        "subtotal": 10000,
        "tax_total": 1900,
        "total": 11900,
    },
    "line_items": [
        {
            "description": "Ajuste por intereses",
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
    },
}

DOCUMENT_SUBMISSION_REQUEST_EXAMPLES = [
    DOCUMENT_SUBMISSION_INVOICE_EXAMPLE,
    DOCUMENT_SUBMISSION_POS_EXAMPLE,
    DOCUMENT_SUBMISSION_CREDIT_NOTE_EXAMPLE,
    DOCUMENT_SUBMISSION_DEBIT_NOTE_EXAMPLE,
]

DOCUMENT_SUBMISSION_OPENAPI_EXAMPLES = {
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
        "xml_filename": "ws_FDK000001.xml",
    },
}

DOCUMENT_STATUS_RESPONSE_EXAMPLE: dict[str, Any] = {
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
        "document_key": None,
        "error_messages": [],
    },
    "artifacts": None,
}

# Documento ya procesado: DIAN reporta la clave (XmlDocumentKey) y el AR firmado.
DOCUMENT_STATUS_ACCEPTED_RESPONSE_EXAMPLE: dict[str, Any] = {
    "submission_id": "0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9",
    "tracking_id": "0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9",
    "client_reference": None,
    "document_key": DOCUMENT_KEY_EXAMPLE,
    "qr_url": f"https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={DOCUMENT_KEY_EXAMPLE}",
    "status": "accepted",
    "messages": ["Procesado Correctamente."],
    "dian_response": {
        "is_valid": True,
        "status_code": "00",
        "status_description": "Procesado Correctamente.",
        "status_message": "La Factura electronica FDK000001, ha sido autorizada.",
        "tracking_id": "0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9",
        "document_key": DOCUMENT_KEY_EXAMPLE,
        "error_messages": [],
    },
    "artifacts": {
        "xml_base64": None,
        "xml_filename": None,
        "application_response_xml_base64": "PEFwcGxpY2F0aW9uUmVzcG9uc2U+Li4uPC9BcHBsaWNhdGlvblJlc3BvbnNlPg==",
        "application_response_xml_filename": "ar_0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9.xml",
    },
}

ATTACHED_DOCUMENT_REQUEST_EXAMPLE = {
    "document_number": "FDK000001",
    "document_type_code": "01",
    "issuer_nit": "900123456",
    "issuer_name": "Example Issuer SAS",
    "receiver_name": "Cliente Demo SAS",
    "receiver_email": "facturas@cliente.test",
    "reply_to_email": "billing@example-issuer.test",
    "company_name": "Example Issuer SAS",
    "business_line": "Ferreteria y materiales",
    "invoice_xml_base64": INVOICE_XML_BASE64,
    "invoice_xml_filename": "ws_FDK000001.xml",
    "issue_date": "2026-04-01",
    "cufe": DOCUMENT_KEY_EXAMPLE,
    "validation_result_code": "02",
}

ATTACHED_DOCUMENT_RESPONSE_EXAMPLE = {
    "xml_filename": "ad_FDK000001.xml",
    "zip_filename": "ad_FDK000001.zip",
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
    "version": "0.1.0a0",
    "dian_environment": "habilitacion",
    "certificate_loaded": True,
    "certificate_valid_until": "2027-12-31T23:59:59+00:00",
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
        "application_response_xml_filename": "ar_030_SETP990000123.xml",
        "dian_response_xml_base64": DIAN_EVENT_RESPONSE_XML_BASE64,
        "dian_response_xml_filename": "dian_030_SETP990000123.xml",
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
