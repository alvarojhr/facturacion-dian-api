"""XAdES-EPES signing for DIAN electronic documents."""

from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from facturacion_dian_kit.core.signing.certificate import CertificateBundle, get_certificate_bundle
from facturacion_dian_kit.core.xml.namespaces import NS_DS, NS_EXT, NS_XADES
from lxml import etree
from signxml import (
    CanonicalizationMethod,
    DigestAlgorithm,
    SignatureConstructionMethod,
    SignatureMethod,
)
from signxml.util import add_pem_header, strip_pem_header
from signxml.xades import XAdESSignaturePolicy, XAdESSigner

DIAN_POLICY_URL = (
    "https://facturaelectronica.dian.gov.co/politicadefirma/v2/politicadefirmav2.pdf"
)
DIAN_POLICY_DESCRIPTION = (
    "PolÃ­tica de firma para facturas electrÃ³nicas de la RepÃºblica de Colombia."
)
DIAN_POLICY_DIGEST = "dMoMvtcG5aIzgYo0tIsSQeVJBDnUnfSOfBpxXrmor0Y="
DIAN_SIGNER_ROLE = "supplier"
COLOMBIA_TZ = timezone(timedelta(hours=-5))


def _qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _load_cert(cert: x509.Certificate | str | bytes) -> x509.Certificate:
    if isinstance(cert, x509.Certificate):
        return cert
    return x509.load_pem_x509_certificate(add_pem_header(cert))


class DianXAdESSigner(XAdESSigner):
    """Emit the XAdES layout DIAN accepts for invoice documents."""

    def _add_key_info(self, sig_root, signing_settings):  # type: ignore[override]
        if "Id" not in sig_root.attrib:
            sig_root.set("Id", f"xmldsig-{uuid4()}")

        key_info = etree.SubElement(sig_root, _qn(NS_DS, "KeyInfo"), nsmap=self.namespaces)
        if "Id" not in key_info.attrib:
            key_info.set("Id", f"{sig_root.get('Id')}-keyinfo")

        assert signing_settings.cert_chain is not None
        leaf_cert = _load_cert(signing_settings.cert_chain[0])

        x509_data = etree.SubElement(key_info, _qn(NS_DS, "X509Data"), nsmap=self.namespaces)
        x509_certificate = etree.SubElement(x509_data, _qn(NS_DS, "X509Certificate"), nsmap=self.namespaces)
        x509_certificate.text = strip_pem_header(leaf_cert.public_bytes(Encoding.PEM))

    def _build_xades_ds_object(self, sig_root, signing_settings):  # type: ignore[override]
        if "Id" not in sig_root.attrib:
            sig_root.set("Id", f"xmldsig-{uuid4()}")

        key_info = self._find(sig_root, "KeyInfo")
        if "Id" not in key_info.attrib:
            key_info.set("Id", f"{sig_root.get('Id')}-keyinfo")

        ds_object = etree.SubElement(sig_root, _qn(NS_DS, "Object"), nsmap=self.namespaces)
        qualifying_properties = etree.SubElement(
            ds_object,
            _qn(NS_XADES, "QualifyingProperties"),
            nsmap=self.namespaces,
            Target=f"#{sig_root.get('Id')}",
        )
        signed_properties = etree.SubElement(
            qualifying_properties,
            _qn(NS_XADES, "SignedProperties"),
            nsmap=self.namespaces,
            Id=f"{sig_root.get('Id')}-signedprops",
        )
        signed_signature_properties = etree.SubElement(
            signed_properties,
            _qn(NS_XADES, "SignedSignatureProperties"),
            nsmap=self.namespaces,
        )
        for annotator in self.signed_signature_properties_annotators:
            annotator(signed_signature_properties, sig_root=sig_root, signing_settings=signing_settings)

        self._add_reference_to_signed_info(sig_root, key_info)
        self._add_reference_to_signed_info(
            sig_root,
            signed_properties,
            Type="http://uri.etsi.org/01903#SignedProperties",
        )

    def add_signing_time(self, signed_signature_properties, sig_root, signing_settings):  # type: ignore[override]
        signing_time = etree.SubElement(
            signed_signature_properties,
            _qn(NS_XADES, "SigningTime"),
            nsmap=self.namespaces,
        )
        signing_time.text = datetime.now(COLOMBIA_TZ).isoformat(timespec="milliseconds")

    def add_signing_certificate(self, signed_signature_properties, sig_root, signing_settings):  # type: ignore[override]
        signing_certificate = etree.SubElement(
            signed_signature_properties,
            _qn(NS_XADES, "SigningCertificate"),
            nsmap=self.namespaces,
        )

        assert signing_settings.cert_chain is not None
        leaf_cert = _load_cert(signing_settings.cert_chain[0])

        cert_node = etree.SubElement(signing_certificate, _qn(NS_XADES, "Cert"), nsmap=self.namespaces)
        cert_digest = etree.SubElement(cert_node, _qn(NS_XADES, "CertDigest"), nsmap=self.namespaces)
        etree.SubElement(
            cert_digest,
            _qn(NS_DS, "DigestMethod"),
            nsmap=self.namespaces,
            Algorithm=self.digest_alg.value,
        )
        digest_value = etree.SubElement(cert_digest, _qn(NS_DS, "DigestValue"), nsmap=self.namespaces)
        digest_value.text = b64encode(
            self._get_digest(
                leaf_cert.public_bytes(Encoding.DER),
                algorithm=self.digest_alg,
            )
        ).decode()

        issuer_serial = etree.SubElement(cert_node, _qn(NS_XADES, "IssuerSerial"), nsmap=self.namespaces)
        issuer_name = etree.SubElement(issuer_serial, _qn(NS_DS, "X509IssuerName"), nsmap=self.namespaces)
        issuer_name.text = leaf_cert.issuer.rfc4514_string()
        serial_number = etree.SubElement(
            issuer_serial,
            _qn(NS_DS, "X509SerialNumber"),
            nsmap=self.namespaces,
        )
        serial_number.text = str(leaf_cert.serial_number)


