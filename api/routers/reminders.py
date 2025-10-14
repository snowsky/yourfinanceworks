from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

from models.database import get_db
from models.models_per_tenant import User, Reminder, ReminderNotification, RecurrencePattern, ReminderStatus, ReminderPriority
from models.models import MasterUser
from schemas.reminders import (
    ReminderCreate, ReminderUpdate, ReminderStatusUpdate, ReminderResponse, 
    ReminderWithUsers, ReminderList, ReminderFilter, BulkReminderUpdate, 
    BulkReminderResponse, ReminderNotificationResponse
)
from routers.auth import get_current_user
from utils.rbac import require_admin

router = APIRouter()

def check_reminder_permissions(reminder: Reminder, current_user: MasterUser, action: str = "access"):
    """
    Check if the current user has permission to perform an action on a reminder.
    Users can access reminders they created or are assigned to.
    Admins can access all reminders.
    """
    # Admins can do anything
    try:
        require_admin(current_user, f"{action} reminders")
        return  # Admin check passed
    except HTTPException:
        pass  # Not an admin, check user permissions

    # Users can access reminders they created or are assigned to
    if reminder.created_by_id != current_user.id and reminder.assigned_to_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to {action} this reminder"
        )

def calculate_next_due_date(due_date: datetime, pattern: RecurrencePattern, interval: int) -> Optional[datetime]:
    """Calculate the next due date for a recurring reminder"""
    if pattern == RecurrencePattern.NONE:
        return None
    
    if pattern == RecurrencePattern.DAILY:
        return due_date + timedelta(days=interval)
    elif pattern == RecurrencePattern.WEEKLY:
        return due_date + timedelta(weeks=interval)
    elif pattern == RecurrencePattern.MONTHLY:
        # Add months (approximate with 30 days for simplicity)
        return due_date + timedelta(days=30 * interval)
    elif pattern == RecurrencePattern.YEARLY:
        # Add years (approximate with 365 days)
        return due_date + timedelta(days=365 * interval)
    
    return None

