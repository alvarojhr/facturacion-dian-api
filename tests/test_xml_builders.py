"""Tests for UBL 2.1 XML builders.

Validates structure, namespace correctness, and content for:
- Factura ElectrÃ³nica (Invoice)
- Documento Equivalente POS (Invoice variant)
- Nota CrÃ©dito (CreditNote)
"""

from __future__ import annotations

import pytest
from facturacion_dian_kit.core.config import settings
from facturacion_dian_kit.core.models import DocumentLine, DocumentSubmitRequest
from facturacion_dian_kit.core.xml.common import _money, _sub, build_invoice_line, build_tax_totals
from facturacion_dian_kit.core.xml.credit_note_builder import (
    build_credit_note_xml,
    credit_note_to_xml_string,
)
from facturacion_dian_kit.core.xml.debit_note_builder import (
    build_debit_note_xml,
    debit_note_to_xml_string,
)
from facturacion_dian_kit.core.xml.invoice_builder import build_invoice_xml, invoice_to_xml_string
from facturacion_dian_kit.core.xml.namespaces import (
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

# â”€â”€â”€ Namespace shortcuts for XPath â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

NS = {
    "inv": NS_INVOICE,
    "cn": NS_CREDIT_NOTE,
    "dn": NS_DEBIT_NOTE,
    "cac": NS_CAC,
    "cbc": NS_CBC,
    "ext": NS_EXT,
    "sts": NS_STS,
}


# â”€â”€â”€ Fixtures â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        pos_register_location="Carrera 6 # 8 - 66, Floridablanca",
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
        pos_register_location="Carrera 6 # 8 - 66, Floridablanca",
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
        credit_note_reason="DevoluciÃ³n parcial de mercancÃ­a",
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


# â”€â”€â”€ Helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
# Invoice Builder (Factura ElectrÃ³nica)
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
        assert _xpath_text(root, "cbc:ProfileID") == "DIAN 2.1: Factura ElectrÃ³nica de Venta"

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
        assert account_id == "1"  # 1 = Persona JurÃ­dica

    def test_customer_email_in_contact(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        email = _xpath_text(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:Contact/cbc:ElectronicMail"
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
        assert _xpath_text(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PhysicalLocation/cac:Address/cbc:CityName",
        ) == "Bogota"
        assert _xpath_text(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PhysicalLocation/cac:Address/cac:AddressLine/cbc:Line",
        ) == "Calle 10 # 5-11"

    def test_customer_contact_includes_phone(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:Contact/cbc:Telephone",
        ) == "3001234567"


class TestInvoiceBuilderResolution:
    """Test numbering resolution data under DianExtensions."""

    def test_invoice_control_uses_resolution_data(
        self, invoice_request: DocumentSubmitRequest
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        assert _xpath_text(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
            "sts:DianExtensions/sts:InvoiceControl/sts:InvoiceAuthorization",
        ) == "18764000001"
        assert _xpath_text(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
            "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizedInvoices/sts:Prefix",
        ) == "SETT"
        assert _xpath_text(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
            "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizedInvoices/sts:From",
        ) == "120"
        assert _xpath_text(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
            "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizedInvoices/sts:To",
        ) == "240"
        assert _xpath_text(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
            "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizationPeriod/cbc:StartDate",
        ) == "2026-01-01"
        assert _xpath_text(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
            "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizationPeriod/cbc:EndDate",
        ) == "2026-12-31"


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
        percent = _xpath_text(
            root, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent"
        )
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
        assert _xpath_text(root, "cac:InvoiceLine[1]/cac:Item/cbc:Name") == "Tornillo hexagonal 1/4 x 1 zinc"
        assert _xpath_text(root, "cac:InvoiceLine[1]/cac:Item/cac:SellersItemIdentification/cbc:ID") == "SKU-0001"
        standard = _xpath(root, "cac:InvoiceLine[1]/cac:Item/cac:StandardItemIdentification/cbc:ID")[0]
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
            root,
            "cac:AccountingCustomerParty/cac:Party"
            "/cac:PartyTaxScheme/cbc:CompanyID"
        )
        assert company_id == "222222222222"

    def test_consumidor_final_persona_natural(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        account_id = _xpath_text(root, "cac:AccountingCustomerParty/cbc:AdditionalAccountID")
        assert account_id == "2"  # 2 = Persona Natural

    def test_consumidor_final_has_party_identification(self, pos_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        identifier = _xpath(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        )[0]
        assert identifier.text == "222222222222"
        assert identifier.get("schemeName") == "13"

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
        assert _xpath_text(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:PhysicalLocation/cac:Address/cbc:CityName",
        ) == "Medellin"
        assert _xpath_text(
            root,
            "cac:AccountingCustomerParty/cac:Party/cac:Contact/cbc:ElectronicMail",
        ) == "cliente.pos@example.com"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Credit Note Builder (Nota CrÃ©dito)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestCreditNoteBuilderStructure:
    """Test CreditNote XML structure."""

    def test_root_element_is_credit_note(self, credit_note_request: DocumentSubmitRequest) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert root.tag == f"{{{NS_CREDIT_NOTE}}}CreditNote"

    def test_root_has_credit_note_namespace(self, credit_note_request: DocumentSubmitRequest) -> None:
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
        assert note == "DevoluciÃ³n parcial de mercancÃ­a"

    def test_profile_id_matches_dian_catalog(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:ProfileID") == "DIAN 2.1: Nota CrÃ©dito de Factura ElectrÃ³nica de Venta"

    def test_customization_id_matches_referenced_credit_note(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:CustomizationID") == "20"

    def test_credit_note_uses_request_resolution_control(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert _xpath_text(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
            "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizedInvoices/sts:From",
        ) == "30"
        assert _xpath_text(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/"
            "sts:DianExtensions/sts:InvoiceControl/sts:AuthorizationPeriod/cbc:StartDate",
        ) == "2026-02-01"


class TestCreditNoteDiscrepancy:
    """Test DiscrepancyResponse and BillingReference elements."""

    def test_discrepancy_response_exists(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        discrepancy = _xpath(root, "cac:DiscrepancyResponse")
        assert len(discrepancy) == 1

    def test_discrepancy_reference_id(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        ref_id = _xpath_text(root, "cac:DiscrepancyResponse/cbc:ReferenceID")
        assert ref_id == "SETT000001"

    def test_discrepancy_response_code(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        code = _xpath_text(root, "cac:DiscrepancyResponse/cbc:ResponseCode")
        assert code == "1"  # DevoluciÃ³n parcial (anulaciÃ³n "2" is forbidden for tipo 22)

    def test_discrepancy_description(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        desc = _xpath_text(root, "cac:DiscrepancyResponse/cbc:Description")
        assert desc == "DevoluciÃ³n parcial de mercancÃ­a"

    def test_billing_reference_exists(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        billing_ref = _xpath(root, "cac:BillingReference")
        assert len(billing_ref) == 1

    def test_billing_reference_invoice_id(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        ref_id = _xpath_text(
            root, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID"
        )
        assert ref_id == "SETT000001"

    def test_billing_reference_cufe(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        cufe = _xpath_text(
            root, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:UUID"
        )
        assert cufe == "abc123def456"


class TestCreditNoteLines:
    """Test CreditNoteLine elements."""

    def test_uses_credit_note_line_tag(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        lines = _xpath(root, "cac:CreditNoteLine")
        assert len(lines) == 1

    def test_no_invoice_lines(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        lines = _xpath(root, "cac:InvoiceLine")
        assert len(lines) == 0

    def test_credited_quantity_tag(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        qty = _xpath(root, "cac:CreditNoteLine/cbc:CreditedQuantity")
        assert len(qty) == 1
        assert qty[0].text == "100.0"  # quantity is float

    def test_credit_note_monetary_total(
        self, credit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        assert _xpath_text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount") == "59500.00"


class TestDebitNoteBuilder:
    """Test DebitNote XML structure."""

    def test_root_element_is_debit_note(
        self, debit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert root.tag == f"{{{NS_DEBIT_NOTE}}}DebitNote"

    def test_profile_id_matches_dian(
        self, debit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert _xpath_text(root, "cbc:ProfileID") == "DIAN 2.1: Nota DÃ©bito de Factura ElectrÃ³nica de Venta"

    def test_uses_requested_monetary_total(
        self, debit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert _xpath_text(root, "cac:RequestedMonetaryTotal/cbc:PayableAmount") == "11900.00"

    def test_uses_debit_note_line(
        self, debit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert len(_xpath(root, "cac:DebitNoteLine")) == 1
        assert _xpath_text(root, "cac:DebitNoteLine/cbc:DebitedQuantity") == "1.0"

    def test_billing_reference_cufe(
        self, debit_note_request: DocumentSubmitRequest
    ) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        assert _xpath_text(
            root,
            "cac:BillingReference/cac:InvoiceDocumentReference/cbc:UUID",
        ) == "abc123def456"


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
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent/sts:DianExtensions"
        )
        assert len(dian_ext) == 1

    def test_software_provider_exists(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        sp = _xpath(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent"
            "/sts:DianExtensions/sts:SoftwareProvider"
        )
        assert len(sp) == 1

    def test_software_security_code_exists(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        ssc = _xpath(
            root,
            "ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent"
            "/sts:DianExtensions/sts:SoftwareSecurityCode"
        )
        assert len(ssc) == 1
        # SSC should be a non-empty SHA-384 hex
        assert len(ssc[0].text) == 96

    def test_signature_placeholder_empty(self, invoice_request: DocumentSubmitRequest) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        ext2_content = _xpath(
            root,
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
        )
        assert len(ext2_content) == 1
        # Should be empty (placeholder for XAdES signature)
        assert len(ext2_content[0]) == 0

    def test_pos_includes_software_manufacturer_extension(self, pos_request: DocumentSubmitRequest) -> None:
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

    def test_pos_includes_buyer_benefits_extension(self, pos_request: DocumentSubmitRequest) -> None:
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

    def test_pos_signature_placeholder_is_last_extension(self, pos_request: DocumentSubmitRequest) -> None:
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


class TestMoneyFormatter:
    """Test _money helper."""

    def test_integer_to_two_decimals(self) -> None:
        assert _money(1000) == "1000.00"

    def test_zero(self) -> None:
        assert _money(0) == "0.00"

    def test_large_amount(self) -> None:
        assert _money(9999999) == "9999999.00"

