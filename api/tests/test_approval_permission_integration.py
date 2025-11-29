"""
Integration Tests for Approval Permission System

Tests the integration between the approval permission service and the approval service.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session

from commercial.workflows.approvals.services.approval_service import ApprovalService, InsufficientApprovalPermissions
from commercial.workflows.approvals.services.approval_permission_service import ApprovalPermissionService
from core.models.models_per_tenant import User, ApprovalRule, ApprovalDelegate, Expense, ExpenseApproval
from core.schemas.approval import ApprovalStatus


class TestApprovalPermissionIntegration:
    """Integration tests for approval permission system."""
    
    @pytest.fixture
    def permission_service(self, db_session: Session):
        """Create an ApprovalPermissionService instance."""
        return ApprovalPermissionService(db_session)
    
    @pytest.fixture
    def approval_service(self, db_session: Session):
        """Create an ApprovalService instance."""
        return ApprovalService(db_session)
    
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
    def approver_user(self, db_session: Session):
        """Create an approver user."""
        user = User(
            email="approver@test.com",
            hashed_password="hashed",
            role="user",
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
    def approval_rule(self, db_session: Session, approver_user):
        """Create an approval rule."""
        rule = ApprovalRule(
            name="Standard Approval",
            min_amount=0.0,
            max_amount=1000.0,
            currency="USD",
            approval_level=1,
            approver_id=approver_user.id,
            is_active=True,
            priority=1
        )
        db_session.add(rule)
        db_session.commit()
        db_session.refresh(rule)
        return rule
    
    @pytest.fixture
    def test_expense(self, db_session: Session, regular_user):
        """Create a test expense."""
        expense = Expense(
            amount=500.0,
            currency="USD",
            notes="Test expense",
            category="Office Supplies",
            status="draft",
            expense_date=datetime.now(timezone.utc),
            user_id=regular_user.id,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        db_session.refresh(expense)
        return expense
    
    @pytest.fixture
    def pending_approval(self, db_session: Session, test_expense, approver_user, approval_rule):
        """Create a pending approval."""
        approval = ExpenseApproval(
            expense_id=test_expense.id,
            approver_id=approver_user.id,
            approval_rule_id=approval_rule.id,
            status=ApprovalStatus.PENDING,
            submitted_at=datetime.now(timezone.utc),
            approval_level=1,
            is_current_level=True
        )
        db_session.add(approval)
        db_session.commit()
        db_session.refresh(approval)
        return approval


class TestSubmissionPermissions(TestApprovalPermissionIntegration):
    """Test submission permission integration."""
    
    def test_admin_can_submit_for_approval(
        self, approval_service, admin_user, test_expense, approval_rule
    ):
        """Test that admin users can submit expenses for approval."""
        # Should not raise exception
        approvals = approval_service.submit_for_approval(
            test_expense.id, admin_user.id, "Admin submission"
        )
        assert len(approvals) > 0
    
    def test_regular_user_can_submit_for_approval(
        self, approval_service, regular_user, test_expense, approval_rule
    ):
        """Test that regular users can submit expenses for approval."""
        # Should not raise exception
        approvals = approval_service.submit_for_approval(
            test_expense.id, regular_user.id, "User submission"
        )
        assert len(approvals) > 0
    
    def test_viewer_cannot_submit_for_approval(
        self, approval_service, viewer_user, test_expense, approval_rule
    ):
        """Test that viewer users cannot submit expenses for approval."""
        with pytest.raises(HTTPException) as exc_info:
            approval_service.submit_for_approval(
                test_expense.id, viewer_user.id, "Viewer submission"
            )
        assert exc_info.value.status_code == 403


class TestApprovalPermissions(TestApprovalPermissionIntegration):
    """Test approval permission integration."""
    
    def test_designated_approver_can_approve(
        self, approval_service, approver_user, pending_approval
    ):
        """Test that designated approvers can approve expenses."""
        # Should not raise exception
        updated_approval = approval_service.approve_expense(
            pending_approval.id, approver_user.id, "Approved by designated approver"
        )
        assert updated_approval.status == ApprovalStatus.APPROVED
    
    def test_admin_can_approve_any_expense(
        self, approval_service, admin_user, pending_approval
    ):
        """Test that admin users can approve any expense."""
        # Admin should be able to approve even if not designated approver
        updated_approval = approval_service.approve_expense(
            pending_approval.id, admin_user.id, "Approved by admin"
        )
        assert updated_approval.status == ApprovalStatus.APPROVED
    
    def test_regular_user_cannot_approve_without_permission(
        self, approval_service, regular_user, pending_approval
    ):
        """Test that regular users cannot approve without permission."""
        with pytest.raises(InsufficientApprovalPermissions):
            approval_service.approve_expense(
                pending_approval.id, regular_user.id, "Unauthorized approval"
            )
    
    def test_viewer_cannot_approve_any_expense(
        self, approval_service, viewer_user, pending_approval
    ):
        """Test that viewer users cannot approve any expense."""
        with pytest.raises(InsufficientApprovalPermissions):
            approval_service.approve_expense(
                pending_approval.id, viewer_user.id, "Viewer approval attempt"
            )


class TestDelegationIntegration(TestApprovalPermissionIntegration):
    """Test delegation integration with approval service."""
    
    def test_delegate_can_approve_on_behalf(
        self, db_session, approval_service, approver_user, delegate_user, pending_approval
    ):
        """Test that delegates can approve on behalf of approvers."""
        # Create active delegation
        now = datetime.now(timezone.utc)
        delegation = ApprovalDelegate(
            approver_id=approver_user.id,
            delegate_id=delegate_user.id,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=7),
            is_active=True
        )
        db_session.add(delegation)
        db_session.commit()
        
        # Delegate should be able to approve
        updated_approval = approval_service.approve_expense(
            pending_approval.id, delegate_user.id, "Approved by delegate"
        )
        assert updated_approval.status == ApprovalStatus.APPROVED
    
    def test_expired_delegate_cannot_approve(
        self, db_session, approval_service, approver_user, delegate_user, pending_approval
    ):
        """Test that expired delegates cannot approve."""
        # Create expired delegation
        now = datetime.now(timezone.utc)
        delegation = ApprovalDelegate(
            approver_id=approver_user.id,
            delegate_id=delegate_user.id,
            start_date=now - timedelta(days=7),
            end_date=now - timedelta(days=1),
            is_active=True
        )
        db_session.add(delegation)
        db_session.commit()
        
        # Expired delegate should not be able to approve
        with pytest.raises(InsufficientApprovalPermissions):
            approval_service.approve_expense(
                pending_approval.id, delegate_user.id, "Expired delegate approval"
            )


class TestApprovalLimitIntegration(TestApprovalPermissionIntegration):
    """Test approval limit integration."""
    
    def test_approver_can_approve_within_limits(
        self, approval_service, approver_user, pending_approval
    ):
        """Test that approvers can approve within their limits."""
        # Expense amount is 500, rule allows up to 1000
        updated_approval = approval_service.approve_expense(
            pending_approval.id, approver_user.id, "Within limits"
        )
        assert updated_approval.status == ApprovalStatus.APPROVED
    
    def test_approver_cannot_approve_above_limits(
        self, db_session, approval_service, approver_user, approval_rule
    ):
        """Test that approvers cannot approve above their limits."""
        # Create high-value expense
        high_expense = Expense(
            amount=1500.0,  # Above the 1000 limit
            currency="USD",
            notes="High value expense",
            category="Equipment",
            status="draft",
            expense_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(high_expense)
        db_session.commit()
        db_session.refresh(high_expense)
        
        # Create approval for high-value expense
        high_approval = ExpenseApproval(
            expense_id=high_expense.id,
            approver_id=approver_user.id,
            approval_rule_id=approval_rule.id,
            status=ApprovalStatus.PENDING,
            submitted_at=datetime.now(timezone.utc),
            approval_level=1,
            is_current_level=True
        )
        db_session.add(high_approval)
        db_session.commit()
        db_session.refresh(high_approval)
        
        # Approver should not be able to approve above their limit
        with pytest.raises(InsufficientApprovalPermissions):
            approval_service.approve_expense(
                high_approval.id, approver_user.id, "Above limits"
            )


class TestPermissionServiceIntegration(TestApprovalPermissionIntegration):
    """Test direct permission service integration."""
    
    def test_permission_service_validates_approval_limits(
        self, permission_service, approver_user, test_expense, approval_rule
    ):
        """Test that permission service validates approval limits correctly."""
        # Should pass validation within limits
        result = permission_service.validate_approval_permission(
            approver_user, test_expense, 1
        )
        assert result is True
    
    def test_permission_service_rejects_above_limits(
        self, db_session, permission_service, approver_user, approval_rule
    ):
        """Test that permission service rejects approvals above limits."""
        # Create high-value expense
        high_expense = Expense(
            amount=1500.0,  # Above the 1000 limit
            currency="USD",
            notes="High value expense",
            category="Equipment",
            status="draft",
            expense_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(high_expense)
        db_session.commit()
        db_session.refresh(high_expense)
        
        # Should fail validation above limits
        result = permission_service.validate_approval_permission(
            approver_user, high_expense, 1
        )
        assert result is False
    
    def test_permission_service_resolves_delegation(
        self, db_session, permission_service, approver_user, delegate_user
    ):
        """Test that permission service resolves delegation correctly."""
        # Create active delegation
        now = datetime.now(timezone.utc)
        delegation = ApprovalDelegate(
            approver_id=approver_user.id,
            delegate_id=delegate_user.id,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=7),
            is_active=True
        )
        db_session.add(delegation)
        db_session.commit()
        
        # Should resolve to delegate
        effective_approver = permission_service.resolve_effective_approver(approver_user.id)
        assert effective_approver == delegate_user.id
    
    def test_permission_service_gets_user_limits(
        self, permission_service, approver_user, approval_rule
    ):
        """Test that permission service gets user limits correctly."""
        limits = permission_service.get_user_approval_limits(approver_user)
        
        assert limits["can_approve"] is True
        assert limits["max_amount"] == 1000.0
        assert limits["min_amount"] == 0.0
        assert 1 in limits["approval_levels"]