"""
Tests for Approval Permission Service

Tests cover:
- Approval limit validation based on user roles and approval rules
- Permission checks for approval rule management
- Delegation permission validation
- Complex approval workflow permissions
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session

from commercial.workflows.approvals.services.approval_permission_service import ApprovalPermissionService
from core.models.models_per_tenant import User, ApprovalRule, ApprovalDelegate, Expense
from core.utils.rbac import (
    can_approve_expenses,
    can_manage_approval_rules,
    can_delegate_approvals
)


class TestApprovalPermissionService:
    """Test cases for ApprovalPermissionService."""
    
    @pytest.fixture
    def permission_service(self, db_session: Session):
        """Create an ApprovalPermissionService instance."""
        return ApprovalPermissionService(db_session)
    
    @pytest.fixture
    def admin_user(self, db_session: Session):
        """Create an admin user."""
        user = User(
            email="admin@test.com",
            hashed_password="hashed",
            role="admin",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.fixture
    def regular_user(self, db_session: Session):
        """Create a regular user."""
        user = User(
            email="user@test.com",
            hashed_password="hashed",
            role="user",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.fixture
    def viewer_user(self, db_session: Session):
        """Create a viewer user."""
        user = User(
            email="viewer@test.com",
            hashed_password="hashed",
            role="viewer",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.fixture
    def delegate_user(self, db_session: Session):
        """Create a delegate user."""
        user = User(
            email="delegate@test.com",
            hashed_password="hashed",
            role="user",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.fixture
    def approval_rule(self, db_session: Session, regular_user):
        """Create an approval rule."""
        rule = ApprovalRule(
            name="Standard Approval",
            min_amount=0.0,
            max_amount=1000.0,
            currency="USD",
            approval_level=1,
            approver_id=regular_user.id,
            is_active=True,
            priority=1
        )
        db_session.add(rule)
        db_session.commit()
        db_session.refresh(rule)
        return rule
    
    @pytest.fixture
    def high_amount_rule(self, db_session: Session, admin_user):
        """Create a high amount approval rule."""
        rule = ApprovalRule(
            name="High Amount Approval",
            min_amount=1000.0,
            max_amount=10000.0,
            currency="USD",
            approval_level=2,
            approver_id=admin_user.id,
            is_active=True,
            priority=2
        )
        db_session.add(rule)
        db_session.commit()
        db_session.refresh(rule)
        return rule
    
    @pytest.fixture
    def test_expense(self, db_session: Session):
        """Create a test expense."""
        expense = Expense(
            amount=500.0,
            currency="USD",
            notes="Test expense",
            category="Office Supplies",
            status="pending_approval",
            expense_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        db_session.refresh(expense)
        return expense


class TestBasicPermissionChecks(TestApprovalPermissionService):
    """Test basic permission checks."""
    
    def test_admin_can_approve_expenses(self, admin_user):
        """Test that admin users can approve expenses."""
        assert can_approve_expenses(admin_user) is True
    
    def test_regular_user_can_approve_expenses(self, regular_user):
        """Test that regular users can approve expenses."""
        assert can_approve_expenses(regular_user) is True
    
    def test_viewer_cannot_approve_expenses(self, viewer_user):
        """Test that viewer users cannot approve expenses."""
        assert can_approve_expenses(viewer_user) is False
    
    def test_admin_can_manage_approval_rules(self, admin_user):
        """Test that admin users can manage approval rules."""
        assert can_manage_approval_rules(admin_user) is True
    
    def test_regular_user_cannot_manage_approval_rules(self, regular_user):
        """Test that regular users cannot manage approval rules."""
        assert can_manage_approval_rules(regular_user) is False
    
    def test_admin_can_delegate_approvals(self, admin_user):
        """Test that admin users can delegate approvals."""
        assert can_delegate_approvals(admin_user) is True
    
    def test_regular_user_can_delegate_approvals(self, regular_user):
        """Test that regular users can delegate approvals."""
        assert can_delegate_approvals(regular_user) is True
    
    def test_viewer_cannot_delegate_approvals(self, viewer_user):
        """Test that viewer users cannot delegate approvals."""
        assert can_delegate_approvals(viewer_user) is False


class TestApprovalLimitValidation(TestApprovalPermissionService):
    """Test approval limit validation."""
    
    def test_admin_can_approve_any_amount(self, permission_service, admin_user, test_expense):
        """Test that admin users can approve any amount."""
        # Admin should be able to approve regardless of amount
        test_expense.amount = 50000.0
        result = permission_service.validate_approval_permission(admin_user, test_expense)
        assert result is True
    
    def test_user_with_rule_can_approve_within_limits(
        self, permission_service, regular_user, test_expense, approval_rule
    ):
        """Test that users can approve within their rule limits."""
        # Expense amount is 500, rule allows up to 1000
        result = permission_service.validate_approval_permission(regular_user, test_expense)
        assert result is True
    
    def test_user_cannot_approve_above_limits(
        self, permission_service, regular_user, test_expense, approval_rule
    ):
        """Test that users cannot approve above their rule limits."""
        # Set expense amount above rule limit
        test_expense.amount = 1500.0
        result = permission_service.validate_approval_permission(regular_user, test_expense)
        assert result is False
    
    def test_user_without_rules_cannot_approve(
        self, permission_service, regular_user, test_expense
    ):
        """Test that users without approval rules cannot approve."""
        # No approval rules created for this user
        result = permission_service.validate_approval_permission(regular_user, test_expense)
        assert result is False
    
    def test_viewer_cannot_approve_any_amount(
        self, permission_service, viewer_user, test_expense
    ):
        """Test that viewer users cannot approve any amount."""
        with pytest.raises(HTTPException) as exc_info:
            permission_service.validate_approval_permission(viewer_user, test_expense)
        assert exc_info.value.status_code == 403


class TestApprovalLimitsRetrieval(TestApprovalPermissionService):
    """Test approval limits retrieval."""
    
    def test_get_admin_approval_limits(self, permission_service, admin_user):
        """Test getting approval limits for admin user."""
        limits = permission_service.get_user_approval_limits(admin_user)
        
        assert limits["can_approve"] is True
        assert limits["unlimited"] is True
        assert limits["max_amount"] is None
        assert limits["min_amount"] is None
    
    def test_get_user_approval_limits_with_rules(
        self, permission_service, regular_user, approval_rule
    ):
        """Test getting approval limits for user with rules."""
        limits = permission_service.get_user_approval_limits(regular_user)
        
        assert limits["can_approve"] is True
        assert limits["unlimited"] is False
        assert limits["max_amount"] == 1000.0
        assert limits["min_amount"] == 0.0
        assert 1 in limits["approval_levels"]
    
    def test_get_user_approval_limits_without_rules(
        self, permission_service, regular_user
    ):
        """Test getting approval limits for user without rules."""
        limits = permission_service.get_user_approval_limits(regular_user)
        
        assert limits["can_approve"] is False
        assert limits["unlimited"] is False
        assert limits["max_amount"] == 0
        assert limits["min_amount"] == 0
        assert limits["approval_levels"] == []


class TestRuleManagementPermissions(TestApprovalPermissionService):
    """Test approval rule management permissions."""
    
    def test_admin_can_manage_rules(self, permission_service, admin_user):
        """Test that admin users can manage approval rules."""
        # Should not raise exception
        permission_service.validate_rule_management_permission(admin_user)
    
    def test_regular_user_cannot_manage_rules(self, permission_service, regular_user):
        """Test that regular users cannot manage approval rules."""
        with pytest.raises(HTTPException) as exc_info:
            permission_service.validate_rule_management_permission(regular_user)
        assert exc_info.value.status_code == 403
    
    def test_viewer_cannot_manage_rules(self, permission_service, viewer_user):
        """Test that viewer users cannot manage approval rules."""
        with pytest.raises(HTTPException) as exc_info:
            permission_service.validate_rule_management_permission(viewer_user)
        assert exc_info.value.status_code == 403


class TestDelegationPermissions(TestApprovalPermissionService):
    """Test delegation permission validation."""
    
    def test_admin_can_delegate(self, permission_service, admin_user, delegate_user):
        """Test that admin users can set up delegations."""
        # Should not raise exception
        permission_service.validate_delegation_permission(admin_user, delegate_user)
    
    def test_regular_user_can_delegate(self, permission_service, regular_user, delegate_user):
        """Test that regular users can set up delegations."""
        # Should not raise exception
        permission_service.validate_delegation_permission(regular_user, delegate_user)
    
    def test_viewer_cannot_delegate(self, permission_service, viewer_user, delegate_user):
        """Test that viewer users cannot set up delegations."""
        with pytest.raises(HTTPException) as exc_info:
            permission_service.validate_delegation_permission(viewer_user, delegate_user)
        assert exc_info.value.status_code == 403
    
    def test_cannot_delegate_to_viewer(self, permission_service, admin_user, viewer_user):
        """Test that cannot delegate to viewer users."""
        with pytest.raises(HTTPException) as exc_info:
            permission_service.validate_delegation_permission(admin_user, viewer_user)
        assert exc_info.value.status_code == 400


class TestDelegationResolution(TestApprovalPermissionService):
    """Test delegation resolution logic."""
    
    def test_resolve_approver_without_delegation(
        self, permission_service, regular_user
    ):
        """Test resolving approver when no delegation exists."""
        effective_approver = permission_service.resolve_effective_approver(regular_user.id)
        assert effective_approver == regular_user.id
    
    def test_resolve_approver_with_active_delegation(
        self, permission_service, db_session, regular_user, delegate_user
    ):
        """Test resolving approver with active delegation."""
        # Create active delegation
        now = datetime.now(timezone.utc)
        delegation = ApprovalDelegate(
            approver_id=regular_user.id,
            delegate_id=delegate_user.id,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=7),
            is_active=True
        )
        db_session.add(delegation)
        db_session.commit()
        
        effective_approver = permission_service.resolve_effective_approver(regular_user.id)
        assert effective_approver == delegate_user.id
    
    def test_resolve_approver_with_expired_delegation(
        self, permission_service, db_session, regular_user, delegate_user
    ):
        """Test resolving approver with expired delegation."""
        # Create expired delegation
        now = datetime.now(timezone.utc)
        delegation = ApprovalDelegate(
            approver_id=regular_user.id,
            delegate_id=delegate_user.id,
            start_date=now - timedelta(days=7),
            end_date=now - timedelta(days=1),
            is_active=True
        )
        db_session.add(delegation)
        db_session.commit()
        
        effective_approver = permission_service.resolve_effective_approver(regular_user.id)
        assert effective_approver == regular_user.id


class TestDelegationValidation(TestApprovalPermissionService):
    """Test delegation setup validation."""
    
    def test_validate_valid_delegation_setup(
        self, permission_service, regular_user, delegate_user
    ):
        """Test validating a valid delegation setup."""
        start_date = datetime.now(timezone.utc) + timedelta(days=1)
        end_date = start_date + timedelta(days=7)
        
        # Should not raise exception
        permission_service.validate_delegation_setup(
            regular_user.id, delegate_user.id, start_date, end_date
        )
    
    def test_validate_delegation_invalid_date_range(
        self, permission_service, regular_user, delegate_user
    ):
        """Test validating delegation with invalid date range."""
        start_date = datetime.now(timezone.utc) + timedelta(days=7)
        end_date = start_date - timedelta(days=1)  # End before start
        
        with pytest.raises(HTTPException) as exc_info:
            permission_service.validate_delegation_setup(
                regular_user.id, delegate_user.id, start_date, end_date
            )
        assert exc_info.value.status_code == 400
        assert "start date must be before end date" in exc_info.value.detail
    
    def test_validate_delegation_to_self(
        self, permission_service, regular_user
    ):
        """Test validating delegation to self."""
        start_date = datetime.now(timezone.utc) + timedelta(days=1)
        end_date = start_date + timedelta(days=7)
        
        with pytest.raises(HTTPException) as exc_info:
            permission_service.validate_delegation_setup(
                regular_user.id, regular_user.id, start_date, end_date
            )
        assert exc_info.value.status_code == 400
        assert "Cannot delegate to yourself" in exc_info.value.detail
    
    def test_validate_overlapping_delegation(
        self, permission_service, db_session, regular_user, delegate_user
    ):
        """Test validating overlapping delegation."""
        # Create existing delegation
        now = datetime.now(timezone.utc)
        existing_delegation = ApprovalDelegate(
            approver_id=regular_user.id,
            delegate_id=delegate_user.id,
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=7),
            is_active=True
        )
        db_session.add(existing_delegation)
        db_session.commit()
        
        # Try to create overlapping delegation
        start_date = now + timedelta(days=3)
        end_date = now + timedelta(days=10)
        
        with pytest.raises(HTTPException) as exc_info:
            permission_service.validate_delegation_setup(
                regular_user.id, delegate_user.id, start_date, end_date
            )
        assert exc_info.value.status_code == 400
        assert "overlaps with existing delegation" in exc_info.value.detail


class TestApprovalLevelValidation(TestApprovalPermissionService):
    """Test approval level validation."""
    
    def test_user_can_approve_at_level_with_rule(
        self, permission_service, regular_user, approval_rule
    ):
        """Test that user can approve at level with matching rule."""
        result = permission_service.can_user_approve_at_level(
            regular_user, 1, 500.0, "USD"
        )
        assert result is True
    
    def test_user_cannot_approve_at_level_without_rule(
        self, permission_service, regular_user
    ):
        """Test that user cannot approve at level without matching rule."""
        result = permission_service.can_user_approve_at_level(
            regular_user, 2, 500.0, "USD"
        )
        assert result is False
    
    def test_admin_can_approve_at_any_level(
        self, permission_service, admin_user
    ):
        """Test that admin can approve at any level."""
        result = permission_service.can_user_approve_at_level(
            admin_user, 5, 50000.0, "USD"
        )
        assert result is True


class TestUserRetrieval(TestApprovalPermissionService):
    """Test user retrieval functions."""
    
    def test_get_users_with_approval_permission(
        self, permission_service, admin_user, regular_user, viewer_user
    ):
        """Test getting users with approval permissions."""
        users = permission_service.get_users_with_approval_permission()
        user_emails = [user.email for user in users]
        
        assert admin_user.email in user_emails
        assert regular_user.email in user_emails
        assert viewer_user.email not in user_emails
    
    def test_get_approval_rule_managers(
        self, permission_service, admin_user, regular_user, viewer_user
    ):
        """Test getting users who can manage approval rules."""
        managers = permission_service.get_approval_rule_managers()
        manager_emails = [manager.email for manager in managers]
        
        assert admin_user.email in manager_emails
        assert regular_user.email not in manager_emails
        assert viewer_user.email not in manager_emails