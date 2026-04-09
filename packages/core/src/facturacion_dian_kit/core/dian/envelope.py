"""SOAP 1.2 envelope builder for DIAN Web Services.

Builds the SOAP envelope with WS-Addressing headers for DIAN's
WCF-based web services (WcfDianCustomerServices.svc).

Reference: DIAN Anexo Técnico v1.9, § 9 — Web Services.
"""

from __future__ import annotations

import base64
import io
import zipfile
from uuid import uuid4

from lxml import etree

# ─── SOAP / WS-Addressing Namespaces ───────────────────────────

NS_SOAP = "http://www.w3.org/2003/05/soap-envelope"
NS_WSA = "http://www.w3.org/2005/08/addressing"
NS_WCF = "http://wcf.dian.colombia"
WSA_ANONYMOUS = "http://www.w3.org/2005/08/addressing/anonymous"

NSMAP_SOAP: dict[str | None, str] = {
    "soap": NS_SOAP,
    "wsa": NS_WSA,
    "wcf": NS_WCF,
}

# DIAN WCF action URIs
ACTION_SEND_BILL_SYNC = (
    "http://wcf.dian.colombia/IWcfDianCustomerServices/SendBillSync"
)
ACTION_SEND_TEST_SET_ASYNC = (
    "http://wcf.dian.colombia/IWcfDianCustomerServices/SendTestSetAsync"
)
ACTION_GET_STATUS = (
    "http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatus"
)
ACTION_GET_STATUS_ZIP = (
    "http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatusZip"
)
ACTION_GET_ACQUIRER = (
    "http://wcf.dian.colombia/IWcfDianCustomerServices/GetAcquirer"
)
ACTION_GET_NUMBERING_RANGE = (
    "http://wcf.dian.colombia/IWcfDianCustomerServices/GetNumberingRange"
)


