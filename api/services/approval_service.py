"""
Approval Service

This service handles the core approval workflow management for expenses.
It manages expense submission, approval decisions, delegation, and audit trails.
"""

import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from models.models_per_tenant import (
    Expense, ExpenseApproval, ApprovalRule, User, ApprovalDelegate
)
from schemas.approval import (
    ApprovalStatus, ExpenseApprovalCreate, ExpenseApprovalDecision,
    ApprovalDelegateCreate, PendingApprovalSummary, ApprovalHistoryItem,
    ExpenseApprovalHistory, ApprovalMetrics
)
from services.approval_rule_engine import ApprovalRuleEngine
from services.notification_service import NotificationService
from services.approval_permission_service import ApprovalPermissionService
from services.approval_validation_service import ApprovalValidationService
from services.approval_notification_retry_service import ApprovalNotificationRetryService
from exceptions.approval_exceptions import (
    ValidationError, ApprovalServiceError, InsufficientApprovalPermissions,
    ExpenseAlreadyApproved, ExpenseAlreadyRejected, NoApprovalRuleFound,
    ApprovalLevelMismatch, InvalidApprovalState, ExpenseNotFoundException,
    ApprovalNotFoundException, NotificationDeliveryError, ApprovalWorkflowError,
    ApprovalConcurrencyError, ApprovalTimeoutError
)

logger = logging.getLogger(__name__)


