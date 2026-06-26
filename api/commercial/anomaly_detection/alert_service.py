"""Immediate in-app alerting for newly detected anomalies (Slice 2).

Writes system ReminderNotification rows (the in-app bell feed) for tenant
admins when the audit worker saves a new high/critical open anomaly on the
normal (non-reprocess) path. The NotificationService.create_in_app_notification
method is a logging stub and does NOT reach the bell, so we write the row here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from core.models.models_per_tenant import Anomaly, ReminderNotification, User
from core.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

ALERT_LEVELS = {"high", "critical"}

_ENTITY_LABELS = {
    "invoice": "invoice",
    "expense": "expense",
    "bank_transaction": "transaction",
    "bank_statement_transaction": "transaction",
}


class AnomalyAlertService:
    def __init__(self, db: Session):
        self.db = db
        self._notifier = NotificationService(db)

    def notify_new_anomalies(self, anomalies: List[Anomaly], reprocess_mode: bool) -> dict:
        """Fire immediate in-app alerts for new high/critical open anomalies."""
        alerted = 0
        skipped = 0
        if reprocess_mode:
            # Bulk reprocess never alerts in-app; the daily digest catches these.
            return {"alerted": 0, "skipped": len(anomalies)}

        admins = self.db.query(User).filter(User.role == "admin", User.is_active == True).all()  # noqa: E712
        now = datetime.now(timezone.utc)

        for anomaly in anomalies:
            if (anomaly.risk_level not in ALERT_LEVELS
                    or anomaly.status != "open"
                    or anomaly.alerted_at is not None):
                skipped += 1
                continue

            label = _ENTITY_LABELS.get(anomaly.entity_type, anomaly.entity_type)
            subject = (
                f"{anomaly.risk_level.title()}-risk anomaly on "
                f"{label} #{anomaly.id}"
            )
            message = (anomaly.reason or "An anomaly was detected.")[:500]

            fired = False
            for admin in admins:
                if not self._notifier.should_send_notification(admin.id, "anomaly_alert", "in_app"):
                    continue
                self.db.add(ReminderNotification(
                    reminder_id=None,
                    user_id=admin.id,
                    notification_type="anomaly_alert",
                    channel="in_app",
                    scheduled_for=now,
                    sent_at=now,
                    is_sent=True,
                    subject=subject,
                    message=message,
                ))
                fired = True

            anomaly.alerted_at = now
            if fired:
                alerted += 1
            else:
                skipped += 1

        self.db.commit()
        logger.info(f"Anomaly in-app alerts: {alerted} alerted, {skipped} skipped")
        return {"alerted": alerted, "skipped": skipped}
