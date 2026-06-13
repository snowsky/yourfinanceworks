"""Onboarding activation checklist: derive setup-step completion from tenant data.

Each step is computed live from existing data (no persisted completion state), so it
can never drift from reality. The only persisted state is a dismiss flag, stored as a
single ``Settings`` row (key=``onboarding_checklist``).
"""

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CHECKLIST_DISMISS_KEY = "onboarding_checklist"

# Invoice statuses that mean "an invoice has actually been sent to a client".
_SENT_STATUSES = ("sent", "paid", "partially_paid", "overdue")

# Fixed step order. Keys are the API contract; labels/links live in the frontend.
_STEP_KEYS = (
    "add_client",
    "create_invoice",
    "record_expense",
    "customize_branding",
    "send_invoice",
)


class OnboardingChecklistService:
    """Computes activation-checklist status for a single tenant DB session."""

    def __init__(self, db: Session):
        self.db = db

    def checklist_status(self) -> dict:
        from core.models.models_per_tenant import Client, Expense, Invoice

        done = {
            "add_client": self.db.query(Client.id).first() is not None,
            "create_invoice": self.db.query(Invoice.id)
            .filter(Invoice.is_deleted == False)  # noqa: E712
            .first()
            is not None,
            "record_expense": self.db.query(Expense.id)
            .filter(Expense.is_deleted == False)  # noqa: E712
            .first()
            is not None,
            "customize_branding": self._has_branding(),
            "send_invoice": self.db.query(Invoice.id)
            .filter(
                Invoice.is_deleted == False,  # noqa: E712
                Invoice.status.in_(_SENT_STATUSES),
            )
            .first()
            is not None,
        }
        steps = [{"key": key, "done": done[key]} for key in _STEP_KEYS]
        completed = sum(1 for s in steps if s["done"])
        return {
            "steps": steps,
            "completed": completed,
            "total": len(_STEP_KEYS),
            "all_complete": completed == len(_STEP_KEYS),
            "dismissed": self._is_dismissed(),
        }

    def dismiss(self) -> dict:
        from core.models.models_per_tenant import Settings

        record = (
            self.db.query(Settings)
            .filter(Settings.key == CHECKLIST_DISMISS_KEY)
            .first()
        )
        if record is None:
            record = Settings(
                key=CHECKLIST_DISMISS_KEY,
                value={"dismissed": True},
                category="onboarding",
            )
            self.db.add(record)
        else:
            record.value = {"dismissed": True}
        self.db.commit()
        return self.checklist_status()

    def _has_branding(self) -> bool:
        from core.models.models_per_tenant import Settings

        record = (
            self.db.query(Settings)
            .filter(Settings.key == "invoice_branding")
            .first()
        )
        return bool(record and record.value)

    def _is_dismissed(self) -> bool:
        from core.models.models_per_tenant import Settings

        record = (
            self.db.query(Settings)
            .filter(Settings.key == CHECKLIST_DISMISS_KEY)
            .first()
        )
        return bool(record and record.value and record.value.get("dismissed") is True)
