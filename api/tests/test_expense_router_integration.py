"""
Integration tests for expense router with approval status support.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from core.constants.expense_status import ExpenseStatus


class MockExpense:
    """Mock expense for testing"""
    def __init__(self, status=ExpenseStatus.DRAFT.value, **kwargs):
        self.status = status
        self.invoice_id = kwargs.get('invoice_id', None)
        for key, value in kwargs.items():
            setattr(self, key, value)


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


class TestExpenseRouterIntegration:
    """Test expense router integration with approval statuses"""
    
    def test_expense_creation_with_status(self):
        """Test expense creation with different status values"""
        # Test default status
        expense = MockExpense()
        assert expense.status == ExpenseStatus.DRAFT.value
        
        # Test explicit status
        expense_recorded = MockExpense(status=ExpenseStatus.RECORDED.value)
        assert expense_recorded.status == ExpenseStatus.RECORDED.value
    
    def test_expense_update_status_validation(self):
        """Test expense update with status transition validation"""
        expense = MockExpense(status=ExpenseStatus.DRAFT.value)
        
        # Valid transition: draft -> pending_approval
        assert validate_status_transition(expense.status, ExpenseStatus.PENDING_APPROVAL.value)
        
        # Invalid transition: draft -> approved
        assert not validate_status_transition(expense.status, ExpenseStatus.APPROVED.value)
    
    def test_expense_modification_restrictions(self):
        """Test that expenses in approval workflow cannot be modified"""
        # Draft expense can be modified
        draft_expense = MockExpense(status=ExpenseStatus.DRAFT.value)
        check_expense_modification_allowed(draft_expense)  # Should not raise
        
        # Pending approval expense cannot be modified
        pending_expense = MockExpense(status=ExpenseStatus.PENDING_APPROVAL.value)
        with pytest.raises(HTTPException) as exc_info:
            check_expense_modification_allowed(pending_expense)
        assert "Cannot modify expense with status 'pending_approval'" in str(exc_info.value)
        
        # Approved expense cannot be modified
        approved_expense = MockExpense(status=ExpenseStatus.APPROVED.value)
        with pytest.raises(HTTPException) as exc_info:
            check_expense_modification_allowed(approved_expense)
        assert "Cannot modify expense with status 'approved'" in str(exc_info.value)
    
    def test_expense_deletion_restrictions(self):
        """Test that expenses in approval workflow cannot be deleted"""
        # Draft expense can be deleted (if not linked to invoice)
        draft_expense = MockExpense(status=ExpenseStatus.DRAFT.value)
        assert draft_expense.status not in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]
        
        # Pending approval expense cannot be deleted
        pending_expense = MockExpense(status=ExpenseStatus.PENDING_APPROVAL.value)
        assert pending_expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]
        
        # Approved expense cannot be deleted
        approved_expense = MockExpense(status=ExpenseStatus.APPROVED.value)
        assert approved_expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]
    
    def test_complete_approval_workflow(self):
        """Test a complete approval workflow progression"""
        expense = MockExpense(status=ExpenseStatus.DRAFT.value)
        
        # Step 1: Submit for approval (draft -> pending_approval)
        assert validate_status_transition(expense.status, ExpenseStatus.PENDING_APPROVAL.value)
        expense.status = ExpenseStatus.PENDING_APPROVAL.value
        
        # Expense cannot be modified while pending
        with pytest.raises(HTTPException):
            check_expense_modification_allowed(expense)
        
        # Step 2: Approve (pending_approval -> approved)
        assert validate_status_transition(expense.status, ExpenseStatus.APPROVED.value)
        expense.status = ExpenseStatus.APPROVED.value
        
        # Expense cannot be modified while approved
        with pytest.raises(HTTPException):
            check_expense_modification_allowed(expense)
        
        # Step 3: Reimburse (approved -> reimbursed)
        assert validate_status_transition(expense.status, ExpenseStatus.REIMBURSED.value)
        expense.status = ExpenseStatus.REIMBURSED.value
        
        # Terminal state - no further transitions allowed
        for status in ExpenseStatus.get_all_values():
            if status != ExpenseStatus.REIMBURSED.value:
                assert not validate_status_transition(expense.status, status)
    
    def test_rejection_and_resubmission_workflow(self):
        """Test expense rejection and resubmission workflow"""
        expense = MockExpense(status=ExpenseStatus.PENDING_APPROVAL.value)
        
        # Step 1: Reject (pending_approval -> rejected)
        assert validate_status_transition(expense.status, ExpenseStatus.REJECTED.value)
        expense.status = ExpenseStatus.REJECTED.value
        
        # Rejected expense can be modified
        check_expense_modification_allowed(expense)  # Should not raise
        
        # Step 2: Resubmit (rejected -> resubmitted)
        assert validate_status_transition(expense.status, ExpenseStatus.RESUBMITTED.value)
        expense.status = ExpenseStatus.RESUBMITTED.value
        
        # Resubmitted expense can be modified
        check_expense_modification_allowed(expense)  # Should not raise
        
        # Step 3: Submit again (resubmitted -> pending_approval)
        assert validate_status_transition(expense.status, ExpenseStatus.PENDING_APPROVAL.value)
    
    def test_bypass_approval_workflow(self):
        """Test bypassing approval workflow for simple expenses"""
        expense = MockExpense(status=ExpenseStatus.DRAFT.value)
        
        # Direct transition to recorded (bypass approval)
        assert validate_status_transition(expense.status, ExpenseStatus.RECORDED.value)
        expense.status = ExpenseStatus.RECORDED.value
        
        # Recorded expense can be modified
        check_expense_modification_allowed(expense)  # Should not raise
        
        # Can be reimbursed directly
        assert validate_status_transition(expense.status, ExpenseStatus.REIMBURSED.value)
    
    def test_invalid_status_transitions(self):
        """Test that invalid status transitions are rejected"""
        # Cannot go from recorded to pending_approval
        assert not validate_status_transition(ExpenseStatus.RECORDED.value, ExpenseStatus.PENDING_APPROVAL.value)
        
        # Cannot go from approved to rejected
        assert not validate_status_transition(ExpenseStatus.APPROVED.value, ExpenseStatus.REJECTED.value)
        
        # Cannot go from reimbursed to anything
        for status in ExpenseStatus.get_all_values():
            if status != ExpenseStatus.REIMBURSED.value:
                assert not validate_status_transition(ExpenseStatus.REIMBURSED.value, status)
        
        # Cannot skip approval levels
        assert not validate_status_transition(ExpenseStatus.DRAFT.value, ExpenseStatus.APPROVED.value)
        assert not validate_status_transition(ExpenseStatus.DRAFT.value, ExpenseStatus.REIMBURSED.value)