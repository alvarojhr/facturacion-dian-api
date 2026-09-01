"""Tests for UBL 2.1 XML builders.

Validates structure, namespace correctness, and content for:
- Factura Electrónica (Invoice)
- Documento Equivalente POS (Invoice variant)
- Nota Crédito (CreditNote)
"""

from __future__ import annotations

import pytest
from facturacion_dian_api.core.config import settings
from facturacion_dian_api.core.models import (
    DocumentLine,
    DocumentSubmitRequest,
    EventReceiverPerson,
    EventSubmitRequest,
)
from facturacion_dian_api.core.xml.application_response_builder import (
    application_response_to_xml_string,
    build_application_response_xml,
)
from facturacion_dian_api.core.xml.common import _money, _sub, build_invoice_line, build_tax_totals
from facturacion_dian_api.core.xml.credit_note_builder import (
    build_credit_note_xml,
    credit_note_to_xml_string,
)
from facturacion_dian_api.core.xml.debit_note_builder import (
    build_debit_note_xml,
    debit_note_to_xml_string,
)
from facturacion_dian_api.core.xml.invoice_builder import build_invoice_xml, invoice_to_xml_string
from facturacion_dian_api.core.xml.namespaces import (
    APPLICATION_RESPONSE_PROFILE_ID,
    EVENT_DESCRIPTIONS,
    NS_APPLICATION_RESPONSE,
    NS_CAC,
    NS_CBC,
    NS_CREDIT_NOTE,
    NS_DEBIT_NOTE,
    NS_EXT,
    NS_INVOICE,
    NS_STS,
    cac,
    cbc,
    ext,
)
from lxml import etree

# ─── Namespace shortcuts for XPath ─────────────────────────────

NS = {
    "inv": NS_INVOICE,
    "cn": NS_CREDIT_NOTE,
    "dn": NS_DEBIT_NOTE,
    "ar": NS_APPLICATION_RESPONSE,
    "cac": NS_CAC,
    "cbc": NS_CBC,
    "ext": NS_EXT,
    "sts": NS_STS,
}


# ─── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def invoice_request() -> DocumentSubmitRequest:
    return DocumentSubmitRequest(
        invoice_number="SETT000001",
        document_type="FACTURA_ELECTRONICA",
        customer_nit="800199436",
        customer_document_type="NIT",
        customer_name="Empresa Ejemplo S.A.S.",
        customer_email="compras@ejemplo.com",
        customer_phone="3001234567",
        customer_address="Calle 10 # 5-11",
        customer_city_code="11001",
        customer_city_name="Bogota",
        customer_department_code="11",
        customer_department_name="Bogota D.C.",
        customer_country_code="CO",
        issue_date="2026-03-12",
        issue_time="14:30:00-05:00",
        subtotal=100000,
        tax_total=19000,
        total=119000,
        lines=[
            DocumentLine(
                description="Tornillo hexagonal 1/4 x 1 zinc",
                item_name="Tornillo hexagonal 1/4 x 1 zinc",
                item_code="SKU-0001",
                unit_code="94",
                quantity=100,
                unit_price=500,
                line_total=50000,
                tax_type="IVA_19",
                tax_amount=9500,
            ),
            DocumentLine(
                description="Tuerca hexagonal 1/4 zinc",
                item_name="Tuerca hexagonal 1/4 zinc",
                item_code="SKU-0002",
                unit_code="94",
                quantity=100,
                unit_price=500,
                line_total=50000,
                tax_type="IVA_19",
                tax_amount=9500,
            ),
        ],
        payment_method="CASH",
        resolution_number="18764000001",
        prefix="SETT",
        resolution_range_from=120,
        resolution_range_to=240,
        resolution_valid_from="2026-01-01",
        resolution_valid_to="2026-12-31",
        client_reference="550e8400-e29b-41d4-a716-446655440000",
    )


@pytest.fixture
def pos_request() -> DocumentSubmitRequest:
    return DocumentSubmitRequest(
        invoice_number="POS000001",
        document_type="DOCUMENTO_EQUIVALENTE_POS",
        customer_nit=None,
        customer_document_type="FINAL_CONSUMER",
        customer_name="Consumidor Final",
        issue_date="2026-03-12",
        issue_time="10:15:30-05:00",
        subtotal=42000,
        tax_total=7980,
        total=49980,
        lines=[
            DocumentLine(
                description="Martillo carpintero 16oz",
                item_name="Martillo carpintero 16oz",
                item_code="SKU-0100",
                unit_code="94",
                quantity=1,
                unit_price=42000,
                line_total=42000,
                tax_type="IVA_19",
                tax_amount=7980,
            ),
        ],
        payment_method="CARD",
        resolution_number="18764000002",
        prefix="POS",
        resolution_range_from=1,
        resolution_range_to=999999,
        resolution_valid_from="2019-01-19",
        resolution_valid_to="2030-01-19",
        pos_register_plate="Caja 1",
        pos_register_location="Carrera 50 # 10 - 20, Floridablanca",
        cashier_name="Administrador",
        pos_register_type="POS",
        sale_code="POS-20260314-TEST",
        buyer_loyalty_points=0,
        client_reference="660e8400-e29b-41d4-a716-446655440001",
    )


@pytest.fixture
def identified_pos_request() -> DocumentSubmitRequest:
    return DocumentSubmitRequest(
        invoice_number="POS000002",
        document_type="DOCUMENTO_EQUIVALENTE_POS",
        customer_nit="12345678",
        customer_document_type="CC",
        customer_name="Cliente POS Identificado",
        customer_email="cliente.pos@example.com",
        customer_phone="3110000000",
        customer_address="Carrera 7 # 12-34",
        customer_city_code="05001",
        customer_city_name="Medellin",
        customer_department_code="05",
        customer_department_name="Antioquia",
        customer_country_code="CO",
        issue_date="2026-03-12",
        issue_time="11:00:00-05:00",
        subtotal=20000,
        tax_total=3800,
        total=23800,
        lines=[
            DocumentLine(
                description="Broca metal 1/4",
                item_name="Broca metal 1/4",
                item_code="SKU-0101",
                unit_code="94",
                quantity=1,
                unit_price=20000,
                line_total=20000,
                tax_type="IVA_19",
                tax_amount=3800,
            ),
        ],
        payment_method="CARD",
        resolution_number="18764000002",
        prefix="POS",
        resolution_range_from=1,
        resolution_range_to=999999,
        resolution_valid_from="2019-01-19",
        resolution_valid_to="2030-01-19",
        pos_register_plate="Caja 1",
        pos_register_location="Carrera 50 # 10 - 20, Floridablanca",
        cashier_name="Administrador",
        pos_register_type="POS",
        sale_code="POS-20260314-TEST-2",
        buyer_loyalty_points=0,
        client_reference="770e8400-e29b-41d4-a716-446655440002",
    )


