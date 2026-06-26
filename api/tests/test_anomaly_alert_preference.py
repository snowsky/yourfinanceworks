"""should_send_notification honours the anomaly_alert preference (Slice 2)."""
from core.models.models_per_tenant import User
from core.models import EmailNotificationSettings
from core.services.notification_service import NotificationService


def _admin(db):
    u = User(email="admin@example.com", hashed_password="x", is_active=True,
             role="admin", first_name="A", last_name="D")
    db.add(u); db.commit(); db.refresh(u)
    return u


def _cleanup(db):
    db.query(EmailNotificationSettings).delete()
    db.query(User).delete()
    db.commit()


def test_anomaly_alert_defaults_on_for_both_channels(db_session):
    user = _admin(db_session)
    try:
        svc = NotificationService(db_session)
        assert svc.should_send_notification(user.id, "anomaly_alert", "in_app") is True
        assert svc.should_send_notification(user.id, "anomaly_alert", "email") is True
    finally:
        _cleanup(db_session)


def test_anomaly_alert_off_suppresses_both_channels(db_session):
    user = _admin(db_session)
    try:
        settings = EmailNotificationSettings(user_id=user.id, anomaly_alert=False)
        db_session.add(settings); db_session.commit()
        svc = NotificationService(db_session)
        assert svc.should_send_notification(user.id, "anomaly_alert", "in_app") is False
        assert svc.should_send_notification(user.id, "anomaly_alert", "email") is False
    finally:
        _cleanup(db_session)
