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
    Expense, ExpenseApproval, ApprovalRule, User, ApprovalDelegate, ExpenseAttachment
)
from schemas.approval import ApprovalStatus, ApprovalRuleCreate, ApprovalRuleUpdate
from exceptions.approval_exceptions import (
    ValidationError, ExpenseValidationError, ApprovalRuleConflictError,
    DelegationValidationError, DelegationConflictError, ExpenseNotFoundException,
    ApprovalNotFoundException, ApprovalRuleNotFoundException
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
    
    def validate_approval_rule_create(self, rule_data: ApprovalRuleCreate) -> None:
        """
        Validate approval rule creation data.
        
        Args:
            rule_data: Approval rule creation data
            
        Raises:
            ValidationError: If validation fails
            ApprovalRuleConflictError: If rule conflicts with existing rules
        """
        # Validate name
        if not rule_data.name or not rule_data.name.strip():
            raise ValidationError(
                field="name",
                value=rule_data.name,
                reason="Rule name is required"
            )
        
        if len(rule_data.name.strip()) < 3:
            raise ValidationError(
                field="name",
                value=rule_data.name,
                reason="Rule name must be at least 3 characters long"
            )
        
        # Check for duplicate names
        existing_rule = self.db.query(ApprovalRule).filter(
            ApprovalRule.name == rule_data.name.strip()
        ).first()
        if existing_rule:
            raise ApprovalRuleConflictError(
                rule_name=rule_data.name,
                conflict_type="duplicate name",
                conflicting_rule_id=existing_rule.id
            )
        
        # Validate amount thresholds
        if rule_data.min_amount is not None and rule_data.min_amount < 0:
            raise ValidationError(
                field="min_amount",
                value=rule_data.min_amount,
                reason="Minimum amount cannot be negative"
            )
        
        if rule_data.max_amount is not None and rule_data.max_amount < 0:
            raise ValidationError(
                field="max_amount",
                value=rule_data.max_amount,
                reason="Maximum amount cannot be negative"
            )
        
        if (rule_data.min_amount is not None and rule_data.max_amount is not None and
            rule_data.max_amount <= rule_data.min_amount):
            raise ValidationError(
                field="max_amount",
                value=rule_data.max_amount,
                reason="Maximum amount must be greater than minimum amount"
            )
        
        # Validate currency
        if not self._is_valid_currency_code(rule_data.currency):
            raise ValidationError(
                field="currency",
                value=rule_data.currency,
                reason=f"Invalid currency code: {rule_data.currency}"
            )
        
        # Validate approval level
        if rule_data.approval_level < 1 or rule_data.approval_level > 10:
            raise ValidationError(
                field="approval_level",
                value=rule_data.approval_level,
                reason="Approval level must be between 1 and 10"
            )
        
        # Validate approver exists
        approver = self.db.query(User).filter(User.id == rule_data.approver_id).first()
        if not approver:
            raise ValidationError(
                field="approver_id",
                value=rule_data.approver_id,
                reason="Approver user not found"
            )
        
        # Validate priority
        if rule_data.priority < 0 or rule_data.priority > 1000:
            raise ValidationError(
                field="priority",
                value=rule_data.priority,
                reason="Priority must be between 0 and 1000"
            )
        
        # Validate auto-approve threshold
        if rule_data.auto_approve_below is not None:
            if rule_data.auto_approve_below < 0:
                raise ValidationError(
                    field="auto_approve_below",
                    value=rule_data.auto_approve_below,
                    reason="Auto-approve threshold cannot be negative"
                )
            
            if (rule_data.min_amount is not None and 
                rule_data.auto_approve_below > rule_data.min_amount):
                raise ValidationError(
                    field="auto_approve_below",
                    value=rule_data.auto_approve_below,
                    reason="Auto-approve threshold cannot exceed minimum amount"
                )
        
        # Validate category filter format
        if rule_data.category_filter:
            try:
                import json
                categories = json.loads(rule_data.category_filter)
                if not isinstance(categories, list):
                    raise ValueError("Must be a list")
                for category in categories:
                    if not isinstance(category, str) or not category.strip():
                        raise ValueError("Categories must be non-empty strings")
            except (json.JSONDecodeError, ValueError) as e:
                raise ValidationError(
                    field="category_filter",
                    value=rule_data.category_filter,
                    reason=f"Invalid category filter format: {str(e)}"
                )
        
        # Check for conflicting rules
        self._check_rule_conflicts(rule_data)
    
    def validate_approval_rule_update(
        self, 
        rule_id: int, 
        rule_data: ApprovalRuleUpdate
    ) -> ApprovalRule:
        """
        Validate approval rule update data.
        
        Args:
            rule_id: ID of the rule to update
            rule_data: Update data
            
        Returns:
            Existing ApprovalRule object
            
        Raises:
            ApprovalRuleNotFoundException: If rule not found
            ValidationError: If validation fails
        """
        # Get existing rule
        existing_rule = self.db.query(ApprovalRule).filter(
            ApprovalRule.id == rule_id
        ).first()
        if not existing_rule:
            raise ApprovalRuleNotFoundException(rule_id)
        
        # Validate fields that are being updated
        update_data = rule_data.model_dump(exclude_unset=True)
        
        # Name validation
        if "name" in update_data:
            name = update_data["name"]
            if not name or not name.strip():
                raise ValidationError(
                    field="name",
                    value=name,
                    reason="Rule name is required"
                )
            
            if len(name.strip()) < 3:
                raise ValidationError(
                    field="name",
                    value=name,
                    reason="Rule name must be at least 3 characters long"
                )
            
            # Check for duplicate names (excluding current rule)
            duplicate_rule = self.db.query(ApprovalRule).filter(
                and_(
                    ApprovalRule.name == name.strip(),
                    ApprovalRule.id != rule_id
                )
            ).first()
            if duplicate_rule:
                raise ApprovalRuleConflictError(
                    rule_name=name,
                    conflict_type="duplicate name",
                    conflicting_rule_id=duplicate_rule.id
                )
        
        # Amount validation
        min_amount = update_data.get("min_amount", existing_rule.min_amount)
        max_amount = update_data.get("max_amount", existing_rule.max_amount)
        
        if min_amount is not None and min_amount < 0:
            raise ValidationError(
                field="min_amount",
                value=min_amount,
                reason="Minimum amount cannot be negative"
            )
        
        if max_amount is not None and max_amount < 0:
            raise ValidationError(
                field="max_amount",
                value=max_amount,
                reason="Maximum amount cannot be negative"
            )
        
        if (min_amount is not None and max_amount is not None and
            max_amount <= min_amount):
            raise ValidationError(
                field="max_amount",
                value=max_amount,
                reason="Maximum amount must be greater than minimum amount"
            )
        
        # Currency validation
        if "currency" in update_data:
            currency = update_data["currency"]
            if not self._is_valid_currency_code(currency):
                raise ValidationError(
                    field="currency",
                    value=currency,
                    reason=f"Invalid currency code: {currency}"
                )
        
        # Approval level validation
        if "approval_level" in update_data:
            level = update_data["approval_level"]
            if level < 1 or level > 10:
                raise ValidationError(
                    field="approval_level",
                    value=level,
                    reason="Approval level must be between 1 and 10"
                )
        
        # Approver validation
        if "approver_id" in update_data:
            approver_id = update_data["approver_id"]
            approver = self.db.query(User).filter(User.id == approver_id).first()
            if not approver:
                raise ValidationError(
                    field="approver_id",
                    value=approver_id,
                    reason="Approver user not found"
                )
        
        # Priority validation
        if "priority" in update_data:
            priority = update_data["priority"]
            if priority < 0 or priority > 1000:
                raise ValidationError(
                    field="priority",
                    value=priority,
                    reason="Priority must be between 0 and 1000"
                )
        
        # Auto-approve validation
        if "auto_approve_below" in update_data:
            auto_approve = update_data["auto_approve_below"]
            if auto_approve is not None:
                if auto_approve < 0:
                    raise ValidationError(
                        field="auto_approve_below",
                        value=auto_approve,
                        reason="Auto-approve threshold cannot be negative"
                    )
                
                if min_amount is not None and auto_approve > min_amount:
                    raise ValidationError(
                        field="auto_approve_below",
                        value=auto_approve,
                        reason="Auto-approve threshold cannot exceed minimum amount"
                    )
        
        return existing_rule
    
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
    
    def _check_rule_conflicts(self, rule_data: ApprovalRuleCreate) -> None:
        """Check for conflicting approval rules."""
        # Check for overlapping amount ranges at the same level
        query = self.db.query(ApprovalRule).filter(
            and_(
                ApprovalRule.approval_level == rule_data.approval_level,
                ApprovalRule.currency == rule_data.currency,
                ApprovalRule.is_active == True
            )
        )
        
        # Add amount range filters
        if rule_data.min_amount is not None:
            query = query.filter(
                or_(
                    ApprovalRule.max_amount.is_(None),
                    ApprovalRule.max_amount > rule_data.min_amount
                )
            )
        
        if rule_data.max_amount is not None:
            query = query.filter(
                or_(
                    ApprovalRule.min_amount.is_(None),
                    ApprovalRule.min_amount < rule_data.max_amount
                )
            )
        
        conflicting_rules = query.all()
        
        if conflicting_rules:
            # Check for actual conflicts based on category filters
            for existing_rule in conflicting_rules:
                if self._rules_have_overlapping_categories(rule_data, existing_rule):
                    raise ApprovalRuleConflictError(
                        rule_name=rule_data.name,
                        conflict_type="overlapping amount range and categories",
                        conflicting_rule_id=existing_rule.id,
                        details={
                            "existing_rule_name": existing_rule.name,
                            "existing_min_amount": existing_rule.min_amount,
                            "existing_max_amount": existing_rule.max_amount,
                            "new_min_amount": rule_data.min_amount,
                            "new_max_amount": rule_data.max_amount
                        }
                    )
    
    def _rules_have_overlapping_categories(
        self, 
        new_rule: ApprovalRuleCreate, 
        existing_rule: ApprovalRule
    ) -> bool:
        """Check if two rules have overlapping category filters."""
        try:
            import json
            
            # If either rule has no category filter, they apply to all categories
            if not new_rule.category_filter or not existing_rule.category_filter:
                return True
            
            new_categories = set(json.loads(new_rule.category_filter))
            existing_categories = set(json.loads(existing_rule.category_filter))
            
            # Check for intersection
            return bool(new_categories.intersection(existing_categories))
            
        except (json.JSONDecodeError, TypeError):
            # If we can't parse the filters, assume they overlap to be safe
            return True