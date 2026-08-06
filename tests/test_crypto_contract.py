"""Contrato criptografico que la libreria `cryptography` debe cumplir.

`tests/test_signing.py` fija la ESTRUCTURA del documento firmado: donde vive la
firma, que referencias declara, que politica anuncia. Ninguno de esos asserts
comprueba que la firma sea criptograficamente VALIDA, ni que un certificado con
el empaquetado que emiten las autoridades de certificacion reales se pueda
abrir. Un cambio de version de `cryptography` puede romper justo eso sin mover
un solo assert de estructura, y el sintoma no aparece hasta que DIAN rechaza la
peticion en produccion.

Este modulo cubre ese hueco. Es la red que se corre ANTES y DESPUES de subir
`cryptography` (AGENTS.md seccion 4.1, que describe el procedimiento completo).

Tres capas, de la mas primitiva a la mas integrada:

1. El primitivo RSA: determinismo del relleno PKCS#1 v1.5, y que lo firmado se
   verifique contra la clave publica.
2. Carga de PKCS#12 con los cifrados que se encuentran en el mundo real,
   incluido el legado (PBESv1 + 3DES + MAC SHA-1) que todavia emiten muchas
   herramientas de exportacion. `test_signing.py` solo prueba el moderno.
3. Verificacion criptografica de la firma WS-Security del sobre SOAP: los
   digests de cada `ds:Reference` y el `ds:SignatureValue` contra la clave
   publica del certificado. Es lo que hace el receptor al otro lado.

Nada de material criptografico va escrito en el codigo: ni claves, ni firmas
esperadas, ni contrasenas. Todo se genera en tiempo de prueba. La comparacion
entre versiones de la libreria NO se hace fijando bytes aqui —eso obligaria a
versionar una clave privada en un repo publico— sino corriendo esta suite
completa contra la version vieja y la nueva y comparando el resultado, que es el
procedimiento que exige AGENTS.md 4.1.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from facturacion_dian_api.core.dian.envelope import build_send_test_set_async_envelope
from facturacion_dian_api.core.signing.certificate import CertificateBundle, load_certificate
from facturacion_dian_api.core.signing.ws_security import sign_soap_envelope
from lxml import etree

MESSAGE = b"facturacion-dian-api crypto contract"


def _self_signed(key: rsa.RSAPrivateKey) -> x509.Certificate:
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CO"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Issuer"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Crypto Contract Test"),
    ])
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(0x0C0FFEE)
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    """Clave RSA-2048 generada para la corrida. DIAN exige ese tamano."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def bundle(signing_key: rsa.RSAPrivateKey) -> CertificateBundle:
    return CertificateBundle(
        private_key=signing_key,
        certificate=_self_signed(signing_key),
        ca_chain=[],
    )


@pytest.fixture
def passphrase() -> str:
    """Contrasena distinta en cada prueba; nunca una constante en el codigo."""
    return secrets.token_hex(16)


# ═══════════════════════════════════════════════════════════════
# 1. El primitivo RSA
# ═══════════════════════════════════════════════════════════════


class TestRsaSigningPrimitive:
    """RSA-SHA256 con relleno PKCS#1 v1.5.

    Es el primitivo que usan las DOS firmas del servicio: XAdES sobre el
    documento UBL (via signxml) y WS-Security sobre el sobre SOAP (directo, en
    `ws_security.py`).
    """

    def test_key_is_2048_bits(self, signing_key: rsa.RSAPrivateKey) -> None:
        assert signing_key.key_size == 2048

    def test_pkcs1v15_signing_is_deterministic(self, signing_key: rsa.RSAPrivateKey) -> None:
        """PKCS#1 v1.5 no lleva aleatoriedad, a diferencia de PSS.

        De esto depende que dos corridas del mismo documento produzcan la misma
        firma, y es la propiedad que permite comparar el resultado de la suite
        entre dos versiones de la libreria.
        """
        first = signing_key.sign(MESSAGE, padding.PKCS1v15(), hashes.SHA256())
        second = signing_key.sign(MESSAGE, padding.PKCS1v15(), hashes.SHA256())
        assert first == second

    def test_signature_verifies_against_the_public_key(
        self, signing_key: rsa.RSAPrivateKey
    ) -> None:
        signature = signing_key.sign(MESSAGE, padding.PKCS1v15(), hashes.SHA256())
        signing_key.public_key().verify(
            signature, MESSAGE, padding.PKCS1v15(), hashes.SHA256()
        )

    def test_a_tampered_message_is_rejected(self, signing_key: rsa.RSAPrivateKey) -> None:
        # Control negativo: sin esto, un `verify` que nunca falle daria por
        # buena cualquier firma y la prueba de arriba no probaria nada.
        signature = signing_key.sign(MESSAGE, padding.PKCS1v15(), hashes.SHA256())
        with pytest.raises(InvalidSignature):
            signing_key.public_key().verify(
                signature, MESSAGE + b" ", padding.PKCS1v15(), hashes.SHA256()
            )


