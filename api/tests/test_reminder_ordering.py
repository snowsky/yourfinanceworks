"""
Test reminder ordering and pinning functionality.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from core.models.models_per_tenant import Reminder, User, RecurrencePattern, ReminderStatus, ReminderPriority
from unittest.mock import patch, MagicMock
from core.schemas.reminders import ReorderReminders


def test_reminder_default_sorting(db_session: Session, sample_user: User):
    """Test that reminders are sorted by is_pinned and position by default"""
    # Create reminders in random order
    now = datetime.now(timezone.utc)
    r1 = Reminder(title="R1", due_date=now, created_by_id=sample_user.id, assigned_to_id=sample_user.id, position=2, is_pinned=False)
    r2 = Reminder(title="R2", due_date=now, created_by_id=sample_user.id, assigned_to_id=sample_user.id, position=1, is_pinned=False)
    r3 = Reminder(title="R3", due_date=now, created_by_id=sample_user.id, assigned_to_id=sample_user.id, position=3, is_pinned=True)

    db_session.add_all([r1, r2, r3])
    db_session.commit()

    from core.routers.reminders import get_reminders

    # Mock UserRoleService.is_admin_user to avoid JSONB filters on SQLite
    with patch("core.routers.reminders.UserRoleService.is_admin_user", return_value=True):
        # Call the router function directly, passing all arguments explicitly
        results = get_reminders(
            page=1,
            per_page=20,
            status=None,
            priority=None,
            assigned_to_id=sample_user.id,
            created_by_id=None,
            due_date_from=None,
            due_date_to=None,
            search=None,
            sort_by="due_date",
            sort_order="asc",
            db=db_session,
            current_user=sample_user
        )

    items = results.items
    assert len(items) == 3
    # Sorted order: Pin first, then position
    assert items[0].title == "R3"  # Pinned
    assert items[1].title == "R2"  # Position 1
    assert items[2].title == "R1"  # Position 2

def test_reorder_reminders(db_session: Session, sample_user: User):
    """Test the bulk reorder endpoint"""
    r1 = Reminder(title="R1", due_date=datetime.now(timezone.utc), created_by_id=sample_user.id, assigned_to_id=sample_user.id, position=0)
    r2 = Reminder(title="R2", due_date=datetime.now(timezone.utc), created_by_id=sample_user.id, assigned_to_id=sample_user.id, position=1)

    db_session.add_all([r1, r2])
    db_session.commit()

    from core.routers.reminders import reorder_reminders
    from core.schemas.reminders import ReorderReminders

    # Swap their order
    reorder_data = ReorderReminders(reminder_ids=[r2.id, r1.id])

    # Mock require_admin and other dependencies if needed, but here we call it directly
    with patch("core.routers.reminders.check_reminder_permissions", return_value=None):
        reorder_reminders(reorder_data=reorder_data, db=db_session, current_user=sample_user)

    db_session.refresh(r1)
    db_session.refresh(r2)

    assert r1.position == 2
    assert r2.position == 1

def test_toggle_reminder_pin(db_session: Session, sample_user: User):
    """Test toggling the is_pinned status"""
    r1 = Reminder(title="R1", due_date=datetime.now(timezone.utc), created_by_id=sample_user.id, assigned_to_id=sample_user.id, is_pinned=False)
    db_session.add(r1)
    db_session.commit()

    from core.routers.reminders import toggle_reminder_pin

    # Toggle to True
    with patch("core.routers.reminders.check_reminder_permissions", return_value=None):
        toggle_reminder_pin(reminder_id=r1.id, db=db_session, current_user=sample_user)

    db_session.refresh(r1)
    assert r1.is_pinned is True

    # Toggle back to False
    with patch("core.routers.reminders.check_reminder_permissions", return_value=None):
        toggle_reminder_pin(reminder_id=r1.id, db=db_session, current_user=sample_user)

    db_session.refresh(r1)
    assert r1.is_pinned is False
