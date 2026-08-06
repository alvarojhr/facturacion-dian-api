"""Contrato criptografico que la libreria `cryptography` debe cumplir.

`tests/test_signing.py` fija la ESTRUCTURA del documento firmado: donde vive la
firma, que referencias declara, que politica anuncia. Ninguno de esos asserts
comprueba que la firma sea criptograficamente VALIDA, ni que un certificado con
el empaquetado que emiten las autoridades de certificacion reales se pueda
abrir. Un cambio de version de `cryptography` puede romper justo eso sin mover
un solo assert de estructura, y el sintoma no aparece hasta que DIAN rechaza la
peticion en produccion.

Este modulo cubre ese hueco. Es la red que se corre ANTES y DESPUES de subir
`cryptography` (AGENTS.md seccion 4: firma y XML son fragiles a proposito).

Tres capas, de la mas primitiva a la mas integrada:

1. Known-answer test del primitivo RSA. PKCS#1 v1.5 es determinista: una clave
   fija y un mensaje fijo producen SIEMPRE los mismos bytes. Si esta prueba
   cambia de resultado entre dos versiones, la libreria cambio como firma.
2. Carga de PKCS#12 con los cifrados que se encuentran en el mundo real,
   incluido el legado (PBESv1 + 3DES + MAC SHA-1) que todavia emiten muchas
   herramientas de exportacion. `test_signing.py` solo prueba el moderno.
3. Verificacion criptografica de la firma WS-Security del sobre SOAP: los
   digests de cada `ds:Reference` y el `ds:SignatureValue` contra la clave
   publica del certificado. Es lo que hace el receptor al otro lado.

La clave RSA de este modulo se construye a partir de primos fijos escritos en el
codigo, no de un PEM: es material de juguete, generado para estas pruebas, y en
forma de enteros no se confunde con una credencial real.
"""

from __future__ import annotations

import base64
import hashlib
import math
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

# ─── Clave RSA-2048 fija (material de prueba) ──────────────────

_KAT_P = int(
    "1532876844902425591892430798844729389985260983382529457337258291439974903209"
    "9691307468706002136195933043560355470755976534854057530296428133250488094691"
    "6313359129600042780979575501414316359317714596107823283587492456309223997601"
    "0080176623268219647120036306731630247820240342183451300454906452642903121165"
    "16259"
)
_KAT_Q = int(
    "1524391144608290311697620790484559572443934477210861308898902353987769745971"
    "5084549247502767723991512626967329938327700173751771088380295617820886993501"
    "0599011918906909184669906550185403367421475259251377589677000724777938611665"
    "8203440136061851416518687730443598360793192010777692858472064840664951256027"
    "33671"
)
_KAT_E = 65537

# Mensaje y firma fijados. RSA PKCS#1 v1.5 no lleva aleatoriedad: el resultado
# es una funcion pura de (clave, mensaje). Si este base64 deja de coincidir, la
# libreria cambio el algoritmo de firma y ningun documento nuestro seria
# verificable por DIAN con el mismo certificado.
_KAT_MESSAGE = b"facturacion-dian-api RSA-SHA256 known-answer vector"
_KAT_SIGNATURE_B64 = (
    "AA8FfBylfGkQFu0Bc7hgKKDlSXbC5CtS17dNb1x1QwVWqJi6SJKYZC79ySh8TjHPfxc7KNOMEFUb"
    "/lbZoXxfAei1RUu+G+rrygjDse4+biVpge6BFfOVg0fIfcMeUB8/z+omhBstenfY4KCjKCPqpG6h"
    "Xm/xnfS79hOwhq1e0MPbRBnK88EzRvjkOnjJuTFk6WrDZEvdrS513PtkkmelkO+ID91cGGitzHgT"
    "ct7emjaQMkZIlJBnyvfj9tjnfej5FsaQvtkFO0e+SO7RwRHGPsfw33wUxh6jVCI5NxSUYas0+0MS"
    "fM1rOIA81DshtkeFF6KXgAnXU9k3lwrHG0C22A=="
)

CERT_PASSWORD = "test123"


def _fixed_private_key() -> rsa.RSAPrivateKey:
    """Reconstruye la clave de prueba desde sus primos."""
    p, q, e = _KAT_P, _KAT_Q, _KAT_E
    lam = (p - 1) * (q - 1) // math.gcd(p - 1, q - 1)
    d = pow(e, -1, lam)
    return rsa.RSAPrivateNumbers(
        p=p,
        q=q,
        d=d,
        dmp1=rsa.rsa_crt_dmp1(d, p),
        dmq1=rsa.rsa_crt_dmq1(d, q),
        iqmp=rsa.rsa_crt_iqmp(p, q),
        public_numbers=rsa.RSAPublicNumbers(e=e, n=p * q),
    ).private_key()


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
def fixed_key() -> rsa.RSAPrivateKey:
    return _fixed_private_key()


@pytest.fixture(scope="module")
def bundle(fixed_key: rsa.RSAPrivateKey) -> CertificateBundle:
    return CertificateBundle(
        private_key=fixed_key,
        certificate=_self_signed(fixed_key),
        ca_chain=[],
    )


