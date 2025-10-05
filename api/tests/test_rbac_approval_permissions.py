"""
Tests for RBAC Approval Permission Functions

Tests cover the approval-specific permission functions added to the RBAC utility.
"""

import pytest
from fastapi import HTTPException

from models.models_per_tenant import User
from models.models import MasterUser
from utils.rbac import (
    can_submit_for_approval,
    can_approve_expenses,
    can_approve_amount,
    can_manage_approval_rules,
    can_delegate_approvals,
    can_view_approval_history,
    can_view_all_approvals,
    require_approval_submission,
    require_approval_permission,
    require_approval_rule_management,
    require_delegation_permission
)


class TestApprovalPermissionFunctions:
    """Test approval permission functions."""
    
    @pytest.fixture
    def admin_user(self):
        """Create an admin user."""
        return User(
            id=1,
            email="admin@test.com",
            role="admin",
            is_active=True
        )
    
    @pytest.fixture
    def regular_user(self):
        """Create a regular user."""
        return User(
            id=2,
            email="user@test.com",
            role="user",
            is_active=True
        )
    
    @pytest.fixture
    def viewer_user(self):
        """Create a viewer user."""
        return User(
            id=3,
            email="viewer@test.com",
            role="viewer",
            is_active=True
        )
    
    @pytest.fixture
    def master_admin_user(self):
        """Create a master admin user."""
        return MasterUser(
            id=1,
            email="master@test.com",
            role="admin",
            is_active=True,
            is_superuser=True
        )


class TestSubmissionPermissions(TestApprovalPermissionFunctions):
    """Test expense submission permissions."""
    
    def test_admin_can_submit_for_approval(self, admin_user):
        """Test that admin users can submit expenses for approval."""
        assert can_submit_for_approval(admin_user) is True
    
    def test_regular_user_can_submit_for_approval(self, regular_user):
        """Test that regular users can submit expenses for approval."""
        assert can_submit_for_approval(regular_user) is True
    
    def test_viewer_cannot_submit_for_approval(self, viewer_user):
        """Test that viewer users cannot submit expenses for approval."""
        assert can_submit_for_approval(viewer_user) is False
    
    def test_require_approval_submission_admin(self, admin_user):
        """Test that admin users pass approval submission requirement."""
        # Should not raise exception
        require_approval_submission(admin_user)
    
    def test_require_approval_submission_user(self, regular_user):
        """Test that regular users pass approval submission requirement."""
        # Should not raise exception
        require_approval_submission(regular_user)
    
    def test_require_approval_submission_viewer_fails(self, viewer_user):
        """Test that viewer users fail approval submission requirement."""
        with pytest.raises(HTTPException) as exc_info:
            require_approval_submission(viewer_user)
        assert exc_info.value.status_code == 403


class TestApprovalPermissions(TestApprovalPermissionFunctions):
    """Test expense approval permissions."""
    
    def test_admin_can_approve_expenses(self, admin_user):
        """Test that admin users can approve expenses."""
        assert can_approve_expenses(admin_user) is True
    
    def test_regular_user_can_approve_expenses(self, regular_user):
        """Test that regular users can approve expenses."""
        assert can_approve_expenses(regular_user) is True
    
    def test_viewer_cannot_approve_expenses(self, viewer_user):
        """Test that viewer users cannot approve expenses."""
        assert can_approve_expenses(viewer_user) is False
    
    def test_admin_can_approve_any_amount(self, admin_user):
        """Test that admin users can approve any amount."""
        assert can_approve_amount(admin_user, 50000.0, "USD") is True
    
    def test_regular_user_can_approve_amount_basic_check(self, regular_user):
        """Test that regular users pass basic amount approval check."""
        # This is just the basic role check - actual limits are enforced elsewhere
        assert can_approve_amount(regular_user, 1000.0, "USD") is True
    
    def test_viewer_cannot_approve_any_amount(self, viewer_user):
        """Test that viewer users cannot approve any amount."""
        assert can_approve_amount(viewer_user, 100.0, "USD") is False
    
    def test_require_approval_permission_admin(self, admin_user):
        """Test that admin users pass approval permission requirement."""
        # Should not raise exception
        require_approval_permission(admin_user)
    
    def test_require_approval_permission_user(self, regular_user):
        """Test that regular users pass approval permission requirement."""
        # Should not raise exception
        require_approval_permission(regular_user)
    
    def test_require_approval_permission_viewer_fails(self, viewer_user):
        """Test that viewer users fail approval permission requirement."""
        with pytest.raises(HTTPException) as exc_info:
            require_approval_permission(viewer_user)
        assert exc_info.value.status_code == 403


