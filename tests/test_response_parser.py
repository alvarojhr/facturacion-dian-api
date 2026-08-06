"""Tests for DIAN response interpretation helpers."""

import base64

import pytest
from facturacion_dian_api.core.dian.response_parser import (
    DianResponse,
    parse_get_acquirer_response,
    parse_get_numbering_range_response,
    parse_get_xml_by_document_key_response,
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


def _download_envelope(inner: str) -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <GetXmlByDocumentKeyResponse xmlns="http://wcf.dian.colombia">
      <GetXmlByDocumentKeyResult xmlns:a="http://schemas.datacontract.org/2004/07/DianResponse">
        {inner}
      </GetXmlByDocumentKeyResult>
    </GetXmlByDocumentKeyResponse>
  </s:Body>
</s:Envelope>""".encode()


def test_parse_get_xml_by_document_key_response_decodes_xml() -> None:
    xml_payload = b"<Invoice><ID>FDK000001</ID></Invoice>"
    encoded = base64.b64encode(xml_payload).decode("ascii")

    response = parse_get_xml_by_document_key_response(
        _download_envelope(f"<a:XmlBase64Bytes>{encoded}</a:XmlBase64Bytes>")
    )

    assert response.success is True
    assert response.xml_bytes == xml_payload
    assert response.status == "DOWNLOADED"
    assert response.error_message == ""


@pytest.mark.parametrize("field", ["XmlBase64Bytes", "XmlBytesBase64", "XmlBytes"])
def test_parse_get_xml_by_document_key_accepts_known_payload_field_names(field: str) -> None:
    # DIAN no expone un unico nombre estable para el contenedor del base64
    # entre operaciones, asi que el parser tolera las variantes conocidas.
    xml_payload = b"<Invoice>demo</Invoice>"
    encoded = base64.b64encode(xml_payload).decode("ascii")

    response = parse_get_xml_by_document_key_response(
        _download_envelope(f"<a:{field}>{encoded}</a:{field}>")
    )

    assert response.success is True
    assert response.xml_bytes == xml_payload


def test_parse_get_xml_by_document_key_reports_status_from_dian() -> None:
    xml_payload = b"<Invoice>demo</Invoice>"
    encoded = base64.b64encode(xml_payload).decode("ascii")

    response = parse_get_xml_by_document_key_response(
        _download_envelope(
            f"<a:XmlBase64Bytes>{encoded}</a:XmlBase64Bytes>"
            "<a:StatusMessage>Documento encontrado</a:StatusMessage>"
        )
    )

    assert response.success is True
    assert response.status == "Documento encontrado"


def test_parse_get_xml_by_document_key_missing_payload_is_not_found() -> None:
    response = parse_get_xml_by_document_key_response(
        _download_envelope("<a:StatusCode>404</a:StatusCode>")
    )

    assert response.success is False
    assert response.xml_bytes is None
    assert response.error_message


def test_parse_get_xml_by_document_key_error_message_overrides_success() -> None:
    xml_payload = b"<Invoice>demo</Invoice>"
    encoded = base64.b64encode(xml_payload).decode("ascii")

    response = parse_get_xml_by_document_key_response(
        _download_envelope(
            f"<a:XmlBase64Bytes>{encoded}</a:XmlBase64Bytes>"
            "<a:ErrorMessage>Documento no autorizado</a:ErrorMessage>"
        )
    )

    assert response.success is False
    assert response.error_message == "Documento no autorizado"


def test_parse_get_xml_by_document_key_corrupt_base64_is_not_success() -> None:
    # base64.b64decode ignora los caracteres no-base64 en vez de fallar, asi
    # que "###" decodifica a b"" sin lanzar. Eso no puede reportarse como
    # descarga exitosa con cero bytes.
    response = parse_get_xml_by_document_key_response(
        _download_envelope("<a:XmlBase64Bytes>###</a:XmlBase64Bytes>")
    )

    assert response.success is False
    assert response.xml_bytes is None
    assert response.error_message == "Failed to decode base64 XML from DIAN response"


def test_parse_get_xml_by_document_key_soap_fault() -> None:
    fault_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <s:Fault>
      <s:Code><s:Value>s:Sender</s:Value></s:Code>
      <s:Reason><s:Text xml:lang="es">Token de seguridad invalido</s:Text></s:Reason>
    </s:Fault>
  </s:Body>
</s:Envelope>"""

    response = parse_get_xml_by_document_key_response(fault_xml)

    assert response.success is False
    assert response.error_message == "Token de seguridad invalido"


def test_parse_get_xml_by_document_key_malformed_xml_does_not_raise() -> None:
    response = parse_get_xml_by_document_key_response(b"<not-xml")

    assert response.success is False
    assert response.error_message == "Failed to parse DIAN response XML"


def test_parse_get_xml_by_document_key_to_dict_omits_raw_bytes() -> None:
    xml_payload = b"<Invoice>demo</Invoice>"
    encoded = base64.b64encode(xml_payload).decode("ascii")

    response = parse_get_xml_by_document_key_response(
        _download_envelope(f"<a:XmlBase64Bytes>{encoded}</a:XmlBase64Bytes>")
    )
    payload = response.to_dict()

    # raw_response viaja al cliente HTTP: debe ser serializable y no cargar
    # el XML binario, que ya se expone aparte como xml_base64.
    assert "xml_bytes" not in payload
    assert payload["success"] is True
    assert payload["status"] == "DOWNLOADED"



def _get_status_envelope(inner: str) -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <GetStatusResponse xmlns="http://wcf.dian.colombia">
      <GetStatusResult xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse">
        {inner}
      </GetStatusResult>
    </GetStatusResponse>
  </s:Body>
</s:Envelope>""".encode()


def test_get_status_exposes_document_key_reported_by_dian() -> None:
    """
    ``XmlDocumentKey`` es el CUFE/CUDE del documento que DIAN proceso. Se expone
    aparte del tracking id: quien reconcilia un envio cuyo acuse se perdio necesita
    la clave, y recalcularla daria otro valor si el reintento se firmo con otra hora.
    """
    document_key = "a" * 96

    response = parse_send_bill_response(
        _get_status_envelope(
            f"""<b:IsValid>true</b:IsValid>
        <b:StatusCode>00</b:StatusCode>
        <b:StatusDescription>Procesado Correctamente.</b:StatusDescription>
        <b:XmlDocumentKey>{document_key}</b:XmlDocumentKey>"""
        )
    )

    assert response.document_key == document_key
    assert response.to_dict()["document_key"] == document_key


def test_zip_key_is_a_tracking_id_and_not_a_document_key() -> None:
    """Un ZipKey identifica el envio, no el documento: no debe filtrarse como clave."""
    response = parse_send_bill_response(
        _get_status_envelope(
            """<b:IsValid>true</b:IsValid>
        <b:StatusCode>00</b:StatusCode>
        <b:ZipKey>zip-key-123</b:ZipKey>"""
        )
    )

    assert response.tracking_id == "zip-key-123"
    assert response.document_key is None


def test_document_key_absent_leaves_tracking_id_fallback_intact() -> None:
    """Sin ZipKey el tracking id sigue cayendo a XmlDocumentKey (contrato existente)."""
    document_key = "b" * 96

    response = parse_send_bill_response(
        _get_status_envelope(
            f"""<b:IsValid>true</b:IsValid>
        <b:StatusCode>00</b:StatusCode>
        <b:XmlDocumentKey>{document_key}</b:XmlDocumentKey>"""
        )
    )

    assert response.tracking_id == document_key
    assert response.document_key == document_key
