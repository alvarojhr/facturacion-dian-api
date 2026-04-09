"""DIAN SOAP response parser."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

NS_SOAP = "http://www.w3.org/2003/05/soap-envelope"
NS_DIAN = "http://wcf.dian.colombia"


def _local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def _first_text_by_local_name(parent: etree._Element, *names: str) -> str | None:
    expected = set(names)
    for child in parent.iterdescendants():
        if _local_name(child) in expected and child.text:
            text = child.text.strip()
            if text:
                return text
    return None


def _collect_texts_from_containers(parent: etree._Element, *container_names: str) -> list[str]:
    expected = set(container_names)
    values: list[str] = []

    for container in parent.iterdescendants():
        if _local_name(container) not in expected:
            continue
        for child in container.iterdescendants():
            if len(child) == 0 and child.text:
                text = child.text.strip()
                if text:
                    values.append(text)
    return values


def _find_result_element(root: etree._Element) -> etree._Element | None:
    result_names = {
        "SendBillSyncResult",
        "SendTestSetAsyncResult",
        "GetStatusResult",
        "GetStatusZipResult",
    }

    for element in root.iterdescendants():
        if _local_name(element) not in result_names:
            continue

        if _local_name(element) == "GetStatusZipResult":
            for child in element.iterdescendants():
                if _local_name(child) == "DianResponse":
                    return child
        return element

    return None


def _find_first_element_by_local_name(
    root: etree._Element,
    *names: str,
) -> etree._Element | None:
    expected = set(names)
    for element in root.iterdescendants():
        if _local_name(element) in expected:
            return element
    return None


@dataclass
class DianResponse:
    """Parsed DIAN SOAP response."""

    is_valid: bool = False
    status_code: str = ""
    status_description: str = ""
    status_message: str = ""
    error_messages: list[str] = field(default_factory=list)
    xml_bytes: bytes | None = None
    tracking_id: str | None = None
    raw_xml: str = ""

    @property
    def is_test_set_accepted(self) -> bool:
        return self.status_code == "2" and "se encuentra Aceptado" in self.status_description

    @property
    def is_test_set_rejected(self) -> bool:
        return self.status_code == "2" and "se encuentra Rechazado" in self.status_description

    @property
    def is_accepted(self) -> bool:
        return self.is_test_set_accepted or (self.is_valid and self.status_code in ("00", ""))

    @property
    def is_rejected(self) -> bool:
        return self.is_test_set_rejected or (not self.is_valid and not self.is_test_set_accepted)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "status_code": self.status_code,
            "status_description": self.status_description,
            "status_message": self.status_message,
            "error_messages": self.error_messages,
            "tracking_id": self.tracking_id,
            "raw_xml": self.raw_xml,
        }


@dataclass
class AcquirerResponse:
    """Parsed DIAN buyer lookup response."""

    found: bool = False
    status_code: str = ""
    message: str = ""
    receiver_name: str | None = None
    receiver_email: str | None = None
    raw_xml: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "status_code": self.status_code,
            "message": self.message,
            "receiver_name": self.receiver_name,
            "receiver_email": self.receiver_email,
            "raw_xml": self.raw_xml,
        }


@dataclass
class NumberingRange:
    """Parsed DIAN numbering range item."""

    resolution_number: str
    resolution_date: str | None
    prefix: str
    from_number: int
    to_number: int
    valid_date_from: str | None
    valid_date_to: str | None
    technical_key: str | None


@dataclass
class NumberingRangeResponse:
    """Parsed DIAN numbering range lookup response."""

    ranges: list[NumberingRange] = field(default_factory=list)
    raw_xml: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ranges": [
                {
                    "resolution_number": item.resolution_number,
                    "resolution_date": item.resolution_date,
                    "prefix": item.prefix,
                    "from_number": item.from_number,
                    "to_number": item.to_number,
                    "valid_date_from": item.valid_date_from,
                    "valid_date_to": item.valid_date_to,
                    "technical_key": item.technical_key,
                }
                for item in self.ranges
            ],
            "raw_xml": self.raw_xml,
        }


def parse_send_bill_response(response_xml: bytes) -> DianResponse:
    """Parse the SOAP response from DIAN."""
    result = DianResponse(raw_xml=response_xml.decode("utf-8", errors="replace"))

    try:
        root = etree.fromstring(response_xml)
    except etree.XMLSyntaxError:
        result.status_message = "Failed to parse DIAN response XML"
        return result

    fault = root.find(f".//{{{NS_SOAP}}}Fault")
    if fault is not None:
        fault_reason = fault.find(f"{{{NS_SOAP}}}Reason/{{{NS_SOAP}}}Text")
        result.status_message = fault_reason.text if fault_reason is not None and fault_reason.text else "SOAP Fault"
        return result

    result_el = _find_result_element(root)
    if result_el is None:
        result.status_message = "No recognized result element in DIAN response"
        return result

    is_valid_text = _first_text_by_local_name(result_el, "IsValid")
    if is_valid_text is not None:
        result.is_valid = is_valid_text.lower() == "true"

    status_code = _first_text_by_local_name(result_el, "StatusCode")
    if status_code is not None:
        result.status_code = status_code

    status_description = _first_text_by_local_name(result_el, "StatusDescription")
    if status_description is not None:
        result.status_description = status_description

    status_message = _first_text_by_local_name(result_el, "StatusMessage")
    if status_message is not None:
        result.status_message = status_message

    result.error_messages = _collect_texts_from_containers(result_el, "ErrorMessage", "ErrorMessageList")

    tracking_id = _first_text_by_local_name(
        result_el,
        "ZipKey",
        "XmlDocumentKey",
        "TrackId",
        "TrackingId",
        "trackingId",
    )
    if tracking_id is not None:
        result.tracking_id = tracking_id

    xml_b64 = _first_text_by_local_name(result_el, "XmlBase64Bytes", "XmlBytes")
    if xml_b64 is not None:
        try:
            result.xml_bytes = base64.b64decode(xml_b64)
        except Exception:
            result.xml_bytes = None

    if result.tracking_id and not result.error_messages and not result.status_message:
        result.is_valid = True
        if not result.status_description:
            result.status_description = "Documento recibido por DIAN"
        result.status_message = "Documento enviado correctamente a DIAN"

    return result


def parse_get_acquirer_response(response_xml: bytes) -> AcquirerResponse:
    """Parse the SOAP response from DIAN GetAcquirer."""
    result = AcquirerResponse(raw_xml=response_xml.decode("utf-8", errors="replace"))

    try:
        root = etree.fromstring(response_xml)
    except etree.XMLSyntaxError:
        result.message = "Failed to parse DIAN response XML"
        return result

    fault = root.find(f".//{{{NS_SOAP}}}Fault")
    if fault is not None:
        fault_reason = fault.find(f"{{{NS_SOAP}}}Reason/{{{NS_SOAP}}}Text")
        result.message = fault_reason.text if fault_reason is not None and fault_reason.text else "SOAP Fault"
        return result

    result_el = _find_first_element_by_local_name(root, "GetAcquirerResult", "AdquirienteResponse")
    if result_el is None:
        result.message = "No recognized result element in DIAN response"
        return result

    status_code = _first_text_by_local_name(result_el, "StatusCode")
    if status_code is not None:
        result.status_code = status_code

    message = _first_text_by_local_name(result_el, "Message")
    if message is not None:
        result.message = message

    receiver_name = _first_text_by_local_name(result_el, "ReceiverName")
    if receiver_name is not None:
        result.receiver_name = receiver_name

    receiver_email = _first_text_by_local_name(result_el, "ReceiverEmail")
    if receiver_email is not None:
        result.receiver_email = receiver_email

    result.found = bool(result.receiver_name)
    if not result.message and result.found:
        result.message = "Adquiriente encontrado"

    return result


def parse_get_numbering_range_response(response_xml: bytes) -> NumberingRangeResponse:
    """Parse the SOAP response from DIAN GetNumberingRange."""
    result = NumberingRangeResponse(raw_xml=response_xml.decode("utf-8", errors="replace"))

    try:
        root = etree.fromstring(response_xml)
    except etree.XMLSyntaxError:
        return result

    for element in root.iterdescendants():
        if _local_name(element) != "NumberRangeResponse":
            continue

        resolution_number = _first_text_by_local_name(element, "ResolutionNumber") or ""
        prefix = _first_text_by_local_name(element, "Prefix") or ""
        from_number = int(_first_text_by_local_name(element, "FromNumber") or "0")
        to_number = int(_first_text_by_local_name(element, "ToNumber") or "0")

        result.ranges.append(NumberingRange(
            resolution_number=resolution_number,
            resolution_date=_first_text_by_local_name(element, "ResolutionDate"),
            prefix=prefix,
            from_number=from_number,
            to_number=to_number,
            valid_date_from=_first_text_by_local_name(element, "ValidDateFrom"),
            valid_date_to=_first_text_by_local_name(element, "ValidDateTo"),
            technical_key=_first_text_by_local_name(element, "TechnicalKey"),
        ))

    return result
