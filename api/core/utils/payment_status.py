"""Pure helpers for deriving an invoice's status from its payment total.

Kept free of DB / FastAPI / stripe imports so the transition logic can be
unit-tested in isolation (the payments router that uses it cannot be imported
outside the full app environment).
"""
from typing import Optional, Tuple

# Statuses that are driven entirely by payments. Any other status
# (draft/sent/overdue/approved/...) is a "real" lifecycle status the user set.
PAYMENT_DRIVEN_STATUSES = ("paid", "partially_paid")


def resolve_invoice_status(
    *,
    current_status: str,
    pre_payment_status: Optional[str],
    total_paid: float,
    amount: float,
) -> Tuple[str, Optional[str]]:
    """Return ``(new_status, new_pre_payment_status)`` for an invoice.

    Rules:
    - ``total_paid >= amount`` -> ``"paid"``; ``0 < total_paid`` -> ``"partially_paid"``.
    - When the invoice first enters a payment-driven status, the status it held
      beforehand is snapshotted into ``pre_payment_status`` so it can be restored.
    - When all payments are removed, the snapshot is restored. Invoices with no
      snapshot (e.g. rows created before this field existed) fall back to
      ``"sent"`` — they had been paid, so they had been issued.
    - With no payments and a non-payment status, nothing changes (a ``draft`` or
      ``overdue`` invoice is left alone).
    """
    if total_paid >= amount:
        new_status: Optional[str] = "paid"
    elif total_paid > 0:
        new_status = "partially_paid"
    else:
        new_status = None

    if new_status in PAYMENT_DRIVEN_STATUSES:
        snapshot = pre_payment_status
        if current_status not in PAYMENT_DRIVEN_STATUSES:
            # First transition out of a real status — remember it.
            snapshot = current_status
        return new_status, snapshot

    if current_status in PAYMENT_DRIVEN_STATUSES:
        # All payments gone — restore what the invoice was before it was paid.
        return (pre_payment_status or "sent"), None

    # No payments and not payment-driven: leave the status as the user set it.
    return current_status, pre_payment_status