@router.get("/", response_model=ReminderList)
def get_reminders(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[List[ReminderStatus]] = Query(None, description="Filter by status"),
    priority: Optional[List[ReminderPriority]] = Query(None, description="Filter by priority"),
    assigned_to_id: Optional[int] = Query(None, description="Filter by assigned user"),
    created_by_id: Optional[int] = Query(None, description="Filter by creator"),
    due_date_from: Optional[datetime] = Query(None, description="Filter by due date from"),
    due_date_to: Optional[datetime] = Query(None, description="Filter by due date to"),
    search: Optional[str] = Query(None, max_length=100, description="Search in title and description"),
    sort_by: str = Query("due_date", description="Sort by field"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get paginated list of reminders with filtering and sorting"""
    
    # Base query with joins for user information
    query = db.query(Reminder).options(
        joinedload(Reminder.created_by),
        joinedload(Reminder.assigned_to),
        joinedload(Reminder.completed_by)
    ).filter(Reminder.is_deleted == False)

    # Apply permission filters - users can only see reminders they created or are assigned to
    # Admins can see all reminders
    try:
        require_admin(current_user, "view all reminders")
    except HTTPException:
        # Not an admin, filter to only user's reminders
        query = query.filter(
            or_(
                Reminder.created_by_id == current_user.id,
                Reminder.assigned_to_id == current_user.id
            )
        )

    # Apply filters
    if status:
        query = query.filter(Reminder.status.in_(status))
    
    if priority:
        query = query.filter(Reminder.priority.in_(priority))
    
    if assigned_to_id:
        query = query.filter(Reminder.assigned_to_id == assigned_to_id)
    
    if created_by_id:
        query = query.filter(Reminder.created_by_id == created_by_id)
    
    if due_date_from:
        query = query.filter(Reminder.due_date >= due_date_from)
    
    if due_date_to:
        query = query.filter(Reminder.due_date <= due_date_to)
    
    if search:
        search_filter = or_(
            Reminder.title.ilike(f"%{search}%"),
            Reminder.description.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Apply sorting
    if sort_order == "desc":
        if sort_by == "due_date":
            query = query.order_by(desc(Reminder.due_date))
        elif sort_by == "created_at":
            query = query.order_by(desc(Reminder.created_at))
        elif sort_by == "priority":
            # Order by priority: URGENT, HIGH, MEDIUM, LOW
            priority_order = func.case(
                (Reminder.priority == ReminderPriority.URGENT, 1),
                (Reminder.priority == ReminderPriority.HIGH, 2),
                (Reminder.priority == ReminderPriority.MEDIUM, 3),
                (Reminder.priority == ReminderPriority.LOW, 4),
                else_=5
            )
            query = query.order_by(desc(priority_order))
    else:
        if sort_by == "due_date":
            query = query.order_by(asc(Reminder.due_date))
        elif sort_by == "created_at":
            query = query.order_by(asc(Reminder.created_at))
        elif sort_by == "priority":
            priority_order = func.case(
                (Reminder.priority == ReminderPriority.URGENT, 1),
                (Reminder.priority == ReminderPriority.HIGH, 2),
                (Reminder.priority == ReminderPriority.MEDIUM, 3),
                (Reminder.priority == ReminderPriority.LOW, 4),
                else_=5
            )
            query = query.order_by(asc(priority_order))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page).all()
    
    return ReminderList(
        items=[ReminderWithUsers.model_validate(item) for item in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page)
    )

@router.get("/{reminder_id}", response_model=ReminderWithUsers)
def get_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get a specific reminder by ID"""

    reminder = db.query(Reminder).options(
        joinedload(Reminder.created_by),
        joinedload(Reminder.assigned_to),
        joinedload(Reminder.completed_by)
    ).filter(
        Reminder.id == reminder_id,
        Reminder.is_deleted == False
    ).first()

    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )

    # Check permissions
    check_reminder_permissions(reminder, current_user, "view")

    return ReminderWithUsers.model_validate(reminder)

@router.post("/", response_model=ReminderWithUsers, status_code=status.HTTP_201_CREATED)
def create_reminder(
    reminder_data: ReminderCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Create a new reminder"""
    
    # Verify assigned user exists in the current tenant
    assigned_user = db.query(User).filter(User.id == reminder_data.assigned_to_id).first()
    if not assigned_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assigned user not found"
        )
    
    # Calculate next due date for recurring reminders
    next_due_date = None
    if reminder_data.recurrence_pattern != RecurrencePattern.NONE:
        next_due_date = calculate_next_due_date(
            reminder_data.due_date,
            reminder_data.recurrence_pattern,
            reminder_data.recurrence_interval
        )
    
    # Create reminder
    reminder = Reminder(
        title=reminder_data.title,
        description=reminder_data.description,
        due_date=reminder_data.due_date,
        next_due_date=next_due_date,
        recurrence_pattern=reminder_data.recurrence_pattern,
        recurrence_interval=reminder_data.recurrence_interval,
        recurrence_end_date=reminder_data.recurrence_end_date,
        priority=reminder_data.priority,
        created_by_id=current_user.id,
        assigned_to_id=reminder_data.assigned_to_id,
        tags=reminder_data.tags,
        extra_metadata=reminder_data.extra_metadata
    )
    
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    
    # Create immediate notification if reminder is due soon (within 1 hour)
    now = datetime.now(timezone.utc)
    time_until_due = (reminder.due_date - now).total_seconds()
    if 0 < time_until_due <= 3600:  # Due within next hour
        notification = ReminderNotification(
            reminder_id=reminder.id,
            user_id=reminder.assigned_to_id,
            notification_type="due",
            channel="in_app",
            scheduled_for=reminder.due_date,
            subject=f"Reminder Due: {reminder.title}",
            message=f"Your reminder '{reminder.title}' is due soon.",
            is_sent=True,
            sent_at=now
        )
        db.add(notification)
        db.commit()
    
    # Load relationships for response
    reminder = db.query(Reminder).options(
        joinedload(Reminder.created_by),
        joinedload(Reminder.assigned_to),
        joinedload(Reminder.completed_by)
    ).filter(Reminder.id == reminder.id).first()
    
    return ReminderWithUsers.model_validate(reminder)

@router.put("/{reminder_id}", response_model=ReminderWithUsers)
def update_reminder(
    reminder_id: int,
    reminder_data: ReminderUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update an existing reminder"""

    reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.is_deleted == False
    ).first()

    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )

    # Check permissions
    check_reminder_permissions(reminder, current_user, "update")
    
    # Update fields
    update_data = reminder_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "assigned_to_id" and value:
            # Verify assigned user exists
            assigned_user = db.query(User).filter(User.id == value).first()
            if not assigned_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Assigned user not found"
                )
        
        setattr(reminder, field, value)
    
    # Recalculate next due date if recurrence changed
    if "recurrence_pattern" in update_data or "recurrence_interval" in update_data or "due_date" in update_data:
        if reminder.recurrence_pattern != RecurrencePattern.NONE:
            reminder.next_due_date = calculate_next_due_date(
                reminder.due_date,
                reminder.recurrence_pattern,
                reminder.recurrence_interval
            )
        else:
            reminder.next_due_date = None
    
    db.commit()
    db.refresh(reminder)
    
    # Load relationships for response
    reminder = db.query(Reminder).options(
        joinedload(Reminder.created_by),
        joinedload(Reminder.assigned_to),
        joinedload(Reminder.completed_by)
    ).filter(Reminder.id == reminder.id).first()
    
    return ReminderWithUsers.model_validate(reminder)

