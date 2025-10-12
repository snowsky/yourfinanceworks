"""
Approval Notification Scheduler Service

This service handles scheduling and sending of approval-related notifications
including reminders for pending approvals and escalations for overdue approvals.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.models_per_tenant import (
    ExpenseApproval, User, ApprovalRule, Expense
)
from schemas.approval import ApprovalStatus
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ApprovalNotificationScheduler:
    """
    Service for scheduling and managing approval-related notifications.
    
    This service handles:
    - Reminder notifications for pending approvals
    - Escalation notifications for overdue approvals
    - Batch processing of notifications
    - Configuration of reminder and escalation thresholds
    """
    
    def __init__(self, db: Session, notification_service: NotificationService):
        self.db = db
        self.notification_service = notification_service
        
        # Default configuration - can be made configurable later
        self.reminder_threshold_hours = 24  # Send reminder after 24 hours
        self.escalation_threshold_hours = 72  # Escalate after 72 hours
        self.reminder_frequency_hours = 24  # Send reminders every 24 hours
    
    def send_pending_approval_reminders(self, company_name: str = "Invoice Management System") -> Dict[str, Any]:
        """
        Send reminder notifications for pending approvals that exceed the threshold.
        
        Args:
            company_name: Name of the company for email branding
            
        Returns:
            Dictionary with summary of sent reminders
        """
        try:
            # Calculate threshold time
            threshold_time = datetime.now(timezone.utc) - timedelta(hours=self.reminder_threshold_hours)
            
            # Get pending approvals that need reminders
            pending_approvals = self.db.query(ExpenseApproval).filter(
                and_(
                    ExpenseApproval.status == ApprovalStatus.PENDING,
                    ExpenseApproval.is_current_level == True,
                    ExpenseApproval.submitted_at <= threshold_time
                )
            ).all()
            
            if not pending_approvals:
                logger.info("No pending approvals requiring reminders")
                return {
                    "total_reminders_sent": 0,
                    "approvers_notified": 0,
                    "errors": []
                }
            
            # Group by approver
            approver_groups = {}
            for approval in pending_approvals:
                approver_id = approval.approver_id
                if approver_id not in approver_groups:
                    approver_groups[approver_id] = []
                
                # Check if we should send reminder (not sent recently)
                if self._should_send_reminder(approval):
                    approver_groups[approver_id].append({
                        'expense_id': approval.expense_id,
                        'amount': approval.expense.amount,
                        'category': approval.expense.category,
                        'submitted_at': approval.submitted_at,
                        'approval_id': approval.id
                    })
            
            # Send reminders to each approver
            total_sent = 0
            approvers_notified = 0
            errors = []
            
            for approver_id, approvals_data in approver_groups.items():
                if not approvals_data:  # Skip if no approvals need reminders
                    continue
                    
                try:
                    success = self.notification_service.send_approval_reminder(
                        approver_id=approver_id,
                        pending_approvals=approvals_data,
                        company_name=company_name
                    )
                    
                    if success:
                        total_sent += len(approvals_data)
                        approvers_notified += 1
                        
                        # Update last reminder time for these approvals
                        approval_ids = [a['approval_id'] for a in approvals_data]
                        self._update_last_reminder_time(approval_ids)
                        
                        logger.info(f"Sent reminder to approver {approver_id} for {len(approvals_data)} approvals")
                    else:
                        errors.append(f"Failed to send reminder to approver {approver_id}")
                        
                except Exception as e:
                    error_msg = f"Error sending reminder to approver {approver_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            return {
                "total_reminders_sent": total_sent,
                "approvers_notified": approvers_notified,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error in send_pending_approval_reminders: {str(e)}")
            return {
                "total_reminders_sent": 0,
                "approvers_notified": 0,
                "errors": [f"System error: {str(e)}"]
            }
    
    def send_overdue_approval_escalations(
        self, 
        company_name: str = "Invoice Management System"
    ) -> Dict[str, Any]:
        """
        Send escalation notifications for overdue approvals.
        
        Args:
            company_name: Name of the company for email branding
            
        Returns:
            Dictionary with summary of sent escalations
        """
        try:
            # Calculate escalation threshold time
            threshold_time = datetime.now(timezone.utc) - timedelta(hours=self.escalation_threshold_hours)
            
            # Get overdue approvals
            overdue_approvals = self.db.query(ExpenseApproval).filter(
                and_(
                    ExpenseApproval.status == ApprovalStatus.PENDING,
                    ExpenseApproval.is_current_level == True,
                    ExpenseApproval.submitted_at <= threshold_time
                )
            ).all()
            
            if not overdue_approvals:
                logger.info("No overdue approvals requiring escalation")
                return {
                    "total_escalations_sent": 0,
                    "approvers_escalated": 0,
                    "errors": []
                }
            
            # Group by approver
            approver_groups = {}
            for approval in overdue_approvals:
                approver_id = approval.approver_id
                if approver_id not in approver_groups:
                    approver_groups[approver_id] = []
                
                # Check if we should send escalation (not escalated recently)
                if self._should_send_escalation(approval):
                    approver_groups[approver_id].append({
                        'expense_id': approval.expense_id,
                        'amount': approval.expense.amount,
                        'category': approval.expense.category,
                        'submitted_at': approval.submitted_at,
                        'approval_id': approval.id
                    })
            
            # Send escalations
            total_sent = 0
            approvers_escalated = 0
            errors = []
            
            for approver_id, approvals_data in approver_groups.items():
                if not approvals_data:  # Skip if no approvals need escalation
                    continue
                
                try:
                    # Find escalation recipient (could be manager, admin, etc.)
                    escalation_recipient = self._get_escalation_recipient(approver_id)
                    
                    if not escalation_recipient:
                        errors.append(f"No escalation recipient found for approver {approver_id}")
                        continue
                    
                    success = self.notification_service.send_approval_escalation(
                        approver_id=approver_id,
                        overdue_approvals=approvals_data,
                        escalation_recipient_id=escalation_recipient.id,
                        company_name=company_name
                    )
                    
                    if success:
                        total_sent += len(approvals_data)
                        approvers_escalated += 1
                        
                        # Update last escalation time for these approvals
                        approval_ids = [a['approval_id'] for a in approvals_data]
                        self._update_last_escalation_time(approval_ids)
                        
                        logger.info(f"Sent escalation for approver {approver_id} to {escalation_recipient.email}")
                    else:
                        errors.append(f"Failed to send escalation for approver {approver_id}")
                        
                except Exception as e:
                    error_msg = f"Error sending escalation for approver {approver_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            return {
                "total_escalations_sent": total_sent,
                "approvers_escalated": approvers_escalated,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error in send_overdue_approval_escalations: {str(e)}")
            return {
                "total_escalations_sent": 0,
                "approvers_escalated": 0,
                "errors": [f"System error: {str(e)}"]
            }
    
    def process_all_approval_notifications(
        self, 
        company_name: str = "Invoice Management System"
    ) -> Dict[str, Any]:
        """
        Process all approval notifications (reminders and escalations).
        
        Args:
            company_name: Name of the company for email branding
            
        Returns:
            Dictionary with summary of all notifications sent
        """
        logger.info("Starting approval notification processing")
        
        # Send reminders
        reminder_results = self.send_pending_approval_reminders(company_name)
        
        # Send escalations
        escalation_results = self.send_overdue_approval_escalations(company_name)
        
        # Combine results
        total_notifications = (
            reminder_results["total_reminders_sent"] + 
            escalation_results["total_escalations_sent"]
        )
        
        all_errors = reminder_results["errors"] + escalation_results["errors"]
        
        results = {
            "total_notifications_sent": total_notifications,
            "reminders": reminder_results,
            "escalations": escalation_results,
            "errors": all_errors,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Approval notification processing complete: {total_notifications} notifications sent")
        
        return results
    
    def get_pending_approval_summary(self) -> Dict[str, Any]:
        """
        Get summary of pending approvals for monitoring.
        
        Returns:
            Dictionary with pending approval statistics
        """
        try:
            now = datetime.now(timezone.utc)
            reminder_threshold = now - timedelta(hours=self.reminder_threshold_hours)
            escalation_threshold = now - timedelta(hours=self.escalation_threshold_hours)
            
            # Get all pending approvals
            pending_approvals = self.db.query(ExpenseApproval).filter(
                and_(
                    ExpenseApproval.status == ApprovalStatus.PENDING,
                    ExpenseApproval.is_current_level == True
                )
            ).all()
            
            # Categorize approvals
            total_pending = len(pending_approvals)
            needs_reminder = len([a for a in pending_approvals if a.submitted_at <= reminder_threshold])
            needs_escalation = len([a for a in pending_approvals if a.submitted_at <= escalation_threshold])
            
            # Group by approver
            approver_counts = {}
            for approval in pending_approvals:
                approver_id = approval.approver_id
                if approver_id not in approver_counts:
                    approver_counts[approver_id] = {
                        'total': 0,
                        'needs_reminder': 0,
                        'needs_escalation': 0
                    }
                
                approver_counts[approver_id]['total'] += 1
                
                if approval.submitted_at <= reminder_threshold:
                    approver_counts[approver_id]['needs_reminder'] += 1
                
                if approval.submitted_at <= escalation_threshold:
                    approver_counts[approver_id]['needs_escalation'] += 1
            
            return {
                "total_pending": total_pending,
                "needs_reminder": needs_reminder,
                "needs_escalation": needs_escalation,
                "approvers_with_pending": len(approver_counts),
                "approver_breakdown": approver_counts,
                "thresholds": {
                    "reminder_hours": self.reminder_threshold_hours,
                    "escalation_hours": self.escalation_threshold_hours
                },
                "generated_at": now.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating pending approval summary: {str(e)}")
            return {
                "error": str(e),
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
    
    # Private helper methods
    
    def _should_send_reminder(self, approval: ExpenseApproval) -> bool:
        """
        Check if a reminder should be sent for this approval.
        
        This checks if enough time has passed since the last reminder
        to avoid spamming approvers.
        """
        # For now, we'll use a simple approach - check if reminder frequency has passed
        # In a production system, you might want to track last_reminder_sent in the database
        
        # If no reminder has been sent, or if reminder frequency has passed, send reminder
        last_reminder = getattr(approval, 'last_reminder_sent', None)
        if not last_reminder:
            return True
        
        time_since_reminder = datetime.now(timezone.utc) - last_reminder
        return time_since_reminder.total_seconds() >= (self.reminder_frequency_hours * 3600)
    
    def _should_send_escalation(self, approval: ExpenseApproval) -> bool:
        """
        Check if an escalation should be sent for this approval.
        
        This checks if enough time has passed since the last escalation
        to avoid duplicate escalations.
        """
        # Similar to reminders, check if escalation should be sent
        last_escalation = getattr(approval, 'last_escalation_sent', None)
        if not last_escalation:
            return True
        
        # Only escalate once per day to avoid spam
        time_since_escalation = datetime.now(timezone.utc) - last_escalation
        return time_since_escalation.total_seconds() >= (24 * 3600)  # 24 hours
    
    def _get_escalation_recipient(self, approver_id: int) -> Optional[User]:
        """
        Get the escalation recipient for a given approver.
        
        This could be implemented based on organizational hierarchy,
        admin roles, or configuration. For now, we'll find a user with
        admin privileges or return None.
        """
        try:
            # Find a user with admin role or similar
            # This is a simplified implementation - in production you might have
            # a more sophisticated hierarchy or configuration system
            
            admin_user = self.db.query(User).filter(
                User.role == "admin"  # Assuming there's a role field
            ).first()
            
            if admin_user and admin_user.id != approver_id:
                return admin_user
            
            # Fallback: find any user that's not the approver
            # This is just for demonstration - implement proper escalation logic
            fallback_user = self.db.query(User).filter(
                User.id != approver_id
            ).first()
            
            return fallback_user
            
        except Exception as e:
            logger.error(f"Error finding escalation recipient for approver {approver_id}: {str(e)}")
            return None
    
    def _update_last_reminder_time(self, approval_ids: List[int]) -> None:
        """
        Update the last reminder time for the given approvals.
        
        Note: This would require adding a last_reminder_sent field to the
        ExpenseApproval model in a production system.
        """
        # For now, this is a placeholder
        # In production, you would update the database:
        # self.db.query(ExpenseApproval).filter(
        #     ExpenseApproval.id.in_(approval_ids)
        # ).update({"last_reminder_sent": datetime.now(timezone.utc)})
        # self.db.commit()
        pass
    
    def _update_last_escalation_time(self, approval_ids: List[int]) -> None:
        """
        Update the last escalation time for the given approvals.
        
        Note: This would require adding a last_escalation_sent field to the
        ExpenseApproval model in a production system.
        """
        # For now, this is a placeholder
        # In production, you would update the database:
        # self.db.query(ExpenseApproval).filter(
        #     ExpenseApproval.id.in_(approval_ids)
        # ).update({"last_escalation_sent": datetime.now(timezone.utc)})
        # self.db.commit()
        pass
    
    def configure_thresholds(
        self,
        reminder_threshold_hours: Optional[int] = None,
        escalation_threshold_hours: Optional[int] = None,
        reminder_frequency_hours: Optional[int] = None
    ) -> None:
        """
        Configure notification thresholds.
        
        Args:
            reminder_threshold_hours: Hours after submission to send first reminder
            escalation_threshold_hours: Hours after submission to send escalation
            reminder_frequency_hours: Hours between reminder notifications
        """
        if reminder_threshold_hours is not None:
            self.reminder_threshold_hours = reminder_threshold_hours
        
        if escalation_threshold_hours is not None:
            self.escalation_threshold_hours = escalation_threshold_hours
        
        if reminder_frequency_hours is not None:
            self.reminder_frequency_hours = reminder_frequency_hours
        
        logger.info(f"Updated notification thresholds: reminder={self.reminder_threshold_hours}h, "
                   f"escalation={self.escalation_threshold_hours}h, frequency={self.reminder_frequency_hours}h")