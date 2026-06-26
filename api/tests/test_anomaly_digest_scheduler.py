"""Scheduler wiring for the anomaly digest (Slice 2)."""
from core.services.reminder_background_service import ReminderBackgroundService


def test_anomaly_digest_skipped_when_email_unconfigured(db_session):
    svc = ReminderBackgroundService()
    out = svc._process_anomaly_digest(db_session, tenant_id=1)
    assert out["status"] == "skipped"
    assert out["reason"] == "email_config_missing"