# ═══════════════════════════════════════════════════════════════
# 1. Known-answer test del primitivo RSA
# ═══════════════════════════════════════════════════════════════


class TestRsaKnownAnswer:
    """Fija los bytes exactos que produce RSA-SHA256 con relleno PKCS#1 v1.5.

    Es el primitivo que usan las DOS firmas del servicio: XAdES sobre el
    documento UBL (via signxml) y WS-Security sobre el sobre SOAP (directo, en
    `ws_security.py`).
    """

    def test_signature_matches_the_pinned_vector(self, fixed_key: rsa.RSAPrivateKey) -> None:
        signature = fixed_key.sign(_KAT_MESSAGE, padding.PKCS1v15(), hashes.SHA256())
        assert base64.b64encode(signature).decode("ascii") == _KAT_SIGNATURE_B64

    def test_key_reconstructed_from_primes_is_2048_bits(
        self, fixed_key: rsa.RSAPrivateKey
    ) -> None:
        # DIAN exige claves RSA de 2048 bits; si la reconstruccion cambiara de
        # tamano el vector de arriba dejaria de significar lo que dice.
        assert fixed_key.key_size == 2048

    def test_pinned_vector_verifies_against_the_public_key(
        self, fixed_key: rsa.RSAPrivateKey
    ) -> None:
        fixed_key.public_key().verify(
            base64.b64decode(_KAT_SIGNATURE_B64),
            _KAT_MESSAGE,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_a_tampered_message_is_rejected(self, fixed_key: rsa.RSAPrivateKey) -> None:
        # Control negativo: sin esto, un `verify` que nunca falle daria por
        # buena cualquier firma y las pruebas de arriba no probarian nada.
        with pytest.raises(InvalidSignature):
            fixed_key.public_key().verify(
                base64.b64decode(_KAT_SIGNATURE_B64),
                _KAT_MESSAGE + b" ",
                padding.PKCS1v15(),
                hashes.SHA256(),
            )


# ═══════════════════════════════════════════════════════════════
# 2. Carga de PKCS#12 tal como lo empaquetan las CA reales
# ═══════════════════════════════════════════════════════════════


def _encryption(algorithm: pkcs12.PBES, mac: hashes.HashAlgorithm):  # type: ignore[no-untyped-def]
    return (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .key_cert_algorithm(algorithm)
        .hmac_hash(mac)
        .build(CERT_PASSWORD.encode("utf-8"))
    )


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

    @pytest.fixture
    def _cert(self, fixed_key: rsa.RSAPrivateKey) -> x509.Certificate:
        return _self_signed(fixed_key)

    def _write(
        self,
        path: Path,
        key: rsa.RSAPrivateKey,
        cert: x509.Certificate,
        encryption,  # type: ignore[no-untyped-def]
    ) -> Path:
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

    @pytest.mark.parametrize(
        ("label", "algorithm", "mac"),
        [
            ("moderno-aes256-sha256", pkcs12.PBES.PBESv2SHA256AndAES256CBC, hashes.SHA256()),
            ("legado-3des-sha1", pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC, hashes.SHA1()),
        ],
    )
    def test_load_certificate_reads_the_encoding(
        self,
        tmp_path: Path,
        fixed_key: rsa.RSAPrivateKey,
        _cert: x509.Certificate,
        label: str,
        algorithm: pkcs12.PBES,
        mac: hashes.HashAlgorithm,
    ) -> None:
        path = self._write(
            tmp_path / f"{label}.p12", fixed_key, _cert, _encryption(algorithm, mac)
        )

        loaded = load_certificate(str(path), CERT_PASSWORD)

        assert loaded.is_valid
        assert loaded.certificate.serial_number == _cert.serial_number

    @pytest.mark.parametrize(
        ("label", "algorithm", "mac"),
        [
            ("moderno-aes256-sha256", pkcs12.PBES.PBESv2SHA256AndAES256CBC, hashes.SHA256()),
            ("legado-3des-sha1", pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC, hashes.SHA1()),
        ],
    )
    def test_key_survives_the_round_trip_intact(
        self,
        tmp_path: Path,
        fixed_key: rsa.RSAPrivateKey,
        _cert: x509.Certificate,
        label: str,
        algorithm: pkcs12.PBES,
        mac: hashes.HashAlgorithm,
    ) -> None:
        """Abrir el `.p12` debe devolver la MISMA clave, no una equivalente.

        Se comprueba contra el vector fijado: si la clave sobrevive el
        empaquetado, firma exactamente los mismos bytes.
        """
        path = self._write(
            tmp_path / f"{label}.p12", fixed_key, _cert, _encryption(algorithm, mac)
        )

        loaded = load_certificate(str(path), CERT_PASSWORD)
        signature = loaded.private_key.sign(
            _KAT_MESSAGE, padding.PKCS1v15(), hashes.SHA256()
        )

        assert base64.b64encode(signature).decode("ascii") == _KAT_SIGNATURE_B64


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
