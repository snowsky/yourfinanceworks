"""
Report Retry Service

This service provides retry logic for failed report operations with
exponential backoff, circuit breaker patterns, and comprehensive logging.
"""

import asyncio
import time
import logging
from typing import Callable, Any, Optional, Dict, List, Union
from functools import wraps
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from core.exceptions.report_exceptions import (
    BaseReportException, ReportErrorCode, ReportGenerationException
)


class RetryStrategy(str, Enum):
    """Available retry strategies"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    backoff_multiplier: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd
    retryable_exceptions: List[type] = field(default_factory=lambda: [
        ReportGenerationException,
        ConnectionError,
        TimeoutError
    ])
    non_retryable_error_codes: List[ReportErrorCode] = field(default_factory=lambda: [
        ReportErrorCode.REPORT_INVALID_TYPE,
        ReportErrorCode.REPORT_ACCESS_DENIED,
        ReportErrorCode.VALIDATION_DATE_RANGE_INVALID,
        ReportErrorCode.VALIDATION_FILTER_INVALID,
        ReportErrorCode.TEMPLATE_ACCESS_DENIED,
        ReportErrorCode.SCHEDULE_ACCESS_DENIED
    ])


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: float = 60.0  # Seconds before trying half-open
    success_threshold: int = 2  # Successes needed to close from half-open
    timeout: float = 30.0  # Request timeout in seconds


@dataclass
class RetryAttempt:
    """Information about a retry attempt"""
    attempt_number: int
    delay: float
    exception: Optional[Exception] = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration: Optional[float] = None


@dataclass
class RetryResult:
    """Result of a retry operation"""
    success: bool
    result: Any = None
    exception: Optional[Exception] = None
    attempts: List[RetryAttempt] = field(default_factory=list)
    total_duration: float = 0.0
    circuit_breaker_triggered: bool = False


class CircuitBreaker:
    """Circuit breaker implementation for report operations"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.logger = logging.getLogger(__name__)
    
    def can_execute(self) -> bool:
        """Check if operation can be executed based on circuit breaker state"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                self.logger.info("Circuit breaker moved to HALF_OPEN state")
                return True
            return False
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """Record a successful operation"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.logger.info("Circuit breaker moved to CLOSED state")
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning("Circuit breaker returned to OPEN state after failure in HALF_OPEN")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if not self.last_failure_time:
            return True
        
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout


class ReportRetryService:
    """Service for handling retries in report operations"""
    
    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    ):
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = CircuitBreaker(circuit_breaker_config or CircuitBreakerConfig())
        self.logger = logging.getLogger(__name__)
    
    def with_retry(
        self,
        operation: Callable,
        *args,
        retry_config: Optional[RetryConfig] = None,
        **kwargs
    ) -> RetryResult:
        """
        Execute an operation with retry logic
        
        Args:
            operation: The function to execute
            *args: Arguments for the operation
            retry_config: Override retry configuration
            **kwargs: Keyword arguments for the operation
            
        Returns:
            RetryResult with operation outcome and retry information
        """
        config = retry_config or self.retry_config
        start_time = time.time()
        attempts = []
        
        for attempt_num in range(1, config.max_attempts + 1):
            # Check circuit breaker
            if not self.circuit_breaker.can_execute():
                self.logger.warning("Circuit breaker is OPEN, rejecting request")
                return RetryResult(
                    success=False,
                    exception=ReportGenerationException(
                        message="Service temporarily unavailable due to repeated failures",
                        error_code=ReportErrorCode.REPORT_GENERATION_FAILED,
                        details={"circuit_breaker_state": self.circuit_breaker.state.value}
                    ),
                    attempts=attempts,
                    total_duration=time.time() - start_time,
                    circuit_breaker_triggered=True
                )
            
            attempt_start = time.time()
            attempt = RetryAttempt(
                attempt_number=attempt_num,
                delay=0.0 if attempt_num == 1 else self._calculate_delay(attempt_num - 1, config)
            )
            
            try:
                # Add delay for retry attempts
                if attempt.delay > 0:
                    self.logger.info(f"Retrying operation in {attempt.delay:.2f} seconds (attempt {attempt_num})")
                    time.sleep(attempt.delay)
                
                # Execute the operation
                result = operation(*args, **kwargs)
                
                # Record success
                attempt.duration = time.time() - attempt_start
                attempts.append(attempt)
                self.circuit_breaker.record_success()
                
                self.logger.info(f"Operation succeeded on attempt {attempt_num}")
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_duration=time.time() - start_time
                )
                
            except Exception as e:
                attempt.duration = time.time() - attempt_start
                attempt.exception = e
                attempts.append(attempt)
                
                # Check if exception is retryable
                if not self._is_retryable_exception(e, config):
                    self.logger.error(f"Non-retryable exception on attempt {attempt_num}: {e}")
                    self.circuit_breaker.record_failure()
                    return RetryResult(
                        success=False,
                        exception=e,
                        attempts=attempts,
                        total_duration=time.time() - start_time
                    )
                
                # Log the failure
                self.logger.warning(f"Operation failed on attempt {attempt_num}: {e}")
                
                # If this was the last attempt, record failure and return
                if attempt_num == config.max_attempts:
                    self.circuit_breaker.record_failure()
                    return RetryResult(
                        success=False,
                        exception=e,
                        attempts=attempts,
                        total_duration=time.time() - start_time
                    )
        
        # This should never be reached, but just in case
        return RetryResult(
            success=False,
            exception=Exception("Unexpected end of retry loop"),
            attempts=attempts,
            total_duration=time.time() - start_time
        )
    
    async def with_retry_async(
        self,
        operation: Callable,
        *args,
        retry_config: Optional[RetryConfig] = None,
        **kwargs
    ) -> RetryResult:
        """
        Execute an async operation with retry logic
        
        Args:
            operation: The async function to execute
            *args: Arguments for the operation
            retry_config: Override retry configuration
            **kwargs: Keyword arguments for the operation
            
        Returns:
            RetryResult with operation outcome and retry information
        """
        config = retry_config or self.retry_config
        start_time = time.time()
        attempts = []
        
        for attempt_num in range(1, config.max_attempts + 1):
            # Check circuit breaker
            if not self.circuit_breaker.can_execute():
                self.logger.warning("Circuit breaker is OPEN, rejecting request")
                return RetryResult(
                    success=False,
                    exception=ReportGenerationException(
                        message="Service temporarily unavailable due to repeated failures",
                        error_code=ReportErrorCode.REPORT_GENERATION_FAILED,
                        details={"circuit_breaker_state": self.circuit_breaker.state.value}
                    ),
                    attempts=attempts,
                    total_duration=time.time() - start_time,
                    circuit_breaker_triggered=True
                )
            
            attempt_start = time.time()
            attempt = RetryAttempt(
                attempt_number=attempt_num,
                delay=0.0 if attempt_num == 1 else self._calculate_delay(attempt_num - 1, config)
            )
            
            try:
                # Add delay for retry attempts
                if attempt.delay > 0:
                    self.logger.info(f"Retrying operation in {attempt.delay:.2f} seconds (attempt {attempt_num})")
                    await asyncio.sleep(attempt.delay)
                
                # Execute the operation
                result = await operation(*args, **kwargs)
                
                # Record success
                attempt.duration = time.time() - attempt_start
                attempts.append(attempt)
                self.circuit_breaker.record_success()
                
                self.logger.info(f"Operation succeeded on attempt {attempt_num}")
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_duration=time.time() - start_time
                )
                
            except Exception as e:
                attempt.duration = time.time() - attempt_start
                attempt.exception = e
                attempts.append(attempt)
                
                # Check if exception is retryable
                if not self._is_retryable_exception(e, config):
                    self.logger.error(f"Non-retryable exception on attempt {attempt_num}: {e}")
                    self.circuit_breaker.record_failure()
                    return RetryResult(
                        success=False,
                        exception=e,
                        attempts=attempts,
                        total_duration=time.time() - start_time
                    )
                
                # Log the failure
                self.logger.warning(f"Operation failed on attempt {attempt_num}: {e}")
                
                # If this was the last attempt, record failure and return
                if attempt_num == config.max_attempts:
                    self.circuit_breaker.record_failure()
                    return RetryResult(
                        success=False,
                        exception=e,
                        attempts=attempts,
                        total_duration=time.time() - start_time
                    )
        
        # This should never be reached, but just in case
        return RetryResult(
            success=False,
            exception=Exception("Unexpected end of retry loop"),
            attempts=attempts,
            total_duration=time.time() - start_time
        )
    
    def _calculate_delay(self, attempt_num: int, config: RetryConfig) -> float:
        """Calculate delay for retry attempt based on strategy"""
        if config.strategy == RetryStrategy.IMMEDIATE:
            delay = 0.0
        elif config.strategy == RetryStrategy.FIXED_DELAY:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * attempt_num
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.backoff_multiplier ** (attempt_num - 1))
        else:
            delay = config.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, config.max_delay)
        
        # Add jitter if enabled
        if config.jitter:
            import random
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure delay is not negative
        
        return delay
    
    def _is_retryable_exception(self, exception: Exception, config: RetryConfig) -> bool:
        """Check if an exception should trigger a retry"""
        # Check if exception type is retryable
        if not any(isinstance(exception, exc_type) for exc_type in config.retryable_exceptions):
            return False
        
        # For BaseReportException, check if error code is retryable
        if isinstance(exception, BaseReportException):
            if exception.error_code in config.non_retryable_error_codes:
                return False
            # Use the retryable flag from the exception
            return exception.retryable
        
        return True
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        return {
            "state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "success_count": self.circuit_breaker.success_count,
            "last_failure_time": self.circuit_breaker.last_failure_time.isoformat() if self.circuit_breaker.last_failure_time else None,
            "can_execute": self.circuit_breaker.can_execute()
        }
    
    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker to closed state"""
        self.circuit_breaker.state = CircuitBreakerState.CLOSED
        self.circuit_breaker.failure_count = 0
        self.circuit_breaker.success_count = 0
        self.circuit_breaker.last_failure_time = None
        self.logger.info("Circuit breaker manually reset to CLOSED state")


def retry_on_failure(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_exceptions: Optional[List[type]] = None
):
    """
    Decorator for adding retry logic to functions
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        strategy: Retry strategy to use
        retryable_exceptions: List of exception types that should trigger retries
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                strategy=strategy,
                retryable_exceptions=retryable_exceptions or [Exception]
            )
            
            retry_service = ReportRetryService(retry_config=config)
            result = retry_service.with_retry(func, *args, **kwargs)
            
            if result.success:
                return result.result
            else:
                raise result.exception
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                strategy=strategy,
                retryable_exceptions=retryable_exceptions or [Exception]
            )
            
            retry_service = ReportRetryService(retry_config=config)
            result = await retry_service.with_retry_async(func, *args, **kwargs)
            
            if result.success:
                return result.result
            else:
                raise result.exception
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator