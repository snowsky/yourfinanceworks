"""Decimal-based money helpers.

Money must not be accumulated with binary floats: summing many amounts drifts
(``0.1 + 0.2 == 0.30000000000000004``), and for rollups that drifted total is persisted
to ``Expense.amount``. These helpers accumulate in :class:`decimal.Decimal` and round to
cents (half-up), returning a plain ``float`` for the existing ``Float`` ORM columns.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

_CENTS = Decimal("0.01")


def _to_decimal(value: object) -> Decimal:
    # Go through str() so we capture the human-meaningful value ("4.5") rather than the
    # binary-float artifact, then leave rounding to the caller.
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def round_money(value: object) -> float:
    """Round a single amount to 2 decimal places (half-up). ``None`` -> ``0.0``."""
    return float(_to_decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP))


def sum_money(values: Iterable[Optional[float]]) -> float:
    """Sum amounts in Decimal and round the result to cents. Skips ``None`` entries."""
    total = sum((_to_decimal(v) for v in values if v is not None), Decimal("0"))
    return float(total.quantize(_CENTS, rounding=ROUND_HALF_UP))
