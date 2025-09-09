"""
Unit tests for comprehensive error handling in the reporting module.

Tests validation, retry logic, circuit breaker functionality, and error responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from api.exceptions.report_exceptions import (
    ReportValidationException, ReportGenerationException, ReportTemplateException,
    ReportScheduleException, ReportExportException, ReportDataException,
    ReportErrorCode, validation_error, date_range_error, client_not_found_error,
    amount_range_error, template_not_found_error, schedule_not_found_error,
    export_format_error
)
from api.services.report_validation_service import ReportValidationService
from api.services.report_retry_service import (
    ReportRetryService, RetryConfig, CircuitBreakerConfig, RetryStrategy,
    CircuitBreaker, CircuitBreakerState, retry_on_failure
)
from api.services.report_service import ReportService
from api.schemas.report import ReportType, ExportFormat, ReportResult
from api.models.models_per_tenant import Client


class TestReportExceptions:
    """Test custom report exception classes"""
    
    def test_base_report_exception_creation(self):
        """Test creating base report exception with all fields"""
        exception = ReportValidationException(
            message="Test error",
            error_code=ReportErrorCode.VALIDATION_FILTER_INVALID,
            field="test_field",
            details={"key": "value"},
            suggestions=["Try this", "Or this"]
        )
        
        assert exception.message == "Test error"
        assert exception.error_code == ReportErrorCode.VALIDATION_FILTER_INVALID
        assert exception.field == "test_field"
        assert exception.details == {"key": "value"}
        assert exception.suggestions == ["Try this", "Or this"]
        assert not exception.retryable
    
    def test_exception_to_dict(self):
        """Test converting exception to dictionary"""
        exception = ReportGenerationException(
            message="Generation failed",
            error_code=ReportErrorCode.REPORT_GENERATION_FAILED,
            details={"attempt": 1},
            suggestions=["Retry later"],
            retryable=True
        )
        
        result = exception.to_dict()
        
        assert result["error_code"] == "REPORT_004"
        assert result["message"] == "Generation failed"
        assert result["details"] == {"attempt": 1}
        assert result["suggestions"] == ["Retry later"]
        assert result["retryable"] is True
    
    def test_convenience_functions(self):
        """Test convenience functions for creating common exceptions"""
        # Test validation error
        error = validation_error("Invalid input", field="test", suggestions=["Fix it"])
        assert isinstance(error, ReportValidationException)
        assert error.field == "test"
        
        # Test date range error
        error = date_range_error("2023-01-01", "2022-12-31")
        assert error.error_code == ReportErrorCode.VALIDATION_DATE_RANGE_INVALID
        
        # Test client not found error
        error = client_not_found_error([1, 2, 3])
        assert error.error_code == ReportErrorCode.VALIDATION_CLIENT_NOT_FOUND
        assert error.details["invalid_client_ids"] == [1, 2, 3]
        
        # Test amount range error
        error = amount_range_error(100.0, 50.0)
        assert error.error_code == ReportErrorCode.VALIDATION_AMOUNT_RANGE_INVALID
        
        # Test template not found error
        error = template_not_found_error(123)
        assert error.error_code == ReportErrorCode.TEMPLATE_NOT_FOUND
        assert error.details["template_id"] == 123
        
        # Test schedule not found error
        error = schedule_not_found_error(456)
        assert error.error_code == ReportErrorCode.SCHEDULE_NOT_FOUND
        
        # Test export format error
        error = export_format_error("invalid_format")
        assert error.error_code == ReportErrorCode.EXPORT_FORMAT_UNSUPPORTED


class TestReportValidationService:
    """Test report validation service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def validation_service(self, mock_db):
        """Create validation service with mocked database"""
        return ReportValidationService(mock_db)
    
    def test_validate_report_type_valid(self, validation_service):
        """Test validating valid report types"""
        result = validation_service._validate_report_type("client")
        assert result == ReportType.CLIENT
        
        result = validation_service._validate_report_type("invoice")
        assert result == ReportType.INVOICE
    
    def test_validate_report_type_invalid(self, validation_service):
        """Test validating invalid report types"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_report_type("invalid_type")
        
        assert exc_info.value.error_code == ReportErrorCode.REPORT_INVALID_TYPE
        assert "invalid_type" in exc_info.value.message
        assert "Valid report types" in exc_info.value.suggestions[0]
    
    def test_validate_report_type_empty(self, validation_service):
        """Test validating empty report type"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_report_type("")
        
        assert "Report type is required" in exc_info.value.message
        assert exc_info.value.field == "report_type"
    
    def test_validate_export_format_valid(self, validation_service):
        """Test validating valid export formats"""
        result = validation_service._validate_export_format("pdf")
        assert result == ExportFormat.PDF
        
        result = validation_service._validate_export_format("CSV")  # Case insensitive
        assert result == ExportFormat.CSV
    
    def test_validate_export_format_invalid(self, validation_service):
        """Test validating invalid export formats"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_export_format("invalid_format")
        
        assert exc_info.value.error_code == ReportErrorCode.VALIDATION_EXPORT_FORMAT_INVALID
        assert "invalid_format" in exc_info.value.message
    
    def test_validate_date_range_valid(self, validation_service):
        """Test validating valid date ranges"""
        result = validation_service._validate_date_range(
            "2023-01-01T00:00:00Z",
            "2023-12-31T23:59:59Z"
        )
        
        assert "date_from" in result
        assert "date_to" in result
        assert result["date_from"] < result["date_to"]
    
    def test_validate_date_range_invalid_order(self, validation_service):
        """Test validating date range with invalid order"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_date_range(
                "2023-12-31T00:00:00Z",
                "2023-01-01T00:00:00Z"
            )
        
        assert exc_info.value.error_code == ReportErrorCode.VALIDATION_DATE_RANGE_INVALID
    
    def test_validate_date_range_too_large(self, validation_service):
        """Test validating date range that's too large"""
        start_date = datetime.now() - timedelta(days=800)  # More than 2 years
        end_date = datetime.now()
        
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_date_range(
                start_date.isoformat(),
                end_date.isoformat()
            )
        
        assert exc_info.value.error_code == ReportErrorCode.VALIDATION_DATE_RANGE_INVALID
        assert "Date range too large" in exc_info.value.message
    
    def test_validate_client_ids_valid(self, validation_service, mock_db):
        """Test validating valid client IDs"""
        # Mock database query to return existing clients
        mock_clients = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_clients
        
        result = validation_service._validate_client_ids([1, 2, 3])
        assert result == [1, 2, 3]
    
    def test_validate_client_ids_not_found(self, validation_service, mock_db):
        """Test validating client IDs that don't exist"""
        # Mock database query to return only some clients
        mock_clients = [Mock(id=1), Mock(id=2)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_clients
        
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_client_ids([1, 2, 3, 4])
        
        assert exc_info.value.error_code == ReportErrorCode.VALIDATION_CLIENT_NOT_FOUND
        assert set(exc_info.value.details["invalid_client_ids"]) == {3, 4}
    
    def test_validate_client_ids_invalid_type(self, validation_service):
        """Test validating client IDs with invalid types"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_client_ids("not_a_list")
        
        assert "must be a list of integers" in exc_info.value.message
    
    def test_validate_client_ids_too_many(self, validation_service):
        """Test validating too many client IDs"""
        too_many_ids = list(range(1, 102))  # 101 IDs, max is 100
        
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_client_ids(too_many_ids)
        
        assert "Too many client IDs" in exc_info.value.message
    
    def test_validate_currency_valid(self, validation_service):
        """Test validating valid currency codes"""
        result = validation_service._validate_currency("usd")
        assert result == "USD"
        
        result = validation_service._validate_currency("EUR")
        assert result == "EUR"
    
    def test_validate_currency_invalid(self, validation_service):
        """Test validating invalid currency codes"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_currency("INVALID")
        
        assert exc_info.value.error_code == ReportErrorCode.VALIDATION_CURRENCY_INVALID
    
    def test_validate_amount_range_valid(self, validation_service):
        """Test validating valid amount ranges"""
        result = validation_service._validate_amount_range(10.0, 100.0)
        assert result["amount_min"] == 10.0
        assert result["amount_max"] == 100.0
    
    def test_validate_amount_range_invalid_order(self, validation_service):
        """Test validating amount range with invalid order"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_amount_range(100.0, 10.0)
        
        assert exc_info.value.error_code == ReportErrorCode.VALIDATION_AMOUNT_RANGE_INVALID
    
    def test_validate_boolean_flag(self, validation_service):
        """Test validating boolean flags"""
        assert validation_service._validate_boolean_flag(True, "test") is True
        assert validation_service._validate_boolean_flag(False, "test") is False
        assert validation_service._validate_boolean_flag("true", "test") is True
        assert validation_service._validate_boolean_flag("false", "test") is False
        assert validation_service._validate_boolean_flag(1, "test") is True
        assert validation_service._validate_boolean_flag(0, "test") is False
        
        with pytest.raises(ReportValidationException):
            validation_service._validate_boolean_flag("invalid", "test")


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker with test configuration"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,  # Short timeout for testing
            success_threshold=2
        )
        return CircuitBreaker(config)
    
    def test_initial_state(self, circuit_breaker):
        """Test circuit breaker initial state"""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.failure_count == 0
    
    def test_failure_threshold(self, circuit_breaker):
        """Test circuit breaker opens after failure threshold"""
        # Record failures up to threshold
        for i in range(3):
            circuit_breaker.record_failure()
            if i < 2:
                assert circuit_breaker.state == CircuitBreakerState.CLOSED
        
        # Should be open after threshold
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.can_execute() is False
    
    def test_recovery_timeout(self, circuit_breaker):
        """Test circuit breaker recovery after timeout"""
        # Open the circuit breaker
        for _ in range(3):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Should still be open immediately
        assert circuit_breaker.can_execute() is False
        
        # Wait for recovery timeout
        import time
        time.sleep(1.1)
        
        # Should allow execution (half-open)
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
    
    def test_half_open_success(self, circuit_breaker):
        """Test circuit breaker closes after successful half-open attempts"""
        # Open the circuit breaker
        for _ in range(3):
            circuit_breaker.record_failure()
        
        # Move to half-open
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        
        # Record successful attempts
        circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
        
        circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
    
    def test_half_open_failure(self, circuit_breaker):
        """Test circuit breaker returns to open after half-open failure"""
        # Move to half-open
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        
        # Record failure
        circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitBreakerState.OPEN


class TestRetryService:
    """Test retry service functionality"""
    
    @pytest.fixture
    def retry_service(self):
        """Create retry service with test configuration"""
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.1,  # Short delay for testing
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        return ReportRetryService(retry_config=config)
    
    def test_successful_operation(self, retry_service):
        """Test retry service with successful operation"""
        def successful_operation():
            return "success"
        
        result = retry_service.with_retry(successful_operation)
        
        assert result.success is True
        assert result.result == "success"
        assert len(result.attempts) == 1
        assert result.exception is None
    
    def test_retryable_failure_then_success(self, retry_service):
        """Test retry service with retryable failure then success"""
        call_count = 0
        
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ReportGenerationException(
                    "Temporary failure",
                    ReportErrorCode.REPORT_GENERATION_FAILED
                )
            return "success"
        
        result = retry_service.with_retry(flaky_operation)
        
        assert result.success is True
        assert result.result == "success"
        assert len(result.attempts) == 3
        assert call_count == 3
    
    def test_non_retryable_failure(self, retry_service):
        """Test retry service with non-retryable failure"""
        def failing_operation():
            raise ReportValidationException(
                "Validation error",
                ReportErrorCode.VALIDATION_FILTER_INVALID
            )
        
        result = retry_service.with_retry(failing_operation)
        
        assert result.success is False
        assert len(result.attempts) == 1  # Should not retry
        assert isinstance(result.exception, ReportValidationException)
    
    def test_max_attempts_exceeded(self, retry_service):
        """Test retry service when max attempts are exceeded"""
        def always_failing_operation():
            raise ReportGenerationException(
                "Always fails",
                ReportErrorCode.REPORT_GENERATION_FAILED
            )
        
        result = retry_service.with_retry(always_failing_operation)
        
        assert result.success is False
        assert len(result.attempts) == 3  # Max attempts
        assert isinstance(result.exception, ReportGenerationException)
    
    def test_circuit_breaker_integration(self, retry_service):
        """Test retry service with circuit breaker"""
        # Open the circuit breaker by recording failures
        for _ in range(5):
            retry_service.circuit_breaker.record_failure()
        
        def operation():
            return "success"
        
        result = retry_service.with_retry(operation)
        
        assert result.success is False
        assert result.circuit_breaker_triggered is True
        assert len(result.attempts) == 0  # No attempts made
    
    def test_retry_decorator(self):
        """Test retry decorator functionality"""
        call_count = 0
        
        @retry_on_failure(max_attempts=3, base_delay=0.01)
        def decorated_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = decorated_function()
        assert result == "success"
        assert call_count == 3


class TestReportServiceErrorHandling:
    """Test error handling in the main report service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def report_service(self, mock_db):
        """Create report service with mocked dependencies"""
        with patch('api.services.report_service.ReportDataAggregator'), \
             patch('api.services.report_service.ReportExportService'), \
             patch('api.services.report_service.ReportValidationService'), \
             patch('api.services.report_service.ReportRetryService'):
            return ReportService(mock_db)
    
    def test_validation_error_handling(self, report_service):
        """Test handling of validation errors"""
        # Mock validation service to raise validation error
        report_service.validation_service.validate_report_request.side_effect = \
            ReportValidationException(
                "Invalid filters",
                ReportErrorCode.VALIDATION_FILTER_INVALID,
                field="filters",
                suggestions=["Fix your filters"]
            )
        
        result = report_service.generate_report("client", {}, "json")
        
        assert result.success is False
        assert result.error_code == "VALIDATION_003"
        assert result.error_message == "Invalid filters"
        assert result.suggestions == ["Fix your filters"]
    
    def test_generation_error_with_retry(self, report_service):
        """Test handling of generation errors with retry"""
        # Mock validation to succeed
        report_service.validation_service.validate_report_request.return_value = {
            "report_type": ReportType.CLIENT,
            "filters": {},
            "export_format": ExportFormat.JSON
        }
        
        # Mock retry service to return failure
        mock_retry_result = Mock()
        mock_retry_result.success = False
        mock_retry_result.exception = ReportGenerationException(
            "Generation failed",
            ReportErrorCode.REPORT_GENERATION_FAILED,
            suggestions=["Try again later"]
        )
        mock_retry_result.attempts = [Mock(), Mock()]  # 2 attempts
        mock_retry_result.total_duration = 5.0
        mock_retry_result.circuit_breaker_triggered = False
        
        report_service.retry_service.with_retry.return_value = mock_retry_result
        
        result = report_service.generate_report("client", {}, "json")
        
        assert result.success is False
        assert result.error_code == "REPORT_004"
        assert result.error_message == "Generation failed"
        assert result.suggestions == ["Try again later"]
        assert result.retry_attempts == 2
    
    def test_unexpected_error_handling(self, report_service):
        """Test handling of unexpected errors"""
        # Mock validation service to raise unexpected error
        report_service.validation_service.validate_report_request.side_effect = \
            Exception("Unexpected error")
        
        result = report_service.generate_report("client", {}, "json")
        
        assert result.success is False
        assert result.error_code == "REPORT_004"
        assert "unexpected error" in result.error_message.lower()
        assert len(result.suggestions) > 0


class TestErrorHandlingIntegration:
    """Integration tests for error handling across the reporting module"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = Mock(spec=Session)
        # Mock client query for validation
        mock_clients = [Mock(id=1), Mock(id=2)]
        db.query.return_value.filter.return_value.all.return_value = mock_clients
        return db
    
    def test_end_to_end_validation_error(self, mock_db):
        """Test end-to-end validation error flow"""
        with patch('api.services.report_service.ReportDataAggregator'), \
             patch('api.services.report_service.ReportExportService'):
            
            service = ReportService(mock_db)
            
            # Test with invalid report type
            result = service.generate_report("invalid_type", {}, "json")
            
            assert result.success is False
            assert result.error_code == "REPORT_001"
            assert "Invalid report type" in result.error_message
            assert len(result.suggestions) > 0
    
    def test_end_to_end_client_not_found_error(self, mock_db):
        """Test end-to-end client not found error flow"""
        with patch('api.services.report_service.ReportDataAggregator'), \
             patch('api.services.report_service.ReportExportService'):
            
            service = ReportService(mock_db)
            
            # Test with non-existent client IDs
            result = service.generate_report(
                "client",
                {"client_ids": [1, 2, 999]},  # 999 doesn't exist
                "json"
            )
            
            assert result.success is False
            assert result.error_code == "VALIDATION_004"
            assert "not found" in result.error_message
            assert 999 in result.error_details["invalid_client_ids"]
    
    def test_error_message_localization_ready(self):
        """Test that error messages are ready for localization"""
        error = validation_error("Test error", field="test")
        error_dict = error.to_dict()
        
        # Error codes should be machine-readable for localization
        assert error_dict["error_code"].startswith("VALIDATION_")
        assert isinstance(error_dict["suggestions"], list)
        assert isinstance(error_dict["details"], dict)