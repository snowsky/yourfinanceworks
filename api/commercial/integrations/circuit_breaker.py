"""
Circuit Breaker Pattern Implementation for Cloud Provider Resilience

This module provides a circuit breaker implementation to handle provider failures
gracefully, preventing cascading failures and allowing recovery time.
"""

import time
import threading
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"         # Failing, requests blocked
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    def __init__(self, provider_name: str, failure_count: int, last_failure_time: float):
        self.provider_name = provider_name
        self.failure_count = failure_count
        self.last_failure_time = last_failure_time
        super().__init__(f"Circuit breaker is OPEN for {provider_name}. "
                        f"Failures: {failure_count}, Last failure: {last_failure_time}")


class CircuitBreaker:
    """
    Circuit breaker implementation for provider resilience.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing state, requests fail immediately with exception
    - HALF_OPEN: Testing recovery, limited requests allowed

    Transitions:
    CLOSED -> OPEN: When failure threshold reached
    OPEN -> HALF_OPEN: After timeout period
    HALF_OPEN -> CLOSED: When test request succeeds
    HALF_OPEN -> OPEN: When test request fails
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,  # seconds
        expected_exception: tuple = (Exception,),
        success_threshold: int = 3,
        name: str = "CircuitBreaker"
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds to wait before trying recovery
            expected_exception: Tuple of exception types to monitor
            success_threshold: Number of successes needed in HALF_OPEN to close
            name: Identifier for this circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.name = name

        # State management
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

        # Thread safety
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return False
        return time.time() - self._last_failure_time >= self.recovery_timeout

    def _reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        logger.info(f"Circuit breaker {self.name} resetting to CLOSED state")
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

    def _record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info(f"Circuit breaker {self.name} transitioning from HALF_OPEN to CLOSED")
                    self._reset()
            elif self._state == CircuitBreakerState.CLOSED:
                # Normal success, just log if we had previous failures
                if self._failure_count > 0:
                    logger.info(f"Circuit breaker {self.name} success after {self._failure_count} failures")

    def _record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.warning(f"Circuit breaker {self.name} test request failed, returning to OPEN")
                self._state = CircuitBreakerState.OPEN
                self._success_count = 0
            elif (self._state == CircuitBreakerState.CLOSED and
                  self._failure_count >= self.failure_threshold):
                logger.warning(f"Circuit breaker {self.name} failure threshold ({self.failure_threshold}) "
                             f"reached, transitioning to OPEN")
                self._state = CircuitBreakerState.OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call the function through the circuit breaker.

        Args:
            func: The function to call
            *args, **kwargs: Arguments to pass to the function

        Returns:
            Result of the function call

        Raises:
            CircuitBreakerOpenException: If circuit is OPEN
            Exception: Any exception raised by the function
        """
        if self._state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker {self.name} attempting recovery")
                self._state = CircuitBreakerState.HALF_OPEN
                self._success_count = 0
            else:
                raise CircuitBreakerOpenException(
                    self.name, self._failure_count, self._last_failure_time
                )

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e
        except Exception as e:
            # For unexpected exceptions, we still record as failure but re-raise as-is
            self._record_failure()
            raise e

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call an async function through the circuit breaker.

        Args:
            func: The async function to call
            *args, **kwargs: Arguments to pass to the function

        Returns:
            Result of the function call

        Raises:
            CircuitBreakerOpenException: If circuit is OPEN
            Exception: Any exception raised by the function
        """
        if self._state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker {self.name} attempting recovery")
                self._state = CircuitBreakerState.HALF_OPEN
                self._success_count = 0
            else:
                raise CircuitBreakerOpenException(
                    self.name, self._failure_count, self._last_failure_time
                )

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e
        except Exception as e:
            # For unexpected exceptions, we still record as failure but re-raise as-is
            self._record_failure()
            raise e

    def __call__(self, func: Callable) -> Callable:
        """
        Decorator to wrap a function with circuit breaker protection.

        Args:
            func: Function to wrap

        Returns:
            Wrapped function
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper

    def get_health_status(self) -> dict:
        """
        Get health status information.

        Returns:
            Dictionary with circuit breaker status
        """
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "time_until_retry": max(0, self.recovery_timeout - (time.time() - (self._last_failure_time or 0)))
            if self._state == CircuitBreakerState.OPEN else 0
        }


class CloudProviderCircuitBreaker:
    """
    Specialized circuit breaker for cloud provider operations.

    Includes provider-specific configuration and monitoring.
    """

    def __init__(
        self,
        provider_name: str,
        operation_name: str = "operation",
        failure_threshold: int = 3,  # Lower threshold for cloud providers
        recovery_timeout: float = 30.0,  # Shorter recovery time
        success_threshold: int = 2
    ):
        self.provider_name = provider_name
        self.operation_name = operation_name

        # AWS and Azure specific exception types
        expected_exceptions = (
            ConnectionError,
            TimeoutError,
            OSError,  # Network errors
            # AWS specific
            Exception,  # We'll catch all for now and filter in wrapper
        )

        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exceptions,
            success_threshold=success_threshold,
            name=f"{provider_name}_{operation_name}"
        )

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        return self.circuit_breaker.call(func, *args, **kwargs)

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function through circuit breaker."""
        return await self.circuit_breaker.call_async(func, *args, **kwargs)

    def get_health_status(self) -> dict:
        """Get health status."""
        status = self.circuit_breaker.get_health_status()
        status.update({
            "provider": self.provider_name,
            "operation": self.operation_name
        })
        return status

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        logger.info(f"Manually resetting circuit breaker for {self.provider_name}_{self.operation_name}")
        self.circuit_breaker._reset()


def circuit_breaker_for_provider(
    provider_name: str,
    operation_name: str = "operation",
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0
) -> CloudProviderCircuitBreaker:
    """
    Factory function to create a circuit breaker for cloud providers.

    Args:
        provider_name: Name of the cloud provider (aws_kms, azure_kv, etc.)
        operation_name: Name of the operation (generate_key, decrypt, etc.)
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time to wait before recovery attempt

    Returns:
        Configured circuit breaker instance
    """
    return CloudProviderCircuitBreaker(
        provider_name=provider_name,
        operation_name=operation_name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout
    )
