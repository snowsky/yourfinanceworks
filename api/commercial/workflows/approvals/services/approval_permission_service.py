"""
Approval Permission Service

This service handles approval-specific permission checks including:
- Approval limit validation based on user roles and approval rules
- Permission checks for approval rule management
- Delegation permission validation
- Complex approval workflow permissions
"""

from typing import List, Optional, Union
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.models.models_per_tenant import User, ApprovalRule, ApprovalDelegate, Expense
from core.models.models import MasterUser
from core.utils.rbac import (
    require_approval_permission,
    require_approval_rule_management,
    require_delegation_permission,
    can_approve_expenses,
    can_manage_approval_rules,
    can_delegate_approvals
)
from core.constants.error_codes import ROLE_NOT_ALLOWED


class ApprovalPermissionService:
    """Service for handling approval-specific permission checks."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_approval_permission(
        self, 
        user: Union[User, MasterUser], 
        expense: Expense,
        approval_level: int = 1
    ) -> bool:
        """
        Validate if a user can approve a specific expense.
        
        Args:
            user: The user attempting to approve
            expense: The expense to be approved
            approval_level: The approval level being validated
            
        Returns:
            bool: True if user can approve this expense
            
        Raises:
            HTTPException: If user lacks approval permissions
        """
        # Basic role check
        if not can_approve_expenses(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have approval permissions"
            )
        
        # Check if user has approval limits for this expense amount
        return self._validate_approval_limits(user, expense.amount, expense.currency, approval_level)
    
    def _validate_approval_limits(
        self, 
        user: Union[User, MasterUser], 
        amount: float, 
        currency: str,
        approval_level: int
    ) -> bool:
        """
        Validate if a user can approve expenses up to the specified amount.
        
        Args:
            user: The user attempting to approve
            amount: The expense amount
            currency: The expense currency
            approval_level: The approval level
            
        Returns:
            bool: True if user can approve this amount
        """
        # Admin users can approve any amount (subject to approval rules)
        if user.role == "admin":
            return True
        
        # For non-admin users, check approval rules to determine limits
        approval_rules = self.db.query(ApprovalRule).filter(
            ApprovalRule.approver_id == user.id,
            ApprovalRule.is_active == True,
            ApprovalRule.approval_level == approval_level,
            ApprovalRule.currency == currency
        ).all()
        
        # If no specific rules found, check for rules without currency restriction
        if not approval_rules:
            approval_rules = self.db.query(ApprovalRule).filter(
                ApprovalRule.approver_id == user.id,
                ApprovalRule.is_active == True,
                ApprovalRule.approval_level == approval_level
            ).all()
        
        # If user has no approval rules, they cannot approve
        if not approval_rules:
            return False
        
        # Check if any rule allows this amount
        for rule in approval_rules:
            if self._amount_within_rule_limits(amount, rule):
                return True
        
        return False
    
    def _amount_within_rule_limits(self, amount: float, rule: ApprovalRule) -> bool:
        """
        Check if an amount falls within the limits of an approval rule.
        
        Args:
            amount: The expense amount
            rule: The approval rule to check against
            
        Returns:
            bool: True if amount is within rule limits
        """
        # Check minimum amount
        if rule.min_amount is not None and amount < rule.min_amount:
            return False
        
        # Check maximum amount
        if rule.max_amount is not None and amount > rule.max_amount:
            return False
        
        return True
    
    def get_user_approval_limits(
        self, 
        user: Union[User, MasterUser], 
        currency: str = "USD"
    ) -> dict:
        """
        Get the approval limits for a user.
        
        Args:
            user: The user to check limits for
            currency: The currency to check limits for
            
        Returns:
            dict: Dictionary containing approval limits information
        """
        if user.role == "admin":
            return {
                "can_approve": True,
                "max_amount": None,  # No limit for admins
                "min_amount": None,
                "approval_levels": [],
                "unlimited": True
            }
        
        approval_rules = self.db.query(ApprovalRule).filter(
            ApprovalRule.approver_id == user.id,
            ApprovalRule.is_active == True,
            ApprovalRule.currency == currency
        ).all()
        
        if not approval_rules:
            return {
                "can_approve": False,
                "max_amount": 0,
                "min_amount": 0,
                "approval_levels": [],
                "unlimited": False
            }
        
        # Calculate overall limits from all rules
        max_amounts = [rule.max_amount for rule in approval_rules if rule.max_amount is not None]
        min_amounts = [rule.min_amount for rule in approval_rules if rule.min_amount is not None]
        approval_levels = list(set([rule.approval_level for rule in approval_rules]))
        
        return {
            "can_approve": True,
            "max_amount": max(max_amounts) if max_amounts else None,
            "min_amount": min(min_amounts) if min_amounts else None,
            "approval_levels": sorted(approval_levels),
            "unlimited": not max_amounts  # Unlimited if no max amounts defined
        }
    
    def validate_rule_management_permission(self, user: Union[User, MasterUser]) -> None:
        """
        Validate if a user can manage approval rules.
        
        Args:
            user: The user attempting to manage rules
            
        Raises:
            HTTPException: If user lacks rule management permissions
        """
        require_approval_rule_management(user, "manage approval rules")
    
    def validate_delegation_permission(
        self, 
        user: Union[User, MasterUser], 
        delegate_user: Optional[Union[User, MasterUser]] = None
    ) -> None:
        """
        Validate if a user can set up approval delegations.
        
        Args:
            user: The user attempting to set up delegation
            delegate_user: The user being delegated to (optional)
            
        Raises:
            HTTPException: If user lacks delegation permissions
        """
        require_delegation_permission(user, "set up approval delegations")
        
        # Additional validation: ensure delegate has approval permissions
        if delegate_user and not can_approve_expenses(delegate_user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delegate user does not have approval permissions"
            )
    
    def get_active_delegation(
        self, 
        approver_id: int, 
        current_time: Optional[datetime] = None
    ) -> Optional[ApprovalDelegate]:
        """
        Get the active delegation for an approver.
        
        Args:
            approver_id: The ID of the approver
            current_time: The current time (defaults to now)
            
        Returns:
            ApprovalDelegate: The active delegation, if any
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        return self.db.query(ApprovalDelegate).filter(
            ApprovalDelegate.approver_id == approver_id,
            ApprovalDelegate.is_active == True,
            ApprovalDelegate.start_date <= current_time,
            ApprovalDelegate.end_date >= current_time
        ).first()
    
    def resolve_effective_approver(
        self, 
        approver_id: int, 
        current_time: Optional[datetime] = None
    ) -> int:
        """
        Resolve the effective approver, considering active delegations.
        
        Args:
            approver_id: The original approver ID
            current_time: The current time (defaults to now)
            
        Returns:
            int: The effective approver ID (delegate if active, otherwise original)
        """
        delegation = self.get_active_delegation(approver_id, current_time)
        return delegation.delegate_id if delegation else approver_id
    
    def validate_delegation_setup(
        self,
        approver_id: int,
        delegate_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> None:
        """
        Validate a delegation setup for business rules.
        
        Args:
            approver_id: The approver setting up delegation
            delegate_id: The delegate user ID
            start_date: Delegation start date
            end_date: Delegation end date
            
        Raises:
            HTTPException: If delegation setup violates business rules
        """
        # Validate date range
        if start_date >= end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delegation start date must be before end date"
            )
        
        # Validate that approver is not delegating to themselves
        if approver_id == delegate_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delegate to yourself"
            )
        
        # Check for overlapping delegations
        overlapping = self.db.query(ApprovalDelegate).filter(
            ApprovalDelegate.approver_id == approver_id,
            ApprovalDelegate.is_active == True,
            ApprovalDelegate.start_date < end_date,
            ApprovalDelegate.end_date > start_date
        ).first()
        
        if overlapping:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delegation period overlaps with existing delegation"
            )
    
    def can_user_approve_at_level(
        self, 
        user: Union[User, MasterUser], 
        approval_level: int,
        amount: float,
        currency: str = "USD"
    ) -> bool:
        """
        Check if a user can approve at a specific approval level.
        
        Args:
            user: The user to check
            approval_level: The approval level
            amount: The expense amount
            currency: The expense currency
            
        Returns:
            bool: True if user can approve at this level
        """
        if not can_approve_expenses(user):
            return False
        
        return self._validate_approval_limits(user, amount, currency, approval_level)
    
    def get_users_with_approval_permission(self) -> List[User]:
        """
        Get all users who have approval permissions.
        
        Returns:
            List[User]: List of users with approval permissions
        """
        return self.db.query(User).filter(
            User.role.in_(["admin", "user"]),
            User.is_active == True
        ).all()
    
    def get_approval_rule_managers(self) -> List[User]:
        """
        Get all users who can manage approval rules.
        
        Returns:
            List[User]: List of users who can manage approval rules
        """
        return self.db.query(User).filter(
            User.role == "admin",
            User.is_active == True
        ).all()