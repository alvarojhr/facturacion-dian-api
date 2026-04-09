"""Shared test fixtures for facturacion-dian-kit."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from facturacion_dian_kit.core.dian.client import DianClient
from facturacion_dian_kit.core.dian.response_parser import (
    AcquirerResponse,
    DianResponse,
    NumberingRange,
    NumberingRangeResponse,
)
from facturacion_dian_kit.server.app import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""

    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_live_dian_calls(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Keep the default test suite deterministic by stubbing DIAN network calls."""

    if request.node.get_closest_marker("integration"):
        return

    async def fake_submit(
        self: DianClient,
        filename: str,
        content_b64: str,
        test_set_id: str | None = None,
    ) -> DianResponse:
        del self, filename, content_b64, test_set_id
        return DianResponse(
            is_valid=True,
            status_code="00",
            status_description="Processed successfully.",
            status_message="Document received successfully.",
            tracking_id=str(uuid4()),
        )

    async def fake_status(self: DianClient, tracking_id: str) -> DianResponse:
        del self
        return DianResponse(
            is_valid=False,
            status_code="99",
            status_description="Document not found.",
            status_message="Tracking ID not found.",
            tracking_id=tracking_id,
        )

    async def fake_get_acquirer(
        self: DianClient,
        identification_type: str,
        identification_number: str,
    ) -> AcquirerResponse:
        del self, identification_type
        if identification_number == "0000000000":
            return AcquirerResponse(
                found=False,
                status_code="404",
                message="Buyer not found",
            )

        return AcquirerResponse(
            found=True,
            status_code="00",
            message="Buyer found",
            receiver_name="Cliente DIAN S.A.S.",
            receiver_email="contacto@cliente-dian.test",
        )

    async def fake_get_numbering_range(
        self: DianClient,
        account_code: str,
        account_code_t: str,
        software_code: str,
    ) -> NumberingRangeResponse:
        del self, account_code, account_code_t, software_code
        return NumberingRangeResponse(
            ranges=[
                NumberingRange(
                    resolution_number="18764107158626",
                    resolution_date="2026-03-13",
                    prefix="FDK",
                    from_number=1,
                    to_number=99999,
                    valid_date_from="2026-03-13",
                    valid_date_to="2028-03-13",
                    technical_key="tech-key-fe",
                ),
                NumberingRange(
                    resolution_number="18764107158627",
                    resolution_date="2026-03-13",
                    prefix="POS",
                    from_number=1,
                    to_number=999999,
                    valid_date_from="2026-03-13",
                    valid_date_to="2028-03-13",
                    technical_key="tech-key-pos",
                ),
            ]
        )

    monkeypatch.setattr(DianClient, "send_test_set_async", fake_submit)
    monkeypatch.setattr(DianClient, "send_bill_sync", fake_submit)
    monkeypatch.setattr(DianClient, "get_status", fake_status)
    monkeypatch.setattr(DianClient, "get_status_zip", fake_status)
    monkeypatch.setattr(DianClient, "get_acquirer", fake_get_acquirer)
    monkeypatch.setattr(DianClient, "get_numbering_range", fake_get_numbering_range)
    monkeypatch.setattr(
        "facturacion_dian_kit.core.submission.get_certificate_bundle",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "facturacion_dian_kit.core.submission.sign_document_xml",
        lambda xml_root, bundle: b"<Signed>ok</Signed>",
    )


@pytest.fixture
def sample_invoice_payload() -> dict:
    """Sample FACTURA_ELECTRONICA payload for the public API."""

    return {
        "client_reference": "client-ref-001",
        "document": {
            "number": "FDK000001",
            "type": "FACTURA_ELECTRONICA",
            "issue_date": "2026-03-12",
            "issue_time": "14:30:00-05:00",
            "payment_method": "CASH",
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
                "quantity": 100,
                "unit_price": 500,
                "line_total": 50000,
                "tax_type": "IVA_19",
                "tax_amount": 9500,
            },
            {
                "description": "Tuerca hexagonal 1/4 zinc",
                "quantity": 100,
                "unit_price": 500,
                "line_total": 50000,
                "tax_type": "IVA_19",
                "tax_amount": 9500,
            },
        ],
        "submission_options": {
            "software_id": "software-123",
            "software_pin": "12345",
            "technical_key": "fc8eac422eba16e22ffd8c6f94b3f40a6e38162c",
            "test_set_id": "test-set-123",
        },
    }


@pytest.fixture
def sample_pos_payload() -> dict:
    """Sample DOCUMENTO_EQUIVALENTE_POS payload."""

    return {
        "document": {
            "number": "POS000001",
            "type": "DOCUMENTO_EQUIVALENTE_POS",
            "issue_date": "2026-03-12",
            "issue_time": "10:15:30-05:00",
            "payment_method": "CARD",
            "point_of_sale": {
                "register_plate": "POS-1",
                "register_location": "Main counter",
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
                "quantity": 1,
                "unit_price": 42000,
                "line_total": 42000,
                "tax_type": "IVA_19",
                "tax_amount": 7980,
            }
        ],
        "submission_options": {
            "software_id": "software-123",
            "software_pin": "12345",
            "test_set_id": "test-set-123",
        },
    }


@pytest.fixture
def sample_credit_note_payload() -> dict:
    """Sample NOTA_CREDITO payload."""

    return {
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
            "referenced_document_key": "abc123def456",
            "referenced_issue_date": "2026-03-12",
            "reason": "Partial return",
        },
        "submission_options": {
            "software_id": "software-123",
            "software_pin": "12345",
            "test_set_id": "test-set-123",
        },
    }


@pytest.fixture
def sample_debit_note_payload() -> dict:
    """Sample NOTA_DEBITO payload."""

    return {
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
            "referenced_document_key": "abc123def456",
            "referenced_issue_date": "2026-03-12",
            "reason": "Interest charge",
            "response_code": "1",
        },
        "submission_options": {
            "software_id": "software-123",
            "software_pin": "12345",
            "test_set_id": "test-set-123",
        },
    }
