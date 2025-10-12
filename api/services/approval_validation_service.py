"""
Approval Validation Service

This service provides comprehensive validation for approval workflow operations,
ensuring data integrity and business rule compliance.
"""
import re
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.models_per_tenant import (
    Expense, ExpenseApproval, User, ApprovalDelegate, ExpenseAttachment
)
from schemas.approval import ApprovalStatus
from exceptions.approval_exceptions import (
    ValidationError, ExpenseValidationError,
    DelegationValidationError, DelegationConflictError, ExpenseNotFoundException,
    ApprovalNotFoundException
)


class ApprovalValidationService:
    """
    Service for validating approval workflow operations.
    
    This service provides comprehensive validation for:
    - Expense submission requirements
    - Approval rule configuration
    - Delegation setup
    - Permission requirements
    - Business rule compliance
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_expense_for_approval(self, expense_id: int) -> Expense:
        """
        Validate that an expense meets requirements for approval submission.
        
        Args:
            expense_id: ID of the expense to validate
            
        Returns:
            Validated Expense object
            
        Raises:
            ExpenseNotFoundException: If expense not found
            ExpenseValidationError: If expense fails validation
        """
        # Get the expense
        expense = self.db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            raise ExpenseNotFoundException(expense_id)
        
        # Check required fields
        missing_fields = []
        validation_errors = []
        
        # Amount validation
        if not expense.amount or expense.amount <= 0:
            missing_fields.append("amount")
            validation_errors.append("Amount must be greater than 0")
        
        # Category validation
        if not expense.category or not expense.category.strip():
            missing_fields.append("category")
            validation_errors.append("Category is required")
        
        # Date validation
        if not expense.expense_date:
            missing_fields.append("expense_date")
            validation_errors.append("Expense date is required")
        elif expense.expense_date.date() > datetime.now().date():
            validation_errors.append("Expense date cannot be in the future")
        
        # Currency validation
        if not expense.currency or not expense.currency.strip():
            missing_fields.append("currency")
            validation_errors.append("Currency is required")
        elif not self._is_valid_currency_code(expense.currency):
            validation_errors.append(f"Invalid currency code: {expense.currency}")
        
        # Description validation (optional but recommended)
        if expense.notes and len(expense.notes.strip()) > 0 and len(expense.notes.strip()) < 3:
            validation_errors.append("Notes should be at least 3 characters long if provided")
        
        # Vendor validation for certain categories
        high_risk_categories = ["travel", "entertainment", "meals", "equipment"]
        if (expense.category.lower() in high_risk_categories and 
            (not expense.vendor or len(expense.vendor.strip()) < 2)):
            missing_fields.append("vendor")
            validation_errors.append(f"Vendor is required for {expense.category} expenses")
        
        # Receipt validation for high amounts
        if expense.amount > 100 and not self._has_receipt_attachment(expense):
            validation_errors.append("Receipt attachment is required for expenses over $100")
        
        if missing_fields or validation_errors:
            raise ExpenseValidationError(
                expense_id=expense_id,
                missing_fields=missing_fields,
                details={
                    "validation_errors": validation_errors,
                    "expense_amount": expense.amount,
                    "expense_category": expense.category
                }
            )
        
        return expense
    
    def validate_approval_submission(
        self, 
        expense_id: int, 
        submitter_id: int,
        notes: Optional[str] = None
    ) -> Tuple[Expense, User]:
        """
        Validate approval submission request.
        
        Args:
            expense_id: ID of the expense to submit
            submitter_id: ID of the user submitting
            notes: Optional submission notes
            
        Returns:
            Tuple of (validated_expense, submitter_user)
            
        Raises:
            ExpenseNotFoundException: If expense not found
            ValidationError: If submitter not found or validation fails
            ExpenseValidationError: If expense fails validation
        """
        # Validate expense
        expense = self.validate_expense_for_approval(expense_id)
        
        # Validate submitter
        submitter = self.db.query(User).filter(User.id == submitter_id).first()
        if not submitter:
            raise ValidationError(
                field="submitter_id",
                value=submitter_id,
                reason="Submitter user not found"
            )
        
        # Check if expense belongs to submitter or submitter has permission
        if expense.user_id != submitter_id:
            # Check if submitter has admin permissions or is expense manager
            if not self._can_user_submit_expense(submitter, expense):
                raise ValidationError(
                    field="submitter_id",
                    value=submitter_id,
                    reason="User cannot submit this expense for approval",
                    details={
                        "expense_owner_id": expense.user_id,
                        "submitter_id": submitter_id
                    }
                )
        
        # Validate notes length if provided
        if notes and len(notes) > 1000:
            raise ValidationError(
                field="notes",
                value=len(notes),
                reason="Notes cannot exceed 1000 characters"
            )
        
        # Check expense status
        if expense.status in ["approved", "pending_approval"]:
            raise ValidationError(
                field="expense_status",
                value=expense.status,
                reason=f"Expense is already in {expense.status} state"
            )
        
        return expense, submitter
    
    def validate_approval_decision(
        self, 
        approval_id: int, 
        approver_id: int,
        decision_status: str,
        rejection_reason: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Tuple[ExpenseApproval, User]:
        """
        Validate approval decision request.
        
        Args:
            approval_id: ID of the approval to decide on
            approver_id: ID of the user making the decision
            decision_status: "approved" or "rejected"
            rejection_reason: Required if decision_status is "rejected"
            notes: Optional decision notes
            
        Returns:
            Tuple of (approval_record, approver_user)
            
        Raises:
            ApprovalNotFoundException: If approval not found
            ValidationError: If validation fails
        """
        # Get approval record
        approval = self.db.query(ExpenseApproval).filter(
            ExpenseApproval.id == approval_id
        ).first()
        if not approval:
            raise ApprovalNotFoundException(approval_id)
        
        # Get approver
        approver = self.db.query(User).filter(User.id == approver_id).first()
        if not approver:
            raise ValidationError(
                field="approver_id",
                value=approver_id,
                reason="Approver user not found"
            )
        
        # Validate decision status
        if decision_status not in ["approved", "rejected"]:
            raise ValidationError(
                field="decision_status",
                value=decision_status,
                reason="Decision status must be 'approved' or 'rejected'"
            )
        
        # Validate rejection reason
        if decision_status == "rejected":
            if not rejection_reason or not rejection_reason.strip():
                raise ValidationError(
                    field="rejection_reason",
                    value=rejection_reason,
                    reason="Rejection reason is required when rejecting an expense"
                )
            if len(rejection_reason.strip()) < 10:
                raise ValidationError(
                    field="rejection_reason",
                    value=len(rejection_reason.strip()),
                    reason="Rejection reason must be at least 10 characters long"
                )
        
        # Validate notes length
        if notes and len(notes) > 1000:
            raise ValidationError(
                field="notes",
                value=len(notes),
                reason="Notes cannot exceed 1000 characters"
            )
        
        # Check approval state
        if approval.status != ApprovalStatus.PENDING:
            raise ValidationError(
                field="approval_status",
                value=approval.status,
                reason=f"Approval is in {approval.status} state and cannot be modified"
            )
        
        # Check if this is the current approval level
        if not approval.is_current_level:
            raise ValidationError(
                field="approval_level",
                value=approval.approval_level,
                reason="This approval level is not currently active"
            )
        
        return approval, approver
    
    
    
    def validate_delegation_create(
        self, 
        approver_id: int, 
        delegate_id: int,
        start_date: datetime, 
        end_date: datetime
    ) -> Tuple[User, User]:
        """
        Validate delegation creation.
        
        Args:
            approver_id: ID of the approver
            delegate_id: ID of the delegate
            start_date: Start date of delegation
            end_date: End date of delegation
            
        Returns:
            Tuple of (approver_user, delegate_user)
            
        Raises:
            ValidationError: If validation fails
            DelegationValidationError: If delegation validation fails
            DelegationConflictError: If delegation conflicts with existing ones
        """
        # Validate users exist
        approver = self.db.query(User).filter(User.id == approver_id).first()
        if not approver:
            raise ValidationError(
                field="approver_id",
                value=approver_id,
                reason="Approver user not found"
            )
        
        delegate = self.db.query(User).filter(User.id == delegate_id).first()
        if not delegate:
            raise ValidationError(
                field="delegate_id",
                value=delegate_id,
                reason="Delegate user not found"
            )
        
        # Validate users are different
        if approver_id == delegate_id:
            raise DelegationValidationError(
                approver_id=approver_id,
                delegate_id=delegate_id,
                reason="Approver and delegate cannot be the same user"
            )
        
        # Validate date range
        if end_date <= start_date:
            raise DelegationValidationError(
                approver_id=approver_id,
                delegate_id=delegate_id,
                reason="End date must be after start date"
            )
        
        # Validate delegation period is not too long (max 1 year)
        max_duration = timedelta(days=365)
        if end_date - start_date > max_duration:
            raise DelegationValidationError(
                approver_id=approver_id,
                delegate_id=delegate_id,
                reason="Delegation period cannot exceed 1 year"
            )
        
        # Validate start date is not too far in the past
        if start_date < datetime.now(timezone.utc) - timedelta(days=30):
            raise DelegationValidationError(
                approver_id=approver_id,
                delegate_id=delegate_id,
                reason="Start date cannot be more than 30 days in the past"
            )
        
        # Check for overlapping delegations
        overlapping_delegation = self.db.query(ApprovalDelegate).filter(
            and_(
                ApprovalDelegate.approver_id == approver_id,
                ApprovalDelegate.is_active == True,
                or_(
                    and_(
                        ApprovalDelegate.start_date <= end_date,
                        ApprovalDelegate.end_date >= start_date
                    )
                )
            )
        ).first()
        
        if overlapping_delegation:
            raise DelegationConflictError(
                approver_id=approver_id,
                start_date=start_date,
                end_date=end_date,
                conflicting_delegation_id=overlapping_delegation.id
            )
        
        return approver, delegate
    
    # Private helper methods
    
    def _is_valid_currency_code(self, currency: str) -> bool:
        """Validate currency code format."""
        if not currency or len(currency) != 3:
            return False
        return currency.upper().isalpha()
    
    def _has_receipt_attachment(self, expense: Expense) -> bool:
        """Check if expense has receipt attachment."""
        # Check if expense has any attachments
        attachments = self.db.query(ExpenseAttachment).filter(
            ExpenseAttachment.expense_id == expense.id
        ).first()
        return attachments is not None
    
    def _can_user_submit_expense(self, user: User, expense: Expense) -> bool:
        """Check if user can submit expense for approval."""
        # Check if user is admin or has expense management permissions
        # This would integrate with the RBAC system
        return user.role in ["admin", "expense_manager"] or expense.user_id == user.id
    