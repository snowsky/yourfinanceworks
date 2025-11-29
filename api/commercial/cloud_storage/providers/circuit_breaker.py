"""
Cloud Storage Circuit Breaker Implementation

Specialized circuit breaker for cloud storage operations with automatic
fallback capabilities and storage-specific error handling.
"""

import logging
from typing import Callable, Any, Optional, Dict
from datetime import datetime, timedelta

from commercial.integrations.circuit_breaker import (
    CloudProviderCircuitBreaker, 
    CircuitBreakerOpenException,
    CircuitBreakerState
)

logger = logging.getLogger(__name__)


class CloudStorageCircuitBreaker(CloudProviderCircuitBreaker):
    """
    Specialized circuit breaker for cloud storage operations.
    
    Extends the base circuit breaker with storage-specific configuration
    and error handling patterns.
    """
    
    def __init__(
        self,
        provider_name: str,
        operation_name: str = "storage_operations",
        failure_threshold: int = 3,  # Lower threshold for storage operations
        recovery_timeout: float = 30.0,  # Shorter recovery time for storage
        success_threshold: int = 2
    ):
        """
        Initialize cloud storage circuit breaker.
        
        Args:
            provider_name: Name of the storage provider (aws_s3, azure_blob, etc.)
            operation_name: Name of the operation type
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds to wait before recovery attempt
            success_threshold: Number of successes needed to close circuit
        """
        super().__init__(
            provider_name=provider_name,
            operation_name=operation_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold
        )
        
        # Storage-specific metrics
        self._operation_metrics = {
            'upload_failures': 0,
            'download_failures': 0,
            'delete_failures': 0,
            'total_operations': 0,
            'last_success_time': None,
            'consecutive_failures': 0
        }
    
    def should_fallback_to_local(self) -> bool:
        """
        Determine if operations should fallback to local storage.
        
        Returns:
            True if circuit is open and should fallback to local storage
        """
        return self.circuit_breaker.state == CircuitBreakerState.OPEN
    
    def should_skip_provider(self) -> bool:
        """
        Determine if provider should be skipped entirely.
        
        Returns:
            True if provider should be skipped due to circuit breaker state
        """
        return self.circuit_breaker.state == CircuitBreakerState.OPEN
    
    async def call_with_fallback_detection(
        self,
        func: Callable,
        operation_type: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function through circuit breaker with operation-specific tracking.
        
        Args:
            func: Function to execute
            operation_type: Type of storage operation (upload, download, delete)
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Result of function execution
            
        Raises:
            CircuitBreakerOpenException: If circuit is open
            Exception: Any exception from the function
        """
        self._operation_metrics['total_operations'] += 1
        
        try:
            result = await self.call_async(func, *args, **kwargs)
            
            # Record success metrics
            self._operation_metrics['last_success_time'] = datetime.now()
            self._operation_metrics['consecutive_failures'] = 0
            
            logger.debug(f"Storage operation {operation_type} succeeded for {self.provider_name}")
            return result
            
        except CircuitBreakerOpenException:
            logger.warning(f"Circuit breaker is OPEN for {self.provider_name}, "
                         f"operation {operation_type} blocked")
            raise
            
        except Exception as e:
            # Record failure metrics
            self._operation_metrics['consecutive_failures'] += 1
            self._operation_metrics[f'{operation_type}_failures'] += 1
            
            logger.warning(f"Storage operation {operation_type} failed for {self.provider_name}: {e}")
            raise
    
    def get_storage_metrics(self) -> Dict[str, Any]:
        """
        Get storage-specific metrics and health information.
        
        Returns:
            Dictionary with storage metrics and circuit breaker status
        """
        base_status = self.get_health_status()
        
        # Calculate failure rates
        total_ops = self._operation_metrics['total_operations']
        upload_failures = self._operation_metrics['upload_failures']
        download_failures = self._operation_metrics['download_failures']
        delete_failures = self._operation_metrics['delete_failures']
        
        failure_rate = 0.0
        if total_ops > 0:
            total_failures = upload_failures + download_failures + delete_failures
            failure_rate = (total_failures / total_ops) * 100
        
        # Time since last success
        time_since_success = None
        if self._operation_metrics['last_success_time']:
            time_since_success = (
                datetime.now() - self._operation_metrics['last_success_time']
            ).total_seconds()
        
        base_status.update({
            'storage_metrics': {
                'total_operations': total_ops,
                'upload_failures': upload_failures,
                'download_failures': download_failures,
                'delete_failures': delete_failures,
                'failure_rate_percent': round(failure_rate, 2),
                'consecutive_failures': self._operation_metrics['consecutive_failures'],
                'last_success_time': self._operation_metrics['last_success_time'],
                'time_since_success_seconds': time_since_success
            },
            'fallback_recommended': self.should_fallback_to_local(),
            'skip_provider': self.should_skip_provider()
        })
        
        return base_status
    
    def reset_metrics(self) -> None:
        """Reset all storage metrics."""
        logger.info(f"Resetting storage metrics for {self.provider_name}")
        
        self._operation_metrics = {
            'upload_failures': 0,
            'download_failures': 0,
            'delete_failures': 0,
            'total_operations': 0,
            'last_success_time': None,
            'consecutive_failures': 0
        }
        
        # Also reset the underlying circuit breaker
        self.reset()
    
    def is_degraded(self) -> bool:
        """
        Check if provider is in a degraded state.
        
        A provider is considered degraded if it has recent failures
        but the circuit breaker is not yet open.
        
        Returns:
            True if provider is degraded
        """
        if self.circuit_breaker.state == CircuitBreakerState.OPEN:
            return True
        
        # Check for high failure rate in recent operations
        consecutive_failures = self._operation_metrics['consecutive_failures']
        if consecutive_failures >= (self.circuit_breaker.failure_threshold // 2):
            return True
        
        # Check time since last success
        if self._operation_metrics['last_success_time']:
            time_since_success = (
                datetime.now() - self._operation_metrics['last_success_time']
            ).total_seconds()
            
            # Consider degraded if no success in last 5 minutes
            if time_since_success > 300:
                return True
        
        return False
    
    def get_health_score(self) -> float:
        """
        Calculate a health score for the provider (0.0 to 1.0).
        
        Returns:
            Health score where 1.0 is perfect health, 0.0 is completely unhealthy
        """
        if self.circuit_breaker.state == CircuitBreakerState.OPEN:
            return 0.0
        
        if self.circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
            return 0.5
        
        # Calculate based on recent failure rate
        total_ops = self._operation_metrics['total_operations']
        if total_ops == 0:
            return 1.0  # No operations yet, assume healthy
        
        consecutive_failures = self._operation_metrics['consecutive_failures']
        
        # Penalize consecutive failures more heavily
        if consecutive_failures == 0:
            return 1.0
        elif consecutive_failures < self.circuit_breaker.failure_threshold:
            # Linear degradation based on consecutive failures
            penalty = consecutive_failures / self.circuit_breaker.failure_threshold
            return max(0.1, 1.0 - penalty)
        else:
            return 0.1  # Very low health but not completely failed
    
    def should_prefer_fallback(self) -> bool:
        """
        Determine if fallback providers should be preferred over this provider.
        
        Returns:
            True if fallback should be preferred
        """
        # Prefer fallback if circuit is open or provider is degraded
        return (
            self.circuit_breaker.state == CircuitBreakerState.OPEN or
            self.is_degraded() or
            self.get_health_score() < 0.7
        )


class StorageCircuitBreakerManager:
    """
    Manager for multiple storage provider circuit breakers.
    
    Provides centralized management and monitoring of circuit breakers
    across all storage providers.
    """
    
    def __init__(self):
        """Initialize the circuit breaker manager."""
        self._circuit_breakers: Dict[str, CloudStorageCircuitBreaker] = {}
        logger.info("Storage circuit breaker manager initialized")
    
    def get_circuit_breaker(
        self,
        provider_name: str,
        operation_name: str = "storage_operations"
    ) -> CloudStorageCircuitBreaker:
        """
        Get or create a circuit breaker for a provider.
        
        Args:
            provider_name: Name of the storage provider
            operation_name: Name of the operation type
            
        Returns:
            Circuit breaker instance for the provider
        """
        key = f"{provider_name}_{operation_name}"
        
        if key not in self._circuit_breakers:
            self._circuit_breakers[key] = CloudStorageCircuitBreaker(
                provider_name=provider_name,
                operation_name=operation_name
            )
            logger.info(f"Created circuit breaker for {key}")
        
        return self._circuit_breakers[key]
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all circuit breakers.
        
        Returns:
            Dictionary mapping provider names to their status
        """
        status = {}
        
        for key, circuit_breaker in self._circuit_breakers.items():
            status[key] = circuit_breaker.get_storage_metrics()
        
        return status
    
    def get_healthy_providers(self) -> list[str]:
        """
        Get list of healthy provider names.
        
        Returns:
            List of provider names that are currently healthy
        """
        healthy_providers = []
        
        for key, circuit_breaker in self._circuit_breakers.items():
            if not circuit_breaker.should_skip_provider():
                provider_name = key.split('_')[0]  # Extract provider name from key
                if provider_name not in healthy_providers:
                    healthy_providers.append(provider_name)
        
        return healthy_providers
    
    def get_degraded_providers(self) -> list[str]:
        """
        Get list of degraded provider names.
        
        Returns:
            List of provider names that are degraded but not completely failed
        """
        degraded_providers = []
        
        for key, circuit_breaker in self._circuit_breakers.items():
            if circuit_breaker.is_degraded() and not circuit_breaker.should_skip_provider():
                provider_name = key.split('_')[0]  # Extract provider name from key
                if provider_name not in degraded_providers:
                    degraded_providers.append(provider_name)
        
        return degraded_providers
    
    def reset_all_circuit_breakers(self) -> None:
        """Reset all circuit breakers."""
        logger.info("Resetting all storage circuit breakers")
        
        for circuit_breaker in self._circuit_breakers.values():
            circuit_breaker.reset_metrics()
    
    def reset_provider_circuit_breaker(self, provider_name: str) -> bool:
        """
        Reset circuit breaker for a specific provider.
        
        Args:
            provider_name: Name of the provider to reset
            
        Returns:
            True if circuit breaker was found and reset
        """
        reset_count = 0
        
        for key, circuit_breaker in self._circuit_breakers.items():
            if key.startswith(provider_name):
                circuit_breaker.reset_metrics()
                reset_count += 1
        
        if reset_count > 0:
            logger.info(f"Reset {reset_count} circuit breakers for provider {provider_name}")
            return True
        
        logger.warning(f"No circuit breakers found for provider {provider_name}")
        return False


# Global circuit breaker manager instance
storage_circuit_breaker_manager = StorageCircuitBreakerManager()