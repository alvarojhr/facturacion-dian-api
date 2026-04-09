"""Tests for SOAP envelope builder and response parser."""

from __future__ import annotations

import base64

from facturacion_dian_kit.core.dian.envelope import (
    ACTION_GET_ACQUIRER,
    ACTION_GET_NUMBERING_RANGE,
    ACTION_GET_STATUS,
    ACTION_GET_STATUS_ZIP,
    ACTION_SEND_BILL_SYNC,
    ACTION_SEND_TEST_SET_ASYNC,
    NS_SOAP,
    NS_WCF,
    NS_WSA,
    WSA_ANONYMOUS,
    build_get_acquirer_envelope,
    build_get_numbering_range_envelope,
    build_get_status_envelope,
    build_get_status_zip_envelope,
    build_send_bill_sync_envelope,
    build_send_test_set_async_envelope,
    zip_and_encode,
)
from facturacion_dian_kit.core.dian.response_parser import DianResponse, parse_send_bill_response
from lxml import etree

ENDPOINT = "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc"

NS = {"s": NS_SOAP, "wsa": NS_WSA, "wcf": NS_WCF}


def _parse(xml_bytes: bytes) -> etree._Element:
    return etree.fromstring(xml_bytes)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SendBillSync Envelope
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestSendBillSyncEnvelope:

    def test_root_is_soap_envelope(self) -> None:
        env = build_send_bill_sync_envelope(ENDPOINT, "test.zip", "base64data")
        root = _parse(env)
        assert root.tag == f"{{{NS_SOAP}}}Envelope"

    def test_has_soap_header_and_body(self) -> None:
        env = build_send_bill_sync_envelope(ENDPOINT, "test.zip", "base64data")
        root = _parse(env)
        header = root.find(f"{{{NS_SOAP}}}Header")
        body = root.find(f"{{{NS_SOAP}}}Body")
        assert header is not None
        assert body is not None

    def test_wsa_action(self) -> None:
        env = build_send_bill_sync_envelope(ENDPOINT, "test.zip", "base64data")
        root = _parse(env)
        action = root.xpath("s:Header/wsa:Action", namespaces=NS)
        assert len(action) == 1
        assert action[0].text == ACTION_SEND_BILL_SYNC
        assert action[0].attrib[f"{{{NS_SOAP}}}mustUnderstand"] == "1"

    def test_wsa_to(self) -> None:
        env = build_send_bill_sync_envelope(ENDPOINT, "test.zip", "base64data")
        root = _parse(env)
        to = root.xpath("s:Header/wsa:To", namespaces=NS)
        assert len(to) == 1
        assert to[0].text == ENDPOINT
        assert to[0].attrib[f"{{{NS_SOAP}}}mustUnderstand"] == "1"

    def test_wsa_message_id(self) -> None:
        env = build_send_bill_sync_envelope(ENDPOINT, "test.zip", "base64data")
        root = _parse(env)
        message_id = root.xpath("s:Header/wsa:MessageID/text()", namespaces=NS)
        assert len(message_id) == 1
        assert message_id[0].startswith("urn:uuid:")

    def test_wsa_reply_to(self) -> None:
        env = build_send_bill_sync_envelope(ENDPOINT, "test.zip", "base64data")
        root = _parse(env)
        address = root.xpath(
            "s:Header/wsa:ReplyTo/wsa:Address/text()",
            namespaces=NS,
        )
        assert address == [WSA_ANONYMOUS]

    def test_body_filename(self) -> None:
        env = build_send_bill_sync_envelope(ENDPOINT, "invoice.zip", "abc123")
        root = _parse(env)
        filename = root.xpath("s:Body/wcf:SendBillSync/wcf:fileName", namespaces=NS)
        assert filename[0].text == "invoice.zip"

    def test_body_content(self) -> None:
        env = build_send_bill_sync_envelope(ENDPOINT, "invoice.zip", "abc123")
        root = _parse(env)
        content = root.xpath("s:Body/wcf:SendBillSync/wcf:contentFile", namespaces=NS)
        assert content[0].text == "abc123"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SendTestSetAsync Envelope
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestSendTestSetAsyncEnvelope:

    def test_action_is_test_set(self) -> None:
        env = build_send_test_set_async_envelope(ENDPOINT, "f.zip", "b64", "ts-id")
        root = _parse(env)
        action = root.xpath("s:Header/wsa:Action", namespaces=NS)
        assert action[0].text == ACTION_SEND_TEST_SET_ASYNC

    def test_test_set_id_present(self) -> None:
        env = build_send_test_set_async_envelope(ENDPOINT, "f.zip", "b64", "my-test-set")
        root = _parse(env)
        ts = root.xpath("s:Body/wcf:SendTestSetAsync/wcf:testSetId", namespaces=NS)
        assert ts[0].text == "my-test-set"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# GetStatus / GetStatusZip Envelopes
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestGetStatusEnvelope:

    def test_get_status_action(self) -> None:
        env = build_get_status_envelope(ENDPOINT, "track-123")
        root = _parse(env)
        action = root.xpath("s:Header/wsa:Action", namespaces=NS)
        assert action[0].text == ACTION_GET_STATUS

    def test_get_status_tracking_id(self) -> None:
        env = build_get_status_envelope(ENDPOINT, "track-123")
        root = _parse(env)
        tid = root.xpath("s:Body/wcf:GetStatus/wcf:trackId", namespaces=NS)
        assert tid[0].text == "track-123"

    def test_get_status_zip_action(self) -> None:
        env = build_get_status_zip_envelope(ENDPOINT, "track-456")
        root = _parse(env)
        action = root.xpath("s:Header/wsa:Action", namespaces=NS)
        assert action[0].text == ACTION_GET_STATUS_ZIP

    def test_get_acquirer_action(self) -> None:
        env = build_get_acquirer_envelope(ENDPOINT, "31", "900123456")
        root = _parse(env)
        action = root.xpath("s:Header/wsa:Action", namespaces=NS)
        assert action[0].text == ACTION_GET_ACQUIRER

    def test_get_acquirer_body(self) -> None:
        env = build_get_acquirer_envelope(ENDPOINT, "13", "12345678")
        root = _parse(env)
        identification_type = root.xpath(
            "s:Body/wcf:GetAcquirer/wcf:identificationType",
            namespaces=NS,
        )
        identification_number = root.xpath(
            "s:Body/wcf:GetAcquirer/wcf:identificationNumber",
            namespaces=NS,
        )
        assert identification_type[0].text == "13"
        assert identification_number[0].text == "12345678"

    def test_get_numbering_range_action(self) -> None:
        env = build_get_numbering_range_envelope(ENDPOINT, "901975980", "901975980", "software-123")
        root = _parse(env)
        action = root.xpath("s:Header/wsa:Action", namespaces=NS)
        assert action[0].text == ACTION_GET_NUMBERING_RANGE

    def test_get_numbering_range_body(self) -> None:
        env = build_get_numbering_range_envelope(ENDPOINT, "901975980", "901975980", "software-123")
        root = _parse(env)
        account_code = root.xpath("s:Body/wcf:GetNumberingRange/wcf:accountCode", namespaces=NS)
        account_code_t = root.xpath("s:Body/wcf:GetNumberingRange/wcf:accountCodeT", namespaces=NS)
        software_code = root.xpath("s:Body/wcf:GetNumberingRange/wcf:softwareCode", namespaces=NS)
        assert account_code[0].text == "901975980"
        assert account_code_t[0].text == "901975980"
        assert software_code[0].text == "software-123"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ZIP + Base64 Encoding
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestZipAndEncode:

    def test_returns_zip_filename(self) -> None:
        zip_name, _ = zip_and_encode("ws_SETT000001.xml", b"<Invoice/>")
        assert zip_name == "ws_SETT000001.zip"

    def test_returns_base64_string(self) -> None:
        _, b64 = zip_and_encode("test.xml", b"<Invoice/>")
        # Should be valid base64
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0

    def test_zip_contains_xml(self) -> None:
        import io
        import zipfile

        _, b64 = zip_and_encode("test.xml", b"<Invoice>content</Invoice>")
        zip_bytes = base64.b64decode(b64)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert "test.xml" in zf.namelist()
            assert zf.read("test.xml") == b"<Invoice>content</Invoice>"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Response Parser
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestResponseParser:

    def _make_response(
        self,
        is_valid: str = "true",
        status_code: str = "00",
        status_desc: str = "Procesado Correctamente",
        status_msg: str = "",
        errors: list[str] | None = None,
    ) -> bytes:
        """Build a minimal DIAN-like SOAP response for testing."""
        error_xml = ""
        if errors:
            error_strings = "".join(
                f'<b:string xmlns:b="http://schemas.microsoft.com/2003/10/Serialization/Arrays">{e}</b:string>'
                for e in errors
            )
            error_xml = f"<ErrorMessage xmlns=\"http://wcf.dian.colombia\">{error_strings}</ErrorMessage>"

        return f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <SendBillSyncResponse xmlns="http://wcf.dian.colombia">
      <SendBillSyncResult>
        <IsValid xmlns="http://wcf.dian.colombia">{is_valid}</IsValid>
        <StatusCode xmlns="http://wcf.dian.colombia">{status_code}</StatusCode>
        <StatusDescription xmlns="http://wcf.dian.colombia">{status_desc}</StatusDescription>
        <StatusMessage xmlns="http://wcf.dian.colombia">{status_msg}</StatusMessage>
        {error_xml}
      </SendBillSyncResult>
    </SendBillSyncResponse>
  </s:Body>
