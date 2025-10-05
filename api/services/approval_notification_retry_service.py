"""
Approval Notification Retry Service

This service handles retry logic for failed approval notifications,
implementing exponential backoff and dead letter queue patterns.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from models.models_per_tenant import User, ExpenseApproval
from services.notification_service import NotificationService
from exceptions.approval_exceptions import NotificationDeliveryError, ApprovalServiceError

logger = logging.getLogger(__name__)


class NotificationRetryRecord:
    """Record for tracking notification retry attempts"""
    
    def __init__(
        self,
        notification_id: str,
        notification_type: str,
        recipient_id: int,
        approval_id: int,
        payload: Dict[str, Any],
        max_retries: int = 5,
        retry_count: int = 0,
        next_retry_at: Optional[datetime] = None,
        last_error: Optional[str] = None,
        created_at: Optional[datetime] = None
    ):
        self.notification_id = notification_id
        self.notification_type = notification_type
        self.recipient_id = recipient_id
        self.approval_id = approval_id
        self.payload = payload
        self.max_retries = max_retries
        self.retry_count = retry_count
        self.next_retry_at = next_retry_at or datetime.now(timezone.utc)
        self.last_error = last_error
        self.created_at = created_at or datetime.now(timezone.utc)
        self.is_dead_letter = retry_count >= max_retries


class ApprovalNotificationRetryService:
    """
    Service for handling retry logic for failed approval notifications.
    
    This service implements:
    - Exponential backoff retry strategy
    - Dead letter queue for permanently failed notifications
    - Retry attempt tracking and logging
    - Notification payload validation
    - Circuit breaker pattern for repeated failures
    """
    
    def __init__(self, db: Session, notification_service: NotificationService):
        self.db = db
        self.notification_service = notification_service
        self.retry_records: Dict[str, NotificationRetryRecord] = {}
        self.circuit_breaker_failures: Dict[int, int] = {}  # user_id -> failure_count
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_reset_time = timedelta(hours=1)
        
        # Retry configuration
        self.base_retry_delay = timedelta(minutes=5)  # Start with 5 minutes
        self.max_retry_delay = timedelta(hours=4)     # Cap at 4 hours
        self.backoff_multiplier = 2.0
        self.max_retries = 5
    
    def schedule_notification_retry(
        self,
        notification_type: str,
        recipient_id: int,
        approval_id: int,
        payload: Dict[str, Any],
        error_message: str,
        retry_count: int = 0
    ) -> str:
        """
        Schedule a notification for retry.
        
        Args:
            notification_type: Type of notification (e.g., "expense_submitted_for_approval")
            recipient_id: ID of the notification recipient
            approval_id: ID of the related approval
            payload: Notification payload data
            error_message: Error message from the failed attempt
            retry_count: Current retry count
            
        Returns:
            Notification ID for tracking
            
        Raises:
            ApprovalServiceError: If scheduling fails
        """
        try:
            # Generate unique notification ID
            notification_id = f"{notification_type}_{approval_id}_{recipient_id}_{int(datetime.now().timestamp())}"
            
            # Calculate next retry time using exponential backoff
            next_retry_at = self._calculate_next_retry_time(retry_count)
            
            # Create retry record
            retry_record = NotificationRetryRecord(
                notification_id=notification_id,
                notification_type=notification_type,
                recipient_id=recipient_id,
                approval_id=approval_id,
                payload=payload,
                max_retries=self.max_retries,
                retry_count=retry_count,
                next_retry_at=next_retry_at,
                last_error=error_message
            )
            
            # Store retry record
            self.retry_records[notification_id] = retry_record
            
            logger.info(
                f"Scheduled notification retry {notification_id} for user {recipient_id}, "
                f"attempt {retry_count + 1}/{self.max_retries}, next retry at {next_retry_at}"
            )
            
            return notification_id
            
        except Exception as e:
            logger.error(f"Failed to schedule notification retry: {str(e)}")
            raise ApprovalServiceError(
                operation="schedule_notification_retry",
                reason=str(e)
            )
    
    def process_retry_queue(self) -> Dict[str, Any]:
        """
        Process all pending notification retries.
        
        Returns:
            Dictionary with retry processing statistics
        """
        now = datetime.now(timezone.utc)
        processed_count = 0
        success_count = 0
        failed_count = 0
        dead_letter_count = 0
        
        # Get notifications ready for retry
        ready_notifications = [
            record for record in self.retry_records.values()
            if record.next_retry_at <= now and not record.is_dead_letter
        ]
        
        logger.info(f"Processing {len(ready_notifications)} notifications ready for retry")
        
        for record in ready_notifications:
            processed_count += 1
            
            try:
                # Check circuit breaker
                if self._is_circuit_breaker_open(record.recipient_id):
                    logger.warning(
                        f"Circuit breaker open for user {record.recipient_id}, "
                        f"skipping notification {record.notification_id}"
                    )
                    # Reschedule for later
                    record.next_retry_at = now + timedelta(hours=1)
                    continue
                
                # Attempt to send notification
                success = self._attempt_notification_delivery(record)
                
                if success:
                    success_count += 1
                    # Remove from retry queue
                    del self.retry_records[record.notification_id]
                    # Reset circuit breaker failure count
                    self.circuit_breaker_failures.pop(record.recipient_id, None)
                    
                    logger.info(
                        f"Successfully delivered notification {record.notification_id} "
                        f"after {record.retry_count + 1} attempts"
                    )
                else:
                    failed_count += 1
                    record.retry_count += 1
                    
                    if record.retry_count >= record.max_retries:
                        # Move to dead letter queue
                        record.is_dead_letter = True
                        dead_letter_count += 1
                        self._handle_dead_letter_notification(record)
                        
                        logger.error(
                            f"Notification {record.notification_id} moved to dead letter queue "
                            f"after {record.retry_count} failed attempts"
                        )
                    else:
                        # Schedule next retry
                        record.next_retry_at = self._calculate_next_retry_time(record.retry_count)
                        
                        logger.warning(
                            f"Notification {record.notification_id} failed, "
                            f"retry {record.retry_count}/{record.max_retries} scheduled for {record.next_retry_at}"
                        )
                
            except Exception as e:
                logger.error(
                    f"Error processing notification retry {record.notification_id}: {str(e)}"
                )
                failed_count += 1
                
                # Increment circuit breaker failure count
                self.circuit_breaker_failures[record.recipient_id] = (
                    self.circuit_breaker_failures.get(record.recipient_id, 0) + 1
                )
        
        # Clean up old dead letter records (older than 7 days)
        self._cleanup_old_dead_letters()
        
        stats = {
            "processed_count": processed_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "dead_letter_count": dead_letter_count,
            "pending_retries": len([r for r in self.retry_records.values() if not r.is_dead_letter]),
            "dead_letters": len([r for r in self.retry_records.values() if r.is_dead_letter])
        }
        
        logger.info(f"Retry queue processing completed: {stats}")
        return stats
    
    def get_retry_status(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """
        Get retry status for a specific notification.
        
        Args:
            notification_id: ID of the notification
            
        Returns:
            Dictionary with retry status information or None if not found
        """
        record = self.retry_records.get(notification_id)
        if not record:
            return None
        
        return {
            "notification_id": record.notification_id,
            "notification_type": record.notification_type,
            "recipient_id": record.recipient_id,
            "approval_id": record.approval_id,
            "retry_count": record.retry_count,
            "max_retries": record.max_retries,
            "next_retry_at": record.next_retry_at.isoformat() if record.next_retry_at else None,
            "is_dead_letter": record.is_dead_letter,
            "last_error": record.last_error,
            "created_at": record.created_at.isoformat()
        }
    
    def get_user_notification_failures(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get notification failures for a specific user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of failed notification records for the user
        """
        user_failures = [
            self.get_retry_status(record.notification_id)
            for record in self.retry_records.values()
            if record.recipient_id == user_id
        ]
        
        return [failure for failure in user_failures if failure is not None]
    
    def cancel_notification_retries(self, approval_id: int) -> int:
        """
        Cancel all pending retries for a specific approval.
        
        Args:
            approval_id: ID of the approval
            
        Returns:
            Number of cancelled retries
        """
        cancelled_count = 0
        to_remove = []
        
        for notification_id, record in self.retry_records.items():
            if record.approval_id == approval_id and not record.is_dead_letter:
                to_remove.append(notification_id)
                cancelled_count += 1
        
        for notification_id in to_remove:
            del self.retry_records[notification_id]
        
        logger.info(f"Cancelled {cancelled_count} notification retries for approval {approval_id}")
        return cancelled_count
    
    def force_retry_notification(self, notification_id: str) -> bool:
        """
        Force immediate retry of a specific notification.
        
        Args:
            notification_id: ID of the notification to retry
            
        Returns:
            True if retry was successful, False otherwise
        """
        record = self.retry_records.get(notification_id)
        if not record or record.is_dead_letter:
            return False
        
        try:
            success = self._attempt_notification_delivery(record)
            
            if success:
                del self.retry_records[notification_id]
                logger.info(f"Force retry successful for notification {notification_id}")
            else:
                record.retry_count += 1
                record.next_retry_at = self._calculate_next_retry_time(record.retry_count)
                logger.warning(f"Force retry failed for notification {notification_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error during force retry of notification {notification_id}: {str(e)}")
            return False
    
    # Private helper methods
    
    def _calculate_next_retry_time(self, retry_count: int) -> datetime:
        """Calculate next retry time using exponential backoff."""
        delay = self.base_retry_delay * (self.backoff_multiplier ** retry_count)
        delay = min(delay, self.max_retry_delay)  # Cap at maximum delay
        
        # Add jitter to prevent thundering herd
        import random
        jitter = timedelta(seconds=random.randint(0, 300))  # 0-5 minutes jitter
        
        return datetime.now(timezone.utc) + delay + jitter
    
    def _attempt_notification_delivery(self, record: NotificationRetryRecord) -> bool:
        """
        Attempt to deliver a notification.
        
        Args:
            record: Notification retry record
            
        Returns:
            True if delivery was successful, False otherwise
        """
        try:
            # Validate payload
            if not self._validate_notification_payload(record):
                logger.error(f"Invalid payload for notification {record.notification_id}")
                return False
            
            # Get fresh approval data
            approval = self.db.query(ExpenseApproval).filter(
                ExpenseApproval.id == record.approval_id
            ).first()
            
            if not approval:
                logger.error(f"Approval {record.approval_id} not found for notification {record.notification_id}")
                return False
            
            # Get recipient user
            recipient = self.db.query(User).filter(User.id == record.recipient_id).first()
            if not recipient:
                logger.error(f"Recipient {record.recipient_id} not found for notification {record.notification_id}")
                return False
            
            # Attempt delivery using notification service
            success = self.notification_service.send_operation_notification(
                event_type=record.notification_type,
                user_id=record.recipient_id,
                resource_type="expense_approval",
                resource_id=str(record.approval_id),
                resource_name=f"Expense #{approval.expense_id}",
                details=record.payload
            )
            
            if not success:
                record.last_error = "Notification service returned failure"
                # Increment circuit breaker failure count
                self.circuit_breaker_failures[record.recipient_id] = (
                    self.circuit_breaker_failures.get(record.recipient_id, 0) + 1
                )
            
            return success
            
        except Exception as e:
            error_msg = str(e)
            record.last_error = error_msg
            logger.error(f"Exception during notification delivery for {record.notification_id}: {error_msg}")
            
            # Increment circuit breaker failure count
            self.circuit_breaker_failures[record.recipient_id] = (
                self.circuit_breaker_failures.get(record.recipient_id, 0) + 1
            )
            
            return False
    
    def _validate_notification_payload(self, record: NotificationRetryRecord) -> bool:
        """Validate notification payload structure."""
        required_fields = ["expense_id", "amount", "category"]
        
        try:
            payload = record.payload
            if not isinstance(payload, dict):
                return False
            
            for field in required_fields:
                if field not in payload:
                    logger.warning(f"Missing required field '{field}' in notification payload")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating notification payload: {str(e)}")
            return False
    
    def _is_circuit_breaker_open(self, user_id: int) -> bool:
        """Check if circuit breaker is open for a user."""
        failure_count = self.circuit_breaker_failures.get(user_id, 0)
        return failure_count >= self.circuit_breaker_threshold
    
    def _handle_dead_letter_notification(self, record: NotificationRetryRecord) -> None:
        """Handle notification that has exceeded retry limits."""
        try:
            # Log dead letter notification
            logger.error(
                f"Dead letter notification: {record.notification_id}, "
                f"type: {record.notification_type}, "
                f"recipient: {record.recipient_id}, "
                f"approval: {record.approval_id}, "
                f"retries: {record.retry_count}, "
                f"last_error: {record.last_error}"
            )
            
            # Could implement additional dead letter handling here:
            # - Send to external monitoring system
            # - Create support ticket
            # - Send fallback notification (SMS, etc.)
            # - Store in persistent dead letter queue
            
            # For now, we'll create an audit log entry
            from utils.audit import log_audit_event
            
            log_audit_event(
                db=self.db,
                user_id=None,  # System event
                action="notification_dead_letter",
                resource_type="notification",
                resource_id=record.notification_id,
                details={
                    "notification_type": record.notification_type,
                    "recipient_id": record.recipient_id,
                    "approval_id": record.approval_id,
                    "retry_count": record.retry_count,
                    "last_error": record.last_error,
                    "created_at": record.created_at.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling dead letter notification {record.notification_id}: {str(e)}")
    
    def _cleanup_old_dead_letters(self) -> None:
        """Clean up old dead letter records."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        to_remove = []
        
        for notification_id, record in self.retry_records.items():
            if record.is_dead_letter and record.created_at < cutoff_date:
                to_remove.append(notification_id)
        
        for notification_id in to_remove:
            del self.retry_records[notification_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old dead letter notifications")
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get comprehensive retry statistics."""
        now = datetime.now(timezone.utc)
        
        total_records = len(self.retry_records)
        pending_retries = len([r for r in self.retry_records.values() if not r.is_dead_letter])
        dead_letters = len([r for r in self.retry_records.values() if r.is_dead_letter])
        
        # Count by notification type
        type_counts = {}
        for record in self.retry_records.values():
            type_counts[record.notification_type] = type_counts.get(record.notification_type, 0) + 1
        
        # Count ready for retry
        ready_for_retry = len([
            r for r in self.retry_records.values()
            if not r.is_dead_letter and r.next_retry_at <= now
        ])
        
        # Circuit breaker status
        circuit_breaker_open_count = len([
            user_id for user_id, failures in self.circuit_breaker_failures.items()
            if failures >= self.circuit_breaker_threshold
        ])
        
        return {
            "total_records": total_records,
            "pending_retries": pending_retries,
            "dead_letters": dead_letters,
            "ready_for_retry": ready_for_retry,
            "circuit_breaker_open_count": circuit_breaker_open_count,
            "notification_types": type_counts,
            "circuit_breaker_failures": dict(self.circuit_breaker_failures)
        }