"""
Tests for approval workflow error handling and validation

This test suite covers comprehensive error handling scenarios for the approval workflow,
including validation errors, permission errors, and retry logic.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from exceptions.approval_exceptions import (
    ValidationError, ExpenseValidationError, InsufficientApprovalPermissions,
    ExpenseAlreadyApproved, NoApprovalRuleFound, InvalidApprovalState,
    ApprovalNotFoundException, DelegationValidationError, NotificationDeliveryError,
    ApprovalWorkflowError, ApprovalConcurrencyError
)
from services.approval_validation_service import ApprovalValidationService
from services.approval_notification_retry_service import ApprovalNotificationRetryService
from services.approval_service import ApprovalService
from models.models_per_tenant import Expense, User, ExpenseApproval, ApprovalRule
from schemas.approval import ApprovalStatus, ApprovalRuleCreate


class TestApprovalValidationService:
    """Test approval validation service error handling"""
    
    @pytest.fixture
    def validation_service(self, db_session):
        return ApprovalValidationService(db_session)
    
    @pytest.fixture
    def sample_expense(self, db_session):
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            description="Test expense",
            user_id=1
        )
        db_session.add(expense)
        db_session.commit()
        return expense
    
    @pytest.fixture
    def sample_user(self, db_session):
        user = User(
            id=1,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            role="employee"
        )
        db_session.add(user)
        db_session.commit()
        return user
    
    def test_validate_expense_for_approval_missing_amount(self, validation_service, db_session):
        """Test validation fails when expense amount is missing"""
        expense = Expense(
            id=1,
            amount=None,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        db_session.commit()
        
        with pytest.raises(ExpenseValidationError) as exc_info:
            validation_service.validate_expense_for_approval(1)
        
        error = exc_info.value
        assert "amount" in error.details["missing_fields"]
        assert error.error_code == "EXPENSE_VALIDATION_ERROR"
    
    def test_validate_expense_for_approval_invalid_amount(self, validation_service, db_session):
        """Test validation fails when expense amount is invalid"""
        expense = Expense(
            id=1,
            amount=-50.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        db_session.commit()
        
        with pytest.raises(ExpenseValidationError) as exc_info:
            validation_service.validate_expense_for_approval(1)
        
        error = exc_info.value
        assert "Amount must be greater than 0" in error.details["validation_errors"]
    
    def test_validate_expense_for_approval_missing_category(self, validation_service, db_session):
        """Test validation fails when category is missing"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        db_session.commit()
        
        with pytest.raises(ExpenseValidationError) as exc_info:
            validation_service.validate_expense_for_approval(1)
        
        error = exc_info.value
        assert "category" in error.details["missing_fields"]
    
    def test_validate_expense_for_approval_future_date(self, validation_service, db_session):
        """Test validation fails when expense date is in the future"""
        future_date = datetime.now().date() + timedelta(days=1)
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=future_date,
            user_id=1
        )
        db_session.add(expense)
        db_session.commit()
        
        with pytest.raises(ExpenseValidationError) as exc_info:
            validation_service.validate_expense_for_approval(1)
        
        error = exc_info.value
        assert "cannot be in the future" in str(error.details["validation_errors"])
    
    def test_validate_expense_for_approval_invalid_currency(self, validation_service, db_session):
        """Test validation fails with invalid currency code"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="INVALID",
            category="office_supplies",
            expense_date=datetime.now().date(),
            user_id=1
        )
        db_session.add(expense)
        db_session.commit()
        
        with pytest.raises(ExpenseValidationError) as exc_info:
            validation_service.validate_expense_for_approval(1)
        
        error = exc_info.value
        assert "Invalid currency code" in str(error.details["validation_errors"])
    
    def test_validate_expense_for_approval_high_risk_category_missing_vendor(self, validation_service, db_session):
        """Test validation fails when high-risk category expense missing vendor"""
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="travel",
            expense_date=datetime.now().date(),
            vendor="",
            user_id=1
        )
        db_session.add(expense)
        db_session.commit()
        
        with pytest.raises(ExpenseValidationError) as exc_info:
            validation_service.validate_expense_for_approval(1)
        
        error = exc_info.value
        assert "vendor" in error.details["missing_fields"]
        assert "required for travel expenses" in str(error.details["validation_errors"])
    
    def test_validate_approval_submission_expense_not_found(self, validation_service):
        """Test validation fails when expense not found"""
        with pytest.raises(ExpenseNotFoundException) as exc_info:
            validation_service.validate_approval_submission(999, 1)
        
        error = exc_info.value
        assert error.error_code == "EXPENSE_NOT_FOUND"
        assert error.details["expense_id"] == 999
    
    def test_validate_approval_submission_submitter_not_found(self, validation_service, sample_expense):
        """Test validation fails when submitter not found"""
        with pytest.raises(ValidationError) as exc_info:
            validation_service.validate_approval_submission(sample_expense.id, 999)
        
        error = exc_info.value
        assert error.details["field"] == "submitter_id"
        assert "not found" in error.details["reason"]
    
    def test_validate_approval_decision_invalid_status(self, validation_service, db_session):
        """Test validation fails with invalid decision status"""
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
        
        with pytest.raises(ValidationError) as exc_info:
            validation_service.validate_approval_decision(1, 1, "invalid_status")
        
        error = exc_info.value
        assert error.details["field"] == "decision_status"
        assert "must be 'approved' or 'rejected'" in error.details["reason"]
    
    def test_validate_approval_decision_missing_rejection_reason(self, validation_service, db_session):
        """Test validation fails when rejection reason is missing"""
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
        
        with pytest.raises(ValidationError) as exc_info:
            validation_service.validate_approval_decision(1, 1, "rejected", rejection_reason="")
        
        error = exc_info.value
        assert error.details["field"] == "rejection_reason"
        assert "required when rejecting" in error.details["reason"]
    
    def test_validate_approval_rule_create_duplicate_name(self, validation_service, db_session):
        """Test validation fails with duplicate rule name"""
        existing_rule = ApprovalRule(
            id=1,
            name="Test Rule",
            approver_id=1,
            approval_level=1,
            currency="USD",
            is_active=True,
            priority=0
        )
        db_session.add(existing_rule)
        db_session.commit()
        
        rule_data = ApprovalRuleCreate(
            name="Test Rule",
            approver_id=1,
            approval_level=1,
            currency="USD"
        )
        
        with pytest.raises(Exception):  # Should raise ApprovalRuleConflictError
            validation_service.validate_approval_rule_create(rule_data)
    
    def test_validate_approval_rule_create_invalid_amount_range(self, validation_service):
        """Test validation fails with invalid amount range"""
        rule_data = ApprovalRuleCreate(
            name="Invalid Rule",
            min_amount=100.0,
            max_amount=50.0,  # Max less than min
            approver_id=1,
            approval_level=1,
            currency="USD"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            validation_service.validate_approval_rule_create(rule_data)
        
        error = exc_info.value
        assert error.details["field"] == "max_amount"
        assert "greater than minimum amount" in error.details["reason"]


class TestApprovalNotificationRetryService:
    """Test approval notification retry service"""
    
    @pytest.fixture
    def mock_notification_service(self):
        return Mock()
    
    @pytest.fixture
    def retry_service(self, db_session, mock_notification_service):
        return ApprovalNotificationRetryService(db_session, mock_notification_service)
    
    def test_schedule_notification_retry(self, retry_service):
        """Test scheduling notification retry"""
        notification_id = retry_service.schedule_notification_retry(
            notification_type="expense_submitted_for_approval",
            recipient_id=1,
            approval_id=1,
            payload={"expense_id": 1, "amount": "USD 100.00", "category": "office_supplies"},
            error_message="SMTP connection failed"
        )
        
        assert notification_id is not None
        assert notification_id in retry_service.retry_records
        
        record = retry_service.retry_records[notification_id]
        assert record.notification_type == "expense_submitted_for_approval"
        assert record.recipient_id == 1
        assert record.approval_id == 1
        assert record.retry_count == 0
        assert record.last_error == "SMTP connection failed"
    
    def test_process_retry_queue_success(self, retry_service, mock_notification_service):
        """Test successful retry processing"""
        # Schedule a retry
        notification_id = retry_service.schedule_notification_retry(
            notification_type="expense_submitted_for_approval",
            recipient_id=1,
            approval_id=1,
            payload={"expense_id": 1, "amount": "USD 100.00", "category": "office_supplies"},
            error_message="Initial failure"
        )
        
        # Set next retry time to now so it's ready for processing
        retry_service.retry_records[notification_id].next_retry_at = datetime.now(timezone.utc)
        
        # Mock successful notification delivery
        mock_notification_service.send_operation_notification.return_value = True
        
        # Process retry queue
        stats = retry_service.process_retry_queue()
        
        assert stats["processed_count"] == 1
        assert stats["success_count"] == 1
        assert stats["failed_count"] == 0
        assert notification_id not in retry_service.retry_records
    
    def test_process_retry_queue_failure_with_retries_remaining(self, retry_service, mock_notification_service):
        """Test retry processing with failure but retries remaining"""
        # Schedule a retry
        notification_id = retry_service.schedule_notification_retry(
            notification_type="expense_submitted_for_approval",
            recipient_id=1,
            approval_id=1,
            payload={"expense_id": 1, "amount": "USD 100.00", "category": "office_supplies"},
            error_message="Initial failure"
        )
        
        # Set next retry time to now
        retry_service.retry_records[notification_id].next_retry_at = datetime.now(timezone.utc)
        
        # Mock failed notification delivery
        mock_notification_service.send_operation_notification.return_value = False
        
        # Process retry queue
        stats = retry_service.process_retry_queue()
        
        assert stats["processed_count"] == 1
        assert stats["success_count"] == 0
        assert stats["failed_count"] == 1
        
        # Record should still exist with incremented retry count
        assert notification_id in retry_service.retry_records
        record = retry_service.retry_records[notification_id]
        assert record.retry_count == 1
        assert not record.is_dead_letter
    
    def test_process_retry_queue_dead_letter(self, retry_service, mock_notification_service):
        """Test retry processing that results in dead letter"""
        # Schedule a retry with max retries already reached
        notification_id = retry_service.schedule_notification_retry(
            notification_type="expense_submitted_for_approval",
            recipient_id=1,
            approval_id=1,
            payload={"expense_id": 1, "amount": "USD 100.00", "category": "office_supplies"},
            error_message="Initial failure",
            retry_count=4  # One less than max_retries (5)
        )
        
        # Set next retry time to now
        retry_service.retry_records[notification_id].next_retry_at = datetime.now(timezone.utc)
        
        # Mock failed notification delivery
        mock_notification_service.send_operation_notification.return_value = False
        
        # Process retry queue
        stats = retry_service.process_retry_queue()
        
        assert stats["processed_count"] == 1
        assert stats["failed_count"] == 1
        assert stats["dead_letter_count"] == 1
        
        # Record should be marked as dead letter
        record = retry_service.retry_records[notification_id]
        assert record.is_dead_letter
        assert record.retry_count == 5
    
    def test_circuit_breaker_functionality(self, retry_service, mock_notification_service):
        """Test circuit breaker prevents retries after repeated failures"""
        user_id = 1
        
        # Simulate multiple failures to trigger circuit breaker
        for i in range(6):  # More than circuit_breaker_threshold (5)
            retry_service.circuit_breaker_failures[user_id] = i + 1
        
        # Schedule a retry
        notification_id = retry_service.schedule_notification_retry(
            notification_type="expense_submitted_for_approval",
            recipient_id=user_id,
            approval_id=1,
            payload={"expense_id": 1, "amount": "USD 100.00", "category": "office_supplies"},
            error_message="Initial failure"
        )
        
        # Set next retry time to now
        retry_service.retry_records[notification_id].next_retry_at = datetime.now(timezone.utc)
        
        # Process retry queue
        stats = retry_service.process_retry_queue()
        
        # Should be skipped due to circuit breaker
        assert stats["processed_count"] == 1
        assert stats["success_count"] == 0
        assert stats["failed_count"] == 0
        
        # Next retry time should be pushed forward
        record = retry_service.retry_records[notification_id]
        assert record.next_retry_at > datetime.now(timezone.utc) + timedelta(minutes=30)
    
    def test_cancel_notification_retries(self, retry_service):
        """Test cancelling notification retries for an approval"""
        approval_id = 1
        
        # Schedule multiple retries for the same approval
        notification_ids = []
        for i in range(3):
            notification_id = retry_service.schedule_notification_retry(
                notification_type="expense_submitted_for_approval",
                recipient_id=i + 1,
                approval_id=approval_id,
                payload={"expense_id": 1, "amount": "USD 100.00", "category": "office_supplies"},
                error_message="Test failure"
            )
            notification_ids.append(notification_id)
        
        # Cancel retries for the approval
        cancelled_count = retry_service.cancel_notification_retries(approval_id)
        
        assert cancelled_count == 3
        
        # All notifications should be removed
        for notification_id in notification_ids:
            assert notification_id not in retry_service.retry_records
    
    def test_get_retry_statistics(self, retry_service):
        """Test getting retry statistics"""
        # Schedule some retries
        retry_service.schedule_notification_retry(
            notification_type="expense_submitted_for_approval",
            recipient_id=1,
            approval_id=1,
            payload={"expense_id": 1, "amount": "USD 100.00", "category": "office_supplies"},
            error_message="Test failure"
        )
        
        retry_service.schedule_notification_retry(
            notification_type="expense_approved",
            recipient_id=2,
            approval_id=2,
            payload={"expense_id": 2, "amount": "USD 200.00", "category": "travel"},
            error_message="Test failure"
        )
        
        # Mark one as dead letter
        notification_id = list(retry_service.retry_records.keys())[0]
        retry_service.retry_records[notification_id].is_dead_letter = True
        
        stats = retry_service.get_retry_statistics()
        
        assert stats["total_records"] == 2
        assert stats["pending_retries"] == 1
        assert stats["dead_letters"] == 1
        assert "expense_submitted_for_approval" in stats["notification_types"]
        assert "expense_approved" in stats["notification_types"]


class TestApprovalServiceErrorHandling:
    """Test approval service error handling"""
    
    @pytest.fixture
    def mock_notification_service(self):
        return Mock()
    
    @pytest.fixture
    def approval_service(self, db_session, mock_notification_service):
        return ApprovalService(db_session, mock_notification_service)
    
    def test_submit_for_approval_with_validation_error(self, approval_service, db_session):
        """Test submit for approval handles validation errors properly"""
        # Create invalid expense (missing required fields)
        expense = Expense(
            id=1,
            amount=None,  # Invalid amount
            currency="USD",
            category="",  # Missing category
            user_id=1
        )
        db_session.add(expense)
        db_session.commit()
        
        with pytest.raises(ExpenseValidationError) as exc_info:
            approval_service.submit_for_approval(1, 1)
        
        error = exc_info.value
        assert error.error_code == "EXPENSE_VALIDATION_ERROR"
        assert "amount" in error.details["missing_fields"]
        assert "category" in error.details["missing_fields"]
    
    def test_submit_for_approval_with_concurrency_error(self, approval_service, db_session):
        """Test submit for approval handles concurrency errors"""
        # Create expense that gets modified concurrently
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            status="approved",  # Already approved by another process
            user_id=1
        )
        db_session.add(expense)
        
        user = User(
            id=1,
            email="test@example.com",
            role="employee"
        )
        db_session.add(user)
        db_session.commit()
        
        with pytest.raises(ExpenseAlreadyApproved) as exc_info:
            approval_service.submit_for_approval(1, 1)
        
        error = exc_info.value
        assert error.error_code == "EXPENSE_ALREADY_APPROVED"
    
    @patch('services.approval_service.ApprovalService._send_approval_notification_with_retry')
    def test_notification_failure_handling(self, mock_send_notification, approval_service, db_session):
        """Test notification failure handling with retry scheduling"""
        # Create valid expense and user
        expense = Expense(
            id=1,
            amount=100.0,
            currency="USD",
            category="office_supplies",
            expense_date=datetime.now().date(),
            status="draft",
            user_id=1
        )
        db_session.add(expense)
        
        user = User(
            id=1,
            email="test@example.com",
            role="employee"
        )
        db_session.add(user)
        
        # Create approval rule
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
        
        # Mock notification failure
        mock_send_notification.side_effect = Exception("SMTP server unavailable")
        
        # Submit for approval should still succeed even if notification fails
        approvals = approval_service.submit_for_approval(1, 1)
        
        assert len(approvals) > 0
        assert approvals[0].status == ApprovalStatus.PENDING
        
        # Notification should have been attempted
        mock_send_notification.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])