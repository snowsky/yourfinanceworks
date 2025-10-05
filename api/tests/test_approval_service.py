"""
Unit tests for ApprovalService

Tests cover all core approval workflow functionality including:
- Expense submission for approval
- Approval and rejection decisions
- Multi-level approval workflows
- Approval delegation
- Auto-approval logic
- Status transitions and audit trails
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from api.services.approval_service import (
    ApprovalService, ApprovalServiceError, InsufficientApprovalPermissions,
    ExpenseAlreadyApproved, NoApprovalRuleFound, ApprovalLevelMismatch,
    InvalidApprovalState
)
from api.models.models_per_tenant import (
    Expense, ExpenseApproval, ApprovalRule, User, ApprovalDelegate
)
from api.schemas.approval import (
    ApprovalStatus, ApprovalDelegateCreate, ExpenseApprovalCreate
)
from api.services.approval_service import ValidationError


class TestApprovalService:
    """Test suite for ApprovalService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_notification_service(self):
        """Mock notification service"""
        return Mock()
    
    @pytest.fixture
    def approval_service(self, mock_db, mock_notification_service):
        """Create ApprovalService instance with mocked dependencies"""
        return ApprovalService(mock_db, mock_notification_service)
    
    @pytest.fixture
    def sample_user(self):
        """Create sample user"""
        return User(
            id=1,
            email="approver@test.com",
            first_name="John",
            last_name="Approver",
            is_active=True
        )
    
    @pytest.fixture
    def sample_expense(self):
        """Create sample expense"""
        return Expense(
            id=1,
            amount=500.0,
            currency="USD",
            category="Travel",
            vendor="Test Vendor",
            expense_date=datetime.now(timezone.utc).date(),
            status="draft",
            user_id=2
        )
    
    @pytest.fixture
    def sample_approval_rule(self, sample_user):
        """Create sample approval rule"""
        return ApprovalRule(
            id=1,
            name="Standard Approval",
            min_amount=0.0,
            max_amount=1000.0,
            currency="USD",
            approval_level=1,
            approver_id=sample_user.id,
            is_active=True,
            priority=1
        )
    
    def test_submit_for_approval_success(self, approval_service, mock_db, sample_expense, sample_user, sample_approval_rule):
        """Test successful expense submission for approval"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense
        mock_db.query.return_value.filter.return_value.all.return_value = []  # No existing approvals
        
        # Mock rule engine
        with patch.object(approval_service.rule_engine, 'should_auto_approve', return_value=False), \
             patch.object(approval_service.rule_engine, 'assign_approvers', return_value=[(1, sample_user, sample_approval_rule)]):
            
            # Execute
            result = approval_service.submit_for_approval(1, 2, "Test submission")
            
            # Verify
            assert len(result) == 1
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            assert sample_expense.status == "pending_approval"
    
    def test_submit_for_approval_already_pending(self, approval_service, mock_db, sample_expense):
        """Test submission when expense is already pending approval"""
        # Setup existing pending approval
        existing_approval = ExpenseApproval(
            id=1,
            expense_id=1,
            status=ApprovalStatus.PENDING
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense
        mock_db.query.return_value.filter.return_value.all.return_value = [existing_approval]
        
        # Execute and verify exception
        with pytest.raises(InvalidApprovalState, match="already in approval workflow"):
            approval_service.submit_for_approval(1, 2)
    
    def test_submit_for_approval_already_approved(self, approval_service, mock_db, sample_expense):
        """Test submission when expense is already approved"""
        sample_expense.status = "approved"
        existing_approval = ExpenseApproval(
            id=1,
            expense_id=1,
            status=ApprovalStatus.APPROVED
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense
        mock_db.query.return_value.filter.return_value.all.return_value = [existing_approval]
        
        # Execute and verify exception
        with pytest.raises(ExpenseAlreadyApproved):
            approval_service.submit_for_approval(1, 2)
    
    def test_submit_for_approval_auto_approve(self, approval_service, mock_db, sample_expense, sample_user, sample_approval_rule):
        """Test auto-approval workflow"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Mock rule engine for auto-approval
        with patch.object(approval_service.rule_engine, 'should_auto_approve', return_value=True), \
             patch.object(approval_service.rule_engine, 'evaluate_expense', return_value=[sample_approval_rule]):
            
            sample_approval_rule.auto_approve_below = 1000.0
            
            # Execute
            result = approval_service.submit_for_approval(1, 2)
            
            # Verify auto-approval
            assert len(result) == 1
            assert result[0].status == ApprovalStatus.APPROVED
            assert sample_expense.status == "approved"
    
    def test_submit_for_approval_no_rules(self, approval_service, mock_db, sample_expense):
        """Test submission when no approval rules match"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Mock rule engine with no matching rules
        with patch.object(approval_service.rule_engine, 'should_auto_approve', return_value=False), \
             patch.object(approval_service.rule_engine, 'assign_approvers', return_value=[]):
            
            # Execute and verify exception
            with pytest.raises(NoApprovalRuleFound):
                approval_service.submit_for_approval(1, 2)
    
    def test_approve_expense_success(self, approval_service, mock_db, sample_expense, sample_user):
        """Test successful expense approval"""
        # Create pending approval
        approval = ExpenseApproval(
            id=1,
            expense_id=1,
            approver_id=sample_user.id,
            status=ApprovalStatus.PENDING,
            is_current_level=True,
            approval_level=1
        )
        approval.expense = sample_expense
        
        mock_db.query.return_value.filter.return_value.first.return_value = approval
        
        # Mock rule engine - no next level (approval complete)
        with patch.object(approval_service.rule_engine, 'get_next_approval_level', return_value=None):
            
            # Execute
            result = approval_service.approve_expense(1, sample_user.id, "Approved")
            
            # Verify
            assert result.status == ApprovalStatus.APPROVED
            assert result.decided_at is not None
            assert result.notes == "Approved"
            assert not result.is_current_level
            assert sample_expense.status == "approved"
            mock_db.commit.assert_called_once()
    
    def test_approve_expense_multi_level(self, approval_service, mock_db, sample_expense, sample_user):
        """Test approval in multi-level workflow"""
        # Set expense to pending approval status initially
        sample_expense.status = "pending_approval"
        
        approval = ExpenseApproval(
            id=1,
            expense_id=1,
            approver_id=sample_user.id,
            status=ApprovalStatus.PENDING,
            is_current_level=True,
            approval_level=1
        )
        approval.expense = sample_expense
        
        mock_db.query.return_value.filter.return_value.first.return_value = approval
        
        # Mock rule engine - has next level
        with patch.object(approval_service.rule_engine, 'get_next_approval_level', return_value=2), \
             patch.object(approval_service, '_activate_next_approval_level') as mock_activate:
            
            # Execute
            result = approval_service.approve_expense(1, sample_user.id)
            
            # Verify
            assert result.status == ApprovalStatus.APPROVED
            assert sample_expense.status == "pending_approval"  # Still pending next level
            mock_activate.assert_called_once_with(sample_expense, 2)
    
    def test_approve_expense_insufficient_permissions(self, approval_service, mock_db):
        """Test approval with insufficient permissions"""
        approval = ExpenseApproval(
            id=1,
            approver_id=999,  # Different user
            status=ApprovalStatus.PENDING,
            is_current_level=True
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = approval
        
        # Mock permission check
        with patch.object(approval_service, '_can_user_approve', return_value=False):
            
            # Execute and verify exception
            with pytest.raises(InsufficientApprovalPermissions):
                approval_service.approve_expense(1, 1)
    
    def test_approve_expense_wrong_status(self, approval_service, mock_db, sample_user):
        """Test approval when approval is not pending"""
        approval = ExpenseApproval(
            id=1,
            approver_id=sample_user.id,
            status=ApprovalStatus.APPROVED,  # Already approved
            is_current_level=True
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = approval
        
        with patch.object(approval_service, '_can_user_approve', return_value=True):
            
            # Execute and verify exception
            with pytest.raises(InvalidApprovalState, match="cannot approve"):
                approval_service.approve_expense(1, sample_user.id)
    
    def test_approve_expense_wrong_level(self, approval_service, mock_db, sample_user):
        """Test approval when not current level"""
        approval = ExpenseApproval(
            id=1,
            approver_id=sample_user.id,
            status=ApprovalStatus.PENDING,
            is_current_level=False,  # Not current level
            approval_level=2
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = approval
        
        with patch.object(approval_service, '_can_user_approve', return_value=True):
            
            # Execute and verify exception
            with pytest.raises(ApprovalLevelMismatch):
                approval_service.approve_expense(1, sample_user.id)
    
    def test_reject_expense_success(self, approval_service, mock_db, sample_expense, sample_user):
        """Test successful expense rejection"""
        approval = ExpenseApproval(
            id=1,
            expense_id=1,
            approver_id=sample_user.id,
            status=ApprovalStatus.PENDING,
            is_current_level=True
        )
        approval.expense = sample_expense
        
        mock_db.query.return_value.filter.return_value.first.return_value = approval
        
        with patch.object(approval_service, '_can_user_approve', return_value=True), \
             patch.object(approval_service, '_cancel_pending_approvals') as mock_cancel:
            
            # Execute
            result = approval_service.reject_expense(1, sample_user.id, "Invalid receipt", "Additional notes")
            
            # Verify
            assert result.status == ApprovalStatus.REJECTED
            assert result.rejection_reason == "Invalid receipt"
            assert result.notes == "Additional notes"
            assert result.decided_at is not None
            assert not result.is_current_level
            assert sample_expense.status == "rejected"
            mock_cancel.assert_called_once_with(1, 1)
            mock_db.commit.assert_called_once()
    
    def test_reject_expense_no_reason(self, approval_service, mock_db, sample_user):
        """Test rejection without reason"""
        approval = ExpenseApproval(id=1, approver_id=sample_user.id)
        mock_db.query.return_value.filter.return_value.first.return_value = approval
        
        # Execute and verify exception
        with pytest.raises(ValidationError, match="Rejection reason is required"):
            approval_service.reject_expense(1, sample_user.id, "")
    
    def test_get_pending_approvals(self, approval_service, mock_db, sample_user):
        """Test getting pending approvals for user"""
        pending_approvals = [
            ExpenseApproval(id=1, approver_id=sample_user.id, status=ApprovalStatus.PENDING, is_current_level=True),
            ExpenseApproval(id=2, approver_id=sample_user.id, status=ApprovalStatus.PENDING, is_current_level=True)
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = pending_approvals
        mock_db.query.return_value = mock_query
        
        # Execute
        result = approval_service.get_pending_approvals(sample_user.id)
        
        # Verify
        assert len(result) == 2
        assert all(a.status == ApprovalStatus.PENDING for a in result)
    
    def test_get_pending_approvals_with_pagination(self, approval_service, mock_db, sample_user):
        """Test getting pending approvals with pagination"""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Execute
        approval_service.get_pending_approvals(sample_user.id, limit=10, offset=20)
        
        # Verify pagination was applied
        mock_query.filter.return_value.order_by.return_value.offset.assert_called_once_with(20)
        mock_query.filter.return_value.order_by.return_value.offset.return_value.limit.assert_called_once_with(10)
    
    def test_get_pending_approvals_summary_empty(self, approval_service, mock_db, sample_user):
        """Test pending approvals summary with no pending items"""
        with patch.object(approval_service, 'get_pending_approvals', return_value=[]):
            
            # Execute
            result = approval_service.get_pending_approvals_summary(sample_user.id)
            
            # Verify
            assert result.total_pending == 0
            assert result.total_amount == 0.0
            assert result.oldest_submission is None
            assert result.by_category == []
    
    def test_get_pending_approvals_summary_with_data(self, approval_service, mock_db, sample_user):
        """Test pending approvals summary with data"""
        # Create mock expenses
        expense1 = Expense(amount=100.0, currency="USD", category="Travel")
        expense2 = Expense(amount=200.0, currency="USD", category="Office")
        expense3 = Expense(amount=150.0, currency="USD", category="Travel")
        
        # Create mock approvals
        now = datetime.now(timezone.utc)
        approvals = [
            ExpenseApproval(expense=expense1, submitted_at=now - timedelta(days=2)),
            ExpenseApproval(expense=expense2, submitted_at=now - timedelta(days=1)),
            ExpenseApproval(expense=expense3, submitted_at=now)
        ]
        
        with patch.object(approval_service, 'get_pending_approvals', return_value=approvals):
            
            # Execute
            result = approval_service.get_pending_approvals_summary(sample_user.id)
            
            # Verify
            assert result.total_pending == 3
            assert result.total_amount == 450.0
            assert result.currency == "USD"
            assert result.oldest_submission == now - timedelta(days=2)
            assert len(result.by_category) == 2
            
            # Check category breakdown
            travel_category = next(c for c in result.by_category if c["category"] == "Travel")
            assert travel_category["count"] == 2
            assert travel_category["amount"] == 250.0
            
            office_category = next(c for c in result.by_category if c["category"] == "Office")
            assert office_category["count"] == 1
            assert office_category["amount"] == 200.0
    
    def test_get_approval_history(self, approval_service, mock_db, sample_expense, sample_user):
        """Test getting approval history for expense"""
        # Create mock approvals
        approvals = [
            ExpenseApproval(
                id=1,
                approver_id=sample_user.id,
                status=ApprovalStatus.APPROVED,
                approval_level=1,
                submitted_at=datetime.now(timezone.utc) - timedelta(days=1),
                decided_at=datetime.now(timezone.utc),
                notes="First level approved"
            )
        ]
        approvals[0].approver = sample_user
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = approvals
        
        # Execute
        result = approval_service.get_approval_history(1)
        
        # Verify
        assert result.expense_id == 1
        assert result.current_status == sample_expense.status
        assert len(result.approval_history) == 1
        
        history_item = result.approval_history[0]
        assert history_item.id == 1
        assert history_item.approver_name == "John Approver"
        assert history_item.approver_email == sample_user.email
        assert history_item.status == ApprovalStatus.APPROVED
        assert history_item.notes == "First level approved"
    
    def test_create_delegation_success(self, approval_service, mock_db, sample_user):
        """Test successful delegation creation"""
        # Create delegate user
        delegate = User(id=2, email="delegate@test.com", first_name="Jane", last_name="Delegate")
        
        # Mock database queries
        def mock_query_side_effect(model):
            if model == User:
                mock_user_query = Mock()
                mock_user_query.filter.return_value.first.side_effect = [sample_user, delegate]
                return mock_user_query
            elif model == ApprovalDelegate:
                mock_delegate_query = Mock()
                mock_delegate_query.filter.return_value.first.return_value = None  # No existing delegation
                return mock_delegate_query
        
        mock_db.query.side_effect = mock_query_side_effect
        
        # Create delegation data
        delegation_data = ApprovalDelegateCreate(
            approver_id=sample_user.id,
            delegate_id=delegate.id,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=7),
            is_active=True
        )
        
        # Execute
        result = approval_service.create_delegation(sample_user.id, delegation_data)
        
        # Verify
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_create_delegation_overlapping(self, approval_service, mock_db, sample_user):
        """Test delegation creation with overlapping dates"""
        delegate = User(id=2, email="delegate@test.com")
        
        # Mock existing delegation
        existing_delegation = ApprovalDelegate(
            approver_id=sample_user.id,
            delegate_id=delegate.id,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=7),
            is_active=True
        )
        
        def mock_query_side_effect(model):
            if model == User:
                mock_user_query = Mock()
                mock_user_query.filter.return_value.first.side_effect = [sample_user, delegate]
                return mock_user_query
            elif model == ApprovalDelegate:
                mock_delegate_query = Mock()
                mock_delegate_query.filter.return_value.first.return_value = existing_delegation
                return mock_delegate_query
        
        mock_db.query.side_effect = mock_query_side_effect
        
        delegation_data = ApprovalDelegateCreate(
            approver_id=sample_user.id,
            delegate_id=delegate.id,
            start_date=datetime.now(timezone.utc) + timedelta(days=3),
            end_date=datetime.now(timezone.utc) + timedelta(days=10),
            is_active=True
        )
        
        # Execute and verify exception
        with pytest.raises(ValidationError, match="Overlapping delegation exists"):
            approval_service.create_delegation(sample_user.id, delegation_data)
    
    def test_get_active_delegations(self, approval_service, mock_db, sample_user):
        """Test getting active delegations"""
        active_delegations = [
            ApprovalDelegate(id=1, approver_id=sample_user.id, is_active=True),
            ApprovalDelegate(id=2, approver_id=sample_user.id, is_active=True)
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = active_delegations
        
        # Execute
        result = approval_service.get_active_delegations(sample_user.id)
        
        # Verify
        assert len(result) == 2
        assert all(d.is_active for d in result)
    
    def test_deactivate_delegation(self, approval_service, mock_db, sample_user):
        """Test delegation deactivation"""
        delegation = ApprovalDelegate(
            id=1,
            approver_id=sample_user.id,
            is_active=True
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = delegation
        
        # Execute
        result = approval_service.deactivate_delegation(1, sample_user.id)
        
        # Verify
        assert not result.is_active
        mock_db.commit.assert_called_once()
    
    def test_get_approval_metrics(self, approval_service, mock_db):
        """Test approval metrics calculation"""
        # Create mock approvals with different statuses
        now = datetime.now(timezone.utc)
        approvals = [
            ExpenseApproval(
                status=ApprovalStatus.APPROVED,
                submitted_at=now - timedelta(hours=24),
                decided_at=now - timedelta(hours=12)
            ),
            ExpenseApproval(
                status=ApprovalStatus.APPROVED,
                submitted_at=now - timedelta(hours=48),
                decided_at=now - timedelta(hours=24)
            ),
            ExpenseApproval(
                status=ApprovalStatus.REJECTED,
                submitted_at=now - timedelta(hours=36),
                decided_at=now - timedelta(hours=18)
            ),
            ExpenseApproval(
                status=ApprovalStatus.PENDING,
                submitted_at=now - timedelta(hours=6),
                decided_at=None
            )
        ]
        
        mock_db.query.return_value.all.return_value = approvals
        
        # Execute
        result = approval_service.get_approval_metrics()
        
        # Verify
        assert result.total_approvals == 4
        assert result.approved_count == 2
        assert result.rejected_count == 1
        assert result.pending_count == 1
        assert abs(result.approval_rate - 66.67) < 0.01  # 2/(2+1) * 100
        assert result.average_approval_time_hours == 18.0  # (12+24+18)/3
    
    def test_resubmit_expense_success(self, approval_service, mock_db, sample_expense):
        """Test successful expense resubmission"""
        sample_expense.status = "rejected"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense
        
        with patch.object(approval_service, 'submit_for_approval', return_value=[]) as mock_submit:
            
            # Execute
            approval_service.resubmit_expense(1, 2, "Resubmitting with corrections")
            
            # Verify
            assert sample_expense.status == "resubmitted"
            mock_submit.assert_called_once_with(1, 2, "Resubmitting with corrections")
    
    def test_resubmit_expense_wrong_status(self, approval_service, mock_db, sample_expense):
        """Test resubmission when expense is not rejected"""
        sample_expense.status = "approved"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense
        
        # Execute and verify exception
        with pytest.raises(InvalidApprovalState, match="cannot resubmit"):
            approval_service.resubmit_expense(1, 2)
    
    def test_validate_expense_for_approval_invalid_amount(self, approval_service):
        """Test expense validation with invalid amount"""
        expense = Expense(amount=0, category="Travel", expense_date=datetime.now().date())
        
        with pytest.raises(ValidationError, match="amount must be greater than 0"):
            approval_service._validate_expense_for_approval(expense)
    
    def test_validate_expense_for_approval_missing_category(self, approval_service):
        """Test expense validation with missing category"""
        expense = Expense(amount=100.0, category="", expense_date=datetime.now().date())
        
        with pytest.raises(ValidationError, match="category is required"):
            approval_service._validate_expense_for_approval(expense)
    
    def test_validate_expense_for_approval_missing_date(self, approval_service):
        """Test expense validation with missing date"""
        expense = Expense(amount=100.0, category="Travel", expense_date=None)
        
        with pytest.raises(ValidationError, match="date is required"):
            approval_service._validate_expense_for_approval(expense)
    
    def test_can_user_approve_direct_approver(self, approval_service, mock_db, sample_user):
        """Test permission check for direct approver"""
        approval = ExpenseApproval(approver_id=sample_user.id)
        
        # Execute
        result = approval_service._can_user_approve(sample_user.id, approval)
        
        # Verify
        assert result is True
    
    def test_can_user_approve_delegate(self, approval_service, mock_db, sample_user):
        """Test permission check for delegate"""
        approval = ExpenseApproval(approver_id=999)  # Different approver
        
        # Mock active delegation
        delegation = ApprovalDelegate(
            approver_id=999,
            delegate_id=sample_user.id,
            is_active=True,
            start_date=datetime.now(timezone.utc) - timedelta(days=1),
            end_date=datetime.now(timezone.utc) + timedelta(days=1)
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = delegation
        
        # Execute
        result = approval_service._can_user_approve(sample_user.id, approval)
        
        # Verify
        assert result is True
    
    def test_can_user_approve_no_permission(self, approval_service, mock_db, sample_user):
        """Test permission check with no permission"""
        approval = ExpenseApproval(approver_id=999)  # Different approver
        
        # Mock no delegation
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute
        result = approval_service._can_user_approve(sample_user.id, approval)
        
        # Verify
        assert result is False
    
    def test_send_approval_notification_success(self, approval_service, mock_notification_service, sample_expense, sample_user):
        """Test successful notification sending"""
        approval = ExpenseApproval(
            id=1,
            approver_id=sample_user.id,
            approval_level=1,
            notes="Test approval"
        )
        approval.expense = sample_expense
        approval.approver = sample_user
        
        # Execute
        approval_service._send_approval_notification(approval, "expense_submitted_for_approval")
        
        # Verify notification was sent
        mock_notification_service.send_operation_notification.assert_called_once()
        call_args = mock_notification_service.send_operation_notification.call_args
        assert call_args[1]["event_type"] == "expense_submitted_for_approval"
        assert call_args[1]["user_id"] == sample_user.id
        assert call_args[1]["resource_type"] == "expense_approval"
    
    def test_send_approval_notification_no_service(self, approval_service, sample_expense, sample_user):
        """Test notification when no notification service is configured"""
        approval_service.notification_service = None
        approval = ExpenseApproval(id=1, approver_id=sample_user.id)
        approval.expense = sample_expense
        approval.approver = sample_user
        
        # Execute - should not raise exception
        approval_service._send_approval_notification(approval, "expense_submitted_for_approval")
        
        # No assertions needed - just verify no exception is raised
    
    def test_send_approval_notification_exception_handling(self, approval_service, mock_notification_service, sample_expense, sample_user):
        """Test notification exception handling"""
        approval = ExpenseApproval(id=1, approver_id=sample_user.id)
        approval.expense = sample_expense
        approval.approver = sample_user
        
        # Mock notification service to raise exception
        mock_notification_service.send_operation_notification.side_effect = Exception("Notification failed")
        
        # Execute - should not raise exception (should be caught and logged)
        approval_service._send_approval_notification(approval, "expense_submitted_for_approval")
        
        # Verify exception was handled gracefully
        mock_notification_service.send_operation_notification.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])