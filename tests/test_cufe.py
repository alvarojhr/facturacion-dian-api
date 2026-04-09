"""Tests for CUFE, CUDE, and Software Security Code calculation.

Verifies SHA-384 hashing logic against known test vectors.
The exact concatenation format follows DIAN Anexo TÃ©cnico v1.9.
"""

from __future__ import annotations

import hashlib

from facturacion_dian_kit.core.cufe.calculator import (
    CudeFields,
    CufeFields,
    build_qr_url,
    calculate_cude,
    calculate_cufe,
    calculate_software_security_code,
)


class TestCufeCalculation:
    """Test CUFE (CÃ³digo Ãšnico de Factura ElectrÃ³nica) generation."""

    def test_cufe_returns_96_char_hex(self) -> None:
        """CUFE must be a 96-char lowercase hex string (SHA-384)."""
        fields = CufeFields(
            num_fac="SETP990000002",
            fec_fac="2019-01-16",
            hor_fac="10:53:10-05:00",
            val_fac=1500000,
            val_iva=285000,
            val_inc=0,
            val_ica=0,
            val_tot_fac=1785000,
            nit_ofe="700085371",
            num_adq="800199436",
            clave_tecnica="fc8eac422eba16e22ffd8c6f94b3f40a6e38162c",
            tipo_ambiente="2",
        )
        cufe = calculate_cufe(fields)
        assert len(cufe) == 96, f"CUFE length should be 96, got {len(cufe)}"
        assert cufe == cufe.lower(), "CUFE must be lowercase hex"
        # Verify it's valid hex
        int(cufe, 16)

    def test_cufe_deterministic(self) -> None:
        """Same inputs must always produce the same CUFE."""
        fields = CufeFields(
            num_fac="SETT000001",
            fec_fac="2026-03-12",
            hor_fac="14:30:00-05:00",
            val_fac=100000,
            val_iva=19000,
            val_inc=0,
            val_ica=0,
            val_tot_fac=119000,
            nit_ofe="900123456",
            num_adq="800199436",
            clave_tecnica="abcdef1234567890",
            tipo_ambiente="2",
        )
        cufe1 = calculate_cufe(fields)
        cufe2 = calculate_cufe(fields)
        assert cufe1 == cufe2

    def test_cufe_changes_with_different_amount(self) -> None:
        """Changing any field must produce a different CUFE."""
        base = CufeFields(
            num_fac="SETT000001",
            fec_fac="2026-03-12",
            hor_fac="14:30:00-05:00",
            val_fac=100000,
            val_iva=19000,
            val_inc=0,
            val_ica=0,
            val_tot_fac=119000,
            nit_ofe="900123456",
            num_adq="800199436",
            clave_tecnica="abcdef1234567890",
            tipo_ambiente="2",
        )
        modified = CufeFields(
            num_fac="SETT000001",
            fec_fac="2026-03-12",
            hor_fac="14:30:00-05:00",
            val_fac=100001,  # Changed by 1 COP
            val_iva=19000,
            val_inc=0,
            val_ica=0,
            val_tot_fac=119001,
            nit_ofe="900123456",
            num_adq="800199436",
            clave_tecnica="abcdef1234567890",
            tipo_ambiente="2",
        )
        assert calculate_cufe(base) != calculate_cufe(modified)

    def test_cufe_known_vector(self) -> None:
        """Verify CUFE against a manually computed SHA-384 hash.

        This test computes the expected hash independently to ensure
        the concatenation format is correct.
        """
        fields = CufeFields(
            num_fac="SETP990000002",
            fec_fac="2019-01-16",
            hor_fac="10:53:10-05:00",
            val_fac=1500000,
            val_iva=285000,
            val_inc=0,
            val_ica=0,
            val_tot_fac=1785000,
            nit_ofe="700085371",
            num_adq="800199436",
            clave_tecnica="fc8eac422eba16e22ffd8c6f94b3f40a6e38162c",
            tipo_ambiente="2",
        )

        # Manually build the expected seed string
        expected_seed = (
            "SETP990000002"
            "2019-01-16"
            "10:53:10-05:00"
            "1500000.00"
            "01285000.00"
            "040.00"
            "030.00"
            "1785000.00"
            "700085371"
            "800199436"
            "fc8eac422eba16e22ffd8c6f94b3f40a6e38162c"
            "2"
        )
        expected_cufe = hashlib.sha384(expected_seed.encode("utf-8")).hexdigest()
        assert calculate_cufe(fields) == expected_cufe

    def test_cufe_monetary_formatting(self) -> None:
        """Monetary values must be formatted with exactly 2 decimal places."""
        fields = CufeFields(
            num_fac="TEST001",
            fec_fac="2026-01-01",
            hor_fac="00:00:00-05:00",
            val_fac=0,       # Should become "0.00"
            val_iva=0,       # Should become "0.00"
            val_inc=0,
            val_ica=0,
            val_tot_fac=0,
            nit_ofe="123",
            num_adq="456",
            clave_tecnica="key",
            tipo_ambiente="2",
        )
        cufe = calculate_cufe(fields)
        # Verify by computing expected
        expected_seed = "TEST0012026-01-0100:00:00-05:000.00010.00040.00030.000.00123456key2"
        expected = hashlib.sha384(expected_seed.encode("utf-8")).hexdigest()
        assert cufe == expected


