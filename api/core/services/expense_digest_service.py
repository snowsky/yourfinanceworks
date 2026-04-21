from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from jinja2 import Template
from sqlalchemy.orm import Session

from config import APP_NAME
from core.models.models_per_tenant import Expense, Settings, User
from core.services.email_service import EmailMessage, EmailService

logger = logging.getLogger(__name__)


DEFAULT_EXPENSE_SETTINGS: Dict[str, Any] = {
    "digest": {
        "enabled": True,
        "interval": "weekly",
        "delivery_time": "09:00",
        "timezone": "UTC",
        "include_no_activity": False,
        "recipients": {
            "mode": "admins",
            "custom_emails": "",
        },
        "include_sections": {
            "totals_by_category": True,
            "top_vendors": True,
            "pending_approvals": True,
            "rejected_expenses": True,
        },
    }
}


class ExpenseDigestService:
    """Processes and sends tenant-level expense digest emails."""

    SETTINGS_KEY = "expense_settings"
    RUNTIME_KEY = "expense_digest_runtime"

    def __init__(self, db: Session, email_service: Optional[EmailService] = None):
        self.db = db
        self.email_service = email_service

    def process_due_digest(
        self,
        triggering_user_id: Optional[int] = None,
        force: bool = False,
        company_name: str = APP_NAME,
    ) -> Dict[str, Any]:
        settings = self._load_expense_settings()
        digest_cfg = settings.get("digest", {})

        if not digest_cfg.get("enabled", True):
            return {"status": "skipped", "reason": "digest_disabled"}

        if not self.email_service:
            return {"status": "skipped", "reason": "email_service_not_configured"}

        now_utc = datetime.now(timezone.utc)
        interval = str(digest_cfg.get("interval", "weekly")).lower()
        if interval not in {"daily", "weekly", "monthly"}:
            interval = "weekly"

        runtime = self._load_runtime()
        if not force and not self._is_due(now_utc, interval, digest_cfg, runtime):
            return {"status": "skipped", "reason": "not_due"}

        start_utc, end_utc = self._period_bounds(now_utc, interval)
        expenses = (
            self.db.query(Expense)
            .filter(
                Expense.is_deleted.is_(False),
                Expense.expense_date >= start_utc,
                Expense.expense_date < end_utc,
            )
            .order_by(Expense.expense_date.desc())
            .all()
        )

        if not expenses and not bool(digest_cfg.get("include_no_activity", False)):
            self._save_runtime(self._next_runtime(now_utc, interval, digest_cfg, runtime, sent=False))
            return {"status": "skipped", "reason": "no_activity"}

        recipients = self._resolve_recipients(digest_cfg, triggering_user_id)
        if not recipients:
            return {"status": "skipped", "reason": "no_recipients"}

        digest_data = self._build_digest_data(expenses, digest_cfg)
        sent_count = 0
        errors: List[str] = []

        for recipient in recipients:
            try:
                message = self._create_digest_message(
                    recipient_email=recipient["email"],
                    recipient_name=recipient["name"],
                    company_name=company_name,
                    interval=interval,
                    start_utc=start_utc,
                    end_utc=end_utc,
                    digest_data=digest_data,
                )
                success = self.email_service.send_email(message)
                if success:
                    sent_count += 1
                else:
                    errors.append(f"failed_to_send:{recipient['email']}")
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"failed_to_send:{recipient['email']}:{exc}")
                logger.error("Failed sending expense digest to %s: %s", recipient["email"], exc)

        if sent_count > 0:
            self._save_runtime(self._next_runtime(now_utc, interval, digest_cfg, runtime, sent=True))

        return {
            "status": "sent" if sent_count > 0 else "failed",
            "recipients_total": len(recipients),
            "recipients_sent": sent_count,
            "errors": errors,
            "interval": interval,
            "expenses_count": len(expenses),
        }

    def _load_expense_settings(self) -> Dict[str, Any]:
        record = self.db.query(Settings).filter(Settings.key == self.SETTINGS_KEY).first()
        raw = record.value if record and isinstance(record.value, dict) else {}
        merged = DEFAULT_EXPENSE_SETTINGS.copy()
        merged_digest = {**DEFAULT_EXPENSE_SETTINGS["digest"], **raw.get("digest", {})}
        merged_recipients = {
            **DEFAULT_EXPENSE_SETTINGS["digest"]["recipients"],
            **merged_digest.get("recipients", {}),
        }
        merged_sections = {
            **DEFAULT_EXPENSE_SETTINGS["digest"]["include_sections"],
            **merged_digest.get("include_sections", {}),
        }
        merged_digest["recipients"] = merged_recipients
        merged_digest["include_sections"] = merged_sections
        merged["digest"] = merged_digest
        return merged

    def _load_runtime(self) -> Dict[str, Any]:
        record = self.db.query(Settings).filter(Settings.key == self.RUNTIME_KEY).first()
        if not record or not isinstance(record.value, dict):
            return {}
        return record.value

    def _save_runtime(self, runtime_value: Dict[str, Any]) -> None:
        runtime = self.db.query(Settings).filter(Settings.key == self.RUNTIME_KEY).first()
        if runtime:
            runtime.value = runtime_value
            runtime.updated_at = datetime.now(timezone.utc)
        else:
            runtime = Settings(key=self.RUNTIME_KEY, value=runtime_value)
            self.db.add(runtime)
        self.db.commit()

    def _is_due(
        self,
        now_utc: datetime,
        interval: str,
        digest_cfg: Dict[str, Any],
        runtime: Dict[str, Any],
    ) -> bool:
        next_run_raw = runtime.get("next_run_at")
        if next_run_raw:
            try:
                next_run = datetime.fromisoformat(next_run_raw)
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=timezone.utc)
                return now_utc >= next_run
            except ValueError:
                logger.warning("Invalid expense digest next_run_at runtime value: %s", next_run_raw)

        tz = self._safe_timezone(str(digest_cfg.get("timezone", "UTC")))
        hh, mm = self._parse_delivery_time(str(digest_cfg.get("delivery_time", "09:00")))
        local_now = now_utc.astimezone(tz)
        scheduled_today = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0)

        if local_now >= scheduled_today:
            return True

        # Before today's delivery time, seed next run so the scheduler can wait.
        seeded = {
            "last_sent_at": runtime.get("last_sent_at"),
            "next_run_at": scheduled_today.astimezone(timezone.utc).isoformat(),
            "interval": interval,
        }
        self._save_runtime(seeded)
        return False

    def _next_runtime(
        self,
        now_utc: datetime,
        interval: str,
        digest_cfg: Dict[str, Any],
        runtime: Dict[str, Any],
        sent: bool,
    ) -> Dict[str, Any]:
        tz = self._safe_timezone(str(digest_cfg.get("timezone", "UTC")))
        hh, mm = self._parse_delivery_time(str(digest_cfg.get("delivery_time", "09:00")))

        local_now = now_utc.astimezone(tz).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if interval == "daily":
            next_local = local_now + timedelta(days=1)
        elif interval == "weekly":
            next_local = local_now + timedelta(days=7)
        else:
            next_local = self._add_month(local_now)

        return {
            "last_sent_at": now_utc.isoformat() if sent else runtime.get("last_sent_at"),
            "next_run_at": next_local.astimezone(timezone.utc).isoformat(),
            "interval": interval,
        }

    @staticmethod
    def _period_bounds(now_utc: datetime, interval: str) -> tuple[datetime, datetime]:
        if interval == "daily":
            return now_utc - timedelta(days=1), now_utc
        if interval == "weekly":
            return now_utc - timedelta(days=7), now_utc
        return now_utc - timedelta(days=30), now_utc

    @staticmethod
    def _safe_timezone(value: str) -> ZoneInfo:
        try:
            return ZoneInfo(value)
        except Exception:
            return ZoneInfo("UTC")

    @staticmethod
    def _parse_delivery_time(value: str) -> tuple[int, int]:
        try:
            hh_s, mm_s = value.split(":")
            hh = min(23, max(0, int(hh_s)))
            mm = min(59, max(0, int(mm_s)))
            return hh, mm
        except Exception:
            return 9, 0

    @staticmethod
    def _add_month(dt: datetime) -> datetime:
        year = dt.year + (1 if dt.month == 12 else 0)
        month = 1 if dt.month == 12 else dt.month + 1
        day = min(dt.day, 28)
        return dt.replace(year=year, month=month, day=day)

    def _resolve_recipients(
        self, digest_cfg: Dict[str, Any], triggering_user_id: Optional[int]
    ) -> List[Dict[str, str]]:
        mode = str((digest_cfg.get("recipients") or {}).get("mode", "admins")).lower()
        users_by_email: Dict[str, Dict[str, str]] = {}

        def add_user(email: Optional[str], name: Optional[str]) -> None:
            if not email:
                return
            key = email.strip().lower()
            if not key:
                return
            users_by_email[key] = {"email": email.strip(), "name": (name or email).strip()}

        if mode == "custom":
            raw = str((digest_cfg.get("recipients") or {}).get("custom_emails", ""))
            for item in raw.replace(";", ",").split(","):
                email = item.strip()
                if "@" in email:
                    add_user(email, email)
        elif mode == "me" and triggering_user_id:
            user = self.db.query(User).filter(User.id == triggering_user_id, User.is_active.is_(True)).first()
            if user:
                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
                add_user(user.email, full_name)
        else:
            admins = (
                self.db.query(User)
                .filter(User.role == "admin", User.is_active.is_(True))
                .all()
            )
            for admin in admins:
                full_name = f"{admin.first_name or ''} {admin.last_name or ''}".strip() or admin.email
                add_user(admin.email, full_name)

        if mode == "me" and not users_by_email:
            # Fallback when running in background without a triggering user.
            admins = (
                self.db.query(User)
                .filter(User.role == "admin", User.is_active.is_(True))
                .all()
            )
            for admin in admins:
                full_name = f"{admin.first_name or ''} {admin.last_name or ''}".strip() or admin.email
                add_user(admin.email, full_name)

        return list(users_by_email.values())

    @staticmethod
    def _build_digest_data(expenses: List[Expense], digest_cfg: Dict[str, Any]) -> Dict[str, Any]:
        totals_by_category: Dict[str, float] = defaultdict(float)
        top_vendor_amounts: Dict[str, float] = defaultdict(float)
        top_vendor_counts: Dict[str, int] = defaultdict(int)
        pending_approvals: List[Dict[str, Any]] = []
        rejected_expenses: List[Dict[str, Any]] = []

        total_amount = 0.0
        for exp in expenses:
            amount = float(exp.total_amount or exp.amount or 0.0)
            total_amount += amount

            category = exp.category or "Uncategorized"
            totals_by_category[category] += amount

            vendor = (exp.vendor or "Unknown Vendor").strip()
            top_vendor_amounts[vendor] += amount
            top_vendor_counts[vendor] += 1

            status = (exp.status or "").lower()
            if status in {"pending_approval", "resubmitted"}:
                pending_approvals.append(
                    {"id": exp.id, "category": category, "amount": amount, "date": exp.expense_date.isoformat()}
                )
            if status == "rejected":
                rejected_expenses.append(
                    {"id": exp.id, "category": category, "amount": amount, "date": exp.expense_date.isoformat()}
                )

        include_sections = digest_cfg.get("include_sections", {})
        data: Dict[str, Any] = {
            "expense_count": len(expenses),
            "total_amount": round(total_amount, 2),
            "currency": (expenses[0].currency if expenses else "USD"),
        }

        if include_sections.get("totals_by_category", True):
            data["totals_by_category"] = [
                {"category": k, "amount": round(v, 2)}
                for k, v in sorted(totals_by_category.items(), key=lambda item: item[1], reverse=True)
            ]
        if include_sections.get("top_vendors", True):
            vendors = []
            for vendor, amount in sorted(top_vendor_amounts.items(), key=lambda item: item[1], reverse=True)[:5]:
                vendors.append(
                    {"vendor": vendor, "amount": round(amount, 2), "count": top_vendor_counts[vendor]}
                )
            data["top_vendors"] = vendors
        if include_sections.get("pending_approvals", True):
            data["pending_approvals"] = pending_approvals[:10]
            data["pending_count"] = len(pending_approvals)
        if include_sections.get("rejected_expenses", True):
            data["rejected_expenses"] = rejected_expenses[:10]
            data["rejected_count"] = len(rejected_expenses)
        return data

    def _create_digest_message(
        self,
        recipient_email: str,
        recipient_name: str,
        company_name: str,
        interval: str,
        start_utc: datetime,
        end_utc: datetime,
        digest_data: Dict[str, Any],
    ) -> EmailMessage:
        from_email = "noreply@invoiceapp.com"
        from_name = company_name
        if self.email_service and hasattr(self.email_service, "config"):
            from_email = self.email_service.config.from_email or from_email
            from_name = self.email_service.config.from_name or from_name

        period_label = f"{start_utc.strftime('%Y-%m-%d')} to {end_utc.strftime('%Y-%m-%d')}"
        subject = f"{company_name} - {interval.title()} Expense Digest ({period_label})"

        html_template = Template(
            """
            <html>
            <body style="font-family: Arial, sans-serif;">
              <h2>{{ company_name }} - Expense Digest</h2>
              <p>Hello {{ recipient_name }},</p>
              <p>Period: <strong>{{ period_label }}</strong></p>
              <p>Total expenses: <strong>{{ digest.expense_count }}</strong></p>
              <p>Total amount: <strong>{{ digest.total_amount }} {{ digest.currency }}</strong></p>

              {% if digest.totals_by_category %}
              <h3>Totals by Category</h3>
              <ul>
                {% for item in digest.totals_by_category %}
                <li>{{ item.category }}: {{ item.amount }}</li>
                {% endfor %}
              </ul>
              {% endif %}

              {% if digest.top_vendors %}
              <h3>Top Vendors</h3>
              <ul>
                {% for item in digest.top_vendors %}
                <li>{{ item.vendor }}: {{ item.amount }} ({{ item.count }} expenses)</li>
                {% endfor %}
              </ul>
              {% endif %}

              {% if digest.pending_approvals is defined %}
              <h3>Pending Approvals ({{ digest.pending_count or 0 }})</h3>
              {% if digest.pending_approvals %}
              <ul>
                {% for item in digest.pending_approvals %}
                <li>#{{ item.id }} - {{ item.category }}: {{ item.amount }}</li>
                {% endfor %}
              </ul>
              {% else %}
              <p>None</p>
              {% endif %}
              {% endif %}

              {% if digest.rejected_expenses is defined %}
              <h3>Rejected Expenses ({{ digest.rejected_count or 0 }})</h3>
              {% if digest.rejected_expenses %}
              <ul>
                {% for item in digest.rejected_expenses %}
                <li>#{{ item.id }} - {{ item.category }}: {{ item.amount }}</li>
                {% endfor %}
              </ul>
              {% else %}
              <p>None</p>
              {% endif %}
              {% endif %}
            </body>
            </html>
            """
        )

        text_template = Template(
            """
            {{ company_name }} - Expense Digest

            Hello {{ recipient_name }},
            Period: {{ period_label }}
            Total expenses: {{ digest.expense_count }}
            Total amount: {{ digest.total_amount }} {{ digest.currency }}
            """
        )

        context = {
            "company_name": company_name,
            "recipient_name": recipient_name,
            "period_label": period_label,
            "digest": digest_data,
        }

        return EmailMessage(
            to_email=recipient_email,
            to_name=recipient_name,
            subject=subject,
            html_body=html_template.render(**context),
            text_body=text_template.render(**context),
            from_email=from_email,
            from_name=from_name,
        )