# ═══════════════════════════════════════════════════════════════
# 2. Carga de PKCS#12 tal como lo empaquetan las CA reales
# ═══════════════════════════════════════════════════════════════


ENCODINGS = [
    ("moderno-aes256-sha256", pkcs12.PBES.PBESv2SHA256AndAES256CBC, hashes.SHA256()),
    ("legado-3des-sha1", pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC, hashes.SHA1()),
]


class TestPkcs12Encodings:
    """El servicio abre UN `.p12` al arranque; si falla, no factura nadie.

    `test_signing.py` genera su certificado con `BestAvailableEncryption`, o
    sea el empaquetado moderno (PBESv2 + AES-256 + MAC SHA-256). Muchos
    certificados de firma digital reales llegan con el empaquetado LEGADO
    (PBESv1 + 3DES + MAC SHA-1), porque asi los exportan las herramientas con
    las que se emiten. `cryptography` viene restringiendo algoritmos antiguos
    version tras version, y si un dia deja de leer ese formato el servicio
    revienta al arrancar mientras la suite sigue en verde.

    Nota de alcance: aqui solo se puede probar lo que la propia libreria sabe
    ESCRIBIR. Un `.p12` cifrado con RC2-40, que alguna CA todavia emite, no se
    puede generar desde este test; ese caso hay que comprobarlo contra el
    certificado real antes de desplegar un bump.
    """

    def _write_p12(
        self,
        path: Path,
        key: rsa.RSAPrivateKey,
        cert: x509.Certificate,
        algorithm: pkcs12.PBES,
        mac: hashes.HashAlgorithm,
        passphrase: str,
    ) -> Path:
        encryption = (
            serialization.PrivateFormat.PKCS12.encryption_builder()
            .key_cert_algorithm(algorithm)
            .hmac_hash(mac)
            .build(passphrase.encode("utf-8"))
        )
        path.write_bytes(
            pkcs12.serialize_key_and_certificates(
                name=b"test",
                key=key,
                cert=cert,
                cas=None,
                encryption_algorithm=encryption,
            )
        )
        return path

    @pytest.mark.parametrize(("label", "algorithm", "mac"), ENCODINGS)
    def test_load_certificate_reads_the_encoding(
        self,
        tmp_path: Path,
        signing_key: rsa.RSAPrivateKey,
        bundle: CertificateBundle,
        passphrase: str,
        label: str,
        algorithm: pkcs12.PBES,
        mac: hashes.HashAlgorithm,
    ) -> None:
        path = self._write_p12(
            tmp_path / f"{label}.p12",
            signing_key,
            bundle.certificate,
            algorithm,
            mac,
            passphrase,
        )

        loaded = load_certificate(str(path), passphrase)

        assert loaded.is_valid
        assert loaded.certificate.serial_number == bundle.certificate.serial_number

    @pytest.mark.parametrize(("label", "algorithm", "mac"), ENCODINGS)
    def test_key_survives_the_round_trip_intact(
        self,
        tmp_path: Path,
        signing_key: rsa.RSAPrivateKey,
        bundle: CertificateBundle,
        passphrase: str,
        label: str,
        algorithm: pkcs12.PBES,
        mac: hashes.HashAlgorithm,
    ) -> None:
        """Abrir el `.p12` debe devolver la MISMA clave, no una equivalente.

        Se comprueba de dos formas: la firma que produce la clave recuperada es
        byte a byte la de la original, y verifica contra la clave publica del
        certificado. Si el empaquetado corrompiera la clave, DIAN rechazaria
        cada documento por firma invalida.
        """
        path = self._write_p12(
            tmp_path / f"{label}.p12",
            signing_key,
            bundle.certificate,
            algorithm,
            mac,
            passphrase,
        )

        loaded = load_certificate(str(path), passphrase)
        recovered = loaded.private_key.sign(MESSAGE, padding.PKCS1v15(), hashes.SHA256())

        assert recovered == signing_key.sign(MESSAGE, padding.PKCS1v15(), hashes.SHA256())
        bundle.certificate.public_key().verify(
            recovered, MESSAGE, padding.PKCS1v15(), hashes.SHA256()
        )

    def test_the_wrong_passphrase_is_rejected(
        self,
        tmp_path: Path,
        signing_key: rsa.RSAPrivateKey,
        bundle: CertificateBundle,
        passphrase: str,
    ) -> None:
        """Control negativo: el `.p12` esta realmente cifrado."""
        label, algorithm, mac = ENCODINGS[1]
        path = self._write_p12(
            tmp_path / f"{label}.p12",
            signing_key,
            bundle.certificate,
            algorithm,
            mac,
            passphrase,
        )

        with pytest.raises(ValueError, match="Failed to load"):
            load_certificate(str(path), secrets.token_hex(16))


