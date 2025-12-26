"""
Reminder Scheduler Service

This service handles the scheduling and automated processing of reminders.
It supports checking for due reminders, sending notifications, and creating recurring instances.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from core.models.models_per_tenant import (
    Reminder, ReminderNotification, User, RecurrencePattern, ReminderStatus
)
from core.services.notification_service import NotificationService
from core.utils.notifications import get_notification_service

logger = logging.getLogger(__name__)


class ReminderSchedulerError(Exception):
    """Custom exception for reminder scheduler errors"""
    pass


class ReminderScheduler:
    """
    Service for managing scheduled reminders and automated reminder processing.

    Features:
    - Check for due and overdue reminders
    - Send email and in-app notifications
    - Create recurring reminder instances
    - Handle reminder state transitions
    """

    def __init__(self, db: Session):
        self.db = db
        self.notification_service = get_notification_service(db)

    def calculate_next_due_date(
        self, 
        due_date: datetime, 
        pattern: RecurrencePattern, 
        interval: int
    ) -> Optional[datetime]:
        """Calculate the next due date for a recurring reminder"""
        if pattern == RecurrencePattern.NONE:
            return None

        if pattern == RecurrencePattern.DAILY:
            return due_date + timedelta(days=interval)
        elif pattern == RecurrencePattern.WEEKLY:
            return due_date + timedelta(weeks=interval)
        elif pattern == RecurrencePattern.MONTHLY:
            # Handle monthly recurrence more accurately
            try:
                if due_date.month == 12:
                    next_month = due_date.replace(year=due_date.year + 1, month=1)
                else:
                    next_month = due_date.replace(month=due_date.month + interval)
                return next_month
            except ValueError:
                # Handle edge cases like Feb 29 -> Feb 28
                return due_date + timedelta(days=30 * interval)
        elif pattern == RecurrencePattern.YEARLY:
            try:
                return due_date.replace(year=due_date.year + interval)
            except ValueError:
                # Handle leap year edge case
                return due_date + timedelta(days=365 * interval)

        return None

    def process_due_reminders(self, company_name: str = "Invoice Management System") -> Dict[str, Any]:
        """
        Process all due reminders and send notifications.

        Returns:
            Dict with processing statistics
        """
        try:
            now = datetime.now(timezone.utc)

            # Find due reminders (including snoozed ones that are no longer snoozed)
            due_reminders = self.db.query(Reminder).options(
                joinedload(Reminder.assigned_to),
                joinedload(Reminder.created_by)
            ).filter(
                Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SNOOZED]),
                Reminder.due_date <= now,
                or_(
                    Reminder.snoozed_until.is_(None),
                    Reminder.snoozed_until <= now
                ),
                Reminder.is_deleted == False
            ).all()

            stats = {
                "total_due": len(due_reminders),
                "notifications_sent": 0,
                "recurring_created": 0,
                "errors": []
            }

            for reminder in due_reminders:
                try:
                    # Send notification if not already sent today
                    if self._should_send_notification(reminder, now):
                        self._send_reminder_notification(
                            reminder, 
                            "due" if reminder.due_date.date() == now.date() else "overdue",
                            company_name
                        )
                        stats["notifications_sent"] += 1

                    # Reset snooze status if snoozed_until has passed
                    if (reminder.status == ReminderStatus.SNOOZED and 
                        reminder.snoozed_until and 
                        reminder.snoozed_until <= now):
                        reminder.status = ReminderStatus.PENDING
                        reminder.snoozed_until = None

                except Exception as e:
                    error_msg = f"Error processing reminder {reminder.id}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            # Process completed recurring reminders
            completed_recurring = self.db.query(Reminder).filter(
                Reminder.status == ReminderStatus.COMPLETED,
                Reminder.recurrence_pattern != RecurrencePattern.NONE,
                Reminder.next_due_date.isnot(None),
                or_(
                    Reminder.recurrence_end_date.is_(None),
                    Reminder.next_due_date <= Reminder.recurrence_end_date
                ),
                Reminder.is_deleted == False
            ).all()

            for reminder in completed_recurring:
                try:
                    # Create next recurring instance
                    self._create_recurring_instance(reminder)
                    stats["recurring_created"] += 1
                except Exception as e:
                    error_msg = f"Error creating recurring instance for reminder {reminder.id}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            self.db.commit()
            return stats

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in process_due_reminders: {str(e)}")
            raise ReminderSchedulerError(f"Failed to process due reminders: {str(e)}")

    def send_upcoming_reminders(
        self, 
        advance_days: int = 1,
        company_name: str = "Invoice Management System"
    ) -> Dict[str, Any]:
        """
        Send notifications for reminders that are due in the near future.

        Args:
            advance_days: How many days in advance to send notifications
            company_name: Company name for notifications

        Returns:
            Dict with processing statistics
        """
        try:
            now = datetime.now(timezone.utc)
            future_date = now + timedelta(days=advance_days)

            # Find upcoming reminders
            upcoming_reminders = self.db.query(Reminder).options(
                joinedload(Reminder.assigned_to),
                joinedload(Reminder.created_by)
            ).filter(
                Reminder.status == ReminderStatus.PENDING,
                Reminder.due_date > now,
                Reminder.due_date <= future_date,
                Reminder.is_deleted == False
            ).all()

            stats = {
                "total_upcoming": len(upcoming_reminders),
                "notifications_sent": 0,
                "errors": []
            }

            for reminder in upcoming_reminders:
                try:
                    # Check if we already sent an upcoming notification
                    if not self._has_recent_notification(reminder, "upcoming", hours=24):
                        self._send_reminder_notification(reminder, "upcoming", company_name)
                        stats["notifications_sent"] += 1
                        
                except Exception as e:
                    error_msg = f"Error sending upcoming notification for reminder {reminder.id}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            self.db.commit()
            return stats

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in send_upcoming_reminders: {str(e)}")
            raise ReminderSchedulerError(f"Failed to send upcoming reminders: {str(e)}")

    def _should_send_notification(self, reminder: Reminder, now: datetime) -> bool:
        """Check if we should send a notification for this reminder"""
        # Don't send more than once per day for the same reminder
        return not self._has_recent_notification(reminder, "due", hours=24)

    def _has_recent_notification(
        self, 
        reminder: Reminder, 
        notification_type: str, 
        hours: int = 24
    ) -> bool:
        """Check if a notification was sent recently"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent_notification = self.db.query(ReminderNotification).filter(
            ReminderNotification.reminder_id == reminder.id,
            ReminderNotification.user_id == reminder.assigned_to_id,
            ReminderNotification.notification_type == notification_type,
            ReminderNotification.sent_at > cutoff_time,
            ReminderNotification.is_sent == True
        ).first()

        return recent_notification is not None

    def _send_reminder_notification(
        self, 
        reminder: Reminder, 
        notification_type: str,
        company_name: str
    ) -> bool:
        """Send a notification for a reminder"""
        try:
            # Create notification record
            now = datetime.now(timezone.utc)

            # Determine notification subject and message
            if notification_type == "due":
                subject = f"Reminder Due: {reminder.title}"
                message = f"Your reminder '{reminder.title}' is due today."
            elif notification_type == "overdue":
                days_overdue = (now.date() - reminder.due_date.date()).days
                subject = f"Overdue Reminder: {reminder.title}"
                message = f"Your reminder '{reminder.title}' is {days_overdue} day(s) overdue."
            elif notification_type == "upcoming":
                days_until = (reminder.due_date.date() - now.date()).days
                subject = f"Upcoming Reminder: {reminder.title}"
                message = f"Your reminder '{reminder.title}' is due in {days_until} day(s)."
            else:
                subject = f"Reminder: {reminder.title}"
                message = f"You have a reminder: {reminder.title}"

            if reminder.description:
                message += f"\n\nDescription: {reminder.description}"

            # Create notification record
            notification = ReminderNotification(
                reminder_id=reminder.id,
                user_id=reminder.assigned_to_id,
                notification_type=notification_type,
                channel="email",  # TODO: Make this configurable
                scheduled_for=now,
                subject=subject,
                message=message
            )

            self.db.add(notification)
            self.db.flush()  # Get the ID

            # Send via notification service if available
            if self.notification_service:
                details = {
                    "reminder_id": reminder.id,
                    "due_date": reminder.due_date.isoformat(),
                    "priority": reminder.priority.value,
                    "description": reminder.description or "",
                    "created_by": reminder.created_by.email if reminder.created_by else "",
                }

                success = self.notification_service.send_operation_notification(
                    event_type=f"reminder_{notification_type}",
                    user_id=reminder.assigned_to_id,
                    resource_type="reminder",
                    resource_id=str(reminder.id),
                    resource_name=reminder.title,
                    details=details,
                    company_name=company_name
                )

                if success:
                    notification.is_sent = True
                    notification.sent_at = now
                else:
                    notification.send_attempts += 1
                    notification.last_attempt_at = now
                    notification.error_message = "Failed to send via notification service"
            else:
                # Mark as sent even if no service available (for testing)
                notification.is_sent = True
                notification.sent_at = now
                logger.info(f"No notification service available, marking as sent")

            return notification.is_sent

        except Exception as e:
            logger.error(f"Failed to send reminder notification: {str(e)}")
            return False

    def _create_recurring_instance(self, completed_reminder: Reminder) -> Optional[Reminder]:
        """Create the next instance of a recurring reminder"""
        try:
            if (not completed_reminder.next_due_date or 
                completed_reminder.recurrence_pattern == RecurrencePattern.NONE):
                return None

            # Check if we should stop recurring (end date reached)
            if (completed_reminder.recurrence_end_date and 
                completed_reminder.next_due_date > completed_reminder.recurrence_end_date):
                return None

            # Calculate the next due date after this instance
            next_next_due = self.calculate_next_due_date(
                completed_reminder.next_due_date,
                completed_reminder.recurrence_pattern,
                completed_reminder.recurrence_interval
            )

            # Create new reminder instance
            new_reminder = Reminder(
                title=completed_reminder.title,
                description=completed_reminder.description,
                due_date=completed_reminder.next_due_date,
                next_due_date=next_next_due,
                recurrence_pattern=completed_reminder.recurrence_pattern,
                recurrence_interval=completed_reminder.recurrence_interval,
                recurrence_end_date=completed_reminder.recurrence_end_date,
                priority=completed_reminder.priority,
                status=ReminderStatus.PENDING,
                created_by_id=completed_reminder.created_by_id,
                assigned_to_id=completed_reminder.assigned_to_id,
                tags=completed_reminder.tags,
                extra_metadata=completed_reminder.extra_metadata
            )

            self.db.add(new_reminder)
            self.db.flush()

            logger.info(f"Created recurring instance {new_reminder.id} from reminder {completed_reminder.id}")
            return new_reminder

        except Exception as e:
            logger.error(f"Failed to create recurring instance: {str(e)}")
            return None

    def cleanup_old_notifications(self, days_old: int = 30) -> int:
        """Clean up old notification records"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

            deleted_count = self.db.query(ReminderNotification).filter(
                ReminderNotification.created_at < cutoff_date,
                ReminderNotification.is_sent == True
            ).delete()

            self.db.commit()
            logger.info(f"Cleaned up {deleted_count} old reminder notifications")
            return deleted_count

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to cleanup old notifications: {str(e)}")
            return 0

    def get_reminder_statistics(self) -> Dict[str, Any]:
        """Get statistics about reminders"""
        try:
            now = datetime.now(timezone.utc)

            # Count reminders by status
            total_active = self.db.query(Reminder).filter(
                Reminder.is_deleted == False
            ).count()

            pending = self.db.query(Reminder).filter(
                Reminder.status == ReminderStatus.PENDING,
                Reminder.is_deleted == False
            ).count()

            overdue = self.db.query(Reminder).filter(
                Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SNOOZED]),
                Reminder.due_date < now,
                or_(
                    Reminder.snoozed_until.is_(None),
                    Reminder.snoozed_until < now
                ),
                Reminder.is_deleted == False
            ).count()

            due_today = self.db.query(Reminder).filter(
                Reminder.status == ReminderStatus.PENDING,
                Reminder.due_date >= now.replace(hour=0, minute=0, second=0, microsecond=0),
                Reminder.due_date < now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
                Reminder.is_deleted == False
            ).count()

            completed_today = self.db.query(Reminder).filter(
                Reminder.status == ReminderStatus.COMPLETED,
                Reminder.completed_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
                Reminder.is_deleted == False
            ).count()

            return {
                "total_active": total_active,
                "pending": pending,
                "overdue": overdue,
                "due_today": due_today,
                "completed_today": completed_today,
                "last_updated": now.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get reminder statistics: {str(e)}")
            return {
                "error": str(e),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