@router.patch("/{reminder_id}/status", response_model=ReminderWithUsers)
def update_reminder_status(
    reminder_id: int,
    status_data: ReminderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update reminder status (complete, snooze, etc.)"""
    
    reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.is_deleted == False
    ).first()
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    # Check permissions (assigned user or creator can update status)
    if (reminder.assigned_to_id != current_user.id and
        reminder.created_by_id != current_user.id):
        try:
            require_admin(current_user, "update this reminder status")
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this reminder status"
            )
    
    # Update status
    reminder.status = status_data.status
    
    if status_data.status == ReminderStatus.COMPLETED:
        reminder.completed_at = datetime.now(timezone.utc)
        reminder.completed_by_id = current_user.id
        reminder.completion_notes = status_data.completion_notes
        reminder.snoozed_until = None
        
        # Create next recurring instance if applicable
        if (reminder.recurrence_pattern != RecurrencePattern.NONE and 
            reminder.next_due_date and
            (not reminder.recurrence_end_date or reminder.next_due_date <= reminder.recurrence_end_date)):
            
            next_reminder = Reminder(
                title=reminder.title,
                description=reminder.description,
                due_date=reminder.next_due_date,
                next_due_date=calculate_next_due_date(
                    reminder.next_due_date,
                    reminder.recurrence_pattern,
                    reminder.recurrence_interval
                ),
                recurrence_pattern=reminder.recurrence_pattern,
                recurrence_interval=reminder.recurrence_interval,
                recurrence_end_date=reminder.recurrence_end_date,
                priority=reminder.priority,
                created_by_id=reminder.created_by_id,
                assigned_to_id=reminder.assigned_to_id,
                tags=reminder.tags,
                extra_metadata=reminder.extra_metadata
            )
            db.add(next_reminder)
    
    elif status_data.status == ReminderStatus.SNOOZED:
        if not status_data.snoozed_until:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Snoozed_until is required when snoozing a reminder"
            )
        reminder.snoozed_until = status_data.snoozed_until
        reminder.snooze_count += 1
        reminder.completed_at = None
        reminder.completed_by_id = None
    
    else:
        # Reset completion fields for other statuses
        reminder.completed_at = None
        reminder.completed_by_id = None
        reminder.completion_notes = None
        reminder.snoozed_until = None
    
    db.commit()
    db.refresh(reminder)
    
    # Load relationships for response
    reminder = db.query(Reminder).options(
        joinedload(Reminder.created_by),
        joinedload(Reminder.assigned_to),
        joinedload(Reminder.completed_by)
    ).filter(Reminder.id == reminder.id).first()
    
    return ReminderWithUsers.model_validate(reminder)

@router.post("/{reminder_id}/unsnooze", response_model=ReminderWithUsers)
def unsnooze_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Unsnooze a reminder (set status back to pending)"""
    
    reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.is_deleted == False
    ).first()
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    # Check permissions (assigned user or creator can unsnooze)
    if (reminder.assigned_to_id != current_user.id and
        reminder.created_by_id != current_user.id):
        try:
            require_admin(current_user, "unsnooze this reminder")
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to unsnooze this reminder"
            )
    
    # Only allow unsnoozing if currently snoozed
    if reminder.status != ReminderStatus.SNOOZED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reminder is not currently snoozed"
        )
    
    # Unsnooze the reminder
    reminder.status = ReminderStatus.PENDING
    reminder.snoozed_until = None
    
    db.commit()
    db.refresh(reminder)
    
    # Load relationships for response
    reminder = db.query(Reminder).options(
        joinedload(Reminder.created_by),
        joinedload(Reminder.assigned_to),
        joinedload(Reminder.completed_by)
    ).filter(Reminder.id == reminder.id).first()
    
    return ReminderWithUsers.model_validate(reminder)