def _build_signer() -> DianXAdESSigner:
    """Create an XAdES-EPES signer configured for DIAN requirements."""
    policy = XAdESSignaturePolicy(
        Identifier=DIAN_POLICY_URL,
        Description=DIAN_POLICY_DESCRIPTION,
        DigestMethod=DigestAlgorithm.SHA256,
        DigestValue=DIAN_POLICY_DIGEST,
    )

    signer = DianXAdESSigner(
        signature_policy=policy,
        claimed_roles=[DIAN_SIGNER_ROLE],
        method=SignatureConstructionMethod.enveloped,
        signature_algorithm=SignatureMethod.RSA_SHA256,
        digest_algorithm=DigestAlgorithm.SHA256,
        c14n_algorithm=CanonicalizationMethod.CANONICAL_XML_1_0,
    )
    signer.signed_data_object_properties_annotators = []
    return signer


def sign_document(
    xml_root: etree._Element,
    bundle: CertificateBundle | None = None,
) -> etree._Element:
    """Sign a UBL XML document with XAdES-EPES for DIAN."""
    if bundle is None:
        bundle = get_certificate_bundle()

    signer = _build_signer()
    signed_root = signer.sign(
        xml_root,
        key=bundle.private_key,
        cert=[bundle.certificate],
        always_add_key_value=False,
        exclude_c14n_transform_element=True,
    )
    _relocate_signature(signed_root)
    _set_signature_value_id(signed_root)
    return signed_root


def _relocate_signature(root: etree._Element) -> None:
    """Move ds:Signature into the final UBLExtension placeholder."""
    ds_signature_tag = _qn(NS_DS, "Signature")
    extension_tag = _qn(NS_EXT, "UBLExtension")
    extension_content_tag = _qn(NS_EXT, "ExtensionContent")

    signature = next((child for child in root if child.tag == ds_signature_tag), None)
    if signature is None:
        return

    root.remove(signature)

    extensions = root.find(_qn(NS_EXT, "UBLExtensions"))
    if extensions is None:
        return

    ubl_extensions = extensions.findall(extension_tag)
    if len(ubl_extensions) < 2:
        return

    extension_content = ubl_extensions[-1].find(extension_content_tag)
    if extension_content is None:
        return

    extension_content.append(signature)


def _set_signature_value_id(root: etree._Element) -> None:
    signature = root.find(f".//{_qn(NS_DS, 'Signature')}")
    if signature is None:
        return

    signature_value = signature.find(_qn(NS_DS, "SignatureValue"))
    if signature_value is None or signature.get("Id") is None:
        return

    signature_value.set("Id", f"{signature.get('Id')}-sigvalue")


def sign_document_xml(
    xml_root: etree._Element,
    bundle: CertificateBundle | None = None,
) -> bytes:
    """Sign and serialize a UBL XML document."""
    signed = sign_document(xml_root, bundle)
    return etree.tostring(
        signed,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=False,
    )