@pytest.fixture
def credit_note_request() -> DocumentSubmitRequest:
    return DocumentSubmitRequest(
        invoice_number="SETT000001",
        document_type="NOTA_CREDITO",
        customer_nit="800199436",
        customer_name="Empresa Ejemplo S.A.S.",
        issue_date="2026-03-13",
        issue_time="09:00:00-05:00",
        subtotal=50000,
        tax_total=9500,
        total=59500,
        lines=[
            DocumentLine(
                description="Tornillo hexagonal 1/4 x 1 zinc",
                quantity=100,
                unit_price=500,
                line_total=50000,
                tax_type="IVA_19",
                tax_amount=9500,
            ),
        ],
        payment_method="CASH",
        resolution_number="18764000001",
        prefix="NC",
        resolution_range_from=30,
        resolution_range_to=60,
        resolution_valid_from="2026-02-01",
        resolution_valid_to="2026-12-31",
        client_reference="550e8400-e29b-41d4-a716-446655440000",
        credit_note_number="NC000001",
        referenced_invoice_number="SETT000001",
        referenced_invoice_cufe="abc123def456",
        credit_note_reason="Devolución parcial de mercancía",
    )


@pytest.fixture
def debit_note_request() -> DocumentSubmitRequest:
    return DocumentSubmitRequest(
        invoice_number="SETT000001",
        document_type="NOTA_DEBITO",
        customer_nit="800199436",
        customer_name="Empresa Ejemplo S.A.S.",
        issue_date="2026-03-13",
        issue_time="11:00:00-05:00",
        subtotal=10000,
        tax_total=1900,
        total=11900,
        lines=[
            DocumentLine(
                description="Ajuste por intereses",
                quantity=1,
                unit_price=10000,
                line_total=10000,
                tax_type="IVA_19",
                tax_amount=1900,
            ),
        ],
        payment_method="CASH",
        resolution_number="18764000001",
        prefix="ND",
        resolution_range_from=70,
        resolution_range_to=90,
        resolution_valid_from="2026-03-01",
        resolution_valid_to="2026-12-31",
        client_reference="550e8400-e29b-41d4-a716-446655440000",
        debit_note_number="ND000001",
        referenced_invoice_number="SETT000001",
        referenced_invoice_cufe="abc123def456",
        debit_note_reason="Intereses",
        debit_note_response_code="1",
    )


FAKE_CUFE = "a" * 96  # 96-char hex simulating SHA-384


# ─── Helper ─────────────────────────────────────────────────────


def _xpath(root: etree._Element, expr: str) -> list:
    """Run XPath with standard namespace map."""
    return root.xpath(expr, namespaces=NS)