@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Soft delete a reminder"""

    reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.is_deleted == False
    ).first()

    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )

    # Check permissions
    check_reminder_permissions(reminder, current_user, "delete")
    
    # Soft delete
    reminder.is_deleted = True
    reminder.deleted_at = datetime.now(timezone.utc)
    reminder.deleted_by_id = current_user.id
    
    db.commit()

@router.post("/bulk-update", response_model=BulkReminderResponse)
def bulk_update_reminders(
    bulk_data: BulkReminderUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Bulk update multiple reminders"""
    
    reminders = db.query(Reminder).filter(
        Reminder.id.in_(bulk_data.reminder_ids),
        Reminder.is_deleted == False
    ).all()
    
    if not reminders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reminders found"
        )
    
    updated_count = 0
    failed_count = 0
    errors = []
    
    for reminder in reminders:
        try:
            # Check permissions
            check_reminder_permissions(reminder, current_user, "update")

            # Apply updates
            update_data = bulk_data.model_dump(exclude_unset=True, exclude={"reminder_ids"})

            for field, value in update_data.items():
                if field == "assigned_to_id" and value is not None:
                    # Verify assigned user exists in the current tenant
                    assigned_user = db.query(User).filter(User.id == value).first()
                    if not assigned_user:
                        failed_count += 1
                        errors.append(f"Assigned user not found for reminder {reminder.id}")
                        continue

                setattr(reminder, field, value)
            
            updated_count += 1
            
        except Exception as e:
            failed_count += 1
            errors.append(f"Error updating reminder {reminder.id}: {str(e)}")
    
    db.commit()
    
    return BulkReminderResponse(
        updated_count=updated_count,
        failed_count=failed_count,
        errors=errors
    )

@router.get("/{reminder_id}/notifications", response_model=List[ReminderNotificationResponse])
def get_reminder_notifications(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get notifications for a specific reminder"""
    
    reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.is_deleted == False
    ).first()
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    notifications = db.query(ReminderNotification).filter(
        ReminderNotification.reminder_id == reminder_id
    ).order_by(desc(ReminderNotification.scheduled_for)).all()
    
    return [ReminderNotificationResponse.model_validate(notif) for notif in notifications]

@router.get("/due/today", response_model=List[ReminderWithUsers])
def get_due_today(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get reminders due today for the current user"""
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    reminders = db.query(Reminder).options(
        joinedload(Reminder.created_by),
        joinedload(Reminder.assigned_to),
        joinedload(Reminder.completed_by)
    ).filter(
        Reminder.assigned_to_id == current_user.id,
        Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SNOOZED]),
        Reminder.due_date >= today_start,
        Reminder.due_date < today_end,
        Reminder.is_deleted == False
    ).order_by(asc(Reminder.due_date)).all()
    
    return [ReminderWithUsers.model_validate(reminder) for reminder in reminders]

