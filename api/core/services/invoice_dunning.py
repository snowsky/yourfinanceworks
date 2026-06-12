"""Invoice payment reminders (dunning).

Emails clients about unpaid invoices on a tenant-configurable cadence of
day-offsets relative to the due date (negative = before due, 0 = on the due
date, positive = after). Driven from the background scheduler loop.

Idempotency: each invoice records ``reminder_last_offset`` — the most-advanced
cadence step already emailed. The pass only ever sends a *more advanced* step,
so it never resends (safe to run on every loop tick) and naturally collapses
missed steps into a single "most relevant" reminder.

Opt-in: gated by ``invoice_settings.payment_reminders_enabled`` (default off),
so enabling email config alone never surprises clients.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.models.models_per_tenant import Client, Invoice, Settings
from core.services.client_email import build_tenant_email_service
from core.services.email_service import EmailMessage
from core.services.notification_templates import (
    DUNNING_HTML_TEMPLATE,
    DUNNING_TEXT_TEMPLATE,
)

logger = logging.getLogger(__name__)

# Statuses worth chasing: issued/unpaid, not draft/paid/cancelled.
DUNNABLE_STATUSES = ("sent", "pending", "overdue", "partially_paid")


def _status_line(days_since_due: int) -> str:
    if days_since_due < 0:
        n = -days_since_due
        return f"due in {n} day{'s' if n != 1 else ''}"
    if days_since_due == 0:
        return "due today"
    return f"{days_since_due} day{'s' if days_since_due != 1 else ''} overdue"


def _tone(days_since_due: int) -> Dict[str, str]:
    """Escalating presentation by lateness. Colors are status colors
    (blue/amber/red), deliberately independent of tenant branding."""
    if days_since_due < 0:
        return {
            "subject_prefix": "Upcoming payment",
            "badge_label": "Payment due soon",
            "intro_line": "This is a friendly heads-up about",
            "badge_bg": "#eff6ff",
            "urgency_color": "#1d4ed8",
        }
    if days_since_due < 7:
        return {
            "subject_prefix": "Payment reminder",
            "badge_label": "Payment reminder",
            "intro_line": "This is a friendly reminder about",
            "badge_bg": "#fffbeb",
            "urgency_color": "#b45309",
        }
    return {
        "subject_prefix": "Overdue notice",
        "badge_label": "Overdue",
        "intro_line": "This is a notice regarding",
        "badge_bg": "#fef2f2",
        "urgency_color": "#b91c1c",
    }


class InvoiceDunningService:
    def __init__(self, db: Session):
        self.db = db

    def _config(self) -> Optional[Dict[str, Any]]:
        record = (
            self.db.query(Settings).filter(Settings.key == "invoice_settings").first()
        )
        return record.value if record else None

    def process(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Send any due reminders for the current tenant. Returns a stats dict."""
        now = now or datetime.now(timezone.utc)
        cfg = self._config() or {}

        if not cfg.get("payment_reminders_enabled"):
            return {"status": "skipped", "reason": "disabled"}

        cadence = self._normalize_cadence(cfg.get("reminder_cadence"))
        if not cadence:
            return {"status": "skipped", "reason": "no_cadence"}

        email_service = build_tenant_email_service(self.db)
        if email_service is None:
            return {"status": "skipped", "reason": "email_not_configured"}

        company_name = email_service.config.from_name or ""
        today = now.date()

        invoices: List[Invoice] = (
            self.db.query(Invoice)
            .filter(
                Invoice.status.in_(DUNNABLE_STATUSES),
                Invoice.due_date.isnot(None),
                Invoice.is_deleted == False,  # noqa: E712
            )
            .all()
        )

        sent = 0
        for inv in invoices:
            try:
                if self._maybe_send(inv, cadence, today, email_service, company_name):
                    sent += 1
            except Exception as e:  # one bad invoice must not abort the batch
                logger.warning(f"Dunning failed for invoice {inv.id}: {e}")

        if sent:
            self.db.commit()

        return {"status": "ok", "sent": sent, "scanned": len(invoices)}

    @staticmethod
    def _normalize_cadence(raw: Any) -> List[int]:
        if not isinstance(raw, (list, tuple)):
            return []
        out = set()
        for v in raw:
            try:
                out.add(int(v))
            except (TypeError, ValueError):
                continue
        return sorted(out)

    def _maybe_send(
        self,
        inv: Invoice,
        cadence: List[int],
        today,
        email_service,
        company_name: str,
    ) -> bool:
        days_since_due = (today - inv.due_date.date()).days

        # The most-advanced cadence step whose date has arrived.
        reached = [step for step in cadence if days_since_due >= step]
        if not reached:
            return False
        step = max(reached)

        if inv.reminder_last_offset is not None and step <= inv.reminder_last_offset:
            return False  # already sent this (or a later) step

        client = self.db.query(Client).filter(Client.id == inv.client_id).first()
        to_email = getattr(client, "email", None) if client else None
        if not to_email:
            return False

        tone = _tone(days_since_due)
        subject = f"{tone['subject_prefix']} — invoice {inv.number}"
        context = {
            "client_name": client.name or "there",
            "invoice_number": inv.number,
            "amount": f"{float(inv.amount):,.2f}",
            "currency": inv.currency or "",
            "due_date": inv.due_date.date().isoformat(),
            "status_line": _status_line(days_since_due),
            "company_name": company_name,
            "badge_label": tone["badge_label"],
            "intro_line": tone["intro_line"],
            "badge_bg": tone["badge_bg"],
            "urgency_color": tone["urgency_color"],
            "subject_prefix": tone["subject_prefix"],
            "title": subject,
        }
        message = EmailMessage(
            to_email=to_email,
            to_name=client.name or "",
            subject=subject,
            html_body=DUNNING_HTML_TEMPLATE.render(**context),
            text_body=DUNNING_TEXT_TEMPLATE.render(**context),
            from_email=email_service.config.from_email,
            from_name=company_name,
        )
        if not email_service.send_email(message):
            return False

        inv.reminder_last_offset = step
        inv.reminder_last_sent_at = datetime.now(timezone.utc)
        return True
