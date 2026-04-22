"""
Test reminder ordering and pinning functionality.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from core.models.models_per_tenant import Reminder, User, RecurrencePattern, ReminderStatus, ReminderPriority
from unittest.mock import patch, MagicMock
from core.schemas.reminders import ReminderCreate, ReminderStatusUpdate, ReminderUpdate, ReorderReminders


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


def test_create_reminder_logs_audit_event(db_session: Session, sample_user: User):
    from core.routers.reminders import create_reminder

    reminder_data = ReminderCreate(
        title="Audit test reminder",
        description="Created in test",
        due_date=datetime.now(timezone.utc) + timedelta(days=1),
        recurrence_pattern=RecurrencePattern.NONE,
        recurrence_interval=1,
        priority=ReminderPriority.HIGH,
        assigned_to_id=sample_user.id,
        is_pinned=True,
        tags=["ops"],
        extra_metadata={"source": "test"},
    )

    with patch("core.routers.reminders.log_audit_event") as mock_log_audit_event:
        result = create_reminder(reminder_data=reminder_data, db=db_session, current_user=sample_user)

    assert result.title == reminder_data.title
    mock_log_audit_event.assert_called_once()
    call_kwargs = mock_log_audit_event.call_args.kwargs
    assert call_kwargs["action"] == "CREATE"
    assert call_kwargs["resource_type"] == "reminder"
    assert call_kwargs["resource_name"] == reminder_data.title
    assert call_kwargs["user_id"] == sample_user.id
    assert call_kwargs["user_email"] == sample_user.email
    assert call_kwargs["details"]["assigned_to_id"] == sample_user.id
    assert call_kwargs["details"]["priority"] == ReminderPriority.HIGH.value
    assert call_kwargs["details"]["status"] == ReminderStatus.PENDING.value


def test_delete_reminder_logs_audit_event(db_session: Session, sample_user: User):
    from core.routers.reminders import delete_reminder

    reminder = Reminder(
        title="Delete audit reminder",
        due_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by_id=sample_user.id,
        assigned_to_id=sample_user.id,
        priority=ReminderPriority.MEDIUM,
    )
    db_session.add(reminder)
    db_session.commit()
    db_session.refresh(reminder)

    with patch("core.routers.reminders.log_audit_event") as mock_log_audit_event:
        delete_reminder(reminder_id=reminder.id, db=db_session, current_user=sample_user)

    db_session.refresh(reminder)
    assert reminder.is_deleted is True
    mock_log_audit_event.assert_called_once()
    call_kwargs = mock_log_audit_event.call_args.kwargs
    assert call_kwargs["action"] == "DELETE"
    assert call_kwargs["resource_type"] == "reminder"
    assert call_kwargs["resource_id"] == str(reminder.id)
    assert call_kwargs["resource_name"] == reminder.title
    assert call_kwargs["details"]["deleted_by_id"] == sample_user.id


def test_update_reminder_logs_audit_event(db_session: Session, sample_user: User):
    from core.routers.reminders import update_reminder

    reminder = Reminder(
        title="Original title",
        due_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by_id=sample_user.id,
        assigned_to_id=sample_user.id,
        priority=ReminderPriority.MEDIUM,
    )
    db_session.add(reminder)
    db_session.commit()
    db_session.refresh(reminder)

    update_data = ReminderUpdate(title="Updated title", priority=ReminderPriority.URGENT)

    with patch("core.routers.reminders.log_audit_event") as mock_log_audit_event:
        result = update_reminder(reminder_id=reminder.id, reminder_data=update_data, db=db_session, current_user=sample_user)

    assert result.title == "Updated title"
    mock_log_audit_event.assert_called_once()
    call_kwargs = mock_log_audit_event.call_args.kwargs
    assert call_kwargs["action"] == "UPDATE"
    assert call_kwargs["details"]["changes"]["title"]["old_value"] == "Original title"
    assert call_kwargs["details"]["changes"]["title"]["new_value"] == "Updated title"
    assert call_kwargs["details"]["changes"]["priority"]["new_value"] == ReminderPriority.URGENT.value


def test_update_reminder_status_logs_audit_event(db_session: Session, sample_user: User):
    from core.routers.reminders import update_reminder_status

    reminder = Reminder(
        title="Status reminder",
        due_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by_id=sample_user.id,
        assigned_to_id=sample_user.id,
        status=ReminderStatus.PENDING,
    )
    db_session.add(reminder)
    db_session.commit()
    db_session.refresh(reminder)

    status_data = ReminderStatusUpdate(status=ReminderStatus.COMPLETED, completion_notes="Done")

    with patch("core.routers.reminders.log_audit_event") as mock_log_audit_event:
        result = update_reminder_status(reminder_id=reminder.id, status_data=status_data, db=db_session, current_user=sample_user)

    assert result.status == ReminderStatus.COMPLETED
    mock_log_audit_event.assert_called_once()
    call_kwargs = mock_log_audit_event.call_args.kwargs
    assert call_kwargs["action"] == "UPDATE_STATUS"
    assert call_kwargs["details"]["status_change"]["old_value"] == ReminderStatus.PENDING.value
    assert call_kwargs["details"]["status_change"]["new_value"] == ReminderStatus.COMPLETED.value
    assert call_kwargs["details"]["completion_notes"] == "Done"


def test_unsnooze_reminder_logs_audit_event(db_session: Session, sample_user: User):
    from core.routers.reminders import unsnooze_reminder

    reminder = Reminder(
        title="Snoozed reminder",
        due_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by_id=sample_user.id,
        assigned_to_id=sample_user.id,
        status=ReminderStatus.SNOOZED,
        snoozed_until=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db_session.add(reminder)
    db_session.commit()
    db_session.refresh(reminder)

    with patch("core.routers.reminders.log_audit_event") as mock_log_audit_event:
        result = unsnooze_reminder(reminder_id=reminder.id, db=db_session, current_user=sample_user)

    assert result.status == ReminderStatus.PENDING
    mock_log_audit_event.assert_called_once()
    call_kwargs = mock_log_audit_event.call_args.kwargs
    assert call_kwargs["action"] == "UPDATE_STATUS"
    assert call_kwargs["details"]["operation"] == "unsnooze"
    assert call_kwargs["details"]["status_change"]["old_value"] == ReminderStatus.SNOOZED.value
    assert call_kwargs["details"]["status_change"]["new_value"] == ReminderStatus.PENDING.value


def test_reorder_reminders_logs_audit_events(db_session: Session, sample_user: User):
    from core.routers.reminders import reorder_reminders

    r1 = Reminder(title="R1", due_date=datetime.now(timezone.utc), created_by_id=sample_user.id, assigned_to_id=sample_user.id, position=1)
    r2 = Reminder(title="R2", due_date=datetime.now(timezone.utc), created_by_id=sample_user.id, assigned_to_id=sample_user.id, position=2)
    db_session.add_all([r1, r2])
    db_session.commit()

    reorder_data = ReorderReminders(reminder_ids=[r2.id, r1.id])

    with patch("core.routers.reminders.log_audit_event") as mock_log_audit_event:
        with patch("core.routers.reminders.check_reminder_permissions", return_value=None):
            reorder_reminders(reorder_data=reorder_data, db=db_session, current_user=sample_user)

    assert mock_log_audit_event.call_count == 2
    first_call = mock_log_audit_event.call_args_list[0].kwargs
    assert first_call["action"] == "REORDER"
    assert "position_change" in first_call["details"]


def test_toggle_reminder_pin_logs_audit_event(db_session: Session, sample_user: User):
    from core.routers.reminders import toggle_reminder_pin

    reminder = Reminder(
        title="Pin reminder",
        due_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by_id=sample_user.id,
        assigned_to_id=sample_user.id,
        is_pinned=False,
    )
    db_session.add(reminder)
    db_session.commit()
    db_session.refresh(reminder)

    with patch("core.routers.reminders.log_audit_event") as mock_log_audit_event:
        with patch("core.routers.reminders.check_reminder_permissions", return_value=None):
            result = toggle_reminder_pin(reminder_id=reminder.id, db=db_session, current_user=sample_user)

    assert result.is_pinned is True
    mock_log_audit_event.assert_called_once()
    call_kwargs = mock_log_audit_event.call_args.kwargs
    assert call_kwargs["action"] == "UPDATE"
    assert call_kwargs["details"]["operation"] == "toggle_pin"
    assert call_kwargs["details"]["pin_change"]["old_value"] is False
    assert call_kwargs["details"]["pin_change"]["new_value"] is True