@router.get("/overdue/", response_model=List[ReminderWithUsers])
def get_overdue_reminders(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get overdue reminders for the current user"""

    now = datetime.now(timezone.utc)

    reminders = db.query(Reminder).options(
        joinedload(Reminder.created_by),
        joinedload(Reminder.assigned_to),
        joinedload(Reminder.completed_by)
    ).filter(
        Reminder.assigned_to_id == current_user.id,
        Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SNOOZED]),
        Reminder.due_date < now,
        or_(
            Reminder.snoozed_until.is_(None),
            Reminder.snoozed_until < now
        ),
        Reminder.is_deleted == False
    ).order_by(asc(Reminder.due_date)).all()

    return [ReminderWithUsers.model_validate(reminder) for reminder in reminders]


# --- Notification Management Endpoints ---

class NotificationCountResponse(BaseModel):
    count: int

class NotificationWithReminder(BaseModel):
    id: int
    reminder_id: int
    user_id: int
    notification_type: str
    channel: str
    scheduled_for: datetime
    subject: Optional[str] = None
    message: Optional[str] = None
    sent_at: Optional[datetime] = None
    is_sent: bool = False
    is_read: bool = False
    send_attempts: int = 0
    last_attempt_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    reminder: dict

class NotificationsListResponse(BaseModel):
    items: List[NotificationWithReminder]

@router.get("/notifications/unread-count", response_model=NotificationCountResponse)
def get_unread_notification_count(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get count of unread notifications for the current user"""

    count = db.query(func.count(ReminderNotification.id)).filter(
        ReminderNotification.user_id == current_user.id,
        ReminderNotification.is_sent == True,
        ReminderNotification.is_read == False
    ).scalar()

    return NotificationCountResponse(count=count or 0)

@router.get("/notifications/recent")
def get_recent_notifications(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of notifications to return"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get recent notifications for the current user"""

    notifications = db.query(ReminderNotification).join(
        Reminder, ReminderNotification.reminder_id == Reminder.id
    ).filter(
        ReminderNotification.user_id == current_user.id,
        ReminderNotification.is_sent == True,
        Reminder.is_deleted == False
    ).order_by(desc(ReminderNotification.scheduled_for)).limit(limit).all()

    items = []
    for notif in notifications:
        reminder = db.query(Reminder).filter(Reminder.id == notif.reminder_id).first()
        if reminder:
            items.append({
                "id": notif.id,
                "reminder_id": notif.reminder_id,
                "user_id": notif.user_id,
                "notification_type": notif.notification_type,
                "channel": notif.channel,
                "scheduled_for": notif.scheduled_for.isoformat(),
                "subject": notif.subject,
                "message": notif.message,
                "sent_at": notif.sent_at.isoformat() if notif.sent_at else None,
                "is_sent": notif.is_sent,
                "is_read": notif.is_read,
                "send_attempts": notif.send_attempts,
                "last_attempt_at": notif.last_attempt_at.isoformat() if notif.last_attempt_at else None,
                "error_message": notif.error_message,
                "created_at": notif.created_at.isoformat(),
                "updated_at": notif.updated_at.isoformat(),
                "reminder": {
                    "id": reminder.id,
                    "title": reminder.title,
                    "description": reminder.description,
                    "due_date": reminder.due_date.isoformat(),
                    "priority": reminder.priority.value,
                    "status": reminder.status.value
                }
            })

    return {"items": items}

@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_200_OK)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Mark a specific notification as read"""

    notification = db.query(ReminderNotification).filter(
        ReminderNotification.id == notification_id,
        ReminderNotification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.is_read = True
    db.commit()

    return {"message": "Notification marked as read"}

@router.post("/notifications/mark-all-read", status_code=status.HTTP_200_OK)
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Mark all notifications as read for the current user"""

    db.query(ReminderNotification).filter(
        ReminderNotification.user_id == current_user.id,
        ReminderNotification.is_sent == True,
        ReminderNotification.is_read == False
    ).update({"is_read": True})

    db.commit()

    return {"message": "All notifications marked as read"}

@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Dismiss (soft delete) a notification"""

    notification = db.query(ReminderNotification).filter(
        ReminderNotification.id == notification_id,
        ReminderNotification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    # Instead of hard deleting, we could add a dismissed field, but for now just return success
    # The frontend will handle removing it from the UI
    return