def _xpath_text(root: etree._Element, expr: str) -> str | None:
    """Run XPath and return text of first match."""
    result = _xpath(root, expr)
    if result:
        el = result[0]
        return el.text if hasattr(el, "text") else str(el)
    return None


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Invoice Builder (Factura Electrónica)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestInvoiceBuilderStructure:
    """Test basic Invoice XML structure and namespaces."""

    def test_root_element_is_invoice(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert root.tag == f"{{{NS_INVOICE}}}Invoice"

    def test_root_has_correct_namespaces(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        nsmap = root.nsmap
        assert nsmap[None] == NS_INVOICE
        assert nsmap["cac"] == NS_CAC
        assert nsmap["cbc"] == NS_CBC
        assert nsmap["ext"] == NS_EXT
        assert nsmap["sts"] == NS_STS

    def test_ubl_version(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:UBLVersionID") == "UBL 2.1"

    def test_customization_id_factura(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:CustomizationID") == "10"

    def test_profile_id(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:ProfileID") == "DIAN 2.1: Factura Electrónica de Venta"

    def test_profile_execution_id(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:ProfileExecutionID") == settings.dian.tipo_ambiente

    def test_document_id(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:ID") == "SETT000001"

    def test_cufe_in_uuid(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        uuid_el = _xpath(root, "cbc:UUID")[0]
        assert uuid_el.text == FAKE_CUFE
        assert uuid_el.get("schemeName") == "CUFE-SHA384"

    def test_issue_date_and_time(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:IssueDate") == "2026-03-12"
        assert _xpath_text(root, "cbc:IssueTime") == "14:30:00-05:00"

    def test_due_date_defaults_to_issue_date(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:DueDate") == "2026-03-12"

    def test_credit_separates_form_means_and_due_date(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        payload = invoice_request.model_dump()
        payload.update(
            payment_method=None,
            payment_form="CREDITO",
            payment_means="DEBIT_CARD",
            due_date="2026-04-12",
        )
        root = build_invoice_xml(DocumentSubmitRequest.model_validate(payload), FAKE_CUFE)
        assert _xpath_text(root, "cbc:DueDate") == "2026-04-12"
        assert _xpath_text(root, "cac:PaymentMeans/cbc:ID") == "2"
        assert _xpath_text(root, "cac:PaymentMeans/cbc:PaymentMeansCode") == "49"
        assert _xpath_text(root, "cac:PaymentMeans/cbc:PaymentDueDate") == "2026-04-12"

    def test_invoice_type_code_factura(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:InvoiceTypeCode") == "01"

    def test_currency_code(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:DocumentCurrencyCode") == "COP"

    def test_line_count_numeric(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:LineCountNumeric") == "2"


class TestInvoiceBuilderParties:
    """Test supplier and customer party elements."""

    def test_supplier_party_exists(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        supplier = _xpath(root, "cac:AccountingSupplierParty")
        assert len(supplier) == 1

    def test_supplier_additional_account_id_defaults_to_juridica(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        account_id = _xpath_text(root, "cac:AccountingSupplierParty/cbc:AdditionalAccountID")
        assert account_id == settings.company.additional_account_id

    def test_supplier_additional_account_id_persona_natural(
        self, invoice_request: DocumentSubmitRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Un emisor persona natural debe declarar "2". Antes estaba
        # hardcodeado "1" y DIAN mostraba "Persona Jurídica".
        monkeypatch.setattr(settings.company, "additional_account_id", "2")
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        account_id = _xpath_text(root, "cac:AccountingSupplierParty/cbc:AdditionalAccountID")
        assert account_id == "2"

    def test_supplier_complete_body_identity_overrides_company_config(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        body_request = invoice_request.model_copy(
            update={
                "issuer_nit": "12345678",
                "issuer_dv": "8",
                "issuer_name": "PEREZ GOMEZ ANA LUCIA",
                "issuer_additional_account_id": "2",
                "issuer_address": "CL 100 # 15-20 BRR EJEMPLO",
                "issuer_city_code": "68276",
                "issuer_city_name": "Floridablanca",
                "issuer_department_code": "68",
                "issuer_department_name": "Santander",
                "issuer_country_code": "CO",
                "issuer_tax_level_code": "R-99-PN",
                "issuer_economic_activity": "4752",
                "issuer_phone": "3001234567",
                "issuer_email": "ana.perez@example.com",
            }
        )

        root = build_invoice_xml(body_request, FAKE_CUFE)
        supplier = "cac:AccountingSupplierParty"

        assert _xpath_text(root, f"{supplier}/cbc:AdditionalAccountID") == "2"
        assert _xpath_text(root, f"{supplier}/cac:Party/cbc:IndustryClassificationCode") == "4752"
        assert _xpath_text(root, f"{supplier}/cac:Party/cac:PartyName/cbc:Name") == (
            "PEREZ GOMEZ ANA LUCIA"
        )
        assert _xpath_text(
            root, f"{supplier}/cac:Party/cac:PhysicalLocation/cac:Address/cbc:ID"
        ) == ("68276")
        assert (
            _xpath_text(
                root,
                f"{supplier}/cac:Party/cac:PhysicalLocation/cac:Address/cac:AddressLine/cbc:Line",
            )
            == "CL 100 # 15-20 BRR EJEMPLO"
        )
        assert (
            _xpath_text(
                root,
                f"{supplier}/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode",
            )
            == "R-99-PN"
        )
        assert (
            _xpath_text(
                root,
                f"{supplier}/cac:Party/cac:PartyTaxScheme/cbc:CompanyID",
            )
            == "12345678"
        )
        assert _xpath_text(root, f"{supplier}/cac:Party/cac:Contact/cbc:Telephone") == (
            "3001234567"
        )
        assert _xpath_text(root, f"{supplier}/cac:Party/cac:Contact/cbc:ElectronicMail") == (
            "ana.perez@example.com"
        )

    def test_supplier_complete_body_falls_back_per_missing_field(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        body_request = invoice_request.model_copy(
            update={
                "issuer_name": "Body Issuer",
                "issuer_city_name": "Body City",
                "issuer_address": None,
            }
        )

        root = build_invoice_xml(body_request, FAKE_CUFE)
        address = "cac:AccountingSupplierParty/cac:Party/cac:PhysicalLocation/cac:Address"
        assert _xpath_text(root, f"{address}/cbc:CityName") == "Body City"
        assert _xpath_text(root, f"{address}/cac:AddressLine/cbc:Line") == settings.company.address

    def test_supplier_without_name_preserves_legacy_company_identity(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        legacy_request = invoice_request.model_copy(
            update={
                "issuer_name": None,
                "issuer_address": "THIS MUST BE IGNORED",
                "issuer_city_name": "THIS MUST BE IGNORED",
                "issuer_economic_activity": "9999",
            }
        )

        root = build_invoice_xml(legacy_request, FAKE_CUFE)
        supplier = "cac:AccountingSupplierParty/cac:Party"
        assert _xpath_text(root, f"{supplier}/cac:PartyName/cbc:Name") == settings.company.name
        assert (
            _xpath_text(
                root,
                f"{supplier}/cac:PhysicalLocation/cac:Address/cac:AddressLine/cbc:Line",
            )
            == settings.company.address
        )
        assert _xpath(root, f"{supplier}/cbc:IndustryClassificationCode") == []

    def test_customer_party_exists(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        customer = _xpath(root, "cac:AccountingCustomerParty")
        assert len(customer) == 1

    def test_customer_name(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        name = _xpath_text(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name")
        assert name == "Empresa Ejemplo S.A.S."

    def test_customer_nit_persona_juridica(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        account_id = _xpath_text(root, "cac:AccountingCustomerParty/cbc:AdditionalAccountID")
        assert account_id == "1"  # 1 = Persona Jurídica

    def test_customer_email_in_contact(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        email = _xpath_text(
            root, "cac:AccountingCustomerParty/cac:Party/cac:Contact/cbc:ElectronicMail"
        )
        assert email == "compras@ejemplo.com"

    def test_supplier_corporate_registration_matches_prefix(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        registration_id = _xpath_text(
            root,
            "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/"
            "cac:CorporateRegistrationScheme/cbc:ID",
        )
        assert registration_id == "SETT"

    def test_supplier_corporate_registration_name_uses_nit(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        registration_name = _xpath_text(
            root,
            "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/"
            "cac:CorporateRegistrationScheme/cbc:Name",
        )
        assert registration_name == settings.company.nit

    def test_customer_nit_uses_computed_verification_digit(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        company_id = _xpath(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID",
        )[0]
        assert company_id.get("schemeID") == "4"

    def test_customer_address_uses_request_fields(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert (
            _xpath_text(
                root,
                "cac:AccountingCustomerParty/cac:Party/cac:PhysicalLocation/cac:Address/cbc:CityName",
            )
            == "Bogota"
        )
        assert (
            _xpath_text(
                root,
                "cac:AccountingCustomerParty/cac:Party/cac:PhysicalLocation/cac:Address/cac:AddressLine/cbc:Line",
            )
            == "Calle 10 # 5-11"
        )

    def test_customer_contact_includes_phone(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert (
            _xpath_text(
                root,
                "cac:AccountingCustomerParty/cac:Party/cac:Contact/cbc:Telephone",
            )
            == "3001234567"
        )


class TestInvoiceBuilderResolution:
    """Test numbering resolution data under DianExtensions."""

    def test_invoice_control_uses_resolution_data(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert (
            _xpath_text(
                root,
                "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
                "sts:DianExtensions/sts:InvoiceControl/sts:InvoiceAuthorization",
            )
            == "18764000001"
        )
        assert (
            _xpath_text(
                root,
                "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
                "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizedInvoices/sts:Prefix",
            )
            == "SETT"
        )
        assert (
            _xpath_text(
                root,
                "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
                "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizedInvoices/sts:From",
            )
            == "120"
        )
        assert (
            _xpath_text(
                root,
                "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
                "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizedInvoices/sts:To",
            )
            == "240"
        )
        assert (
            _xpath_text(
                root,
                "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
                "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizationPeriod/cbc:StartDate",
            )
            == "2026-01-01"
        )
        assert (
            _xpath_text(
                root,
                "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
                "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizationPeriod/cbc:EndDate",
            )
            == "2026-12-31"
        )


class TestInvoiceBuilderTaxes:
    """Test tax totals and monetary totals."""

    def test_tax_total_exists(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        tax_totals = _xpath(root, "cac:TaxTotal")
        assert len(tax_totals) == 1

    def test_tax_total_amount(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        amount = _xpath_text(root, "cac:TaxTotal/cbc:TaxAmount")
        assert amount == "19000.00"

    def test_tax_amount_currency(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        el = _xpath(root, "cac:TaxTotal/cbc:TaxAmount")[0]
        assert el.get("currencyID") == "COP"

    def test_tax_subtotal_percent(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        percent = _xpath_text(root, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent")
        assert percent == "19.00"

    def test_legal_monetary_total(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount") == "100000.00"
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount") == "119000.00"
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount") == "119000.00"

    def test_tax_totals_keep_multiple_rates_under_same_scheme(
        self,
        invoice_request: DocumentSubmitRequest,
    ) -> None:
        mixed_request = invoice_request.model_copy(
            update={
                "subtotal": 100000,
                "tax_total": 12000,
                "total": 112000,
                "lines": [
                    DocumentLine(
                        description="Producto IVA 19",
                        item_name="Producto IVA 19",
                        item_code="SKU-19",
                        unit_code="94",
                        quantity=1,
                        unit_price=50000,
                        line_total=50000,
                        tax_type="IVA_19",
                        tax_amount=9500,
                    ),
                    DocumentLine(
                        description="Producto IVA 5",
                        item_name="Producto IVA 5",
                        item_code="SKU-05",
                        unit_code="94",
                        quantity=1,
                        unit_price=50000,
                        line_total=50000,
                        tax_type="IVA_5",
                        tax_amount=2500,
                    ),
                ],
            }
        )

        root = build_invoice_xml(mixed_request, FAKE_CUFE)

        tax_totals = _xpath(root, "cac:TaxTotal")
        assert len(tax_totals) == 1
        percents = sorted(
            el.text or ""
            for el in _xpath(root, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent")
        )
        assert percents == ["19.00", "5.00"]
        schemes = {
            el.text or ""
            for el in _xpath(
                root,
                "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID",
            )
        }
        assert schemes == {"01"}

    def test_excluded_lines_do_not_emit_document_tax_totals(
        self,
        invoice_request: DocumentSubmitRequest,
    ) -> None:
        excluded_request = invoice_request.model_copy(
            update={
                "subtotal": 100000,
                "tax_total": 0,
                "total": 100000,
                "lines": [
                    DocumentLine(
                        description="Producto excluido",
                        item_name="Producto excluido",
                        item_code="SKU-ZZ",
                        unit_code="94",
                        quantity=1,
                        unit_price=100000,
                        line_total=100000,
                        tax_type="EXCLUDED",
                        tax_amount=0,
                    ),
                ],
            }
        )

        root = build_invoice_xml(excluded_request, FAKE_CUFE)
        assert _xpath(root, "cac:TaxTotal") == []
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount") == "100000.00"
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount") == "0.00"
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount") == "100000.00"

    def test_excluded_lines_are_ignored_in_mixed_document_tax_totals(
        self,
        invoice_request: DocumentSubmitRequest,
    ) -> None:
        mixed_request = invoice_request.model_copy(
            update={
                "subtotal": 100000,
                "tax_total": 9500,
                "total": 109500,
                "lines": [
                    DocumentLine(
                        description="Producto gravado",
                        item_name="Producto gravado",
                        item_code="SKU-19",
                        unit_code="94",
                        quantity=1,
                        unit_price=50000,
                        line_total=50000,
                        tax_type="IVA_19",
                        tax_amount=9500,
                    ),
                    DocumentLine(
                        description="Producto excluido",
                        item_name="Producto excluido",
                        item_code="SKU-ZZ",
                        unit_code="94",
                        quantity=1,
                        unit_price=50000,
                        line_total=50000,
                        tax_type="EXCLUDED",
                        tax_amount=0,
                    ),
                ],
            }
        )

        root = build_invoice_xml(mixed_request, FAKE_CUFE)

        tax_totals = _xpath(root, "cac:TaxTotal")
        assert len(tax_totals) == 1
        assert _xpath_text(root, "cac:TaxTotal/cbc:TaxAmount") == "9500.00"
        assert _xpath_text(root, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount") == "50000.00"
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount") == "100000.00"
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount") == "50000.00"
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount") == "109500.00"


class TestInvoiceBuilderLines:
    """Test invoice lines."""

    def test_correct_number_of_lines(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        lines = _xpath(root, "cac:InvoiceLine")
        assert len(lines) == 2

    def test_line_ids_sequential(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        lines = _xpath(root, "cac:InvoiceLine")
        ids = [line.find(cbc("ID")).text for line in lines]
        assert ids == ["1", "2"]

    def test_line_quantity(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        qty = _xpath_text(root, "cac:InvoiceLine[1]/cbc:InvoicedQuantity")
        assert qty == "100.0"  # quantity is float

    def test_line_quantity_unit_code(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        el = _xpath(root, "cac:InvoiceLine[1]/cbc:InvoicedQuantity")[0]
        assert el.get("unitCode") == "94"

    def test_line_extension_amount(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        amount = _xpath_text(root, "cac:InvoiceLine[1]/cbc:LineExtensionAmount")
        assert amount == "50000.00"

    def test_line_item_description(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        desc = _xpath_text(root, "cac:InvoiceLine[1]/cac:Item/cbc:Description")
        assert desc == "Tornillo hexagonal 1/4 x 1 zinc"

    def test_line_item_identification(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert (
            _xpath_text(root, "cac:InvoiceLine[1]/cac:Item/cbc:Name")
            == "Tornillo hexagonal 1/4 x 1 zinc"
        )
        assert (
            _xpath_text(root, "cac:InvoiceLine[1]/cac:Item/cac:SellersItemIdentification/cbc:ID")
            == "SKU-0001"
        )
        standard = _xpath(
            root, "cac:InvoiceLine[1]/cac:Item/cac:StandardItemIdentification/cbc:ID"
        )[0]
        assert standard.text == "SKU-0001"
        assert standard.get("schemeID") == "999"

    def test_line_price(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        price = _xpath_text(root, "cac:InvoiceLine[1]/cac:Price/cbc:PriceAmount")
        assert price == "500.00"

    def test_line_tax_total(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        tax = _xpath_text(root, "cac:InvoiceLine[1]/cac:TaxTotal/cbc:TaxAmount")
        assert tax == "9500.00"

    def test_excluded_line_omits_tax_total(self, invoice_request: DocumentSubmitRequest) -> None:
        excluded_request = invoice_request.model_copy(
            update={
                "subtotal": 100000,
                "tax_total": 0,
                "total": 100000,
                "lines": [
                    DocumentLine(
                        description="Producto excluido",
                        item_name="Producto excluido",
                        item_code="SKU-ZZ",
                        unit_code="94",
                        quantity=1,
                        unit_price=100000,
                        line_total=100000,
                        tax_type="EXCLUDED",
                        tax_amount=0,
                    ),
                ],
            }
        )

        root = build_invoice_xml(excluded_request, FAKE_CUFE)
        assert _xpath(root, "cac:InvoiceLine[1]/cac:TaxTotal") == []


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# POS Document (Documento Equivalente POS)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestPosDocBuilder:
    """Test POS document variant of Invoice builder."""

    def test_root_is_invoice(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        assert root.tag == f"{{{NS_INVOICE}}}Invoice"

    def test_customization_id_pos(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:CustomizationID") == "10"

    def test_profile_id_pos(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:ProfileID") == "DIAN 2.1: Documento Equivalente POS"

    def test_invoice_type_code_pos(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:InvoiceTypeCode") == "20"

    def test_uuid_scheme_cude(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        uuid_el = _xpath(root, "cbc:UUID")[0]
        assert uuid_el.get("schemeName") == "CUDE-SHA384"

    def test_consumidor_final_nit(self, pos_request: DocumentSubmitRequest) -> None:
        """POS without customer NIT should use consumidor final NIT."""
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        company_id = _xpath_text(
            root, "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID"
        )
        assert company_id == "222222222222"

    def test_consumidor_final_persona_natural(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        account_id = _xpath_text(root, "cac:AccountingCustomerParty/cbc:AdditionalAccountID")
        assert account_id == "2"  # 2 = Persona Natural

    def test_consumidor_final_has_party_identification(
        self, pos_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        identifier = _xpath(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        )[0]
        assert identifier.text == "222222222222"
        assert identifier.get("schemeName") == "13"

    def test_explicit_sentinel_nit_is_treated_as_final_consumer(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        # Un llamador que ya diligencia el centinela de DIAN, pero declara el
        # tipo documental como NIT, caia por la rama de adquiriente
        # identificado: se emitia PhysicalLocation y un TaxLevelCode de
        # responsable, cuando 222222222222 es justamente el consumidor final.
        request = invoice_request.model_copy(
            update={"customer_nit": "222222222222", "customer_document_type": "NIT"}
        )
        root = build_invoice_xml(request, FAKE_CUFE)

        tax_level_code = _xpath_text(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode",
        )
        assert tax_level_code == "R-99-PN"
        assert not _xpath(root, "cac:AccountingCustomerParty/cac:Party/cac:PhysicalLocation")

    def test_blank_nit_is_treated_as_final_consumer(
        self, pos_request: DocumentSubmitRequest
    ) -> None:
        request = pos_request.model_copy(update={"customer_nit": "   "})
        root = build_invoice_xml(request, FAKE_CUFE)

        identifier = _xpath(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        )[0]
        # Un NIT en blanco no puede viajar como identificador del adquiriente.
        assert identifier.text == "222222222222"

    def test_consumidor_final_registration_name_is_the_dian_literal(
        self, pos_request: DocumentSubmitRequest
    ) -> None:
        # FEV v1.9 FAK20 / DEE v1.0 DEAK20: el nombre fiscal del consumidor final
        # debe ser el literal, no el nombre que traiga el llamador.
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        registration_name = _xpath_text(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:RegistrationName",
        )
        assert registration_name == "consumidor final"

    def test_named_buyer_without_document_does_not_leak_name_into_tax_scheme(
        self, pos_request: DocumentSubmitRequest
    ) -> None:
        # Un ERP con el cliente a medias (nombre si, documento no) caia en la rama
        # de consumidor final y emitia un DE contradictorio: el identificador decia
        # "adquiriente no identificado" y el nombre fiscal decia "Juan Perez".
        request = pos_request.model_copy(
            update={
                "customer_nit": None,
                "customer_document_type": "CC",
                "customer_name": "Juan Perez",
            }
        )
        root = build_invoice_xml(request, FAKE_CUFE)

        assert (
            _xpath_text(
                root,
                "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:RegistrationName",
            )
            == "consumidor final"
        )
        # El nombre del llamador no se pierde: el anexo lo admite en PartyName/Name.
        assert (
            _xpath_text(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name")
            == "Juan Perez"
        )

    def test_identified_buyer_keeps_its_own_registration_name(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        # El literal es exclusivo de la rama de consumidor final: un adquiriente
        # identificado conserva su razon social registrada en el RUT.
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        registration_name = _xpath_text(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:RegistrationName",
        )
        assert registration_name == invoice_request.customer_name

    def test_single_line(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        lines = _xpath(root, "cac:InvoiceLine")
        assert len(lines) == 1

    def test_payment_means_card(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        code = _xpath_text(root, "cac:PaymentMeans/cbc:PaymentMeansCode")
        assert code == "48"  # Card

    def test_identified_pos_keeps_customer_document(
        self, identified_pos_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(identified_pos_request, FAKE_CUFE)
        company_id = _xpath(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID",
        )[0]
        assert company_id.text == "12345678"
        assert company_id.get("schemeName") == "13"

    def test_identified_pos_uses_customer_address(
        self, identified_pos_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(identified_pos_request, FAKE_CUFE)
        assert (
            _xpath_text(
                root,
                "cac:AccountingCustomerParty/cac:Party/cac:PhysicalLocation/cac:Address/cbc:CityName",
            )
            == "Medellin"
        )
        assert (
            _xpath_text(
                root,
                "cac:AccountingCustomerParty/cac:Party/cac:Contact/cbc:ElectronicMail",
            )
            == "cliente.pos@example.com"
        )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Credit Note Builder (Nota Crédito)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestCreditNoteBuilderStructure:
    """Test CreditNote XML structure."""

    def test_root_element_is_credit_note(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert root.tag == f"{{{NS_CREDIT_NOTE}}}CreditNote"

    def test_root_has_credit_note_namespace(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert root.nsmap[None] == NS_CREDIT_NOTE

    def test_document_id_is_credit_note_number(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        # Credit note uses its own number
        assert _xpath_text(root, "cbc:ID") == "NC000001"

    def test_uuid_scheme_cude(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        uuid_el = _xpath(root, "cbc:UUID")[0]
        assert uuid_el.text == FAKE_CUFE
        assert uuid_el.get("schemeName") == "CUDE-SHA384"

    def test_credit_note_type_code(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:CreditNoteTypeCode") == "91"

    def test_note_contains_reason(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        note = _xpath_text(root, "cbc:Note")
        assert note == "Devolución parcial de mercancía"

    def test_profile_id_matches_dian_catalog(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert (
            _xpath_text(root, "cbc:ProfileID")
            == "DIAN 2.1: Nota Crédito de Factura Electrónica de Venta"
        )

    def test_customization_id_matches_referenced_credit_note(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:CustomizationID") == "20"

    def test_credit_note_uses_request_resolution_control(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert (
            _xpath_text(
                root,
                "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
                "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizedInvoices/sts:From",
            )
            == "30"
        )
        assert (
            _xpath_text(
                root,
                "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
                "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizationPeriod/cbc:StartDate",
            )
            == "2026-02-01"
        )


class TestCreditNoteDiscrepancy:
    """Test DiscrepancyResponse and BillingReference elements."""

    def test_discrepancy_response_exists(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        discrepancy = _xpath(root, "cac:DiscrepancyResponse")
        assert len(discrepancy) == 1

    def test_discrepancy_reference_id(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        ref_id = _xpath_text(root, "cac:DiscrepancyResponse/cbc:ReferenceID")
        assert ref_id == "SETT000001"

    def test_discrepancy_response_code(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        code = _xpath_text(root, "cac:DiscrepancyResponse/cbc:ResponseCode")
        assert code == "1"  # Devolución parcial (anulación "2" is forbidden for tipo 22)

    def test_discrepancy_description(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        desc = _xpath_text(root, "cac:DiscrepancyResponse/cbc:Description")
        assert desc == "Devolución parcial de mercancía"

    def test_billing_reference_exists(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        billing_ref = _xpath(root, "cac:BillingReference")
        assert len(billing_ref) == 1

    def test_billing_reference_invoice_id(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        ref_id = _xpath_text(root, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID")
        assert ref_id == "SETT000001"

    def test_billing_reference_cufe(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        cufe = _xpath_text(root, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:UUID")
        assert cufe == "abc123def456"


class TestCreditNoteLines:
    """Test CreditNoteLine elements."""

    def test_uses_credit_note_line_tag(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        lines = _xpath(root, "cac:CreditNoteLine")
        assert len(lines) == 1

    def test_no_invoice_lines(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        lines = _xpath(root, "cac:InvoiceLine")
        assert len(lines) == 0

    def test_credited_quantity_tag(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        qty = _xpath(root, "cac:CreditNoteLine/cbc:CreditedQuantity")
        assert len(qty) == 1
        assert qty[0].text == "100.0"  # quantity is float

    def test_credit_note_monetary_total(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount") == "59500.00"


class TestDebitNoteBuilder:
    """Test DebitNote XML structure."""

    def test_root_element_is_debit_note(self, debit_note_request: DocumentSubmitRequest) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert root.tag == f"{{{NS_DEBIT_NOTE}}}DebitNote"

    def test_profile_id_matches_dian(self, debit_note_request: DocumentSubmitRequest) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert (
            _xpath_text(root, "cbc:ProfileID")
            == "DIAN 2.1: Nota Débito de Factura Electrónica de Venta"
        )

    def test_uses_requested_monetary_total(self, debit_note_request: DocumentSubmitRequest) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert _xpath_text(root, "cac:RequestedMonetaryTotal/cbc:PayableAmount") == "11900.00"

    def test_uses_debit_note_line(self, debit_note_request: DocumentSubmitRequest) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert len(_xpath(root, "cac:DebitNoteLine")) == 1
        assert _xpath_text(root, "cac:DebitNoteLine/cbc:DebitedQuantity") == "1.0"

    def test_billing_reference_cufe(self, debit_note_request: DocumentSubmitRequest) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert (
            _xpath_text(
                root,
                "cac:BillingReference/cac:InvoiceDocumentReference/cbc:UUID",
            )
            == "abc123def456"
        )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# UBL Extensions
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestUBLExtensions:
    """Test DIAN STS extensions and signature placeholder."""

    def test_two_extensions_present(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        extensions = _xpath(root, "ext:UBLExtensions/ext:UBLExtension")
        assert len(extensions) == 2

    def test_dian_extensions_element(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        dian_ext = _xpath(
            root, "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/sts:DianExtensions"
        )
        assert len(dian_ext) == 1

    def test_software_provider_exists(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        sp = _xpath(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent"
            "/sts:DianExtensions/sts:SoftwareProvider",
        )
        assert len(sp) == 1

    def test_software_security_code_exists(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        ssc = _xpath(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent"
            "/sts:DianExtensions/sts:SoftwareSecurityCode",
        )
        assert len(ssc) == 1
        # SSC should be a non-empty SHA-384 hex
        assert len(ssc[0].text) == 96

    def test_signature_placeholder_empty(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        ext2_content = _xpath(root, "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent")
        assert len(ext2_content) == 1
        # Should be empty (placeholder for XAdES signature)
        assert len(ext2_content[0]) == 0

    def test_pos_includes_software_manufacturer_extension(
        self, pos_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        extensions = _xpath(root, "ext:UBLExtensions/ext:UBLExtension")
        assert len(extensions) == 5

        manufacturer_names = [
            node.text
            for node in _xpath(
                root,
                "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent/"
                "FabricanteSoftware/InformacionDelFabricanteDelSoftware/Name",
            )
        ]
        assert manufacturer_names == ["NombreApellido", "RazonSocial", "NombreSoftware"]

    def test_pos_includes_buyer_benefits_extension(
        self, pos_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        benefit_names = [
            node.text
            for node in _xpath(
                root,
                "ext:UBLExtensions/ext:UBLExtension[3]/ext:ExtensionContent/"
                "BeneficiosComprador/InformacionBeneficiosComprador/Name",
            )
        ]
        assert benefit_names == ["Codigo", "NombresApellidos", "Puntos"]

    def test_pos_includes_cash_register_extension(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        point_of_sale_names = [
            node.text
            for node in _xpath(
                root,
                "ext:UBLExtensions/ext:UBLExtension[4]/ext:ExtensionContent/"
                "PuntoVenta/InformacionCajaVenta/Name",
            )
        ]
        assert point_of_sale_names == [
            "PlacaCaja",
            "UbicaciónCaja",
            "Cajero",
            "TipoCaja",
            "CódigoVenta",
            "SubTotal",
        ]

    def test_pos_signature_placeholder_is_last_extension(
        self, pos_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        signature_placeholder = _xpath(
            root,
            "ext:UBLExtensions/ext:UBLExtension[5]/ext:ExtensionContent",
        )
        assert len(signature_placeholder) == 1
        assert len(signature_placeholder[0]) == 0


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# XML Serialization
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestXMLSerialization:
    """Test XML serialization to bytes."""

    def test_invoice_to_xml_string(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        xml_bytes = invoice_to_xml_string(root)
        assert isinstance(xml_bytes, bytes)
        assert xml_bytes.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
        assert b"Invoice" in xml_bytes

    def test_credit_note_to_xml_string(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        xml_bytes = credit_note_to_xml_string(root)
        assert isinstance(xml_bytes, bytes)
        assert xml_bytes.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
        assert b"CreditNote" in xml_bytes

    def test_debit_note_to_xml_string(self, debit_note_request: DocumentSubmitRequest) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        xml_bytes = debit_note_to_xml_string(root)
        assert isinstance(xml_bytes, bytes)
        assert xml_bytes.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
        assert b"DebitNote" in xml_bytes

    def test_serialized_xml_is_parseable(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        xml_bytes = invoice_to_xml_string(root)
        parsed = etree.fromstring(xml_bytes)
        assert parsed.tag == f"{{{NS_INVOICE}}}Invoice"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Common Helpers
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestApplicationResponseBuilder:
    """Structure of the RADIAN event ApplicationResponse (Anexo v1.9 § 6.5.4)."""

    EVENT_CUDE = "c" * 96
    EVENT_NUMBER = "EV000001"
    ISSUE_DATE = "2026-07-23"
    ISSUE_TIME = "09:15:00-05:00"

    def _request(self, **overrides: object) -> EventSubmitRequest:
        payload: dict[str, object] = {
            "event_type": "030",
            "environment": "habilitacion",
            "software_id": "software-123",
            "software_pin": "12345",
            "document_cufe": "b" * 96,
            "document_number": "SETP990000123",
            "document_issue_date": "2026-07-10",
            "supplier_nit": "800199436",
            "supplier_name": "Proveedor Ejemplo S.A.S.",
        }
        payload.update(overrides)
        return EventSubmitRequest.model_validate(payload)

    def _build(self, **overrides: object) -> etree._Element:
        return build_application_response_xml(
            self._request(**overrides),
            self.EVENT_CUDE,
            self.EVENT_NUMBER,
            self.ISSUE_DATE,
            self.ISSUE_TIME,
        )

    def test_root_is_application_response(self) -> None:
        root = self._build()
        assert root.tag == f"{{{NS_APPLICATION_RESPONSE}}}ApplicationResponse"

    def test_header_element_order(self) -> None:
        """UBL is a sequence: a reordered header is schema-invalid."""
        root = self._build()
        locals_ = [etree.QName(child).localname for child in root]
        assert locals_ == [
            "UBLExtensions",
            "UBLVersionID",
            "CustomizationID",
            "ProfileID",
            "ProfileExecutionID",
            "ID",
            "UUID",
            "IssueDate",
            "IssueTime",
            "SenderParty",
            "ReceiverParty",
            "DocumentResponse",
        ]

    def test_header_literals(self) -> None:
        root = self._build()
        assert root.findtext(cbc("UBLVersionID")) == "UBL 2.1"
        assert root.findtext(cbc("CustomizationID")) == "1"
        assert root.findtext(cbc("ProfileID")) == APPLICATION_RESPONSE_PROFILE_ID
        assert root.findtext(cbc("ProfileExecutionID")) == "2"
        assert root.findtext(cbc("ID")) == self.EVENT_NUMBER
        assert root.findtext(cbc("IssueDate")) == self.ISSUE_DATE
        assert root.findtext(cbc("IssueTime")) == self.ISSUE_TIME

    def test_uuid_carries_cude_scheme(self) -> None:
        root = self._build()
        uuid = root.find(cbc("UUID"))
        assert uuid is not None
        assert uuid.text == self.EVENT_CUDE
        assert uuid.get("schemeName") == "CUDE-SHA384"
        assert uuid.get("schemeID") == "2"

    def test_produccion_flips_environment_codes(self) -> None:
        root = self._build(environment="produccion")
        assert root.findtext(cbc("ProfileExecutionID")) == "1"
        assert root.find(cbc("UUID")).get("schemeID") == "1"

    def test_two_ubl_extensions_dian_and_signature_slot(self) -> None:
        """AAC01 requires DianExtensions plus an empty slot for ds:Signature."""
        root = self._build()
        extensions = root.findall(f"{ext('UBLExtensions')}/{ext('UBLExtension')}")
        assert len(extensions) == 2
        assert (
            extensions[0].find(f"{ext('ExtensionContent')}/{{{NS_STS}}}DianExtensions") is not None
        )
        assert len(extensions[1].find(ext("ExtensionContent"))) == 0

    def test_dian_extensions_have_no_invoice_control(self) -> None:
        """Events consume no DIAN numbering range, so no sts:InvoiceControl."""
        root = self._build()
        assert root.xpath("//sts:InvoiceControl", namespaces=NS) == []

    def test_dian_extensions_child_order(self) -> None:
        root = self._build()
        dian_ext = root.xpath("//sts:DianExtensions", namespaces=NS)[0]
        assert [etree.QName(child).localname for child in dian_ext] == [
            "InvoiceSource",
            "SoftwareProvider",
            "SoftwareSecurityCode",
            "AuthorizationProvider",
            "QRCode",
        ]

    def test_qr_code_points_at_the_referenced_invoice(self) -> None:
        """AAB36: the QR carries the referenced CUFE, never the event CUDE."""
        root = self._build()
        qr = root.xpath("//sts:QRCode/text()", namespaces=NS)[0]
        assert qr.endswith("documentkey=" + "b" * 96)
        assert self.EVENT_CUDE not in qr

    def test_software_security_code_hashes_the_event_number(self) -> None:
        # § 11.8: NroDocumento = ApplicationResponse/cbc:ID, no el numero de la
        # factura referenciada.
        from facturacion_dian_api.core.cufe.calculator import calculate_software_security_code

        root = self._build()
        code = root.xpath("//sts:SoftwareSecurityCode/text()", namespaces=NS)[0]
        assert code == calculate_software_security_code("software-123", "12345", self.EVENT_NUMBER)

    def test_sender_is_the_configured_company(self) -> None:
        """Sender = quien genera el evento = el receptor de la factura."""
        root = self._build()
        sender_name = root.xpath(
            "cac:SenderParty/cac:PartyTaxScheme/cbc:RegistrationName/text()",
            namespaces=NS,
        )
        sender_nit = root.xpath(
            "cac:SenderParty/cac:PartyTaxScheme/cbc:CompanyID/text()",
            namespaces=NS,
        )
        assert sender_name == [settings.company.name]
        assert sender_nit == [settings.company.nit]

    def test_receiver_is_the_invoice_supplier(self) -> None:
        root = self._build()
        receiver = root.xpath(
            "cac:ReceiverParty/cac:PartyTaxScheme/cbc:CompanyID",
            namespaces=NS,
        )[0]
        assert receiver.text == "800199436"
        assert receiver.get("schemeName") == "31"
        assert receiver.get("schemeAgencyID") == "195"
        assert receiver.get("schemeID")

    def test_party_tax_scheme_hangs_directly_off_the_party(self) -> None:
        """No cac:Party in between — the CUDE XPath depends on this shape."""
        root = self._build()
        assert root.xpath("cac:SenderParty/cac:Party", namespaces=NS) == []
        assert root.xpath("cac:ReceiverParty/cac:Party", namespaces=NS) == []

    @pytest.mark.parametrize("event_type", ["030", "032", "033"])
    def test_response_code_and_description_per_event(self, event_type: str) -> None:
        root = self._build(event_type=event_type)
        response = root.xpath("cac:DocumentResponse/cac:Response", namespaces=NS)[0]
        assert response.findtext(cbc("ResponseCode")) == event_type
        assert response.findtext(cbc("Description")) == EVENT_DESCRIPTIONS[event_type]

    def test_document_reference_fields(self) -> None:
        root = self._build()
        reference = root.xpath("cac:DocumentResponse/cac:DocumentReference", namespaces=NS)[0]
        assert [etree.QName(child).localname for child in reference] == [
            "ID",
            "UUID",
            "DocumentTypeCode",
        ]
        assert reference.findtext(cbc("ID")) == "SETP990000123"
        uuid = reference.find(cbc("UUID"))
        assert uuid.text == "b" * 96
        assert uuid.get("schemeName") == "CUFE-SHA384"
        assert reference.findtext(cbc("DocumentTypeCode")) == "01"

    def test_claim_carries_cause_as_response_code_attributes(self) -> None:
        root = self._build(
            event_type="031",
            claim_cause_code="03",
            claim_description="Se recibieron 80 de 100 unidades.",
        )
        response_code = root.xpath(
            "cac:DocumentResponse/cac:Response/cbc:ResponseCode",
            namespaces=NS,
        )[0]
        assert response_code.text == "031"
        assert response_code.get("listID") == "03"
        assert response_code.get("name") == "Mercancía entregada parcialmente"
        assert root.findtext(cbc("Note")) == "Se recibieron 80 de 100 unidades."
        assert root.xpath(
            "cac:DocumentResponse/cac:Response/cbc:Description/text()",
            namespaces=NS,
        ) == [EVENT_DESCRIPTIONS["031"]]

    def test_non_claim_events_have_bare_response_code(self) -> None:
        root = self._build(event_type="032")
        response_code = root.xpath(
            "cac:DocumentResponse/cac:Response/cbc:ResponseCode",
            namespaces=NS,
        )[0]
        assert response_code.attrib == {}
        assert root.find(cbc("Note")) is None

    def test_receiver_person_becomes_issuer_party(self) -> None:
        root = self._build(
            event_type="032",
            receiver_person=EventReceiverPerson(
                document_number="1098765432",
                document_type="13",
                first_name="Ana",
                family_name="Perez",
                job_title="Jefe de bodega",
                organization_department="Almacen",
            ),
        )
        person = root.xpath(
            "cac:DocumentResponse/cac:IssuerParty/cac:Person",
            namespaces=NS,
        )[0]
        assert [etree.QName(child).localname for child in person] == [
            "ID",
            "FirstName",
            "FamilyName",
            "JobTitle",
            "OrganizationDepartment",
        ]
        person_id = person.find(cbc("ID"))
        assert person_id.text == "1098765432"
        assert person_id.get("schemeName") == "13"
        # Solo el NIT lleva digito de verificacion (AAH14).
        assert person_id.get("schemeID") is None

    def test_issuer_party_omitted_without_receiver_person(self) -> None:
        root = self._build()
        assert root.xpath("cac:DocumentResponse/cac:IssuerParty", namespaces=NS) == []

    def test_serialized_xml_is_parseable(self) -> None:
        xml_bytes = application_response_to_xml_string(self._build())
        assert xml_bytes.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
        parsed = etree.fromstring(xml_bytes)
        assert parsed.tag == f"{{{NS_APPLICATION_RESPONSE}}}ApplicationResponse"


class TestMoneyFormatter:
    """Test _money helper."""

    def test_integer_to_two_decimals(self) -> None:
        assert _money(1000) == "1000.00"

    def test_zero(self) -> None:
        assert _money(0) == "0.00"

    def test_large_amount(self) -> None:
        assert _money(9999999) == "9999999.00"
