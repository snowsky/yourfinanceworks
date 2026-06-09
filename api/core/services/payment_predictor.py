"""Payment-date forecasting — "when will this client pay?".

Heuristic, explainable, and self-contained: for each client we learn the
average issue->payment span from their fully-paid invoices, then project an
expected payment date for each outstanding invoice. Falls back to a global
average, then to the due date, with a confidence label reflecting how much
history backs the estimate.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.models.models_per_tenant import Invoice, Payment

OUTSTANDING_STATUSES = ("sent", "pending", "overdue", "partially_paid")

# Minimum samples for each basis.
CLIENT_MIN = 2
CLIENT_HIGH = 5
GLOBAL_MIN = 3


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


class PaymentDatePredictor:
    def __init__(self, db: Session):
        self.db = db

    def _paid_samples(self) -> Dict[int, List[int]]:
        """Map client_id -> list of issue->payment spans (days) from paid invoices."""
        # Last payment date per paid invoice.
        paid_dates = dict(
            self.db.query(Payment.invoice_id, func.max(Payment.payment_date))
            .group_by(Payment.invoice_id)
            .all()
        )
        samples: Dict[int, List[int]] = {}
        rows = (
            self.db.query(Invoice.id, Invoice.client_id, Invoice.created_at)
            .filter(Invoice.status == "paid", Invoice.is_deleted == False)  # noqa: E712
            .all()
        )
        for inv_id, client_id, created_at in rows:
            paid_at = paid_dates.get(inv_id)
            if not paid_at or not created_at:
                continue
            span = (_as_date(paid_at) - _as_date(created_at)).days
            if span < 0:
                span = 0
            samples.setdefault(client_id, []).append(span)
        return samples

    @staticmethod
    def _avg(values: List[int]) -> float:
        return sum(values) / len(values)

    def predict_outstanding(self, today: Optional[date] = None) -> Dict[str, Any]:
        """Return a forecast entry per outstanding invoice."""
        today = today or datetime.now(timezone.utc).date()
        samples = self._paid_samples()
        global_samples = [d for vals in samples.values() for d in vals]
        global_avg = self._avg(global_samples) if len(global_samples) >= GLOBAL_MIN else None

        invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.status.in_(OUTSTANDING_STATUSES),
                Invoice.is_deleted == False,  # noqa: E712
            )
            .all()
        )

        items: List[Dict[str, Any]] = []
        for inv in invoices:
            client_vals = samples.get(inv.client_id, [])
            if len(client_vals) >= CLIENT_MIN:
                avg_days = self._avg(client_vals)
                basis = "client"
                confidence = "high" if len(client_vals) >= CLIENT_HIGH else "medium"
                sample_size = len(client_vals)
            elif global_avg is not None:
                avg_days = global_avg
                basis = "global"
                confidence = "low"
                sample_size = len(global_samples)
            else:
                avg_days = None
                basis = "due_date"
                confidence = "none"
                sample_size = 0

            issue = _as_date(inv.created_at) or today
            if avg_days is not None:
                predicted = issue + timedelta(days=round(avg_days))
                if predicted < today:
                    predicted = today  # overdue per history -> expect imminently
            else:
                predicted = _as_date(inv.due_date) or today

            items.append(
                {
                    "invoice_id": inv.id,
                    "number": inv.number,
                    "client_id": inv.client_id,
                    "amount": float(inv.amount),
                    "currency": inv.currency,
                    "status": inv.status,
                    "due_date": _as_date(inv.due_date).isoformat() if inv.due_date else None,
                    "predicted_date": predicted.isoformat(),
                    "expected_in_days": (predicted - today).days,
                    "avg_days_to_pay": round(avg_days) if avg_days is not None else None,
                    "basis": basis,
                    "confidence": confidence,
                    "sample_size": sample_size,
                }
            )

        items.sort(key=lambda x: x["predicted_date"])
        return {
            "as_of": today.isoformat(),
            "global_avg_days_to_pay": round(global_avg) if global_avg is not None else None,
            "count": len(items),
            "items": items,
        }
