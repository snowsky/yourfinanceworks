"""Daily anomaly digest emails to tenant admins (Slice 2).

Mirrors ExpenseDigestService: a tenant-level digest gated by a Settings-row
watermark. Selects open high/critical anomalies created since the last run and
emails one summary per opted-in admin, then advances the watermark.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config import APP_NAME, config as app_config
from core.models.models_per_tenant import Anomaly, Settings, User
from core.services.email_service import EmailService, EmailMessage
from core.services.feature_config_service import FeatureConfigService
from core.services.notification_service import NotificationService
from core.services.notification_templates import (
    ANOMALY_DIGEST_HTML_TEMPLATE,
    ANOMALY_DIGEST_TEXT_TEMPLATE,
)

logger = logging.getLogger(__name__)

ALERT_LEVELS = ("high", "critical")
_ENTITY_LABELS = {
    "invoice": "Invoice",
    "expense": "Expense",
    "bank_transaction": "Transaction",
    "bank_statement_transaction": "Transaction",
}


class AnomalyDigestService:
    RUNTIME_KEY = "anomaly_digest_runtime"

    def __init__(self, db: Session, email_service: Optional[EmailService] = None):
        self.db = db
        self.email_service = email_service
        self._notifier = NotificationService(db, email_service)

    def process_due_digest(self, force: bool = False) -> Dict[str, Any]:
        if not FeatureConfigService.is_enabled("anomaly_detection", db=self.db):
            return {"status": "skipped", "reason": "feature_disabled"}

        now = datetime.now(timezone.utc)
        last_run_at = self._load_last_run_at()

        if not force and last_run_at is not None and (now - last_run_at) < timedelta(hours=24):
            return {"status": "skipped", "reason": "not_due"}

        # Window start: the watermark, or the last 24h for a first-ever run.
        window_start = last_run_at if last_run_at is not None else (now - timedelta(hours=24))

        anomalies = (
            self.db.query(Anomaly)
            .filter(
                Anomaly.status == "open",
                Anomaly.risk_level.in_(ALERT_LEVELS),
                Anomaly.created_at > window_start,
            )
            .order_by(Anomaly.created_at.desc())
            .all()
        )

        if not anomalies:
            self._save_last_run_at(now)
            return {"status": "empty"}

        items = [self._serialize(a) for a in anomalies]
        admins = self.db.query(User).filter(User.role == "admin", User.is_active == True).all()  # noqa: E712
        emailed = 0
        for admin in admins:
            if not self._notifier.should_send_notification(admin.id, "anomaly_alert", "email"):
                continue
            if self._send_to_admin(admin, items):
                emailed += 1

        self._save_last_run_at(now)
        return {"status": "sent", "anomaly_count": len(items), "emailed": emailed}

    def _serialize(self, a: Anomaly) -> Dict[str, Any]:
        label = _ENTITY_LABELS.get(a.entity_type, a.entity_type)
        base = app_config.UI_BASE_URL.rstrip("/")
        return {
            "risk_level": a.risk_level,
            "entity_label": label,
            "entity_id": a.entity_id,
            "reason": a.reason or "Anomaly detected",
            "url": f"{base}/anomalies?selected={a.id}",
        }

    def _send_to_admin(self, admin: User, items: List[Dict[str, Any]]) -> bool:
        if not self.email_service:
            return False
        recipient_name = f"{admin.first_name or ''} {admin.last_name or ''}".strip() or admin.email
        subject = f"{len(items)} fraud/anomaly alert(s) need review"
        context = {
            "subject": subject,
            "count": len(items),
            "items": items,
            "company_name": APP_NAME,
        }
        from_email = self.email_service.config.from_email or "noreply@invoiceapp.com"
        from_name = self.email_service.config.from_name or APP_NAME
        message = EmailMessage(
            to_email=admin.email,
            to_name=recipient_name,
            subject=subject,
            html_body=ANOMALY_DIGEST_HTML_TEMPLATE.render(**context),
            text_body=ANOMALY_DIGEST_TEXT_TEMPLATE.render(**context),
            from_email=from_email,
            from_name=from_name,
        )
        return self.email_service.send_email(message)

    def _load_last_run_at(self) -> Optional[datetime]:
        record = self.db.query(Settings).filter(Settings.key == self.RUNTIME_KEY).first()
        if not record or not isinstance(record.value, dict):
            return None
        raw = record.value.get("last_run_at")
        if not raw:
            return None
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    def _save_last_run_at(self, now: datetime) -> None:
        value = {"last_run_at": now.isoformat()}
        record = self.db.query(Settings).filter(Settings.key == self.RUNTIME_KEY).first()
        if record:
            record.value = value
            record.updated_at = now
        else:
            self.db.add(Settings(key=self.RUNTIME_KEY, value=value))
        self.db.commit()
