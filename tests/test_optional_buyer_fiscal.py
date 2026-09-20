"""Optional buyer facts: real signatures, immutable retries and delivery boundary."""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import socket
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from facturacion_dian_api.core.dian.client import DianClient
from facturacion_dian_api.core.dian.response_parser import DianResponse
from facturacion_dian_api.core.models import DocumentSubmitRequest
from facturacion_dian_api.core.signing.certificate import CertificateBundle
from facturacion_dian_api.core.signing.xades import (
    sign_document,
    sign_document_xml,
    verify_document_signature,
    verify_embedded_document_signature,
)
from facturacion_dian_api.core.submission import _build_document_xml
from facturacion_dian_api.core.xml.namespaces import NSMAP_APPLICATION_RESPONSE
from facturacion_dian_api.server.contracts import BuyerInput, DocumentSubmissionRequest
from facturacion_dian_api.server.examples import (
    ATTACHED_DOCUMENT_REQUEST_EXAMPLE,
    DIAN_AR_XML_BASE64,
    DOCUMENT_SUBMISSION_INVOICE_EXAMPLE,
)
from facturacion_dian_api.server.mappers import to_core_submission_request
from lxml import etree
from pydantic import ValidationError

NS = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
      "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
BUYER = "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/"
CC = {"name": "COMPRADOR DE PRUEBA", "document_type": "CC", "document_number": "123456789"}
FAMILIES = [
    ("sample_invoice_payload", "FACTURA_ELECTRONICA"),
    ("sample_credit_note_payload", "NOTA_CREDITO"),
    ("sample_debit_note_payload", "NOTA_DEBITO"),
    ("sample_pos_payload", "DOCUMENTO_EQUIVALENTE_POS"),
]


def xml(payload):
    request = to_core_submission_request(DocumentSubmissionRequest.model_validate(payload))
    return request, _build_document_xml(request, "a" * 96, "https://example.invalid/qr")


@pytest.mark.parametrize("fixture,family", FAMILIES)
@pytest.mark.parametrize("facts", [
    {}, {"additional_account_id": "2"},
    {"tax_level_code": None, "tax_scheme_id": None, "tax_scheme_name": None},
    {"tax_level_code": "O-13;O-15"},
    {"tax_scheme_id": "01", "tax_scheme_name": "IVA"},
    {"tax_level_code": "R-99-PN", "tax_scheme_id": "ZA", "tax_scheme_name": "IVA e INC"},
    {"document_type": "NIT", "document_number": "900123456", "additional_account_id": "1",
     "tax_scheme_id": "04", "tax_scheme_name": "INC"},
    {"document_type": "NIT", "document_number": "900123456", "additional_account_id": "2"},
])
def test_optional_facts_preserve_identity_and_unknowns(request, fixture, family, facts):
    payload = deepcopy(request.getfixturevalue(fixture))
    payload["document"]["type"] = family
    payload["buyer"] = {**CC, **facts}
    core, root = xml(payload)
    assert core.customer_tax_level_code == facts.get("tax_level_code")
    assert core.customer_tax_scheme_id == facts.get("tax_scheme_id")
    assert core.customer_tax_scheme_name == facts.get("tax_scheme_name")
    assert root.xpath("string(" + BUYER + "cbc:RegistrationName)", namespaces=NS) == CC["name"]
    assert root.xpath("string(" + BUYER + "cbc:CompanyID)", namespaces=NS) == payload["buyer"]["document_number"]
    assert root.xpath(BUYER + "cbc:TaxLevelCode/text()", namespaces=NS) == (
        [facts["tax_level_code"]] if facts.get("tax_level_code") else [])
    assert root.xpath("string(" + BUYER + "cac:TaxScheme/cbc:ID)", namespaces=NS) == (facts.get("tax_scheme_id") or "ZZ")
    assert root.xpath("string(" + BUYER + "cac:TaxScheme/cbc:Name)", namespaces=NS) == (facts.get("tax_scheme_name") or "No aplica")
    assert root.xpath("string(cac:AccountingCustomerParty/cbc:AdditionalAccountID)", namespaces=NS) == facts.get("additional_account_id", "2")
    assert root.xpath("cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode/text()", namespaces=NS)
    # Direct SDK construction goes through the same validation without HTTP.
    assert DocumentSubmitRequest.model_validate(core.model_dump()).customer_tax_level_code == core.customer_tax_level_code