# ═══════════════════════════════════════════════════════════════
# 3. La firma WS-Security del sobre SOAP es realmente verificable
# ═══════════════════════════════════════════════════════════════

NS = {
    "soap": "http://www.w3.org/2003/05/soap-envelope",
    "wsa": "http://www.w3.org/2005/08/addressing",
    "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
    "wsu": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}


def _c14n(element: etree._Element) -> bytes:
    return etree.tostring(element, method="c14n", exclusive=True)


def _sign_envelope(bundle: CertificateBundle) -> etree._Element:
    envelope = build_send_test_set_async_envelope(
        "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc",
        "ws_SETT000001.zip",
        "ZmFrZQ==",
        "test-set-id",
    )
    return etree.fromstring(sign_soap_envelope(envelope, bundle))


class TestWsSecuritySignatureIsVerifiable:
    """Rehace, del lado del receptor, la validacion que hace el WCF de DIAN.

    Las pruebas de `test_signing.py` comprueban el ORDEN de los elementos y las
    URIs de las referencias; ninguna recalcula un digest ni verifica la firma.
    Con solo esos asserts, `ws_security.py` podria estar firmando sobre bytes
    equivocados —o `cryptography` haber cambiado el relleno— y la suite seguiria
    verde mientras DIAN devuelve un fallo de autenticacion en cada envio.
    """

    def test_each_reference_digest_matches_its_element(
        self, bundle: CertificateBundle
    ) -> None:
        root = _sign_envelope(bundle)
        references = root.xpath(
            "soap:Header/wsse:Security/ds:Signature/ds:SignedInfo/ds:Reference",
            namespaces=NS,
        )
        assert len(references) == 2

        for reference in references:
            referenced_id = reference.get("URI", "")[1:]
            target = root.xpath(
                "//*[@wsu:Id=$wanted]", namespaces=NS, wanted=referenced_id
            )[0]
            expected = base64.b64encode(hashlib.sha256(_c14n(target)).digest())

            declared = reference.xpath("string(ds:DigestValue)", namespaces=NS)
            assert declared == expected.decode("ascii"), (
                f"el digest de {referenced_id} no corresponde a su elemento"
            )

    def test_signature_value_verifies_against_the_certificate(
        self, bundle: CertificateBundle
    ) -> None:
        root = _sign_envelope(bundle)
        signature = root.xpath(
            "soap:Header/wsse:Security/ds:Signature", namespaces=NS
        )[0]
        signed_info = signature.xpath("ds:SignedInfo", namespaces=NS)[0]
        signature_value = base64.b64decode(
            signature.xpath("string(ds:SignatureValue)", namespaces=NS)
        )

        # No lanza => la firma es valida sobre el SignedInfo canonicalizado.
        bundle.certificate.public_key().verify(
            signature_value,
            _c14n(signed_info),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_binary_security_token_carries_the_signing_certificate(
        self, bundle: CertificateBundle
    ) -> None:
        """El receptor valida con el certificado que va en el propio sobre."""
        root = _sign_envelope(bundle)
        token = root.xpath(
            "string(soap:Header/wsse:Security/wsse:BinarySecurityToken)",
            namespaces=NS,
        )
        assert base64.b64decode(token) == bundle.cert_der

    def test_a_tampered_timestamp_breaks_the_digest(
        self, bundle: CertificateBundle
    ) -> None:
        """Control negativo del test de digests.

        Si alterar el sobre firmado no rompiera nada, las comprobaciones de
        arriba no estarian comprobando nada.
        """
        root = _sign_envelope(bundle)
        created = root.xpath(
            "soap:Header/wsse:Security/wsu:Timestamp/wsu:Created", namespaces=NS
        )[0]
        created.text = "2000-01-01T00:00:00.000Z"

        timestamp = root.xpath(
            "soap:Header/wsse:Security/wsu:Timestamp", namespaces=NS
        )[0]
        declared = root.xpath(
            "string(soap:Header/wsse:Security/ds:Signature/ds:SignedInfo"
            "/ds:Reference[1]/ds:DigestValue)",
            namespaces=NS,
        )
        recomputed = base64.b64encode(hashlib.sha256(_c14n(timestamp)).digest())

        assert declared != recomputed.decode("ascii")

    def test_a_tampered_signature_value_fails_verification(
        self, bundle: CertificateBundle
    ) -> None:
        """Control negativo del test de firma."""
        root = _sign_envelope(bundle)
        signature = root.xpath(
            "soap:Header/wsse:Security/ds:Signature", namespaces=NS
        )[0]
        signed_info = signature.xpath("ds:SignedInfo", namespaces=NS)[0]
        signature_value = bytearray(
            base64.b64decode(signature.xpath("string(ds:SignatureValue)", namespaces=NS))
        )
        signature_value[-1] ^= 0xFF

        with pytest.raises(InvalidSignature):
            bundle.certificate.public_key().verify(
                bytes(signature_value),
                _c14n(signed_info),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
