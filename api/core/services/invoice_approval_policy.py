"""Tenant policy: require invoice approval before an invoice can be sent.

Stored in the ``invoice_settings`` blob:
- ``require_approval_before_send`` (bool, default off)
- ``approval_threshold_amount`` (number >= 0, default 0 = all invoices)

The policy is inert unless the commercial ``approvals`` feature is enabled — a
require-approval rule is meaningless if approvals can't be performed. The amount
threshold is compared directly against ``invoice.amount`` in the invoice's own
currency (no FX normalisation — see the spec's multi-currency caveat).
"""

from typing import Any, Dict

from sqlalchemy.orm import Session

from core.models.models_per_tenant import Settings
from core.utils.feature_gate import feature_enabled

# Statuses meaning the invoice has not yet cleared approval.
_UNAPPROVED_STATUSES = frozenset({"draft", "pending_approval", "rejected"})


def _invoice_settings(db: Session) -> Dict[str, Any]:
    record = db.query(Settings).filter(Settings.key == "invoice_settings").first()
    return record.value if record and record.value else {}


def invoice_requires_approval(db: Session, invoice) -> bool:
    """True when this invoice must be approved before it can be sent."""
    if not feature_enabled("approvals", db):
        return False
    cfg = _invoice_settings(db)
    if not cfg.get("require_approval_before_send"):
        return False
    try:
        threshold = float(cfg.get("approval_threshold_amount") or 0)
    except (TypeError, ValueError):
        threshold = 0.0
    if threshold <= 0:
        return True
    return float(invoice.amount) >= threshold


def send_blocked_by_approval(db: Session, invoice) -> bool:
    """True when sending must be refused: approval required but not yet granted."""
    return (
        invoice_requires_approval(db, invoice)
        and invoice.status in _UNAPPROVED_STATUSES
    )


def validate_approval_threshold(invoice_settings: Dict[str, Any]) -> None:
    """Raise ValueError if ``approval_threshold_amount`` is present and not a
    non-negative number. Mirrors validate_invoice_branding's contract so the
    settings router can convert it to a 400."""
    if "approval_threshold_amount" not in invoice_settings:
        return
    value = invoice_settings["approval_threshold_amount"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("approval_threshold_amount must be a number")
    if value < 0:
        raise ValueError("approval_threshold_amount must be zero or positive")
