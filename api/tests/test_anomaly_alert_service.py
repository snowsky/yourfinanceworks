"""AnomalyAlertService immediate in-app alerts (Slice 2)."""
import pytest

from core.models.models_per_tenant import User, Anomaly, ReminderNotification
from core.models import EmailNotificationSettings
from commercial.anomaly_detection.alert_service import AnomalyAlertService


@pytest.fixture(autouse=True)
def _cleanup(db_session):
    yield
    db_session.query(ReminderNotification).delete()
    db_session.query(EmailNotificationSettings).delete()
    db_session.query(Anomaly).delete()
    db_session.query(User).delete()
    db_session.commit()


def _admin(db, email="admin@example.com"):
    u = User(email=email, hashed_password="x", is_active=True, role="admin",
             first_name="A", last_name="D")
    db.add(u); db.commit(); db.refresh(u)
    return u


def _user(db, role="user", email="reg@example.com"):
    u = User(email=email, hashed_password="x", is_active=True, role=role,
             first_name="R", last_name="U")
    db.add(u); db.commit(); db.refresh(u)
    return u


def _anomaly(db, *, risk_level="high", status="open"):
    a = Anomaly(entity_type="invoice", entity_id=1, risk_score=80.0,
                risk_level=risk_level, reason="dup billing", rule_id="duplicate_billing",
                status=status)
    db.add(a); db.commit(); db.refresh(a)
    return a


def _notifs(db):
    return db.query(ReminderNotification).filter(
        ReminderNotification.notification_type == "anomaly_alert").all()


def test_high_risk_open_anomaly_alerts_admin_and_sets_alerted_at(db_session):
    admin = _admin(db_session)
    a = _anomaly(db_session, risk_level="high")
    result = AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert result["alerted"] == 1
    rows = _notifs(db_session)
    assert len(rows) == 1
    assert rows[0].user_id == admin.id
    assert rows[0].channel == "in_app"
    assert rows[0].reminder_id is None
    assert f"#{a.id}" in rows[0].subject
    db_session.refresh(a)
    assert a.alerted_at is not None


def test_critical_risk_alerts(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="critical")
    AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert len(_notifs(db_session)) == 1


def test_low_and_medium_risk_do_not_alert(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="medium")
    result = AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert result["alerted"] == 0
    assert _notifs(db_session) == []


def test_resolved_anomaly_does_not_alert(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="high", status="confirmed")
    AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert _notifs(db_session) == []


def test_reprocess_mode_suppresses_all_alerts(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="critical")
    result = AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=True)
    assert result["alerted"] == 0
    assert _notifs(db_session) == []
    db_session.refresh(a)
    assert a.alerted_at is None


def test_already_alerted_anomaly_is_skipped(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="high")
    svc = AnomalyAlertService(db_session)
    svc.notify_new_anomalies([a], reprocess_mode=False)
    svc.notify_new_anomalies([a], reprocess_mode=False)  # second pass
    assert len(_notifs(db_session)) == 1  # not doubled


def test_only_admins_receive_alerts(db_session):
    _admin(db_session, email="a@x.com")
    _user(db_session, role="user", email="u@x.com")
    _user(db_session, role="viewer", email="v@x.com")
    a = _anomaly(db_session, risk_level="high")
    AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert len(_notifs(db_session)) == 1  # only the admin


def test_admin_opted_out_gets_no_alert(db_session):
    admin = _admin(db_session)
    db_session.add(EmailNotificationSettings(user_id=admin.id, anomaly_alert=False))
    db_session.commit()
    a = _anomaly(db_session, risk_level="high")
    AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert _notifs(db_session) == []
