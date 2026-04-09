"""Tests for XAdES-EPES signing module.

Uses a self-signed test certificate generated at test time.
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from facturacion_dian_kit.core.dian.envelope import build_send_test_set_async_envelope
from facturacion_dian_kit.core.models import DocumentLine, DocumentSubmitRequest
from facturacion_dian_kit.core.signing.certificate import (
    CertificateBundle,
    load_certificate,
    reset_certificate_cache,
)
from facturacion_dian_kit.core.signing.ws_security import sign_soap_envelope
from facturacion_dian_kit.core.signing.xades import sign_document, sign_document_xml
from facturacion_dian_kit.core.xml.credit_note_builder import build_credit_note_xml
from facturacion_dian_kit.core.xml.debit_note_builder import build_debit_note_xml
from facturacion_dian_kit.core.xml.invoice_builder import build_invoice_xml
from facturacion_dian_kit.core.xml.namespaces import (
    NS_CREDIT_NOTE,
    NS_DEBIT_NOTE,
    NS_DS,
    NS_EXT,
    NS_INVOICE,
    NS_XADES,
)
from lxml import etree

# â”€â”€â”€ Test Certificate Generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _generate_test_p12(path: Path, password: bytes = b"test123") -> None:
    """Generate a self-signed .p12 certificate for testing."""
    # Generate RSA key pair
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Create self-signed certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CO"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Issuer"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Test Certificate"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )

    # Serialize to PKCS#12
    p12_data = serialization.pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )

    path.write_bytes(p12_data)


@pytest.fixture
def test_cert_path(tmp_path: Path) -> Path:
    """Generate a test .p12 certificate and return its path."""
    cert_path = tmp_path / "test_cert.p12"
    _generate_test_p12(cert_path)
    return cert_path


@pytest.fixture
def test_bundle(test_cert_path: Path) -> CertificateBundle:
    """Load the test certificate into a CertificateBundle."""
    return load_certificate(
        cert_path=str(test_cert_path),
        cert_password="test123",
    )


@pytest.fixture
def invoice_request() -> DocumentSubmitRequest:
    return DocumentSubmitRequest(
        invoice_number="SETT000001",
        document_type="FACTURA_ELECTRONICA",
        customer_nit="800199436",
        customer_name="Empresa Ejemplo S.A.S.",
        customer_email="compras@ejemplo.com",
        issue_date="2026-03-12",
        issue_time="14:30:00-05:00",
        subtotal=100000,
        tax_total=19000,
        total=119000,
        lines=[
            DocumentLine(
                description="Tornillo hexagonal 1/4 x 1 zinc",
                quantity=100,
                unit_price=500,
                line_total=50000,
                tax_type="IVA_19",
                tax_amount=9500,
            ),
            DocumentLine(
                description="Tuerca hexagonal 1/4 zinc",
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
        pos_register_plate="Caja 1",
        pos_register_location="Carrera 6 # 8 - 66, Floridablanca",
        cashier_name="Administrador",
        pos_register_type="POS",
        sale_code="POS-20260314-TEST",
        buyer_loyalty_points=0,
        client_reference="660e8400-e29b-41d4-a716-446655440001",
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
        client_reference="550e8400-e29b-41d4-a716-446655440000",
        debit_note_number="ND000001",
        referenced_invoice_number="SETT000001",
        referenced_invoice_cufe="abc123def456",
        debit_note_reason="Intereses",
        debit_note_response_code="1",
    )


FAKE_CUFE = "a" * 96


NS = {
    "ds": NS_DS,
    "ext": NS_EXT,
    "inv": NS_INVOICE,
    "cn": NS_CREDIT_NOTE,
    "dn": NS_DEBIT_NOTE,
    "xades": NS_XADES,
}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Certificate Loading Tests
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestCertificateLoading:
    """Test .p12 certificate loading."""

    def test_load_certificate(self, test_cert_path: Path) -> None:
        bundle = load_certificate(str(test_cert_path), "test123")
        assert bundle.private_key is not None
        assert bundle.certificate is not None

    def test_cert_is_valid(self, test_bundle: CertificateBundle) -> None:
        assert test_bundle.is_valid

    def test_cert_pem_format(self, test_bundle: CertificateBundle) -> None:
        pem = test_bundle.cert_pem
        assert pem.startswith(b"-----BEGIN CERTIFICATE-----")

    def test_cert_der_format(self, test_bundle: CertificateBundle) -> None:
        der = test_bundle.cert_der
        assert len(der) > 0
        # DER starts with ASN.1 SEQUENCE tag
        assert der[0] == 0x30

    def test_private_key_pem(self, test_bundle: CertificateBundle) -> None:
        pem = test_bundle.private_key_pem
        assert b"PRIVATE KEY" in pem

    def test_subject_name(self, test_bundle: CertificateBundle) -> None:
        assert "Test" in test_bundle.subject_name

    def test_not_valid_after(self, test_bundle: CertificateBundle) -> None:
        assert test_bundle.not_valid_after > datetime.now(UTC)

    def test_empty_ca_chain(self, test_bundle: CertificateBundle) -> None:
        assert test_bundle.ca_chain == []

    def test_load_wrong_password_raises(self, test_cert_path: Path) -> None:
        with pytest.raises(ValueError, match="Failed to load"):
            load_certificate(str(test_cert_path), "wrong_password")

    def test_load_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_certificate("/nonexistent/cert.p12", "pass")


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# XAdES-EPES Signing Tests
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestXAdESSigning:
    """Test XAdES-EPES document signing."""

    def test_sign_invoice_returns_element(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)
        assert isinstance(signed, etree._Element)
        assert signed.tag == f"{{{NS_INVOICE}}}Invoice"

    def test_signature_in_ubl_extension(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        """Signature must be inside UBLExtension[2]/ExtensionContent."""
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        sig = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent/ds:Signature",
            namespaces=NS,
        )
        assert len(sig) == 1

    def test_signature_not_at_root_level(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        """ds:Signature should NOT be a direct child of root after relocation."""
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        ds_sig_tag = f"{{{NS_DS}}}Signature"
        root_children_tags = [child.tag for child in signed]
        assert ds_sig_tag not in root_children_tags

    def test_signature_has_signed_info(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        signed_info = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:SignedInfo",
            namespaces=NS,
        )
        assert len(signed_info) == 1

    def test_signature_has_signature_value(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        sig_value = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:SignatureValue",
            namespaces=NS,
        )
        assert len(sig_value) == 1
        assert sig_value[0].text is not None
        assert len(sig_value[0].text.strip()) > 0

    def test_signature_has_key_info(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        key_info = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:KeyInfo",
            namespaces=NS,
        )
        assert len(key_info) == 1

    def test_pos_signature_in_last_ubl_extension(
        self,
        pos_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(pos_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        sig = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[5]/ext:ExtensionContent/ds:Signature",
            namespaces=NS,
        )
        assert len(sig) == 1

    def test_signature_has_x509_certificate(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        x509_cert = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:KeyInfo/ds:X509Data/ds:X509Certificate",
            namespaces=NS,
        )
        assert len(x509_cert) == 1
        assert x509_cert[0].text is not None

    def test_signature_references_match_accepted_order(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        references = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:SignedInfo/ds:Reference",
            namespaces=NS,
        )
        assert len(references) == 3
        assert references[0].get("URI") == ""
        assert references[1].get("URI", "").startswith("#xmldsig-")
        assert references[1].get("URI", "").endswith("-keyinfo")
        assert references[2].get("Type") == "http://uri.etsi.org/01903#SignedProperties"

    def test_document_reference_uses_only_enveloped_transform(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        transforms = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:SignedInfo/ds:Reference[1]/ds:Transforms/ds:Transform/@Algorithm",
            namespaces=NS,
        )
        assert transforms == ["http://www.w3.org/2000/09/xmldsig#enveloped-signature"]

    def test_signature_uses_legacy_signing_certificate_block(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        signing_certificate = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:Object/xades:QualifyingProperties"
            "/xades:SignedProperties/xades:SignedSignatureProperties/xades:SigningCertificate",
            namespaces=NS,
        )
        signing_certificate_v2 = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:Object/xades:QualifyingProperties"
            "/xades:SignedProperties/xades:SignedSignatureProperties/xades:SigningCertificateV2",
            namespaces=NS,
        )

        assert len(signing_certificate) == 1
        assert len(signing_certificate_v2) == 0

    def test_signature_omits_data_object_format(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        data_object_format = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:Object/xades:QualifyingProperties"
            "/xades:SignedProperties/xades:SignedDataObjectProperties/xades:DataObjectFormat",
            namespaces=NS,
        )
        assert len(data_object_format) == 0

    def test_signing_certificate_includes_issuer_serial(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        issuer_serial = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:Object/xades:QualifyingProperties"
            "/xades:SignedProperties/xades:SignedSignatureProperties"
            "/xades:SigningCertificate/xades:Cert/xades:IssuerSerial",
            namespaces=NS,
        )
        assert len(issuer_serial) == 1

    def test_signature_includes_supplier_signer_role(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        claimed_role = signed.xpath(
            "string("
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:Object/xades:QualifyingProperties"
            "/xades:SignedProperties/xades:SignedSignatureProperties"
            "/xades:SignerRole/xades:ClaimedRoles/xades:ClaimedRole"
            ")",
            namespaces=NS,
        )
        assert claimed_role == "supplier"

    def test_signature_policy_matches_accepted_sample(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        description = signed.xpath(
            "string("
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:Object/xades:QualifyingProperties"
            "/xades:SignedProperties/xades:SignedSignatureProperties"
            "/xades:SignaturePolicyIdentifier/xades:SignaturePolicyId"
            "/xades:SigPolicyId/xades:Description"
            ")",
            namespaces=NS,
        )
        digest_value = signed.xpath(
            "string("
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"
            "/ds:Signature/ds:Object/xades:QualifyingProperties"
            "/xades:SignedProperties/xades:SignedSignatureProperties"
            "/xades:SignaturePolicyIdentifier/xades:SignaturePolicyId"
            "/xades:SigPolicyHash/ds:DigestValue"
            ")",
            namespaces=NS,
        )
        assert description == "PolÃ­tica de firma para facturas electrÃ³nicas de la RepÃºblica de Colombia."
        assert digest_value == "dMoMvtcG5aIzgYo0tIsSQeVJBDnUnfSOfBpxXrmor0Y="

    def test_signed_xml_is_well_formed(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)
        xml_bytes = etree.tostring(signed, xml_declaration=True, encoding="UTF-8")
        # Re-parse to confirm well-formedness
        reparsed = etree.fromstring(xml_bytes)
        assert reparsed.tag == f"{{{NS_INVOICE}}}Invoice"

    def test_serialized_signed_xml_remains_verifiable(
        self,
        invoice_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        from signxml.xades import XAdESVerifier

        root = build_invoice_xml(invoice_request, FAKE_CUFE)
        xml_bytes = sign_document_xml(root, test_bundle)
        reparsed = etree.fromstring(xml_bytes)
        XAdESVerifier().verify(reparsed, x509_cert=test_bundle.cert_pem, validate_schema=False)


class TestXAdESSigningCreditNote:
    """Test signing credit notes."""

    def test_sign_credit_note(
        self,
        credit_note_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)
        assert signed.tag == f"{{{NS_CREDIT_NOTE}}}CreditNote"

    def test_credit_note_signature_in_extension(
        self,
        credit_note_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_credit_note_xml(credit_note_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        sig = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent/ds:Signature",
            namespaces=NS,
        )
        assert len(sig) == 1


class TestXAdESSigningDebitNote:
    """Test signing debit notes."""

    def test_sign_debit_note(
        self,
        debit_note_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)
        assert signed.tag == f"{{{NS_DEBIT_NOTE}}}DebitNote"

    def test_debit_note_signature_in_extension(
        self,
        debit_note_request: DocumentSubmitRequest,
        test_bundle: CertificateBundle,
    ) -> None:
        root = build_debit_note_xml(debit_note_request, FAKE_CUFE)
        signed = sign_document(root, test_bundle)

        sig = signed.xpath(
            "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent/ds:Signature",
            namespaces=NS,
        )
        assert len(sig) == 1


class TestWSSecurityEnvelope:
    """Test SOAP WS-Security signing details required by DIAN/WCF."""

    NS_WSS = {
        "soap": "http://www.w3.org/2003/05/soap-envelope",
        "wsa": "http://www.w3.org/2005/08/addressing",
        "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
        "wsu": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
    }

    def test_timestamp_uses_wcf_ttl(self, test_bundle: CertificateBundle) -> None:
        envelope = build_send_test_set_async_envelope(
            "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc",
            "ws_SETT000001.zip",
            "ZmFrZQ==",
            "test-set-id",
        )
        signed = sign_soap_envelope(envelope, test_bundle)
        root = etree.fromstring(signed)

        created_text = root.xpath(
            "soap:Header/wsse:Security/wsu:Timestamp/wsu:Created/text()",
            namespaces=self.NS_WSS,
        )[0]
        expires_text = root.xpath(
            "soap:Header/wsse:Security/wsu:Timestamp/wsu:Expires/text()",
            namespaces=self.NS_WSS,
        )[0]

        created = datetime.fromisoformat(created_text.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(expires_text.replace("Z", "+00:00"))
        ttl_seconds = (expires - created).total_seconds()

        assert 299.0 <= ttl_seconds <= 301.0

    def test_security_header_matches_wcf_element_order(
        self, test_bundle: CertificateBundle
    ) -> None:
        envelope = build_send_test_set_async_envelope(
            "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc",
            "ws_SETT000001.zip",
            "ZmFrZQ==",
            "test-set-id",
        )
        signed = sign_soap_envelope(envelope, test_bundle)
        root = etree.fromstring(signed)

        security = root.xpath(
            "soap:Header/wsse:Security",
            namespaces=self.NS_WSS,
        )[0]
        assert security.attrib[f"{{{self.NS_WSS['soap']}}}mustUnderstand"] == "1"
        assert [child.tag for child in security] == [
            f"{{{self.NS_WSS['wsu']}}}Timestamp",
            f"{{{self.NS_WSS['wsse']}}}BinarySecurityToken",
            f"{{{self.NS_WSS['ds']}}}Signature",
        ]

    def test_signature_references_timestamp_and_to(
        self, test_bundle: CertificateBundle
    ) -> None:
        envelope = build_send_test_set_async_envelope(
            "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc",
            "ws_SETT000001.zip",
            "ZmFrZQ==",
            "test-set-id",
        )
        signed = sign_soap_envelope(envelope, test_bundle)
        root = etree.fromstring(signed)

        references = root.xpath(
            "soap:Header/wsse:Security/ds:Signature/ds:SignedInfo/ds:Reference/@URI",
            namespaces=self.NS_WSS,
        )
        assert references == ["#_0", "#_1"]

    def test_signature_uses_direct_binary_security_token_reference(
        self, test_bundle: CertificateBundle
    ) -> None:
        envelope = build_send_test_set_async_envelope(
            "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc",
            "ws_SETT000001.zip",
            "ZmFrZQ==",
            "test-set-id",
        )
        signed = sign_soap_envelope(envelope, test_bundle)
        root = etree.fromstring(signed)

        bst_id = root.xpath(
            "soap:Header/wsse:Security/wsse:BinarySecurityToken/@wsu:Id",
            namespaces=self.NS_WSS,
        )[0]
        reference = root.xpath(
            "soap:Header/wsse:Security/ds:Signature/ds:KeyInfo/wsse:SecurityTokenReference/wsse:Reference",
            namespaces=self.NS_WSS,
        )[0]

        assert reference.attrib["URI"] == f"#{bst_id}"
        assert (
            reference.attrib["ValueType"]
            == "http://docs.oasis-open.org/wss/2004/01/"
            "oasis-200401-wss-x509-token-profile-1.0#X509v3"
        )

    def test_to_header_is_marked_and_signed(self, test_bundle: CertificateBundle) -> None:
        envelope = build_send_test_set_async_envelope(
            "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc",
            "ws_SETT000001.zip",
            "ZmFrZQ==",
            "test-set-id",
        )
        signed = sign_soap_envelope(envelope, test_bundle)
        root = etree.fromstring(signed)

        to_header = root.xpath(
            "soap:Header/wsa:To",
            namespaces=self.NS_WSS,
        )[0]

        assert to_header.attrib[f"{{{self.NS_WSS['soap']}}}mustUnderstand"] == "1"
        assert to_header.attrib[f"{{{self.NS_WSS['wsu']}}}Id"] == "_1"

