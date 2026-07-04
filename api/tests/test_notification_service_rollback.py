"""A caught failure inside NotificationService must not poison the caller's
session for the rest of the request (regression: missing rollback let a
schema-drift UndefinedColumn error break unrelated queries later in the
same transaction, e.g. invoice creation failing after a notification send
failed)."""
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from core.models.models_per_tenant import User
from core.models import EmailNotificationSettings
from core.services.notification_service import NotificationService


def _user(db):
    u = User(email="rollback_test@example.com", hashed_password="x", is_active=True,
             role="admin", first_name="R", last_name="T")
    db.add(u); db.commit(); db.refresh(u)
    return u


def _cleanup(db):
    db.query(EmailNotificationSettings).delete()
    db.query(User).delete()
    db.commit()


def test_send_operation_notification_rollback_on_db_error(db_session, monkeypatch):
    user = _user(db_session)
    try:
        svc = NotificationService(db_session)

        def boom(user_id):
            # Simulate a real DB-level failure (e.g. UndefinedColumn from
            # schema drift), which aborts the current Postgres transaction
            # until an explicit rollback.
            db_session.execute(text("SELECT column_that_does_not_exist FROM users"))

        monkeypatch.setattr(svc, "get_user_notification_settings", boom)

        result = svc.send_operation_notification(
            event_type="invoice_created",
            user_id=user.id,
            resource_type="invoice",
            resource_id="1",
            resource_name="INV-1",
            details={},
        )
        assert result is False

        # The session must be usable again immediately after — proving the
        # failure was rolled back instead of leaving the transaction aborted.
        assert db_session.query(User).filter(User.id == user.id).first() is not None
    finally:
        _cleanup(db_session)
