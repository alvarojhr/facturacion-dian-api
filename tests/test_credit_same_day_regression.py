"""Regresión compartida con la recuperación de facturas del ERP del 2026-09-15."""

import pytest
from facturacion_dian_api.core.payments import PaymentDetails


def test_credit_recovery_preserves_same_day_due_date() -> None:
    terms = PaymentDetails(
        payment_method="CREDIT", payment_form="CREDITO", payment_due_date="2026-09-15"
    )
    terms.validate_payment_context("2026-09-15", "FACTURA_ELECTRONICA")
    assert terms.payment_due_date == "2026-09-15"
    assert terms.payment_form == "CREDITO"


def test_credit_recovery_rejects_due_date_before_issue_date() -> None:
    terms = PaymentDetails(
        payment_method="CREDIT", payment_form="CREDITO", payment_due_date="2026-09-14"
    )
    with pytest.raises(ValueError, match="cannot be before issue_date"):
        terms.validate_payment_context("2026-09-15", "FACTURA_ELECTRONICA")
