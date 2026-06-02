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


# --- Invoice line/total helpers -------------------------------------------------
# Compute invoice money in Decimal and return float for the Numeric columns. This
# removes binary-float drift from line totals/subtotals/discounts without forcing
# the ORM to return Decimal (which would break float arithmetic elsewhere).

def line_amount(quantity: object, price: object) -> float:
    """Rounded amount for a single line item (quantity * price)."""
    return round_money(_to_decimal(quantity) * _to_decimal(price))


def subtotal_from_items(items: Iterable) -> float:
    """Subtotal as the sum of per-line rounded amounts.

    ``items`` is an iterable of ``(quantity, price)`` pairs. Rounding each line
    before summing keeps the subtotal equal to the sum of the line amounts shown
    to the user.
    """
    return sum_money(line_amount(quantity, price) for quantity, price in items)


def compute_discount(subtotal: object, discount_type: Optional[str], discount_value: object) -> float:
    """Discount amount in cents, never exceeding the subtotal."""
    sub = _to_decimal(subtotal)
    value = _to_decimal(discount_value)
    if value <= 0:
        return 0.0
    if discount_type == "fixed":
        amount = value
    else:  # "percentage" (default)
        amount = sub * value / Decimal("100")
    amount = amount.quantize(_CENTS, rounding=ROUND_HALF_UP)
    if amount > sub:
        amount = sub.quantize(_CENTS, rounding=ROUND_HALF_UP)
    return float(amount)


def invoice_total(subtotal: object, discount_type: Optional[str], discount_value: object) -> float:
    """Invoice amount = subtotal - discount, floored at zero."""
    sub = _to_decimal(subtotal)
    discount = _to_decimal(compute_discount(subtotal, discount_type, discount_value))
    total = sub - discount
    if total < 0:
        total = Decimal("0")
    return float(total.quantize(_CENTS, rounding=ROUND_HALF_UP))
