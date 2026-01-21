"""
Unit tests for the report retry service.

Tests retry logic, circuit breaker functionality, and error recovery mechanisms.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from core.services.report_retry_service import (
    ReportRetryService, RetryConfig, CircuitBreakerConfig, RetryStrategy,
    CircuitBreaker, CircuitBreakerState, retry_on_failure, RetryResult
)
from core.exceptions.report_exceptions import (
    ReportValidationException, ReportGenerationException, ReportErrorCode
)


class TestRetryConfig:
    """Test retry configuration"""
    
    def test_default_config(self):
        """Test default retry configuration"""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert config.backoff_multiplier == 2.0
        assert config.jitter is True
    
    def test_custom_config(self):
        """Test custom retry configuration"""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            jitter=False
        )
        
        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.strategy == RetryStrategy.LINEAR_BACKOFF
        assert config.jitter is False


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration"""
    
    def test_default_config(self):
        """Test default circuit breaker configuration"""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 2
        assert config.timeout == 30.0
    
    def test_custom_config(self):
        """Test custom circuit breaker configuration"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=1
        )
        
        assert config.failure_threshold == 3
        assert config.recovery_timeout == 30.0
        assert config.success_threshold == 1


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker with test configuration"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=0.1,  # Short timeout for testing
            success_threshold=2
        )
        return CircuitBreaker(config)
    
    def test_initial_state(self, circuit_breaker):
        """Test circuit breaker initial state"""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.last_failure_time is None
    
    def test_record_success_in_closed_state(self, circuit_breaker):
        """Test recording success in closed state"""
        circuit_breaker.failure_count = 2
        circuit_breaker.record_success()
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    def test_record_failure_threshold_reached(self, circuit_breaker):
        """Test circuit breaker opens when failure threshold is reached"""
        # Record failures up to threshold
        for i in range(3):
            circuit_breaker.record_failure()
            if i < 2:
                assert circuit_breaker.state == CircuitBreakerState.CLOSED
        
        # Should be open after threshold
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.can_execute() is False
        assert circuit_breaker.last_failure_time is not None
    
    def test_recovery_timeout_transition(self, circuit_breaker):
        """Test transition from open to half-open after recovery timeout"""
        # Open the circuit breaker
        for _ in range(3):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.can_execute() is False
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Should allow execution (transition to half-open)
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
    
    def test_half_open_success_threshold(self, circuit_breaker):
        """Test transition from half-open to closed after success threshold"""
        # Move to half-open state
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker.success_count = 0
        
        # Record first success
        circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
        assert circuit_breaker.success_count == 1
        
        # Record second success (reaches threshold)
        circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    def test_half_open_failure_returns_to_open(self, circuit_breaker):
        """Test that failure in half-open state returns to open"""
        # Move to half-open state
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        
        # Record failure
        circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 1
    
    def test_should_attempt_reset_no_previous_failure(self, circuit_breaker):
        """Test should attempt reset when no previous failure"""
        assert circuit_breaker._should_attempt_reset() is True
    
    def test_should_attempt_reset_timeout_not_reached(self, circuit_breaker):
        """Test should not attempt reset when timeout not reached"""
        circuit_breaker.last_failure_time = datetime.now()
        assert circuit_breaker._should_attempt_reset() is False
    
    def test_should_attempt_reset_timeout_reached(self, circuit_breaker):
        """Test should attempt reset when timeout reached"""
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=1)
        assert circuit_breaker._should_attempt_reset() is True


class TestRetryService:
    """Test retry service functionality"""
    
    @pytest.fixture
    def retry_service(self):
        """Create retry service with test configuration"""
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,  # Very short delay for testing
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            jitter=False  # Disable jitter for predictable testing
        )
        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1
        )
        return ReportRetryService(retry_config, circuit_breaker_config)
    
    def test_successful_operation_first_attempt(self, retry_service):
        """Test successful operation on first attempt"""
        def successful_operation():
            return "success"
        
        result = retry_service.with_retry(successful_operation)
        
        assert result.success is True
        assert result.result == "success"
        assert len(result.attempts) == 1
        assert result.attempts[0].attempt_number == 1
        assert result.attempts[0].exception is None
        assert result.exception is None
        assert result.circuit_breaker_triggered is False
    
    def test_successful_operation_with_arguments(self, retry_service):
        """Test successful operation with arguments"""
        def operation_with_args(x, y, z=None):
            return f"{x}-{y}-{z}"
        
        result = retry_service.with_retry(operation_with_args, "a", "b", z="c")
        
        assert result.success is True
        assert result.result == "a-b-c"
    
    def test_retryable_failure_then_success(self, retry_service):
        """Test operation that fails then succeeds"""
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
        
        # Check attempt details
        assert result.attempts[0].exception is not None
        assert result.attempts[1].exception is not None
        assert result.attempts[2].exception is None
    
    def test_non_retryable_exception(self, retry_service):
        """Test operation with non-retryable exception"""
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
        """Test operation that always fails"""
        def always_failing_operation():
            raise ReportGenerationException(
                "Always fails",
                ReportErrorCode.REPORT_GENERATION_FAILED
            )
        
        result = retry_service.with_retry(always_failing_operation)
        
        assert result.success is False
        assert len(result.attempts) == 3  # Max attempts
        assert isinstance(result.exception, ReportGenerationException)
        assert result.total_duration > 0
    
    def test_circuit_breaker_open_rejects_requests(self, retry_service):
        """Test that open circuit breaker rejects requests"""
        # Open the circuit breaker
        for _ in range(2):
            retry_service.circuit_breaker.record_failure()
        
        def operation():
            return "success"
        
        result = retry_service.with_retry(operation)
        
        assert result.success is False
        assert result.circuit_breaker_triggered is True
        assert len(result.attempts) == 0  # No attempts made
        assert isinstance(result.exception, ReportGenerationException)
        assert "temporarily unavailable" in result.exception.message.lower()
    
    def test_delay_calculation_exponential_backoff(self, retry_service):
        """Test delay calculation for exponential backoff"""
        config = RetryConfig(
            base_delay=1.0,
            backoff_multiplier=2.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            jitter=False
        )
        retry_service.retry_config = config
        
        assert retry_service._calculate_delay(1, config) == 1.0  # 1.0 * 2^0
        assert retry_service._calculate_delay(2, config) == 2.0  # 1.0 * 2^1
        assert retry_service._calculate_delay(3, config) == 4.0  # 1.0 * 2^2
    
    def test_delay_calculation_linear_backoff(self, retry_service):
        """Test delay calculation for linear backoff"""
        config = RetryConfig(
            base_delay=1.0,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            jitter=False
        )
        
        assert retry_service._calculate_delay(1, config) == 1.0  # 1.0 * 1
        assert retry_service._calculate_delay(2, config) == 2.0  # 1.0 * 2
        assert retry_service._calculate_delay(3, config) == 3.0  # 1.0 * 3
    
    def test_delay_calculation_fixed_delay(self, retry_service):
        """Test delay calculation for fixed delay"""
        config = RetryConfig(
            base_delay=1.5,
            strategy=RetryStrategy.FIXED_DELAY,
            jitter=False
        )
        
        assert retry_service._calculate_delay(1, config) == 1.5
        assert retry_service._calculate_delay(2, config) == 1.5
        assert retry_service._calculate_delay(3, config) == 1.5
    
    def test_delay_calculation_immediate(self, retry_service):
        """Test delay calculation for immediate retry"""
        config = RetryConfig(
            base_delay=1.0,
            strategy=RetryStrategy.IMMEDIATE,
            jitter=False
        )
        
        assert retry_service._calculate_delay(1, config) == 0.0
        assert retry_service._calculate_delay(2, config) == 0.0
    
    def test_delay_calculation_max_delay_limit(self, retry_service):
        """Test that delay is limited by max_delay"""
        config = RetryConfig(
            base_delay=10.0,
            max_delay=5.0,
            backoff_multiplier=2.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            jitter=False
        )
        
        # Would be 10.0 * 2^2 = 40.0, but limited to 5.0
        assert retry_service._calculate_delay(3, config) == 5.0
    
    def test_delay_calculation_with_jitter(self, retry_service):
        """Test delay calculation with jitter"""
        config = RetryConfig(
            base_delay=1.0,
            strategy=RetryStrategy.FIXED_DELAY,
            jitter=True
        )
        
        # With jitter, delay should vary around base_delay
        delays = [retry_service._calculate_delay(1, config) for _ in range(10)]
        
        # All delays should be non-negative
        assert all(delay >= 0 for delay in delays)
        
        # There should be some variation (not all the same)
        assert len(set(delays)) > 1
    
    def test_is_retryable_exception_retryable_type(self, retry_service):
        """Test identifying retryable exceptions"""
        config = RetryConfig()
        
        # ReportGenerationException should be retryable
        exception = ReportGenerationException(
            "Test error",
            ReportErrorCode.REPORT_GENERATION_FAILED
        )
        assert retry_service._is_retryable_exception(exception, config) is True
        
        # ConnectionError should be retryable
        exception = ConnectionError("Connection failed")
        assert retry_service._is_retryable_exception(exception, config) is True
    
    def test_is_retryable_exception_non_retryable_type(self, retry_service):
        """Test identifying non-retryable exceptions"""
        config = RetryConfig()
        
        # ValueError should not be retryable (not in retryable_exceptions)
        exception = ValueError("Invalid value")
        assert retry_service._is_retryable_exception(exception, config) is False
    
    def test_is_retryable_exception_non_retryable_error_code(self, retry_service):
        """Test identifying non-retryable error codes"""
        config = RetryConfig()
        
        # Validation errors should not be retryable
        exception = ReportValidationException(
            "Validation error",
            ReportErrorCode.VALIDATION_FILTER_INVALID
        )
        assert retry_service._is_retryable_exception(exception, config) is False
    
    def test_is_retryable_exception_retryable_flag(self, retry_service):
        """Test using retryable flag from exception"""
        config = RetryConfig()
        
        # Exception with retryable=False should not be retryable
        exception = ReportGenerationException(
            "Non-retryable error",
            ReportErrorCode.REPORT_GENERATION_FAILED,
            retryable=False
        )
        assert retry_service._is_retryable_exception(exception, config) is False
        
        # Exception with retryable=True should be retryable
        exception = ReportGenerationException(
            "Retryable error",
            ReportErrorCode.REPORT_GENERATION_FAILED,
            retryable=True
        )
        assert retry_service._is_retryable_exception(exception, config) is True
    
    def test_get_circuit_breaker_status(self, retry_service):
        """Test getting circuit breaker status"""
        status = retry_service.get_circuit_breaker_status()
        
        assert "state" in status
        assert "failure_count" in status
        assert "success_count" in status
        assert "last_failure_time" in status
        assert "can_execute" in status
        
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["can_execute"] is True
    
    def test_reset_circuit_breaker(self, retry_service):
        """Test manually resetting circuit breaker"""
        # Open the circuit breaker
        for _ in range(2):
            retry_service.circuit_breaker.record_failure()
        
        assert retry_service.circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Reset it
        retry_service.reset_circuit_breaker()
        
        assert retry_service.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert retry_service.circuit_breaker.failure_count == 0
        assert retry_service.circuit_breaker.can_execute() is True


class TestAsyncRetryService:
    """Test async retry service functionality"""
    
    @pytest.fixture
    def retry_service(self):
        """Create retry service with test configuration"""
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,
            jitter=False
        )
        return ReportRetryService(retry_config)
    
    @pytest.mark.asyncio
    async def test_async_successful_operation(self, retry_service):
        """Test async successful operation"""
        async def async_operation():
            return "async_success"
        
        result = await retry_service.with_retry_async(async_operation)
        
        assert result.success is True
        assert result.result == "async_success"
        assert len(result.attempts) == 1
    
    @pytest.mark.asyncio
    async def test_async_retryable_failure_then_success(self, retry_service):
        """Test async operation that fails then succeeds"""
        call_count = 0
        
        async def flaky_async_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ReportGenerationException(
                    "Async temporary failure",
                    ReportErrorCode.REPORT_GENERATION_FAILED
                )
            return "async_success"
        
        result = await retry_service.with_retry_async(flaky_async_operation)
        
        assert result.success is True
        assert result.result == "async_success"
        assert len(result.attempts) == 3
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_max_attempts_exceeded(self, retry_service):
        """Test async operation that always fails"""
        async def always_failing_async_operation():
            raise ReportGenerationException(
                "Always fails async",
                ReportErrorCode.REPORT_GENERATION_FAILED
            )
        
        result = await retry_service.with_retry_async(always_failing_async_operation)
        
        assert result.success is False
        assert len(result.attempts) == 3
        assert isinstance(result.exception, ReportGenerationException)


class TestRetryDecorator:
    """Test retry decorator functionality"""
    
    def test_decorator_successful_operation(self):
        """Test decorator with successful operation"""
        @retry_on_failure(max_attempts=3, base_delay=0.01)
        def successful_function():
            return "decorated_success"
        
        result = successful_function()
        assert result == "decorated_success"
    
    def test_decorator_retryable_failure_then_success(self):
        """Test decorator with retryable failure then success"""
        call_count = 0
        
        @retry_on_failure(max_attempts=3, base_delay=0.01, retryable_exceptions=[Exception])
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "decorated_success"
        
        result = flaky_function()
        assert result == "decorated_success"
        assert call_count == 3
    
    def test_decorator_max_attempts_exceeded(self):
        """Test decorator when max attempts are exceeded"""
        @retry_on_failure(max_attempts=2, base_delay=0.01, retryable_exceptions=[Exception])
        def always_failing_function():
            raise Exception("Always fails")
        
        with pytest.raises(Exception) as exc_info:
            always_failing_function()
        
        assert "Always fails" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_async_decorator_successful_operation(self):
        """Test async decorator with successful operation"""
        @retry_on_failure(max_attempts=3, base_delay=0.01)
        async def async_successful_function():
            return "async_decorated_success"
        
        result = await async_successful_function()
        assert result == "async_decorated_success"
    
    @pytest.mark.asyncio
    async def test_async_decorator_retryable_failure_then_success(self):
        """Test async decorator with retryable failure then success"""
        call_count = 0
        
        @retry_on_failure(max_attempts=3, base_delay=0.01, retryable_exceptions=[Exception])
        async def flaky_async_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Async temporary failure")
            return "async_decorated_success"
        
        result = await flaky_async_function()
        assert result == "async_decorated_success"
        assert call_count == 3


class TestRetryResult:
    """Test retry result data structure"""
    
    def test_retry_result_creation(self):
        """Test creating retry result"""
        result = RetryResult(
            success=True,
            result="test_result",
            total_duration=1.5
        )
        
        assert result.success is True
        assert result.result == "test_result"
        assert result.total_duration == 1.5
        assert result.exception is None
        assert len(result.attempts) == 0
        assert result.circuit_breaker_triggered is False
    
    def test_retry_result_with_failure(self):
        """Test creating retry result with failure"""
        exception = Exception("Test error")
        result = RetryResult(
            success=False,
            exception=exception,
            circuit_breaker_triggered=True
        )
        
        assert result.success is False
        assert result.result is None
        assert result.exception == exception
        assert result.circuit_breaker_triggered is True