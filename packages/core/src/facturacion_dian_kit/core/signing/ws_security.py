"""WS-Security header signing for DIAN SOAP envelopes.

Mirrors the message shape emitted by WCF for DIAN's
WSHttpBinding + certificate message credential binding.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from facturacion_dian_kit.core.signing.certificate import CertificateBundle
from lxml import etree
from lxml.etree import _Element

NS_SOAP = "http://www.w3.org/2003/05/soap-envelope"
NS_WSA = "http://www.w3.org/2005/08/addressing"
NS_WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
NS_WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"

ENCODING_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-soap-message-security-1.0#Base64Binary"
)
VALUE_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-x509-token-profile-1.0#X509v3"
)

ALG_EXC_C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
ALG_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
ALG_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"


def _sha256_b64(data: bytes) -> str:
    """SHA-256 digest, Base64-encoded."""
    return base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


def sign_soap_envelope(
    envelope_bytes: bytes,
    bundle: CertificateBundle,
    ttl_ms: int = 300000,
) -> bytes:
    """Add a WCF-compatible WS-Security header to a SOAP envelope."""
    root = etree.fromstring(envelope_bytes)

    header = root.find(f"{{{NS_SOAP}}}Header")
    if header is None:
        raise ValueError("SOAP envelope missing Header")

    to_elem = header.find(f"{{{NS_WSA}}}To")
    if to_elem is None:
        raise ValueError("SOAP Header missing wsa:To element")

    ts_id = "_0"
    to_id = "_1"
    bst_id = f"uuid-{uuid.uuid4()}-1"

    to_elem.set(f"{{{NS_SOAP}}}mustUnderstand", "1")
    to_elem.set(f"{{{NS_WSU}}}Id", to_id)

    security = etree.SubElement(
        header,
        f"{{{NS_WSSE}}}Security",
        {f"{{{NS_SOAP}}}mustUnderstand": "1"},
    )

    timestamp = etree.SubElement(
        security,
        f"{{{NS_WSU}}}Timestamp",
        {f"{{{NS_WSU}}}Id": ts_id},
    )
    now = datetime.now(UTC)
    expires = now + timedelta(milliseconds=ttl_ms)
    etree.SubElement(timestamp, f"{{{NS_WSU}}}Created").text = _format_timestamp(now)
    etree.SubElement(timestamp, f"{{{NS_WSU}}}Expires").text = _format_timestamp(expires)

    bst = etree.SubElement(
        security,
        f"{{{NS_WSSE}}}BinarySecurityToken",
        {
            f"{{{NS_WSU}}}Id": bst_id,
            "EncodingType": ENCODING_TYPE,
            "ValueType": VALUE_TYPE,
        },
    )
    bst.text = base64.b64encode(bundle.cert_der).decode("ascii")

    timestamp_digest = _sha256_b64(_c14n_element(timestamp))
    to_digest = _sha256_b64(_c14n_element(to_elem))

    signed_info_xml = (
        f'<SignedInfo xmlns="{NS_DS}">'
        f'<CanonicalizationMethod Algorithm="{ALG_EXC_C14N}"/>'
        f'<SignatureMethod Algorithm="{ALG_RSA_SHA256}"/>'
        f'<Reference URI="#{ts_id}">'
        f'<Transforms><Transform Algorithm="{ALG_EXC_C14N}"/></Transforms>'
        f'<DigestMethod Algorithm="{ALG_SHA256}"/>'
        f'<DigestValue>{timestamp_digest}</DigestValue>'
        f'</Reference>'
        f'<Reference URI="#{to_id}">'
        f'<Transforms><Transform Algorithm="{ALG_EXC_C14N}"/></Transforms>'
        f'<DigestMethod Algorithm="{ALG_SHA256}"/>'
        f'<DigestValue>{to_digest}</DigestValue>'
        f'</Reference>'
        f'</SignedInfo>'
    )

    signed_info_elem = etree.fromstring(signed_info_xml.encode("utf-8"))
    signed_info_c14n = etree.tostring(
        signed_info_elem,
        method="c14n",
        exclusive=True,
    )
    signature_value = bundle.private_key.sign(  # type: ignore[union-attr]
        signed_info_c14n,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    sig_value_b64 = base64.b64encode(signature_value).decode("ascii")

    signature_xml = (
        f'<Signature xmlns="{NS_DS}">'
        f"{signed_info_xml}"
        f"<SignatureValue>{sig_value_b64}</SignatureValue>"
        f"<KeyInfo>"
        f'<wsse:SecurityTokenReference xmlns:wsse="{NS_WSSE}">'
        f'<wsse:Reference URI="#{bst_id}" ValueType="{VALUE_TYPE}"/>'
        f"</wsse:SecurityTokenReference>"
        f"</KeyInfo>"
        f"</Signature>"
    )
    security.append(etree.fromstring(signature_xml.encode("utf-8")))

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def _format_timestamp(value: datetime) -> str:
    """Serialize UTC timestamps with millisecond precision."""
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"


def _c14n_element(element: _Element) -> bytes:
    """Canonicalize an XML element with exclusive c14n."""
    return etree.tostring(
        element,
        method="c14n",
        exclusive=True,
    )