class ApprovalService:
    """
    Core service for managing expense approval workflows.
    
    This service handles:
    - Expense submission for approval
    - Approval and rejection decisions
    - Multi-level approval workflows
    - Approval delegation
    - Audit trail maintenance
    - Status transitions
    """
    
    def __init__(self, db: Session, notification_service: Optional[NotificationService] = None):
        self.db = db
        self.rule_engine = ApprovalRuleEngine(db)
        self.notification_service = notification_service
        self.permission_service = ApprovalPermissionService(db)
        self.validation_service = ApprovalValidationService(db)
        self.retry_service = ApprovalNotificationRetryService(db, notification_service) if notification_service else None
    
    def submit_for_approval(
        self,
        expense_id: int,
        submitter_id: int,
        approver_id: int,
        notes: Optional[str] = None
    ) -> List[ExpenseApproval]:
        """
        Submit an expense for approval.

        Args:
            expense_id: ID of the expense to submit
            submitter_id: ID of the user submitting the expense
            notes: Optional notes for the submission
            approver_id: Specific approver ID to assign this approval to

        Returns:
            List of created ExpenseApproval records

        Raises:
            ExpenseAlreadyApproved: If expense is already approved
            ValidationError: If expense data is invalid or approver is invalid
            InsufficientApprovalPermissions: If user cannot submit for approval
            ApprovalWorkflowError: If workflow encounters an error
        """
        try:
            # Comprehensive validation using validation service
            expense, submitter = self.validation_service.validate_approval_submission(
                expense_id, submitter_id, notes
            )
            
            # Check for concurrent modifications
            self._check_expense_concurrency(expense)
            
            # Check if expense is already in approval workflow
            existing_approvals = self.db.query(ExpenseApproval).filter(
                ExpenseApproval.expense_id == expense_id
            ).all()
            
            if existing_approvals:
                # Check if any are still pending
                pending_approvals = [a for a in existing_approvals if a.status == ApprovalStatus.PENDING]
                if pending_approvals:
                    raise InvalidApprovalState(
                        approval_id=pending_approvals[0].id,
                        current_state="pending",
                        operation="submit for approval",
                        details={"message": "Expense is already in approval workflow"}
                    )
                
                # Check if already fully approved
                if expense.status == "approved":
                    raise ExpenseAlreadyApproved(
                        expense_id=expense_id,
                        current_status=expense.status
                    )
            
            # Direct approver selection is now mandatory
            if not approver_id:
                raise ValidationError("You must specify an approver for this expense")

            # Validate that the approver exists and is not the submitter
            approver = self.db.query(User).filter(User.id == approver_id).first()
            if not approver:
                raise ValidationError(f"Approver with ID {approver_id} not found")
            if approver_id == submitter_id:
                raise ValidationError("You cannot submit an expense for approval to yourself")

            # Check if expense should be auto-approved (skip for direct assignments)
            if self.rule_engine.should_auto_approve(expense):
                return self._auto_approve_expense(expense, submitter_id, notes)

            # Create a single approval record for the specified approver
            created_approvals = []
            now = datetime.now(timezone.utc)

            approval = ExpenseApproval(
                expense_id=expense_id,
                approver_id=approver_id,
                approval_rule_id=None,  # No rule for direct assignment
                status=ApprovalStatus.PENDING,
                notes=notes,
                submitted_at=now,
                approval_level=1,
                is_current_level=True
            )

            self.db.add(approval)
            created_approvals.append(approval)
            
            # Update expense status
            expense.status = "pending_approval"
            
            # Commit changes
            self.db.commit()
            
            # Refresh objects to get IDs
            for approval in created_approvals:
                self.db.refresh(approval)
            
            # Send notifications for first level approvers with retry logic
            first_level_approvals = [a for a in created_approvals if a.approval_level == 1]
            for approval in first_level_approvals:
                self._send_approval_notification_with_retry(approval, "expense_submitted_for_approval")
            
            return created_approvals
            
        except Exception as e:
            # Rollback any changes if something goes wrong
            self.db.rollback()
            
            if isinstance(e, (ValidationError, ExpenseAlreadyApproved, InvalidApprovalState, NoApprovalRuleFound)):
                raise
            else:
                raise ApprovalWorkflowError(
                    workflow_step="submit_for_approval",
                    expense_id=expense_id,
                    reason=str(e)
                )
    
    def approve_expense(
        self, 
        approval_id: int, 
        approver_id: int, 
        notes: Optional[str] = None
    ) -> ExpenseApproval:
        """
        Approve an expense at a specific approval level.
        
        Args:
            approval_id: ID of the approval record
            approver_id: ID of the user making the approval
            notes: Optional notes for the approval
            
        Returns:
            Updated ExpenseApproval record
            
        Raises:
            InsufficientApprovalPermissions: If user cannot approve this expense
            InvalidApprovalState: If approval is not in pending state
        """
        # Get the approval record
        approval = self.db.query(ExpenseApproval).filter(
            ExpenseApproval.id == approval_id
        ).first()
        
        if not approval:
            raise ValidationError(f"Approval {approval_id} not found")
        
        # Verify approver permissions
        if not self._can_user_approve(approver_id, approval):
            raise InsufficientApprovalPermissions(
                user_id=approver_id, required_permission="approve_expense", expense_id=approval.expense_id, approval_level=approval.approval_level
            )
        
        # Check approval state
        if approval.status != ApprovalStatus.PENDING:
            raise InvalidApprovalState(
                f"Approval is in {approval.status} state, cannot approve"
            )
        
        # Check if this is the current approval level
        if not approval.is_current_level:
            raise ApprovalLevelMismatch(
                approval_id=approval.id,
                current_level=approval.approval_level,
                expected_level=1  # Expected to be current level
            )
        
        # Update approval record
        now = datetime.now(timezone.utc)
        approval.status = ApprovalStatus.APPROVED
        approval.decided_at = now
        approval.notes = notes
        approval.is_current_level = False
        
        # Flush changes to database so get_next_approval_level can see them
        self.db.flush()
        
        # Get the expense
        expense = approval.expense
        
        # Check if this completes all required approvals
        next_level = self.rule_engine.get_next_approval_level(expense)
        
        if next_level is None:
            # All approvals complete - mark expense as approved
            expense.status = "approved"
            self._send_approval_notification(approval, "expense_fully_approved")
        else:
            # Activate next level approvals
            self._activate_next_approval_level(expense, next_level)
            self._send_approval_notification(approval, "expense_level_approved")
        
        # Commit changes
        self.db.commit()
        self.db.refresh(approval)
        
        return approval
    
    def reject_expense(
        self, 
        approval_id: int, 
        approver_id: int, 
        rejection_reason: str, 
        notes: Optional[str] = None
    ) -> ExpenseApproval:
        """
        Reject an expense at a specific approval level.
        
        Args:
            approval_id: ID of the approval record
            approver_id: ID of the user making the rejection
            rejection_reason: Reason for rejection (required)
            notes: Optional additional notes
            
        Returns:
            Updated ExpenseApproval record
            
        Raises:
            InsufficientApprovalPermissions: If user cannot approve this expense
            InvalidApprovalState: If approval is not in pending state
            ValidationError: If rejection_reason is empty
        """
        if not rejection_reason or not rejection_reason.strip():
            raise ValidationError("Rejection reason is required")
        
        # Get the approval record
        approval = self.db.query(ExpenseApproval).filter(
            ExpenseApproval.id == approval_id
        ).first()
        
        if not approval:
            raise ValidationError(f"Approval {approval_id} not found")
        
        # Verify approver permissions
        if not self._can_user_approve(approver_id, approval):
            raise InsufficientApprovalPermissions(
                user_id=approver_id, required_permission="approve_expense", expense_id=approval.expense_id, approval_level=approval.approval_level
            )
        
        # Check approval state
        if approval.status != ApprovalStatus.PENDING:
            raise InvalidApprovalState(
                f"Approval is in {approval.status} state, cannot reject"
            )
        
        # Update approval record
        now = datetime.now(timezone.utc)
        approval.status = ApprovalStatus.REJECTED
        approval.decided_at = now
        approval.rejection_reason = rejection_reason.strip()
        approval.notes = notes
        approval.is_current_level = False
        
        # Update expense status
        expense = approval.expense
        expense.status = "rejected"
        
        # Cancel all other pending approvals for this expense
        self._cancel_pending_approvals(expense.id, approval_id)
        
        # Commit changes
        self.db.commit()
        self.db.refresh(approval)
        
        # Send notification
        self._send_approval_notification(approval, "expense_rejected")
        
        return approval
    
    def get_pending_approvals(
        self, 
        approver_id: int, 
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ExpenseApproval]:
        """
        Get pending approvals for a specific approver.
        
        Args:
            approver_id: ID of the approver
            limit: Optional limit for pagination
            offset: Optional offset for pagination
            
        Returns:
            List of pending ExpenseApproval records
        """
        query = self.db.query(ExpenseApproval).filter(
            and_(
                ExpenseApproval.approver_id == approver_id,
                ExpenseApproval.status == ApprovalStatus.PENDING,
                ExpenseApproval.is_current_level == True
            )
        ).order_by(ExpenseApproval.submitted_at.asc())
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_pending_approvals_summary(self, approver_id: int) -> PendingApprovalSummary:
        """
        Get summary of pending approvals for dashboard display.
        
        Args:
            approver_id: ID of the approver
            
        Returns:
            PendingApprovalSummary with aggregated information
        """
        pending_approvals = self.get_pending_approvals(approver_id)
        
        if not pending_approvals:
            return PendingApprovalSummary(
                total_pending=0,
                total_amount=0.0,
                currency="USD",
                oldest_submission=None,
                by_category=[]
            )
        
        # Calculate totals (assuming same currency for simplicity)
        total_amount = sum(approval.expense.amount for approval in pending_approvals)
        currency = pending_approvals[0].expense.currency if pending_approvals else "USD"
        oldest_submission = min(approval.submitted_at for approval in pending_approvals)
        
        # Group by category
        category_counts = {}
        for approval in pending_approvals:
            category = approval.expense.category
            if category not in category_counts:
                category_counts[category] = {"count": 0, "amount": 0.0}
            category_counts[category]["count"] += 1
            category_counts[category]["amount"] += approval.expense.amount
        
        by_category = [
            {
                "category": category,
                "count": data["count"],
                "amount": data["amount"]
            }
            for category, data in category_counts.items()
        ]
        
        return PendingApprovalSummary(
            total_pending=len(pending_approvals),
            total_amount=total_amount,
            currency=currency,
            oldest_submission=oldest_submission,
            by_category=by_category
        )
    
    def get_approval_history(self, expense_id: int) -> ExpenseApprovalHistory:
        """
        Get complete approval history for an expense.
        
        Args:
            expense_id: ID of the expense
            
        Returns:
            ExpenseApprovalHistory with complete audit trail
        """
        expense = self.db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            raise ValidationError(f"Expense {expense_id} not found")
        
        # Get all approvals for this expense
        approvals = self.db.query(ExpenseApproval).filter(
            ExpenseApproval.expense_id == expense_id
        ).order_by(
            ExpenseApproval.approval_level.asc(),
            ExpenseApproval.submitted_at.asc()
        ).all()
        
        # Convert to history items
        history_items = []
        for approval in approvals:
            approver = approval.approver
            history_items.append(ApprovalHistoryItem(
                id=approval.id,
                approver_name=f"{approver.first_name or ''} {approver.last_name or ''}".strip() or approver.email,
                approver_email=approver.email,
                status=ApprovalStatus(approval.status),
                approval_level=approval.approval_level,
                submitted_at=approval.submitted_at,
                decided_at=approval.decided_at,
                rejection_reason=approval.rejection_reason,
                notes=approval.notes
            ))
        
        return ExpenseApprovalHistory(
            expense_id=expense_id,
            current_status=expense.status,
            approval_history=history_items
        )
    
    def create_delegation(
        self, 
        approver_id: int, 
        delegate_data: ApprovalDelegateCreate
    ) -> ApprovalDelegate:
        """
        Create an approval delegation.
        
        Args:
            approver_id: ID of the approver creating the delegation
            delegate_data: Delegation configuration
            
        Returns:
            Created ApprovalDelegate record
            
        Raises:
            ValidationError: If delegation data is invalid
        """
        # Validate users exist
        approver = self.db.query(User).filter(User.id == approver_id).first()
        if not approver:
            raise ValidationError(f"Approver {approver_id} not found")
        
        delegate = self.db.query(User).filter(User.id == delegate_data.delegate_id).first()
        if not delegate:
            raise ValidationError(f"Delegate {delegate_data.delegate_id} not found")
        
        # Check for overlapping delegations
        existing_delegation = self.db.query(ApprovalDelegate).filter(
            and_(
                ApprovalDelegate.approver_id == approver_id,
                ApprovalDelegate.is_active == True,
                or_(
                    and_(
                        ApprovalDelegate.start_date <= delegate_data.end_date,
                        ApprovalDelegate.end_date >= delegate_data.start_date
                    )
                )
            )
        ).first()
        
        if existing_delegation:
            raise ValidationError(
                f"Overlapping delegation exists from {existing_delegation.start_date} to {existing_delegation.end_date}"
            )
        
        # Create delegation
        delegation = ApprovalDelegate(
            approver_id=approver_id,
            delegate_id=delegate_data.delegate_id,
            start_date=delegate_data.start_date,
            end_date=delegate_data.end_date,
            is_active=delegate_data.is_active
        )
        
        self.db.add(delegation)
        self.db.commit()
        self.db.refresh(delegation)
        
        return delegation
    
    def get_active_delegations(self, approver_id: int) -> List[ApprovalDelegate]:
        """
        Get active delegations for an approver.
        
        Args:
            approver_id: ID of the approver
            
        Returns:
            List of active ApprovalDelegate records
        """
        now = datetime.now(timezone.utc)
        
        return self.db.query(ApprovalDelegate).filter(
            and_(
                ApprovalDelegate.approver_id == approver_id,
                ApprovalDelegate.is_active == True,
                ApprovalDelegate.start_date <= now,
                ApprovalDelegate.end_date >= now
            )
        ).all()
    
    def deactivate_delegation(self, delegation_id: int, approver_id: int) -> ApprovalDelegate:
        """
        Deactivate an approval delegation.
        
        Args:
            delegation_id: ID of the delegation to deactivate
            approver_id: ID of the approver (for permission check)
            
        Returns:
            Updated ApprovalDelegate record
            
        Raises:
            ValidationError: If delegation not found or permission denied
        """
        delegation = self.db.query(ApprovalDelegate).filter(
            and_(
                ApprovalDelegate.id == delegation_id,
                ApprovalDelegate.approver_id == approver_id
            )
        ).first()
        
        if not delegation:
            raise ValidationError(f"Delegation {delegation_id} not found or access denied")
        
        delegation.is_active = False
        self.db.commit()
        self.db.refresh(delegation)
        
        return delegation
    
    def get_approval_metrics(
        self, 
        approver_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ApprovalMetrics:
        """
        Get approval workflow metrics.
        
        Args:
            approver_id: Optional filter by specific approver
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            ApprovalMetrics with aggregated statistics
        """
        query = self.db.query(ExpenseApproval)
        
        if approver_id:
            query = query.filter(ExpenseApproval.approver_id == approver_id)
        
        if start_date:
            query = query.filter(ExpenseApproval.submitted_at >= start_date)
        
        if end_date:
            query = query.filter(ExpenseApproval.submitted_at <= end_date)
        
        approvals = query.all()
        
        if not approvals:
            return ApprovalMetrics(
                total_approvals=0,
                approved_count=0,
                rejected_count=0,
                pending_count=0,
                average_approval_time_hours=None,
                approval_rate=0.0
            )
        
        # Calculate metrics
        total_approvals = len(approvals)
        approved_count = len([a for a in approvals if a.status == ApprovalStatus.APPROVED])
        rejected_count = len([a for a in approvals if a.status == ApprovalStatus.REJECTED])
        pending_count = len([a for a in approvals if a.status == ApprovalStatus.PENDING])
        
        # Calculate average approval time for decided approvals
        decided_approvals = [a for a in approvals if a.decided_at is not None]
        if decided_approvals:
            total_hours = sum(
                (a.decided_at - a.submitted_at).total_seconds() / 3600
                for a in decided_approvals
            )
            average_approval_time_hours = total_hours / len(decided_approvals)
        else:
            average_approval_time_hours = None
        
        # Calculate approval rate (approved / (approved + rejected))
        decided_count = approved_count + rejected_count
        approval_rate = (approved_count / decided_count * 100) if decided_count > 0 else 0.0
        
        return ApprovalMetrics(
            total_approvals=total_approvals,
            approved_count=approved_count,
            rejected_count=rejected_count,
            pending_count=pending_count,
            average_approval_time_hours=average_approval_time_hours,
            approval_rate=approval_rate
        )
    
    def resubmit_expense(
        self, 
        expense_id: int, 
        submitter_id: int, 
        notes: Optional[str] = None
    ) -> List[ExpenseApproval]:
        """
        Resubmit a rejected expense for approval.
        
        Args:
            expense_id: ID of the expense to resubmit
            submitter_id: ID of the user resubmitting
            notes: Optional notes for resubmission
            
        Returns:
            List of created ExpenseApproval records
            
        Raises:
            InvalidApprovalState: If expense is not in rejected state
        """
        expense = self.db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            raise ValidationError(f"Expense {expense_id} not found")
        
        if expense.status != "rejected":
            raise InvalidApprovalState(f"Expense is in {expense.status} state, cannot resubmit")
        
        # Mark expense as resubmitted
        expense.status = "resubmitted"
        self.db.commit()
        
        # Submit for approval again
        return self.submit_for_approval(expense_id, submitter_id, notes)
    
    # Private helper methods
    
    def _check_expense_concurrency(self, expense: Expense) -> None:
        """Check for concurrent modifications to expense."""
        # Refresh expense from database to check for concurrent changes
        self.db.refresh(expense)
        
        # Check if expense was modified by another process
        if expense.status in ["approved", "pending_approval"]:
            raise ApprovalConcurrencyError(
                expense_id=expense.id,
                operation="submit_for_approval"
            )
    
    def _validate_expense_for_approval(self, expense: Expense) -> None:
        """Validate that expense has all required fields for approval."""
        # This method is now handled by ApprovalValidationService
        # Keeping for backward compatibility
        try:
            self.validation_service.validate_expense_for_approval(expense.id)
        except Exception as e:
            if hasattr(e, 'user_message'):
                raise ValidationError(str(e.user_message))
            else:
                raise ValidationError(str(e))
    
    def _can_user_approve(self, user_id: int, approval: ExpenseApproval) -> bool:
        """Check if user can approve the given approval record."""
        # Get the user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # Check basic approval permissions first
        try:
            self.permission_service.validate_approval_permission(user, approval.expense, approval.approval_level)
        except Exception:
            return False
        
        # Direct approver
        if approval.approver_id == user_id:
            return True
        
        # Check delegation using permission service
        effective_approver = self.permission_service.resolve_effective_approver(approval.approver_id)
        return effective_approver == user_id
    
    def _auto_approve_expense(
        self, 
        expense: Expense, 
        submitter_id: int, 
        notes: Optional[str]
    ) -> List[ExpenseApproval]:
        """Auto-approve an expense that meets auto-approval criteria."""
        # Get the rule that allows auto-approval
        matching_rules = self.rule_engine.evaluate_expense(expense)
        auto_approve_rule = None
        
        for rule in matching_rules:
            if (rule.auto_approve_below is not None and 
                expense.amount <= rule.auto_approve_below):
                auto_approve_rule = rule
                break
        
        if not auto_approve_rule:
            raise NoApprovalRuleFound("No auto-approval rule found")
        
        # Create and immediately approve the approval record
        now = datetime.now(timezone.utc)
        approval = ExpenseApproval(
            expense_id=expense.id,
            approver_id=auto_approve_rule.approver_id,
            approval_rule_id=auto_approve_rule.id,
            status=ApprovalStatus.APPROVED,
            notes=f"Auto-approved: {notes}" if notes else "Auto-approved",
            submitted_at=now,
            decided_at=now,
            approval_level=auto_approve_rule.approval_level,
            is_current_level=False
        )
        
        self.db.add(approval)
        
        # Update expense status
        expense.status = "approved"
        
        self.db.commit()
        self.db.refresh(approval)
        
        # Send notification
        self._send_approval_notification(approval, "expense_auto_approved")
        
        return [approval]
    
    def _activate_next_approval_level(self, expense: Expense, next_level: int) -> None:
        """Activate approvals for the next level."""
        # Set current level approvals to not current
        self.db.query(ExpenseApproval).filter(
            and_(
                ExpenseApproval.expense_id == expense.id,
                ExpenseApproval.is_current_level == True
            )
        ).update({"is_current_level": False})
        
        # Activate next level approvals
        next_level_approvals = self.db.query(ExpenseApproval).filter(
            and_(
                ExpenseApproval.expense_id == expense.id,
                ExpenseApproval.approval_level == next_level,
                ExpenseApproval.status == ApprovalStatus.PENDING
            )
        ).all()
        
        for approval in next_level_approvals:
            approval.is_current_level = True
            # Send notification to next level approvers
            self._send_approval_notification(approval, "expense_submitted_for_approval")
    
    def _cancel_pending_approvals(self, expense_id: int, exclude_approval_id: int) -> None:
        """Cancel all pending approvals except the specified one."""
        self.db.query(ExpenseApproval).filter(
            and_(
                ExpenseApproval.expense_id == expense_id,
                ExpenseApproval.id != exclude_approval_id,
                ExpenseApproval.status == ApprovalStatus.PENDING
            )
        ).update({
            "status": "cancelled",
            "is_current_level": False,
            "decided_at": datetime.now(timezone.utc)
        })
    
    def _send_approval_notification_with_retry(self, approval: ExpenseApproval, event_type: str) -> None:
        """Send notification for approval events with retry logic."""
        if not self.notification_service:
            return
        
        try:
            expense = approval.expense
            approver = approval.approver
            
            # Determine recipient based on event type
            if event_type in ["expense_submitted_for_approval"]:
                recipient_id = approver.id
                resource_name = f"Expense #{expense.id} - {expense.category}"
            else:
                # For approval/rejection notifications, notify expense owner
                recipient_id = expense.user_id if expense.user_id else None
                resource_name = f"Your expense #{expense.id} - {expense.category}"
            
            if not recipient_id:
                return
            
            details = {
                "expense_id": expense.id,
                "amount": f"{expense.currency} {expense.amount:.2f}",
                "category": expense.category,
                "vendor": expense.vendor or "N/A",
                "expense_date": expense.expense_date.strftime("%Y-%m-%d") if expense.expense_date else "N/A",
                "approver": f"{approver.first_name or ''} {approver.last_name or ''}".strip() or approver.email,
                "approval_level": approval.approval_level,
                "notes": approval.notes or "No notes provided"
            }
            
            if approval.rejection_reason:
                details["rejection_reason"] = approval.rejection_reason
            
            # Attempt to send notification
            success = self.notification_service.send_operation_notification(
                event_type=event_type,
                user_id=recipient_id,
                resource_type="expense_approval",
                resource_id=str(approval.id),
                resource_name=resource_name,
                details=details
            )
            
            # If notification fails and retry service is available, schedule retry
            if not success and self.retry_service:
                self.retry_service.schedule_notification_retry(
                    notification_type=event_type,
                    recipient_id=recipient_id,
                    approval_id=approval.id,
                    payload=details,
                    error_message="Initial notification delivery failed"
                )
                
        except Exception as e:
            logger.error(f"Error sending approval notification: {str(e)}")
            
            # Schedule retry if retry service is available
            if self.retry_service:
                try:
                    self.retry_service.schedule_notification_retry(
                        notification_type=event_type,
                        recipient_id=recipient_id,
                        approval_id=approval.id,
                        payload=details,
                        error_message=str(e)
                    )
                except Exception as retry_error:
                    logger.error(f"Failed to schedule notification retry: {str(retry_error)}")
    
    def _send_approval_notification(self, approval: ExpenseApproval, event_type: str) -> None:
        """Send notification for approval events (legacy method)."""
        # Delegate to the new retry-enabled method
        self._send_approval_notification_with_retry(approval, event_type)