#!/usr/bin/env python3
"""Offline AE28 evidence using installed wheels, ephemeral keys and public HTTP routes.

This diagnoses an unresolved container policy; it does not certify DIAN compliance.
No private key is exported. Run with Python -I from the wheel QA virtual environment.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata as metadata
import ipaddress
import json
import os
import socket
import sys
from contextlib import ExitStack
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fe-xsd-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    xsd_dir = args.fe_xsd_dir.resolve()
    if output.exists():
        parser.error("Use a new output directory; previous evidence is never overwritten")
    if not (xsd_dir / "UBL-AttachedDocument-2.1.xsd").is_file():
        parser.error("Official FE XSD directory is required")

    def guard(original):
        def connect(sock, address):
            if not isinstance(address, tuple) or not ipaddress.ip_address(address[0]).is_loopback:
                raise AssertionError("External network forbidden in AE28 reproduction")
            return original(sock, address)
        return connect

    # Isolate configuration before importing the application: no working .env or
    # inherited fiscal settings, certificates or production identities are used.
    previous_cwd = Path.cwd()
    with TemporaryDirectory(prefix="ae28-offline-") as isolated, ExitStack() as stack:
        stack.callback(os.chdir, previous_cwd)
        os.chdir(isolated)
        safe_env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("DIAN_", "COMPANY_", "API_", "SERVER_"))}
        safe_env.update(DIAN_ENVIRONMENT="habilitacion", DIAN_SOFTWARE_ID="offline-software",
                        DIAN_SOFTWARE_PIN="offline-pin", DIAN_TECHNICAL_KEY="offline-key",
                        DIAN_TEST_SET_ID="offline-test-set", PYTHONDONTWRITEBYTECODE="1")
        stack.enter_context(patch.dict(os.environ, safe_env, clear=True))
        stack.enter_context(patch.object(socket.socket, "connect", guard(socket.socket.connect)))
        stack.enter_context(patch.object(socket.socket, "connect_ex", guard(socket.socket.connect_ex)))
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        from facturacion_dian_api.core import models
        from facturacion_dian_api.core.dian.client import DianClient
        from facturacion_dian_api.core.dian.response_parser import DianResponse
        from facturacion_dian_api.core.signing.certificate import CertificateBundle
        from facturacion_dian_api.core.signing.xades import (
            sign_document,
            verify_embedded_document_signature,
        )
        from facturacion_dian_api.core.xml.namespaces import NSMAP_APPLICATION_RESPONSE
        from facturacion_dian_api.server import contracts
        from facturacion_dian_api.server.app import app
        from facturacion_dian_api.server.examples import (
            ATTACHED_DOCUMENT_REQUEST_EXAMPLE,
            DIAN_AR_XML_BASE64,
            DOCUMENT_SUBMISSION_INVOICE_EXAMPLE,
        )
        from fastapi.testclient import TestClient
        from lxml import etree

        modules = {"core": str(Path(models.__file__).resolve()),
                   "server": str(Path(contracts.__file__).resolve())}
        if not all(Path(p).is_relative_to(Path(sys.prefix)) for p in modules.values()):
            raise RuntimeError("Run with installed wheels and Python -I, not an editable checkout")
        versions = {}
        for name in modules:
            dist = metadata.distribution("facturacion-dian-api-" + name)
            if json.loads(dist.read_text("direct_url.json") or "{}").get("dir_info", {}).get("editable"):
                raise RuntimeError("Editable packages are not suitable evidence")
            versions[name] = dist.version
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AE28 SYNTHETIC OFFLINE")])
        now = datetime.now(UTC)
        issue_date = now.astimezone(timezone(timedelta(hours=-5))).date()
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(key.public_key()).serial_number(282026)
                .not_valid_before(now - timedelta(minutes=1))
                .not_valid_after(now + timedelta(days=1)).sign(key, hashes.SHA256()))
        bundle = CertificateBundle(key, cert, [])
        stack.enter_context(patch("facturacion_dian_api.core.submission.get_certificate_bundle",
                                 return_value=bundle))
        client = stack.enter_context(TestClient(app))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        ext = "{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}"

        def validate(raw):
            root = etree.fromstring(raw)
            name = etree.QName(root).localname
            etree.XMLSchema(etree.parse(str(xsd_dir / f"UBL-{name}-2.1.xsd"))).assertValid(root)
            verify_embedded_document_signature(root)
            return root

        output.mkdir(parents=True)
        cases = []
        known_container = None
        for label, responsibility in (("unknown", None), ("known", "O-13;O-15")):
            folder = output / label
            folder.mkdir()
            payload = deepcopy(DOCUMENT_SUBMISSION_INVOICE_EXAMPLE)
            payload["buyer"] = {"document_type": "CC", "document_number": "123456789",
                                "name": "COMPRADOR SINTETICO AE28", "additional_account_id": "2"}
            if responsibility:
                payload["buyer"]["tax_level_code"] = responsibility
            payload["document"]["issue_date"] = issue_date.isoformat()
            payload["resolution"].update(valid_from=f"{issue_date.year}-01-01", valid_to=f"{issue_date.year + 1}-12-31")
            payload["submission_options"]["prepare_only"] = True
            prepared = client.post("/api/v1/documents/submissions", json=payload)
            assert prepared.status_code == 200, prepared.text
            doc = prepared.json()
            invoice = base64.b64decode(doc["artifacts"]["xml_base64"])
            root = validate(invoice)
            levels = root.xpath("cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode/text()", namespaces=ns)
            assert levels == ([responsibility] if responsibility else [])

            template = etree.fromstring(base64.b64decode(DIAN_AR_XML_BASE64), etree.XMLParser(remove_blank_text=True))
            ar = etree.Element(template.tag, nsmap=NSMAP_APPLICATION_RESPONSE)
            ar.extend(template)
            for sig in ar.xpath("//*[local-name()='Signature']"):
                sig.getparent().remove(sig)
            extensions = etree.Element(ext + "UBLExtensions")
            etree.SubElement(etree.SubElement(extensions, ext + "UBLExtension"), ext + "ExtensionContent")
            ar.insert(0, extensions)
            ar.find("{" + ns["cbc"] + "}ID").text = "AR-SYNTHETIC-NOT-DIAN"
            ar.find("{" + ns["cbc"] + "}IssueDate").text = payload["document"]["issue_date"]
            index = next(i for i, n in enumerate(ar) if etree.QName(n).localname == "DocumentResponse")
            for offset, (role, identifier) in enumerate((("SenderParty", "800197268"), ("ReceiverParty", "900123456"))):
                party = etree.Element("{" + ns["cac"] + "}" + role)
                ident = etree.SubElement(party, "{" + ns["cac"] + "}PartyIdentification")
                etree.SubElement(ident, "{" + ns["cbc"] + "}ID").text = identifier
                ar.insert(index + offset, party)
            ar.xpath("//cac:DocumentReference/cbc:UUID", namespaces=ns)[0].text = doc["document_key"]
            ar_bytes = etree.tostring(sign_document(ar, bundle), encoding="UTF-8", xml_declaration=True)
            validate(ar_bytes)
            sent = []

            async def accepted(self, filename, content_b64, test_set_id=None):
                del self, filename, test_set_id
                with ZipFile(BytesIO(base64.b64decode(content_b64))) as archive:
                    assert len(archive.namelist()) == 1
                    name = archive.namelist()[0]
                    sent.append((name, archive.read(name)))
                return DianResponse(is_valid=True, validation_result_present=True, status_code="00",
                                    status_description="SYNTHETIC OFFLINE ACCEPTANCE", xml_bytes=ar_bytes)

            retry = deepcopy(payload)
            retry["submission_options"].update(prepare_only=False,
                signed_xml_base64=doc["artifacts"]["xml_base64"],
                signed_xml_filename=doc["artifacts"]["xml_filename"])
            with patch.object(DianClient, "send_bill_sync", accepted), patch.object(DianClient, "send_test_set_async", accepted), patch(
                "facturacion_dian_api.core.submission.sign_document_xml", side_effect=AssertionError("Retry re-signed original")), patch(
                "facturacion_dian_api.core.submission._build_document_xml", side_effect=AssertionError("Retry rebuilt original")):
                result = client.post("/api/v1/documents/submissions", json=retry)
            assert result.status_code == 200 and result.json()["status"] == "accepted", (
                result.status_code, result.json().get("status"), result.json().get("detail"))
            assert sent == [(doc["artifacts"]["xml_filename"], invoice)]
            assert result.json()["artifacts"]["xml_base64"] == doc["artifacts"]["xml_base64"]

            attached = deepcopy(ATTACHED_DOCUMENT_REQUEST_EXAMPLE)
            attached.update(receiver_name=payload["buyer"]["name"], receiver_nit="123456789",
                            receiver_dv=None, receiver_document_type="13", cufe=doc["document_key"],
                            issue_date=payload["document"]["issue_date"],
                            invoice_xml_base64=doc["artifacts"]["xml_base64"],
                            application_response_xml_base64=base64.b64encode(ar_bytes).decode())
            attached.pop("receiver_tax_level_code")
            response = client.post("/api/v1/attached-documents", json=attached)
            entry = {"case": label, "prepare_http": 200, "invoice_signature_and_xsd": True,
                     "synthetic_ar_signature_and_xsd": True, "acceptance": "SIMULATED_ONLY",
                     "retry_preserved_original_bytes": True, "attached_http": response.status_code}
            if responsibility is None:
                assert response.status_code == 422, response.text
                assert "ATTACHED_DOCUMENT_BUYER_RESPONSIBILITY_UNRESOLVED" in response.json()["detail"]
                assert "content_base64" not in response.json()
                entry["error_origin"] = "LOCAL_IMPLEMENTATION_NOT_DIAN"
            else:
                assert response.status_code == 200, response.text
                zip_bytes = base64.b64decode(response.json()["content_base64"])
                with ZipFile(BytesIO(zip_bytes)) as archive:
                    assert archive.namelist() == [response.json()["xml_filename"]]
                    container_bytes = archive.read(archive.namelist()[0])
                known_container = validate(container_bytes)
                embedded = known_container.xpath("//cac:ExternalReference/cbc:Description/text()", namespaces=ns)
                assert [part.encode() for part in embedded] == [invoice, ar_bytes]
                assert known_container.xpath("cac:ReceiverParty/cac:PartyTaxScheme/cbc:TaxLevelCode/text()", namespaces=ns) == [responsibility]
                (folder / "container.xml").write_bytes(container_bytes)
                (folder / "delivery-synthetic.zip").write_bytes(zip_bytes)
                entry.update(container_signature_and_xsd=True, embedded_bytes_preserved=True)
            (folder / "invoice-synthetic.xml").write_bytes(invoice)
            (folder / "application-response-SYNTHETIC-NOT-DIAN.xml").write_bytes(ar_bytes)
            (folder / "prepare-request.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            (folder / "attached-request.json").write_text(json.dumps(attached, indent=2) + "\n", encoding="utf-8")
            (folder / "attached-response.json").write_text(json.dumps(response.json(), indent=2) + "\n", encoding="utf-8")
            cases.append(entry)

        # Deliberately invalid fiscal examples, in memory only. Remove the outer
        # signature: editing it invalidates its signature. XSD alone cannot assess
        # the DIAN cardinality/catalogue rule or authorize an unknown-value policy.
        assert known_container is not None
        schema = etree.XMLSchema(etree.parse(str(xsd_dir / "UBL-AttachedDocument-2.1.xsd")))
        probes = []
        for label, value in (("omitted", None), ("empty", ""), ("R-99-PN", "R-99-PN"),
                             ("invalid_catalogue_value", "NOT-A-DIAN-CODE")):
            candidate = deepcopy(known_container)
            for extensions in candidate.findall(ext + "UBLExtensions"):
                candidate.remove(extensions)
            node = candidate.xpath("cac:ReceiverParty/cac:PartyTaxScheme/cbc:TaxLevelCode", namespaces=ns)[0]
            if value is None:
                node.getparent().remove(node)
            else:
                node.text = value
            probes.append({"variant": label, "generic_ubl_xsd_valid": schema.validate(candidate),
                           "dian_compliance_proven": False, "deliverable": False})
        files = {str(p.relative_to(output)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(output.rglob("*")) if p.is_file()}
        report = {"generated_at": now.isoformat(), "versions": versions, "modules": modules,
                  "external_connections_blocked": True, "private_keys_exported": False,
                  "synthetic_only": True, "cases": cases, "schema_only_probes": probes,
                  "sha256": files}
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output), "versions": versions, "cases": cases,
                          "schema_only_probes": probes}, indent=2))


if __name__ == "__main__":
    main()