@pytest.mark.parametrize("facts", [
    {"tax_level_code": ""}, {"tax_level_code": " "}, {"tax_level_code": "47"},
    {"tax_level_code": "O-99"}, {"tax_level_code": "O-13;"},
    {"tax_scheme_id": "01"}, {"tax_scheme_name": "IVA"},
    {"tax_scheme_id": "ZZ", "tax_scheme_name": "IVA"},
    {"tax_scheme_id": "01", "tax_scheme_name": "No aplica"},
    {"tax_scheme_id": "", "tax_scheme_name": " "},
    {"document_type": "NIT"}, {"document_type": None},
    {"document_number": None}, {"document_number": " "}, {"name": " "},
    {"additional_account_id": "1"},
])
def test_explicit_invalid_facts_fail_http_and_core(sample_invoice_payload, facts):
    with pytest.raises(ValidationError):
        BuyerInput.model_validate({**CC, **facts})
    core = to_core_submission_request(DocumentSubmissionRequest.model_validate(sample_invoice_payload)).model_dump()
    mapping = {"document_number": "nit", "document_type": "document_type"}
    buyer = {**CC, "additional_account_id": None, "tax_level_code": None,
             "tax_scheme_id": None, "tax_scheme_name": None, **facts}
    core.update({"customer_" + mapping.get(k, k): v for k, v in buyer.items()})
    with pytest.raises(ValidationError):
        DocumentSubmitRequest.model_validate(core)


@pytest.mark.parametrize("family", ["NOTA_AJUSTE_DEE_CREDITO", "NOTA_AJUSTE_DEE_DEBITO"])
def test_dee_adjustments_require_known_responsibility(sample_credit_note_payload, family):
    payload = deepcopy(sample_credit_note_payload)
    payload["document"]["type"] = family
    payload["buyer"] = {**CC, "document_type": "NIT", "additional_account_id": "1"}
    with pytest.raises(ValidationError, match="NAAK26/NADAK26"):
        DocumentSubmissionRequest.model_validate(payload)
    payload["buyer"]["tax_level_code"] = "O-13;O-15"
    core, root = xml(payload)
    assert root.xpath(BUYER + "cbc:TaxLevelCode/text()", namespaces=NS) == ["O-13;O-15"]
    core.customer_tax_level_code = None
    with pytest.raises(ValidationError, match="NAAK26/NADAK26"):
        DocumentSubmitRequest.model_validate(core.model_dump())


@pytest.mark.parametrize("number,name", [("123", "consumidor final"), ("222123456789", "Cliente"), ("123456789012", "Cliente")])
def test_no_generic_buyer_heuristics(sample_invoice_payload, number, name):
    sample_invoice_payload["buyer"] = {**CC, "name": name, "document_number": number}
    _, root = xml(sample_invoice_payload)
    assert root.xpath("string(" + BUYER + "cbc:CompanyID)", namespaces=NS) == number
    assert not root.xpath(BUYER + "cbc:TaxLevelCode", namespaces=NS)