</s:Envelope>""".encode()

    def test_parse_valid_response(self) -> None:
        resp = parse_send_bill_response(self._make_response())
        assert resp.is_valid is True
        assert resp.status_code == "00"
        assert resp.is_accepted is True

    def test_parse_rejected_response(self) -> None:
        resp = parse_send_bill_response(
            self._make_response(is_valid="false", status_code="99")
        )
        assert resp.is_valid is False
        assert resp.is_rejected is True

    def test_parse_error_messages(self) -> None:
        resp = parse_send_bill_response(
            self._make_response(
                is_valid="false",
                status_code="99",
                errors=["Error 1", "Error 2"],
            )
        )
        assert len(resp.error_messages) == 2
        assert "Error 1" in resp.error_messages

    def test_parse_status_description(self) -> None:
        resp = parse_send_bill_response(
            self._make_response(status_desc="Documento procesado exitosamente")
        )
        assert resp.status_description == "Documento procesado exitosamente"

    def test_parse_invalid_xml(self) -> None:
        resp = parse_send_bill_response(b"not xml at all")
        assert resp.is_valid is False
        assert "Failed to parse" in resp.status_message

    def test_parse_soap_fault(self) -> None:
        fault_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <s:Fault>
      <s:Code><s:Value>s:Sender</s:Value></s:Code>
      <s:Reason><s:Text xml:lang="en">Invalid request</s:Text></s:Reason>
    </s:Fault>
  </s:Body>
</s:Envelope>"""
        resp = parse_send_bill_response(fault_xml)
        assert resp.is_valid is False
        assert "Invalid request" in resp.status_message

    def test_parse_send_test_set_async_success(self) -> None:
        resp_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <SendTestSetAsyncResponse xmlns="http://wcf.dian.colombia">
      <SendTestSetAsyncResult
        xmlns:b="http://schemas.datacontract.org/2004/07/UploadDocumentResponse"
        xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
        <b:ErrorMessageList i:nil="true" />
        <b:ZipKey>1350f01d-3d19-4440-a153-fa60490af22d</b:ZipKey>
      </SendTestSetAsyncResult>
    </SendTestSetAsyncResponse>
  </s:Body>
