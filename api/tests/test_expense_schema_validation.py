"""
Tests for expense schema validation with status values.
"""

import pytest
from datetime import date
from pydantic import ValidationError

from core.constants.expense_status import ExpenseStatus
from core.schemas.expense import ExpenseCreate, ExpenseUpdate


class TestExpenseSchemaValidation:
    """Test expense schema validation for status values"""
    
    def test_expense_create_valid_status(self):
        """Test creating expense with valid status"""
        expense_data = {
            "amount": 100.0,
            "category": "Travel",
            "expense_date": date.today(),
            "status": ExpenseStatus.DRAFT.value
        }
        
        expense = ExpenseCreate(**expense_data)
        assert expense.status == ExpenseStatus.DRAFT.value
    
    def test_expense_create_invalid_status(self):
        """Test creating expense with invalid status raises validation error"""
        expense_data = {
            "amount": 100.0,
            "category": "Travel", 
            "expense_date": date.today(),
            "status": "invalid_status"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(**expense_data)
        
        assert "Invalid status" in str(exc_info.value)
    
    def test_expense_create_default_status(self):
        """Test creating expense with default status"""
        expense_data = {
            "amount": 100.0,
            "category": "Travel",
            "expense_date": date.today()
        }
        
        expense = ExpenseCreate(**expense_data)
        assert expense.status == ExpenseStatus.RECORDED.value
    
    def test_expense_update_valid_status(self):
        """Test updating expense with valid status"""
        expense_update = ExpenseUpdate(status=ExpenseStatus.PENDING_APPROVAL.value)
        assert expense_update.status == ExpenseStatus.PENDING_APPROVAL.value
    
    def test_expense_update_invalid_status(self):
        """Test updating expense with invalid status raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseUpdate(status="invalid_status")
        
        assert "Invalid status" in str(exc_info.value)
    
    def test_expense_update_none_status(self):
        """Test updating expense with None status is allowed"""
        expense_update = ExpenseUpdate(status=None)
        assert expense_update.status is None
    
    def test_all_valid_statuses_accepted(self):
        """Test that all valid status values are accepted"""
        for status in ExpenseStatus.get_all_values():
            expense_data = {
                "amount": 100.0,
                "category": "Travel",
                "expense_date": date.today(),
                "status": status
            }
            
            expense = ExpenseCreate(**expense_data)
            assert expense.status == status
    
    def test_expense_update_all_valid_statuses(self):
        """Test that all valid status values are accepted in updates"""
        for status in ExpenseStatus.get_all_values():
            expense_update = ExpenseUpdate(status=status)
            assert expense_update.status == status