"""
Tests for approval workflow edge cases and error scenarios

This test suite covers edge cases, boundary conditions, and error scenarios
that could occur in the approval workflow system.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

from core.exceptions.approval_exceptions import (
    ValidationError, ExpenseValidationError, ApprovalConcurrencyError,
    ApprovalTimeoutError, ApprovalWorkflowError, NotificationDeliveryError
)
from commercial.workflows.approvals.services.approval_service import ApprovalService
from commercial.workflows.approvals.services.approval_validation_service import ApprovalValidationService
from core.models.models_per_tenant import Expense, User, ExpenseApproval, ApprovalRule
from core.schemas.approval import ApprovalStatus


class TestApprovalWorkflowEdgeCases:
    """Test edge cases in approval workflow"""
    
    @pytest.fixture
    def approval_service(self, db_session):
        return ApprovalService(db_session)
    
    @pytest.fixture
    def validation_service(self, db_session):
        return ApprovalValidationService(db_session)
    
    def test_submit_expense_with_zero_amount(self, approval_service, db_session):
        """Test submitting expense with zero amount"""
        expense = Expense(
            id=1,
            amount=0.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        db_session.commit()
        
        with pytest.raises(ExpenseValidationError) as exc_info:
            approval_service.submit_for_approval(1, 1)
        
        error = exc_info.value
        assert "Amount must be greater than 0" in str(error.details["validation_errors"])
    
    def test_submit_expense_with_negative_amount(self, approval_service, db_session):
        """Test submitting expense with negative amount"""
        expense = Expense(
            id=1,
            amount=-100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        db_session.commit()
        
        with pytest.raises(ExpenseValidationError) as exc_info:
            approval_service.submit_for_approval(1, 1)
        
        error = exc_info.value
        assert "Amount must be greater than 0" in str(error.details["validation_errors"])
    
    def test_submit_expense_with_very_large_amount(self, approval_service, db_session):
        """Test submitting expense with extremely large amount"""
        expense = Expense(
            id=1,
            amount=999999999.99,  # Very large amount
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        
        # Create approval rule that can handle large amounts
        rule = ApprovalRule(
            id=1,
            name="High Value Rule",
            min_amount=1000000.0,
            approver_id=1,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Should succeed with proper rule
        approvals = approval_service.submit_for_approval(1, 1)
        assert len(approvals) > 0
        assert approvals[0].expense.amount == 999999999.99
    
    def test_submit_expense_with_unicode_characters(self, approval_service, db_session):
        """Test submitting expense with unicode characters in description"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            description="Test with émojis 🎉 and ñoñó characters",
            vendor="Café München",
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        
        rule = ApprovalRule(
            id=1,
            name="Test Rule",
            approver_id=1,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Should handle unicode characters properly
        approvals = approval_service.submit_for_approval(1, 1)
        assert len(approvals) > 0
        assert "émojis" in approvals[0].expense.description
    
    def test_submit_expense_with_very_long_description(self, validation_service, db_session):
        """Test submitting expense with extremely long description"""
        long_description = "A" * 10000  # Very long description
        
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            description=long_description,
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        db_session.commit()
        
        # Should validate successfully (assuming no length limit in validation)
        validated_expense, validated_user = validation_service.validate_approval_submission(1, 1)
        assert validated_expense.description == long_description
    
    def test_submit_expense_with_special_characters_in_category(self, approval_service, db_session):
        """Test submitting expense with special characters in category"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office/supplies & equipment (misc.)",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        
        rule = ApprovalRule(
            id=1,
            name="Test Rule",
            approver_id=1,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Should handle special characters in category
        approvals = approval_service.submit_for_approval(1, 1)
        assert len(approvals) > 0
    
    def test_submit_expense_on_leap_year_date(self, approval_service, db_session):
        """Test submitting expense on February 29th (leap year)"""
        from datetime import date
        
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=date(2024, 2, 29),  # Leap year date
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        
        rule = ApprovalRule(
            id=1,
            name="Test Rule",
            approver_id=1,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Should handle leap year dates properly
        approvals = approval_service.submit_for_approval(1, 1)
        assert len(approvals) > 0
        assert approvals[0].expense.expense_date == date(2024, 2, 29)
    
    def test_approval_with_deleted_approver(self, approval_service, db_session):
        """Test approval workflow when approver is deleted"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        approver = User(id=2, email="approver@example.com", role="manager")
        db_session.add(user)
        db_session.add(approver)
        
        rule = ApprovalRule(
            id=1,
            name="Test Rule",
            approver_id=2,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Submit for approval
        approvals = approval_service.submit_for_approval(1, 1)
        approval_id = approvals[0].id
        
        # Delete the approver
        db_session.delete(approver)
        db_session.commit()
        
        # Try to approve - should handle missing approver gracefully
        with pytest.raises(ValidationError) as exc_info:
            approval_service.approve_expense(approval_id, 2)
        
        error = exc_info.value
        assert "not found" in error.details["reason"]
    
    def test_concurrent_approval_attempts(self, approval_service, db_session):
        """Test concurrent approval attempts on the same expense"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        approver = User(id=2, email="approver@example.com", role="manager")
        db_session.add(user)
        db_session.add(approver)
        
        rule = ApprovalRule(
            id=1,
            name="Test Rule",
            approver_id=2,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Submit for approval
        approvals = approval_service.submit_for_approval(1, 1)
        approval_id = approvals[0].id
        
        # First approval should succeed
        approval_service.approve_expense(approval_id, 2)
        
        # Second approval attempt should fail
        with pytest.raises(Exception):  # Should raise InvalidApprovalState
            approval_service.approve_expense(approval_id, 2)
    
    def test_approval_with_database_connection_error(self, approval_service, db_session):
        """Test approval workflow with database connection issues"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        db_session.commit()
        
        # Mock database error
        with patch.object(db_session, 'commit', side_effect=OperationalError("Connection lost", None, None)):
            with pytest.raises(OperationalError):
                approval_service.submit_for_approval(1, 1)
    
    def test_approval_with_invalid_currency_combinations(self, validation_service, db_session):
        """Test approval with mismatched currencies between expense and rule"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="EUR",  # Euro
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        
        # Rule in different currency
        rule = ApprovalRule(
            id=1,
            name="USD Rule",
            approver_id=1,
            approval_level=1,
            currency="USD",  # USD rule for EUR expense
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Should still validate the expense itself
        validated_expense, validated_user = validation_service.validate_approval_submission(1, 1)
        assert validated_expense.currency == "EUR"
    
    def test_approval_with_timezone_edge_cases(self, approval_service, db_session):
        """Test approval workflow across different timezones"""
        # Create expense with timezone-aware datetime
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        
        rule = ApprovalRule(
            id=1,
            name="Test Rule",
            approver_id=1,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Submit for approval
        approvals = approval_service.submit_for_approval(1, 1)
        
        # Check that timestamps are timezone-aware
        assert approvals[0].submitted_at.tzinfo is not None
        assert approvals[0].submitted_at.tzinfo == timezone.utc
    
    def test_approval_with_null_values_in_optional_fields(self, approval_service, db_session):
        """Test approval workflow with null values in optional fields"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            description=None,  # Null description
            vendor=None,       # Null vendor
            receipt_url=None,  # Null receipt
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        
        rule = ApprovalRule(
            id=1,
            name="Test Rule",
            approver_id=1,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Should handle null optional fields gracefully
        approvals = approval_service.submit_for_approval(1, 1)
        assert len(approvals) > 0
    
    def test_approval_rule_with_extreme_priority_values(self, validation_service):
        """Test approval rule validation with extreme priority values"""
        from core.schemas.approval import ApprovalRuleCreate
        
        # Test with maximum priority
        rule_data = ApprovalRuleCreate(
            name="Max Priority Rule",
            approver_id=1,
            approval_level=1,
            currency="USD",
            priority=1000  # Maximum allowed
        )
        
        # Should not raise validation error
        try:
            validation_service.validate_approval_rule_create(rule_data)
        except ValidationError:
            pytest.fail("Should accept maximum priority value")
        
        # Test with priority above maximum
        rule_data.priority = 1001
        
        with pytest.raises(ValidationError) as exc_info:
            validation_service.validate_approval_rule_create(rule_data)
        
        error = exc_info.value
        assert "Priority must be between 0 and 1000" in error.details["reason"]
    
    def test_approval_with_floating_point_precision_issues(self, approval_service, db_session):
        """Test approval workflow with floating point precision edge cases"""
        # Use amount that might cause floating point precision issues
        expense = Expense(
            id=1,
            amount=99.999999999,  # Many decimal places
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        
        user = User(id=1, email="test@example.com", role="employee")
        db_session.add(user)
        
        rule = ApprovalRule(
            id=1,
            name="Test Rule",
            min_amount=100.0,  # Just above the expense amount
            approver_id=1,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(rule)
        db_session.commit()
        
        # Should handle floating point precision properly
        approvals = approval_service.submit_for_approval(1, 1)
        assert len(approvals) > 0


class TestApprovalValidationEdgeCases:
    """Test edge cases in approval validation"""
    
    @pytest.fixture
    def validation_service(self, db_session):
        return ApprovalValidationService(db_session)
    
    def test_validate_currency_code_edge_cases(self, validation_service):
        """Test currency code validation with edge cases"""
        # Test lowercase currency
        assert not validation_service._is_valid_currency_code("usd")
        
        # Test mixed case
        assert not validation_service._is_valid_currency_code("UsD")
        
        # Test too short
        assert not validation_service._is_valid_currency_code("US")
        
        # Test too long
        assert not validation_service._is_valid_currency_code("USDD")
        
        # Test with numbers
        assert not validation_service._is_valid_currency_code("US1")
        
        # Test with special characters
        assert not validation_service._is_valid_currency_code("US$")
        
        # Test valid uppercase
        assert validation_service._is_valid_currency_code("USD")
        assert validation_service._is_valid_currency_code("EUR")
        assert validation_service._is_valid_currency_code("GBP")
    
    def test_validate_notes_length_boundary(self, validation_service, db_session):
        """Test notes length validation at boundary conditions"""
        approval = ExpenseApproval(
            id=1,
            expense_id=1,
            approver_id=1,
            status=ApprovalStatus.PENDING,
            approval_level=1,
            is_current_level=True,
            submitted_at=datetime.now(timezone.utc)
        )
        db_session.add(approval)
        db_session.commit()
        
        # Test exactly at limit (1000 characters)
        notes_at_limit = "A" * 1000
        try:
            validation_service.validate_approval_decision(1, 1, "approved", notes=notes_at_limit)
        except ValidationError:
            pytest.fail("Should accept notes at exactly 1000 characters")
        
        # Test over limit
        notes_over_limit = "A" * 1001
        with pytest.raises(ValidationError) as exc_info:
            validation_service.validate_approval_decision(1, 1, "approved", notes=notes_over_limit)
        
        error = exc_info.value
        assert "cannot exceed 1000 characters" in error.details["reason"]
    
    def test_validate_rejection_reason_boundary(self, validation_service, db_session):
        """Test rejection reason validation at boundary conditions"""
        approval = ExpenseApproval(
            id=1,
            expense_id=1,
            approver_id=1,
            status=ApprovalStatus.PENDING,
            approval_level=1,
            is_current_level=True,
            submitted_at=datetime.now(timezone.utc)
        )
        db_session.add(approval)
        db_session.commit()
        
        # Test exactly at minimum length (10 characters)
        reason_at_min = "A" * 10
        try:
            validation_service.validate_approval_decision(1, 1, "rejected", rejection_reason=reason_at_min)
        except ValidationError:
            pytest.fail("Should accept rejection reason at exactly 10 characters")
        
        # Test under minimum length
        reason_under_min = "A" * 9
        with pytest.raises(ValidationError) as exc_info:
            validation_service.validate_approval_decision(1, 1, "rejected", rejection_reason=reason_under_min)
        
        error = exc_info.value
        assert "at least 10 characters" in error.details["reason"]


if __name__ == "__main__":
    pytest.main([__file__])