</s:Envelope>"""
        resp = parse_send_bill_response(resp_xml)
        assert resp.is_valid is True
        assert resp.is_accepted is True
        assert resp.tracking_id == "1350f01d-3d19-4440-a153-fa60490af22d"

    def test_parse_send_test_set_async_errors(self) -> None:
        resp_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <SendTestSetAsyncResponse xmlns="http://wcf.dian.colombia">
      <SendTestSetAsyncResult
        xmlns:b="http://schemas.datacontract.org/2004/07/UploadDocumentResponse"
        xmlns:c="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
        <b:ErrorMessageList>
          <c:string>Error 1</c:string>
          <c:string>Error 2</c:string>
        </b:ErrorMessageList>
      </SendTestSetAsyncResult>
    </SendTestSetAsyncResponse>
  </s:Body>
</s:Envelope>"""
        resp = parse_send_bill_response(resp_xml)
        assert resp.is_valid is False
        assert resp.error_messages == ["Error 1", "Error 2"]

    def test_parse_get_status_zip_array_response(self) -> None:
        resp_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <GetStatusZipResponse xmlns="http://wcf.dian.colombia">
      <GetStatusZipResult xmlns:a="http://schemas.datacontract.org/2004/07/DianResponse">
        <a:DianResponse>
          <a:IsValid>true</a:IsValid>
          <a:StatusCode>00</a:StatusCode>
          <a:StatusDescription>Procesado Correctamente</a:StatusDescription>
          <a:StatusMessage>Documento validado</a:StatusMessage>
          <a:XmlDocumentKey>track-zip-123</a:XmlDocumentKey>
        </a:DianResponse>
      </GetStatusZipResult>
    </GetStatusZipResponse>
  </s:Body>
</s:Envelope>"""
        resp = parse_send_bill_response(resp_xml)
        assert resp.is_valid is True
        assert resp.status_code == "00"
        assert resp.tracking_id == "track-zip-123"

    def test_to_dict(self) -> None:
        resp = parse_send_bill_response(self._make_response())
        d = resp.to_dict()
        assert d["is_valid"] is True
        assert d["status_code"] == "00"
        assert isinstance(d["error_messages"], list)

