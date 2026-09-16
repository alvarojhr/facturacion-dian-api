"""COP comparison policy: FEV 1.9 §5.2.1 and DEE 1.0 pp.19-20.

Comparisons never replace the caller's amounts. Documentary sums remain exact.
The general 2 COP allowance and IVA nearest-ten allowance are alternatives,
never cumulative. Zero/excluded taxes and non-IVA retain exact validation.
"""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

CENT = Decimal("0.01")
MONETARY_TOLERANCE = Decimal("2.00")
IVA_TOLERANCE = Decimal("5.00")
IVA_TYPES = frozenset({"IVA_19", "IVA_5", "IVA_0", "EXEMPT"})


def money(value: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 50
        return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def percentage_amount(base: Decimal, percent: Decimal) -> Decimal:
    """Unrounded result, so aggregation does not accumulate rounding of expectations."""
    with localcontext() as ctx:
        ctx.prec = 50
        return base * percent / Decimal("100")


def validate_calculated_amount(
    actual: Decimal, expected: Decimal, *, label: str, iva: bool = False,
) -> None:
    expected = money(expected)
    delta = abs(actual - expected)
    if delta <= MONETARY_TOLERANCE:
        return
    # A multiple of ten within five COP is a nearest multiple. At an exact tie
    # either adjacent multiple is equally near; use the annex's half-even rule.
    nearest_ten = expected.quantize(Decimal("1E1"), rounding=ROUND_HALF_EVEN)
    if iva and delta <= IVA_TOLERANCE and actual == nearest_ten:
        return
    suffix = "; IVA also permits its nearest multiple of ten within 5.00 COP" if iva else ""
    raise ValueError(
        f"{label} differs from calculation ({expected}) by {actual - expected} COP; "
        f"maximum monetary tolerance is 2.00 COP{suffix}"
    )
