"""
Tests for expense status transitions and approval workflow integration.
"""

import pytest
from datetime import datetime, date, timezone
from unittest.mock import Mock
from fastapi import HTTPException

from constants.expense_status import ExpenseStatus


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """Validate if a status transition is allowed"""
    try:
        current = ExpenseStatus(current_status)
        new = ExpenseStatus(new_status)
        return current.can_transition_to(new)
    except ValueError:
        return False


def check_expense_modification_allowed(expense) -> None:
    """Check if an expense can be modified based on its current status"""
    if expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot modify expense with status '{expense.status}'. Expense is in approval workflow."
        )


class TestExpenseStatusEnum:
    """Test the ExpenseStatus enum functionality"""
    
    def test_all_status_values(self):
        """Test that all expected status values are defined"""
        expected_statuses = {
            "draft", "recorded", "reimbursed", 
            "pending_approval", "approved", "rejected", "resubmitted"
        }
        actual_statuses = set(ExpenseStatus.get_all_values())
        assert actual_statuses == expected_statuses
    
    def test_approval_workflow_statuses(self):
        """Test approval workflow status classification"""
        approval_statuses = set(ExpenseStatus.get_approval_workflow_statuses())
        expected_approval = {"pending_approval", "approved", "rejected", "resubmitted"}
        assert approval_statuses == expected_approval
    
    def test_non_approval_statuses(self):
        """Test non-approval status classification"""
        non_approval_statuses = set(ExpenseStatus.get_non_approval_statuses())
        expected_non_approval = {"draft", "recorded", "reimbursed"}
        assert non_approval_statuses == expected_non_approval
    
    def test_requires_approval_workflow(self):
        """Test approval workflow requirement check"""
        assert ExpenseStatus.PENDING_APPROVAL.requires_approval_workflow()
        assert ExpenseStatus.APPROVED.requires_approval_workflow()
        assert ExpenseStatus.REJECTED.requires_approval_workflow()
        assert ExpenseStatus.RESUBMITTED.requires_approval_workflow()
        
        assert not ExpenseStatus.DRAFT.requires_approval_workflow()
        assert not ExpenseStatus.RECORDED.requires_approval_workflow()
        assert not ExpenseStatus.REIMBURSED.requires_approval_workflow()


class TestExpenseStatusTransitions:
    """Test expense status transition validation"""
    
    def test_valid_transitions_from_draft(self):
        """Test valid transitions from draft status"""
        draft = ExpenseStatus.DRAFT
        assert draft.can_transition_to(ExpenseStatus.PENDING_APPROVAL)
        assert draft.can_transition_to(ExpenseStatus.RECORDED)
        
        # Invalid transitions
        assert not draft.can_transition_to(ExpenseStatus.APPROVED)
        assert not draft.can_transition_to(ExpenseStatus.REJECTED)
        assert not draft.can_transition_to(ExpenseStatus.REIMBURSED)
    
    def test_valid_transitions_from_recorded(self):
        """Test valid transitions from recorded status"""
        recorded = ExpenseStatus.RECORDED
        assert recorded.can_transition_to(ExpenseStatus.REIMBURSED)
        
        # Invalid transitions
        assert not recorded.can_transition_to(ExpenseStatus.PENDING_APPROVAL)
        assert not recorded.can_transition_to(ExpenseStatus.APPROVED)
        assert not recorded.can_transition_to(ExpenseStatus.REJECTED)
    
    def test_valid_transitions_from_pending_approval(self):
        """Test valid transitions from pending approval status"""
        pending = ExpenseStatus.PENDING_APPROVAL
        assert pending.can_transition_to(ExpenseStatus.APPROVED)
        assert pending.can_transition_to(ExpenseStatus.REJECTED)
        
        # Invalid transitions
        assert not pending.can_transition_to(ExpenseStatus.DRAFT)
        assert not pending.can_transition_to(ExpenseStatus.RECORDED)
        assert not pending.can_transition_to(ExpenseStatus.REIMBURSED)
    
    def test_valid_transitions_from_approved(self):
        """Test valid transitions from approved status"""
        approved = ExpenseStatus.APPROVED
        assert approved.can_transition_to(ExpenseStatus.REIMBURSED)
        
        # Invalid transitions
        assert not approved.can_transition_to(ExpenseStatus.PENDING_APPROVAL)
        assert not approved.can_transition_to(ExpenseStatus.REJECTED)
        assert not approved.can_transition_to(ExpenseStatus.DRAFT)
    
    def test_valid_transitions_from_rejected(self):
        """Test valid transitions from rejected status"""
        rejected = ExpenseStatus.REJECTED
        assert rejected.can_transition_to(ExpenseStatus.RESUBMITTED)
        assert rejected.can_transition_to(ExpenseStatus.DRAFT)
        
        # Invalid transitions
        assert not rejected.can_transition_to(ExpenseStatus.APPROVED)
        assert not rejected.can_transition_to(ExpenseStatus.PENDING_APPROVAL)
        assert not rejected.can_transition_to(ExpenseStatus.REIMBURSED)
    
    def test_valid_transitions_from_resubmitted(self):
        """Test valid transitions from resubmitted status"""
        resubmitted = ExpenseStatus.RESUBMITTED
        assert resubmitted.can_transition_to(ExpenseStatus.PENDING_APPROVAL)
        
        # Invalid transitions
        assert not resubmitted.can_transition_to(ExpenseStatus.APPROVED)
        assert not resubmitted.can_transition_to(ExpenseStatus.REJECTED)
        assert not resubmitted.can_transition_to(ExpenseStatus.DRAFT)
    
    def test_no_transitions_from_reimbursed(self):
        """Test that reimbursed is a terminal status"""
        reimbursed = ExpenseStatus.REIMBURSED
        
        # No valid transitions from reimbursed
        for status in ExpenseStatus:
            if status != reimbursed:
                assert not reimbursed.can_transition_to(status)
    
    def test_validate_status_transition_function(self):
        """Test the validate_status_transition helper function"""
        # Valid transitions
        assert validate_status_transition("draft", "pending_approval")
        assert validate_status_transition("pending_approval", "approved")
        assert validate_status_transition("rejected", "resubmitted")
        
        # Invalid transitions
        assert not validate_status_transition("approved", "rejected")
        assert not validate_status_transition("reimbursed", "draft")
        
        # Invalid status values
        assert not validate_status_transition("invalid_status", "draft")
        assert not validate_status_transition("draft", "invalid_status")