class TestRuleManagementPermissions(TestApprovalPermissionFunctions):
    """Test approval rule management permissions."""
    
    def test_admin_can_manage_approval_rules(self, admin_user):
        """Test that admin users can manage approval rules."""
        assert can_manage_approval_rules(admin_user) is True
    
    def test_regular_user_cannot_manage_approval_rules(self, regular_user):
        """Test that regular users cannot manage approval rules."""
        assert can_manage_approval_rules(regular_user) is False
    
    def test_viewer_cannot_manage_approval_rules(self, viewer_user):
        """Test that viewer users cannot manage approval rules."""
        assert can_manage_approval_rules(viewer_user) is False
    
    def test_master_admin_can_manage_approval_rules(self, master_admin_user):
        """Test that master admin users can manage approval rules."""
        assert can_manage_approval_rules(master_admin_user) is True
    
    def test_require_approval_rule_management_admin(self, admin_user):
        """Test that admin users pass rule management requirement."""
        # Should not raise exception
        require_approval_rule_management(admin_user)
    
    def test_require_approval_rule_management_user_fails(self, regular_user):
        """Test that regular users fail rule management requirement."""
        with pytest.raises(HTTPException) as exc_info:
            require_approval_rule_management(regular_user)
        assert exc_info.value.status_code == 403
    
    def test_require_approval_rule_management_viewer_fails(self, viewer_user):
        """Test that viewer users fail rule management requirement."""
        with pytest.raises(HTTPException) as exc_info:
            require_approval_rule_management(viewer_user)
        assert exc_info.value.status_code == 403


class TestDelegationPermissions(TestApprovalPermissionFunctions):
    """Test approval delegation permissions."""
    
    def test_admin_can_delegate_approvals(self, admin_user):
        """Test that admin users can delegate approvals."""
        assert can_delegate_approvals(admin_user) is True
    
    def test_regular_user_can_delegate_approvals(self, regular_user):
        """Test that regular users can delegate approvals."""
        assert can_delegate_approvals(regular_user) is True
    
    def test_viewer_cannot_delegate_approvals(self, viewer_user):
        """Test that viewer users cannot delegate approvals."""
        assert can_delegate_approvals(viewer_user) is False
    
    def test_require_delegation_permission_admin(self, admin_user):
        """Test that admin users pass delegation permission requirement."""
        # Should not raise exception
        require_delegation_permission(admin_user)
    
    def test_require_delegation_permission_user(self, regular_user):
        """Test that regular users pass delegation permission requirement."""
        # Should not raise exception
        require_delegation_permission(regular_user)
    
    def test_require_delegation_permission_viewer_fails(self, viewer_user):
        """Test that viewer users fail delegation permission requirement."""
        with pytest.raises(HTTPException) as exc_info:
            require_delegation_permission(viewer_user)
        assert exc_info.value.status_code == 403


class TestViewingPermissions(TestApprovalPermissionFunctions):
    """Test approval viewing permissions."""
    
    def test_admin_can_view_approval_history(self, admin_user):
        """Test that admin users can view approval history."""
        assert can_view_approval_history(admin_user) is True
    
    def test_regular_user_can_view_approval_history(self, regular_user):
        """Test that regular users can view approval history."""
        assert can_view_approval_history(regular_user) is True
    
    def test_viewer_cannot_view_approval_history(self, viewer_user):
        """Test that viewer users cannot view approval history."""
        assert can_view_approval_history(viewer_user) is False
    
    def test_admin_can_view_all_approvals(self, admin_user):
        """Test that admin users can view all approvals."""
        assert can_view_all_approvals(admin_user) is True
    
    def test_regular_user_cannot_view_all_approvals(self, regular_user):
        """Test that regular users cannot view all approvals."""
        assert can_view_all_approvals(regular_user) is False
    
    def test_viewer_cannot_view_all_approvals(self, viewer_user):
        """Test that viewer users cannot view all approvals."""
        assert can_view_all_approvals(viewer_user) is False


class TestMasterUserPermissions(TestApprovalPermissionFunctions):
    """Test permissions for master users."""
    
    def test_master_admin_has_all_permissions(self, master_admin_user):
        """Test that master admin users have all approval permissions."""
        assert can_submit_for_approval(master_admin_user) is True
        assert can_approve_expenses(master_admin_user) is True
        assert can_approve_amount(master_admin_user, 100000.0, "USD") is True
        assert can_manage_approval_rules(master_admin_user) is True
        assert can_delegate_approvals(master_admin_user) is True
        assert can_view_approval_history(master_admin_user) is True
        assert can_view_all_approvals(master_admin_user) is True
    
    def test_master_admin_passes_all_requirements(self, master_admin_user):
        """Test that master admin users pass all permission requirements."""
        # Should not raise exceptions
        require_approval_submission(master_admin_user)
        require_approval_permission(master_admin_user)
        require_approval_rule_management(master_admin_user)
        require_delegation_permission(master_admin_user)


class TestEdgeCases(TestApprovalPermissionFunctions):
    """Test edge cases and error conditions."""
    
    def test_inactive_user_permissions(self):
        """Test permissions for inactive users."""
        inactive_user = User(
            id=4,
            email="inactive@test.com",
            role="admin",
            is_active=False
        )
        
        # Permissions should still work based on role, but business logic
        # should check is_active separately
        assert can_approve_expenses(inactive_user) is True
        assert can_manage_approval_rules(inactive_user) is True
    
    def test_user_without_role(self):
        """Test permissions for user without explicit role."""
        user_no_role = User(
            id=5,
            email="norole@test.com",
            role=None,
            is_active=True
        )
        
        # Should default to no permissions
        assert can_approve_expenses(user_no_role) is False
        assert can_manage_approval_rules(user_no_role) is False
    
    def test_custom_action_messages(self, viewer_user):
        """Test that custom action messages are included in exceptions."""
        with pytest.raises(HTTPException) as exc_info:
            require_approval_permission(viewer_user, "approve high-value expenses")
        
        # The specific action should be mentioned in error handling
        assert exc_info.value.status_code == 403