@pytest.fixture
def real_crypto(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Ephemeral buyer QA")])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(123).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1)).sign(key, hashes.SHA256()))
    bundle = CertificateBundle(key, cert, [])
    monkeypatch.setattr("facturacion_dian_api.core.submission.get_certificate_bundle", lambda: bundle)
    monkeypatch.setattr("facturacion_dian_api.core.submission.sign_document_xml", sign_document_xml)
    monkeypatch.setattr("facturacion_dian_api.core.xml.attached_document_builder.verify_embedded_document_signature", verify_embedded_document_signature)
    def guard(original):
        def no_network(sock, address):
            if not isinstance(address, tuple) or not ipaddress.ip_address(address[0]).is_loopback:
                raise AssertionError("Real network is forbidden in buyer compatibility tests")
            return original(sock, address)
        return no_network
    monkeypatch.setattr(socket.socket, "connect", guard(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guard(socket.socket.connect_ex))
    return bundle


def check_xsd(root, env):
    folder = os.environ.get(env)
    if folder:
        schema = Path(folder) / f"UBL-{etree.QName(root).localname}-2.1.xsd"
        etree.XMLSchema(etree.parse(str(schema))).assertValid(root)


@pytest.mark.parametrize("fixture,family", FAMILIES)
def test_real_preparation_and_retries_keep_exact_bytes(request, client, monkeypatch, real_crypto, fixture, family):
    payload = deepcopy(request.getfixturevalue(fixture))
    payload["buyer"] = deepcopy(CC)
    payload["submission_options"]["prepare_only"] = True
    transmitted = []
    async def transport(self, filename, content_b64, test_set_id=None):
        with ZipFile(BytesIO(base64.b64decode(content_b64))) as archive:
            transmitted.append((archive.namelist()[0], archive.read(archive.namelist()[0])))
        return DianResponse(is_valid=True, validation_result_present=True, status_code="00")
    monkeypatch.setattr(DianClient, "send_test_set_async", transport)
    monkeypatch.setattr(DianClient, "send_bill_sync", transport)
    prepared = client.post("/api/v1/documents/submissions", json=payload)
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["status"] == "prepared"
    artifact = prepared.json()["artifacts"]
    original = base64.b64decode(artifact["xml_base64"])
    root = etree.fromstring(original)
    verify_document_signature(root, real_crypto)
    check_xsd(root, "DIAN_DEE_XSD_DIR" if "POS" in family else "DIAN_FE_XSD_DIR")
    assert not root.xpath(BUYER + "cbc:TaxLevelCode", namespaces=NS)
    assert root.xpath("string(" + BUYER + "cbc:CompanyID)", namespaces=NS) == CC["document_number"]
    assert not transmitted
    payload["submission_options"].update(prepare_only=False, signed_xml_base64=artifact["xml_base64"], signed_xml_filename=artifact["xml_filename"])
    def no_resign(*args, **kwargs):
        raise AssertionError("A signed retry cannot be rebuilt or re-signed")
    monkeypatch.setattr("facturacion_dian_api.core.submission.sign_document_xml", no_resign)
    monkeypatch.setattr("facturacion_dian_api.core.submission._build_document_xml", no_resign)
    for _ in range(2):
        response = client.post("/api/v1/documents/submissions", json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["document_key"] == prepared.json()["document_key"]
        assert response.json()["artifacts"]["xml_base64"] == artifact["xml_base64"]
    assert transmitted == [(artifact["xml_filename"], original)] * 2


def delivery_payload(client, bundle, responsibility, *, scheme=(None, None)):
    payload = deepcopy(DOCUMENT_SUBMISSION_INVOICE_EXAMPLE)
    payload["buyer"] = {**CC, "tax_level_code": responsibility, "tax_scheme_id": scheme[0], "tax_scheme_name": scheme[1]}
    payload["submission_options"]["prepare_only"] = True
    prepared = client.post("/api/v1/documents/submissions", json=payload)
    assert prepared.status_code == 200, prepared.text
    doc = prepared.json()
    template = etree.fromstring(base64.b64decode(DIAN_AR_XML_BASE64), etree.XMLParser(remove_blank_text=True))
    ar = etree.Element(template.tag, nsmap=NSMAP_APPLICATION_RESPONSE)
    ar.extend(template)
    for sig in ar.xpath("//*[local-name()='Signature']"):
        sig.getparent().remove(sig)
    ext = "{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}"
    extensions = etree.Element(ext + "UBLExtensions")
    etree.SubElement(etree.SubElement(extensions, ext + "UBLExtension"), ext + "ExtensionContent")
    ar.insert(0, extensions)
    # Synthetic DIAN sender and original issuer recipient; both are required by UBL.
    response_index = next(i for i, child in enumerate(ar) if etree.QName(child).localname == "DocumentResponse")
    for offset, (role, identifier) in enumerate([("SenderParty", "800197268"), ("ReceiverParty", "900123456")]):
        party = etree.Element("{" + NS["cac"] + "}" + role)
        identification = etree.SubElement(party, "{" + NS["cac"] + "}PartyIdentification")
        etree.SubElement(identification, "{" + NS["cbc"] + "}ID").text = identifier
        ar.insert(response_index + offset, party)
    ar.xpath("//*[local-name()='DocumentReference']/*[local-name()='UUID']")[0].text = doc["document_key"]
    ar_bytes = etree.tostring(sign_document(ar, bundle), encoding="UTF-8", xml_declaration=True)
    verify_embedded_document_signature(etree.fromstring(ar_bytes))
    check_xsd(etree.fromstring(ar_bytes), "DIAN_FE_XSD_DIR")
    attached = deepcopy(ATTACHED_DOCUMENT_REQUEST_EXAMPLE)
    attached.update(receiver_name=CC["name"], receiver_nit=CC["document_number"], receiver_dv=None,
                    receiver_document_type="13", cufe=doc["document_key"],
                    issue_date=payload["document"]["issue_date"],
                    invoice_xml_base64=doc["artifacts"]["xml_base64"],
                    application_response_xml_base64=base64.b64encode(ar_bytes).decode())
    attached.pop("receiver_tax_level_code")
    return attached


@pytest.mark.parametrize("assertion", [None, "R-99-PN"])
def test_unknown_responsibility_blocks_delivery_without_fabrication(client, real_crypto, assertion):
    payload = delivery_payload(client, real_crypto, None)
    payload["receiver_tax_level_code"] = assertion
    original = payload["invoice_xml_base64"]
    response = client.post("/api/v1/attached-documents", json=payload)
    assert response.status_code == 422, response.text
    assert "ATTACHED_DOCUMENT_BUYER_RESPONSIBILITY_UNRESOLVED" in response.json()["detail"]
    assert payload["invoice_xml_base64"] == original
    verify_embedded_document_signature(etree.fromstring(base64.b64decode(original)))
    assert "content_base64" not in response.json()


@pytest.mark.parametrize("scheme", [(None, None), ("01", "IVA"), ("04", "INC"), ("ZA", "IVA e INC"), ("ZZ", "No aplica")])
def test_container_and_zip_use_signed_facts_and_preserve_bytes(client, real_crypto, scheme):
    payload = delivery_payload(client, real_crypto, "O-13;O-15", scheme=scheme)
    response = client.post("/api/v1/attached-documents", json=payload)
    assert response.status_code == 200, response.text
    with ZipFile(BytesIO(base64.b64decode(response.json()["content_base64"]))) as archive:
        assert archive.namelist() == [response.json()["xml_filename"]]
        root = etree.fromstring(archive.read(archive.namelist()[0]))
    verify_document_signature(root, real_crypto)
    check_xsd(root, "DIAN_FE_XSD_DIR")
    assert root.xpath("cac:ReceiverParty/cac:PartyTaxScheme/cbc:TaxLevelCode/text()", namespaces=NS) == ["O-13;O-15"]
    assert root.xpath("cac:ReceiverParty/cac:PartyTaxScheme/cbc:TaxLevelCode/@listName", namespaces=NS) == ["No aplica"]
    assert root.xpath("cac:ReceiverParty/cac:PartyTaxScheme/cac:TaxScheme/cbc:ID/text()", namespaces=NS) == [scheme[0] or "ZZ"]
    descriptions = root.xpath("//cac:ExternalReference/cbc:Description/text()", namespaces=NS)
    for embedded, field in zip(descriptions, ["invoice_xml_base64", "application_response_xml_base64"], strict=True):
        original = base64.b64decode(payload[field])
        assert embedded.encode("utf-8") == original
        assert hashlib.sha256(embedded.encode()).digest() == hashlib.sha256(original).digest()
        verify_embedded_document_signature(etree.fromstring(original))


@pytest.mark.parametrize("field,value", [
    ("receiver_tax_level_code", "R-99-PN"), ("receiver_nit", "123"),
    ("receiver_name", "Otra persona"), ("receiver_document_type", "31"),
    ("issuer_nit", "123"), ("issuer_dv", "0"), ("document_type_code", "91"),
])
def test_container_rejects_contradictions(client, real_crypto, field, value):
    payload = delivery_payload(client, real_crypto, "O-13;O-15")
    payload[field] = value
    response = client.post("/api/v1/attached-documents", json=payload)
    assert response.status_code == 422, response.text
    assert any(message in response.text for message in ("contradicts", "does not match", "receiver_dv is required"))


@pytest.mark.parametrize("field", ["invoice_xml_base64", "application_response_xml_base64"])
def test_tampering_still_fails_crypto(client, real_crypto, field):
    payload = delivery_payload(client, real_crypto, "O-13")
    original = base64.b64decode(payload[field])
    # Replace signed content, preserving a parseable XML and its original signature.
    needle = b"COMPRADOR DE PRUEBA" if field == "invoice_xml_base64" else b"Documento Validado por la DIAN"
    payload[field] = base64.b64encode(original.replace(needle, b"TAMPERED")).decode()
    response = client.post("/api/v1/attached-documents", json=payload)
    assert response.status_code == 422
    assert "signature is invalid" in response.text


def test_container_retains_bom_and_crlf_in_original_bytes(client, real_crypto):
    payload = delivery_payload(client, real_crypto, "O-13")
    # CRLF in the XML declaration does not change the signed infoset.
    original = b"\xef\xbb\xbf" + base64.b64decode(payload["invoice_xml_base64"]).replace(b"?>", b"?>\r\n", 1)
    verify_embedded_document_signature(etree.fromstring(original))
    payload["invoice_xml_base64"] = base64.b64encode(original).decode()
    response = client.post("/api/v1/attached-documents", json=payload)
    assert response.status_code == 200, response.text
    with ZipFile(BytesIO(base64.b64decode(response.json()["content_base64"]))) as archive:
        root = etree.fromstring(archive.read(archive.namelist()[0]))
    verify_document_signature(root, real_crypto)
    extracted = root.xpath("string(cac:Attachment/cac:ExternalReference/cbc:Description)", namespaces=NS).encode()
    assert extracted == original


@pytest.mark.parametrize("kind", ["CC", "CE", "TI", "PASSPORT"])
def test_natural_person_does_not_imply_fiscal_classification(kind):
    buyer = BuyerInput.model_validate({**CC, "document_type": kind})
    assert buyer.additional_account_id is None
    assert buyer.tax_level_code is None
    assert buyer.tax_scheme_id is None


def test_openapi_marks_unknown_fiscal_fields_optional(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert not {"tax_level_code", "tax_scheme_id", "tax_scheme_name"} & set(schemas["BuyerInput"]["required"])
    assert "receiver_tax_level_code" not in schemas["AttachedDocumentRequest"]["required"]


def test_partial_issuer_is_still_rejected(client, sample_invoice_payload):
    sample_invoice_payload["buyer"] = deepcopy(CC)
    sample_invoice_payload["issuer"] = {"nit": "900123456", "dv": "8", "name": "EMISOR"}
    response = client.post("/api/v1/documents/submissions", json=sample_invoice_payload)
    assert response.status_code == 422
    assert "Body-owned issuer is incomplete" in response.text


CONSUMER_CASES = json.loads((Path(__file__).parent / "fixtures/consumer-buyer-compatibility.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CONSUMER_CASES, ids=lambda case: case["name"])
def test_existing_fe_and_pinki_requests(case, real_crypto):
    payload = deepcopy(case["payload"])
    payload["document"]["issue_date"] = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
    if case.get("invalid"):
        with pytest.raises(ValidationError, match=case.get("error")):
            xml(payload)
    else:
        _, root = xml(payload)
        signed = sign_document(root, real_crypto)
        verify_document_signature(signed, real_crypto)
        check_xsd(signed, "DIAN_DEE_XSD_DIR" if "DEE" in payload["document"]["type"] or "POS" in payload["document"]["type"] else "DIAN_FE_XSD_DIR")


@pytest.mark.parametrize("family", ["NOTA_CREDITO", "NOTA_DEBITO"])
def test_notes_keep_discount_and_tax_amounts_in_ubl_order(family, real_crypto):
    payload = deepcopy(next(c["payload"] for c in CONSUMER_CASES if c["name"] == "Pinki NC parcial"))
    payload["document"].update(type=family, issue_date=datetime.now(timezone(timedelta(hours=-5))).date().isoformat())
    payload["buyer"] = deepcopy(CC)
    _, root = xml(payload)
    line = root.xpath("cac:CreditNoteLine|cac:DebitNoteLine", namespaces=NS)[0]
    tags = [etree.QName(node).localname for node in line]
    assert tags.index("TaxTotal") < tags.index("AllowanceCharge") < tags.index("Item")
    assert line.xpath("string(cac:AllowanceCharge/cbc:Amount)", namespaces=NS) == "500.00"
    assert line.xpath("string(cac:TaxTotal/cbc:TaxAmount)", namespaces=NS) == "855.00"
    assert line.xpath("string(cbc:LineExtensionAmount)", namespaces=NS) == "4500.00"
    check_xsd(sign_document(root, real_crypto), "DIAN_FE_XSD_DIR")