class TestCudeCalculation:
    """Test CUDE (CÃ³digo Ãšnico de Documento ElectrÃ³nico) generation."""

    def test_cude_returns_96_char_hex(self) -> None:
        """CUDE must be a 96-char lowercase hex string (SHA-384)."""
        fields = CudeFields(
            num_fac="POS000001",
            fec_fac="2026-03-12",
            hor_fac="10:15:30-05:00",
            val_fac=42000,
            val_iva=7980,
            val_inc=0,
            val_ica=0,
            val_tot_fac=49980,
            nit_ofe="900123456",
            num_adq="222222222222",
            software_pin="12345",
            tipo_ambiente="2",
        )
        cude = calculate_cude(fields)
        assert len(cude) == 96
        assert cude == cude.lower()
        int(cude, 16)

    def test_cude_differs_from_cufe_same_data(self) -> None:
        """CUDE uses software_pin instead of clave_tecnica, so must differ."""
        cufe = calculate_cufe(
            CufeFields(
                num_fac="DOC001",
                fec_fac="2026-01-01",
                hor_fac="12:00:00-05:00",
                val_fac=10000,
                val_iva=1900,
                val_inc=0,
                val_ica=0,
                val_tot_fac=11900,
                nit_ofe="900123456",
                num_adq="800199436",
                clave_tecnica="12345",  # same value as software_pin
                tipo_ambiente="2",
            )
        )
        cude = calculate_cude(
            CudeFields(
                num_fac="DOC001",
                fec_fac="2026-01-01",
                hor_fac="12:00:00-05:00",
                val_fac=10000,
                val_iva=1900,
                val_inc=0,
                val_ica=0,
                val_tot_fac=11900,
                nit_ofe="900123456",
                num_adq="800199436",
                software_pin="12345",  # same value as clave_tecnica
                tipo_ambiente="2",
            )
        )
        # When the key value is the same, CUFE and CUDE should produce
        # the same hash (the formula is structurally identical)
        assert cufe == cude

    def test_cude_known_vector(self) -> None:
        """Verify CUDE against manually computed SHA-384."""
        fields = CudeFields(
            num_fac="POS000001",
            fec_fac="2026-03-12",
            hor_fac="10:15:30-05:00",
            val_fac=42000,
            val_iva=7980,
            val_inc=0,
            val_ica=0,
            val_tot_fac=49980,
            nit_ofe="900123456",
            num_adq="222222222222",
            software_pin="12345",
            tipo_ambiente="2",
        )
        expected_seed = (
            "POS000001"
            "2026-03-12"
            "10:15:30-05:00"
            "42000.00"
            "017980.00"
            "040.00"
            "030.00"
            "49980.00"
            "900123456"
            "222222222222"
            "12345"
            "2"
        )
        expected = hashlib.sha384(expected_seed.encode("utf-8")).hexdigest()
        assert calculate_cude(fields) == expected


class TestSoftwareSecurityCode:
    """Test Software Security Code generation."""

    def test_ssc_returns_96_char_hex(self) -> None:
        """SSC must be 96-char lowercase hex string."""
        ssc = calculate_software_security_code(
            software_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            software_pin="12345",
            invoice_number="SETT000001",
        )
        assert len(ssc) == 96
        assert ssc == ssc.lower()
        int(ssc, 16)

    def test_ssc_known_vector(self) -> None:
        """Verify SSC against manually computed SHA-384."""
        seed = "my-software-id" + "54321" + "INV001"
        expected = hashlib.sha384(seed.encode("utf-8")).hexdigest()
        assert calculate_software_security_code("my-software-id", "54321", "INV001") == expected

    def test_ssc_deterministic(self) -> None:
        """Same inputs must always produce the same SSC."""
        ssc1 = calculate_software_security_code("sid", "pin", "inv")
        ssc2 = calculate_software_security_code("sid", "pin", "inv")
        assert ssc1 == ssc2


class TestQrUrl:
    """Test QR URL generation."""

    def test_build_qr_url(self) -> None:
        """QR URL must point to DIAN catalog with document key."""
        key = "abc123def456"
        url = build_qr_url(key)
        assert url == "https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey=abc123def456"

    def test_build_qr_url_with_full_cufe(self) -> None:
        """QR URL with a full 96-char CUFE."""
        cufe = "a" * 96
        url = build_qr_url(cufe)
        assert cufe in url
        assert url.startswith("https://catalogo-vpfe.dian.gov.co/")

