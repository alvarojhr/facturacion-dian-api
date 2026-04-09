"""Tests for DIAN response interpretation helpers."""

import base64

from facturacion_dian_kit.core.dian.response_parser import (
    DianResponse,
    parse_get_acquirer_response,
    parse_get_numbering_range_response,
    parse_send_bill_response,
)


def test_test_set_accepted_status_is_treated_as_accepted() -> None:
    response = DianResponse(
        is_valid=False,
        status_code="2",
        status_description="Set de prueba con identificador abc se encuentra Aceptado.",
    )

    assert response.is_test_set_accepted is True
    assert response.is_accepted is True
    assert response.is_rejected is False


def test_test_set_rejected_status_is_treated_as_rejected() -> None:
    response = DianResponse(
        is_valid=False,
        status_code="2",
        status_description="Set de prueba con identificador abc se encuentra Rechazado.",
    )

    assert response.is_test_set_rejected is True
    assert response.is_accepted is False
    assert response.is_rejected is True


def test_parse_get_acquirer_response() -> None:
    response_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <GetAcquirerResponse xmlns="http://wcf.dian.colombia">
      <GetAcquirerResult xmlns:a="http://schemas.datacontract.org/2004/07/Gosocket.Dian.Services.Utils.Common">
        <a:Message>Adquiriente encontrado</a:Message>
        <a:ReceiverEmail>cliente@example.com</a:ReceiverEmail>
        <a:ReceiverName>Cliente Demo S.A.S.</a:ReceiverName>
        <a:StatusCode>00</a:StatusCode>
      </GetAcquirerResult>
    </GetAcquirerResponse>
  </s:Body>
</s:Envelope>"""

    response = parse_get_acquirer_response(response_xml)

    assert response.found is True
    assert response.status_code == "00"
    assert response.receiver_name == "Cliente Demo S.A.S."
    assert response.receiver_email == "cliente@example.com"


def test_parse_get_numbering_range_response() -> None:
    response_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <GetNumberingRangeResponse xmlns="http://wcf.dian.colombia">
      <GetNumberingRangeResult>
        <b:NumberRangeResponse xmlns:b="http://schemas.datacontract.org/2004/07/Gosocket.Dian.Services.Utils.Common">
          <b:ResolutionNumber>18764107158626</b:ResolutionNumber>
          <b:ResolutionDate>2026-03-13</b:ResolutionDate>
          <b:Prefix>FPFE</b:Prefix>
          <b:FromNumber>1</b:FromNumber>
          <b:ToNumber>99999</b:ToNumber>
          <b:ValidDateFrom>2026-03-13</b:ValidDateFrom>
          <b:ValidDateTo>2028-03-13</b:ValidDateTo>
          <b:TechnicalKey>tech-key-fe</b:TechnicalKey>
        </b:NumberRangeResponse>
      </GetNumberingRangeResult>
    </GetNumberingRangeResponse>
  </s:Body>
</s:Envelope>"""

    response = parse_get_numbering_range_response(response_xml)

    assert len(response.ranges) == 1
    assert response.ranges[0].prefix == "FPFE"
    assert response.ranges[0].resolution_number == "18764107158626"
    assert response.ranges[0].technical_key == "tech-key-fe"


def test_parse_send_bill_response_extracts_xml_bytes() -> None:
    xml_payload = b"<Invoice>demo</Invoice>"
    encoded = base64.b64encode(xml_payload).decode("ascii")
    response_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <GetStatusZipResponse xmlns="http://wcf.dian.colombia">
      <GetStatusZipResult xmlns:a="http://schemas.datacontract.org/2004/07/DianResponse">
        <a:DianResponse>
          <a:IsValid>true</a:IsValid>
          <a:StatusCode>00</a:StatusCode>
          <a:StatusDescription>Procesado Correctamente</a:StatusDescription>
          <a:XmlBase64Bytes>{encoded}</a:XmlBase64Bytes>
        </a:DianResponse>
      </GetStatusZipResult>
    </GetStatusZipResponse>
  </s:Body>
</s:Envelope>""".encode()

    response = parse_send_bill_response(response_xml)

    assert response.is_valid is True
    assert response.xml_bytes == xml_payload