class TestExpenseModificationValidation:
    """Test expense modification validation based on status"""
    
    def test_check_expense_modification_allowed_draft(self):
        """Test that draft expenses can be modified"""
        expense = Mock()
        expense.status = ExpenseStatus.DRAFT.value
        
        # Should not raise exception
        check_expense_modification_allowed(expense)
    
    def test_check_expense_modification_allowed_recorded(self):
        """Test that recorded expenses can be modified"""
        expense = Mock()
        expense.status = ExpenseStatus.RECORDED.value
        
        # Should not raise exception
        check_expense_modification_allowed(expense)
    
    def test_check_expense_modification_blocked_pending_approval(self):
        """Test that pending approval expenses cannot be modified"""
        expense = Mock()
        expense.status = ExpenseStatus.PENDING_APPROVAL.value
        
        with pytest.raises(Exception) as exc_info:
            check_expense_modification_allowed(expense)
        
        assert "Cannot modify expense with status 'pending_approval'" in str(exc_info.value)
    
    def test_check_expense_modification_blocked_approved(self):
        """Test that approved expenses cannot be modified"""
        expense = Mock()
        expense.status = ExpenseStatus.APPROVED.value
        
        with pytest.raises(Exception) as exc_info:
            check_expense_modification_allowed(expense)
        
        assert "Cannot modify expense with status 'approved'" in str(exc_info.value)
    
    def test_check_expense_modification_allowed_rejected(self):
        """Test that rejected expenses can be modified"""
        expense = Mock()
        expense.status = ExpenseStatus.REJECTED.value
        
        # Should not raise exception
        check_expense_modification_allowed(expense)
    
    def test_check_expense_modification_allowed_resubmitted(self):
        """Test that resubmitted expenses can be modified"""
        expense = Mock()
        expense.status = ExpenseStatus.RESUBMITTED.value
        
        # Should not raise exception
        check_expense_modification_allowed(expense)


class MockExpense:
    """Mock expense class for testing"""
    def __init__(self, status=ExpenseStatus.DRAFT.value, **kwargs):
        self.status = status
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def sample_expense():
    """Create a sample expense for testing"""
    return MockExpense(
        id=1,
        amount=100.0,
        currency="USD",
        expense_date=datetime.now(timezone.utc),
        category="Travel",
        status=ExpenseStatus.DRAFT.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


class TestExpenseStatusIntegration:
    """Integration tests for expense status handling"""
    
    def test_expense_creation_default_status(self):
        """Test that expenses are created with default recorded status"""
        expense = MockExpense(status=ExpenseStatus.RECORDED.value)
        assert expense.status == ExpenseStatus.RECORDED.value
    
    def test_expense_status_workflow_progression(self, sample_expense):
        """Test a complete status workflow progression"""
        # Start with draft
        assert sample_expense.status == ExpenseStatus.DRAFT.value
        
        # Can transition to pending approval
        assert validate_status_transition(sample_expense.status, ExpenseStatus.PENDING_APPROVAL.value)
        sample_expense.status = ExpenseStatus.PENDING_APPROVAL.value
        
        # Can transition to approved
        assert validate_status_transition(sample_expense.status, ExpenseStatus.APPROVED.value)
        sample_expense.status = ExpenseStatus.APPROVED.value
        
        # Can transition to reimbursed
        assert validate_status_transition(sample_expense.status, ExpenseStatus.REIMBURSED.value)
        sample_expense.status = ExpenseStatus.REIMBURSED.value
        
        # Cannot transition from reimbursed
        assert not validate_status_transition(sample_expense.status, ExpenseStatus.DRAFT.value)
    
    def test_expense_rejection_workflow(self, sample_expense):
        """Test expense rejection and resubmission workflow"""
        # Start with pending approval
        sample_expense.status = ExpenseStatus.PENDING_APPROVAL.value
        
        # Can be rejected
        assert validate_status_transition(sample_expense.status, ExpenseStatus.REJECTED.value)
        sample_expense.status = ExpenseStatus.REJECTED.value
        
        # Can be resubmitted
        assert validate_status_transition(sample_expense.status, ExpenseStatus.RESUBMITTED.value)
        sample_expense.status = ExpenseStatus.RESUBMITTED.value
        
        # Can go back to pending approval
        assert validate_status_transition(sample_expense.status, ExpenseStatus.PENDING_APPROVAL.value)
    
    def test_expense_bypass_approval_workflow(self, sample_expense):
        """Test bypassing approval workflow for simple expenses"""
        # Start with draft
        assert sample_expense.status == ExpenseStatus.DRAFT.value
        
        # Can go directly to recorded (bypass approval)
        assert validate_status_transition(sample_expense.status, ExpenseStatus.RECORDED.value)
        sample_expense.status = ExpenseStatus.RECORDED.value
        
        # Can then be reimbursed
        assert validate_status_transition(sample_expense.status, ExpenseStatus.REIMBURSED.value)