def _qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _sub(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    el = etree.SubElement(parent, tag)
    if text is not None:
        el.text = text
    return el


def _add_wsa_headers(
    header: etree._Element,
    action_uri: str,
    endpoint_url: str,
) -> None:
    action = _sub(header, _qn(NS_WSA, "Action"), action_uri)
    action.set(_qn(NS_SOAP, "mustUnderstand"), "1")
    _sub(header, _qn(NS_WSA, "MessageID"), f"urn:uuid:{uuid4()}")
    reply_to = _sub(header, _qn(NS_WSA, "ReplyTo"))
    _sub(reply_to, _qn(NS_WSA, "Address"), WSA_ANONYMOUS)
    to = _sub(header, _qn(NS_WSA, "To"), endpoint_url)
    to.set(_qn(NS_SOAP, "mustUnderstand"), "1")


def build_send_bill_sync_envelope(
    endpoint_url: str,
    filename: str,
    content_b64: str,
) -> bytes:
    """Build SOAP 1.2 envelope for SendBillSync operation.

    Args:
        endpoint_url: The DIAN WSDL endpoint URL.
        filename: Name of the ZIP file (e.g., "ws_SETT000001.zip").
        content_b64: Base64-encoded ZIP content.

    Returns:
        SOAP envelope as UTF-8 bytes.
    """
    envelope = etree.Element(_qn(NS_SOAP, "Envelope"), nsmap=NSMAP_SOAP)
    header = _sub(envelope, _qn(NS_SOAP, "Header"))

    _add_wsa_headers(header, ACTION_SEND_BILL_SYNC, endpoint_url)

    body = _sub(envelope, _qn(NS_SOAP, "Body"))
    send_bill = _sub(body, _qn(NS_WCF, "SendBillSync"))
    _sub(send_bill, _qn(NS_WCF, "fileName"), filename)
    _sub(send_bill, _qn(NS_WCF, "contentFile"), content_b64)

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


def build_send_test_set_async_envelope(
    endpoint_url: str,
    filename: str,
    content_b64: str,
    test_set_id: str,
) -> bytes:
    """Build SOAP 1.2 envelope for SendTestSetAsync operation.

    Used during DIAN habilitación to submit test set documents.

    Args:
        endpoint_url: The DIAN WSDL endpoint URL.
        filename: Name of the ZIP file.
        content_b64: Base64-encoded ZIP content.
        test_set_id: DIAN-provided test set ID.

    Returns:
        SOAP envelope as UTF-8 bytes.
    """
    envelope = etree.Element(_qn(NS_SOAP, "Envelope"), nsmap=NSMAP_SOAP)
    header = _sub(envelope, _qn(NS_SOAP, "Header"))

    _add_wsa_headers(header, ACTION_SEND_TEST_SET_ASYNC, endpoint_url)

    body = _sub(envelope, _qn(NS_SOAP, "Body"))
    send_test = _sub(body, _qn(NS_WCF, "SendTestSetAsync"))
    _sub(send_test, _qn(NS_WCF, "fileName"), filename)
    _sub(send_test, _qn(NS_WCF, "contentFile"), content_b64)
    _sub(send_test, _qn(NS_WCF, "testSetId"), test_set_id)

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


def build_get_status_envelope(
    endpoint_url: str,
    tracking_id: str,
) -> bytes:
    """Build SOAP 1.2 envelope for GetStatus operation."""
    envelope = etree.Element(_qn(NS_SOAP, "Envelope"), nsmap=NSMAP_SOAP)
    header = _sub(envelope, _qn(NS_SOAP, "Header"))

    _add_wsa_headers(header, ACTION_GET_STATUS, endpoint_url)

    body = _sub(envelope, _qn(NS_SOAP, "Body"))
    get_status = _sub(body, _qn(NS_WCF, "GetStatus"))
    _sub(get_status, _qn(NS_WCF, "trackId"), tracking_id)

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


def build_get_status_zip_envelope(
    endpoint_url: str,
    tracking_id: str,
) -> bytes:
    """Build SOAP 1.2 envelope for GetStatusZip operation."""
    envelope = etree.Element(_qn(NS_SOAP, "Envelope"), nsmap=NSMAP_SOAP)
    header = _sub(envelope, _qn(NS_SOAP, "Header"))

    _add_wsa_headers(header, ACTION_GET_STATUS_ZIP, endpoint_url)

    body = _sub(envelope, _qn(NS_SOAP, "Body"))
    get_status = _sub(body, _qn(NS_WCF, "GetStatusZip"))
    _sub(get_status, _qn(NS_WCF, "trackId"), tracking_id)

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


def build_get_acquirer_envelope(
    endpoint_url: str,
    identification_type: str,
    identification_number: str,
) -> bytes:
    """Build SOAP 1.2 envelope for GetAcquirer operation."""
    envelope = etree.Element(_qn(NS_SOAP, "Envelope"), nsmap=NSMAP_SOAP)
    header = _sub(envelope, _qn(NS_SOAP, "Header"))

    _add_wsa_headers(header, ACTION_GET_ACQUIRER, endpoint_url)

    body = _sub(envelope, _qn(NS_SOAP, "Body"))
    get_acquirer = _sub(body, _qn(NS_WCF, "GetAcquirer"))
    _sub(get_acquirer, _qn(NS_WCF, "identificationType"), identification_type)
    _sub(get_acquirer, _qn(NS_WCF, "identificationNumber"), identification_number)

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


def build_get_numbering_range_envelope(
    endpoint_url: str,
    account_code: str,
    account_code_t: str,
    software_code: str,
) -> bytes:
    """Build SOAP 1.2 envelope for GetNumberingRange operation."""
    envelope = etree.Element(_qn(NS_SOAP, "Envelope"), nsmap=NSMAP_SOAP)
    header = _sub(envelope, _qn(NS_SOAP, "Header"))

    _add_wsa_headers(header, ACTION_GET_NUMBERING_RANGE, endpoint_url)

    body = _sub(envelope, _qn(NS_SOAP, "Body"))
    lookup = _sub(body, _qn(NS_WCF, "GetNumberingRange"))
    _sub(lookup, _qn(NS_WCF, "accountCode"), account_code)
    _sub(lookup, _qn(NS_WCF, "accountCodeT"), account_code_t)
    _sub(lookup, _qn(NS_WCF, "softwareCode"), software_code)

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


# ─── ZIP Helpers ─────────────────────────────────────────────


def zip_and_encode(filename: str, xml_bytes: bytes) -> tuple[str, str]:
    """ZIP the signed XML and Base64-encode it.

    Args:
        filename: The XML filename inside the ZIP (e.g., "ws_SETT000001.xml").
        xml_bytes: The signed XML content.

    Returns:
        Tuple of (zip_filename, base64_content).
        zip_filename is the XML filename with .zip extension.
    """
    zip_filename = filename.rsplit(".", 1)[0] + ".zip"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, xml_bytes)

    zip_bytes = buf.getvalue()
    b64 = base64.b64encode(zip_bytes).decode("ascii")

    return zip_filename, b64
