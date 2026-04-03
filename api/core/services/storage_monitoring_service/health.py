"""
Storage health check mixin for StorageMonitoringService.
"""

import logging
import time
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from collections import defaultdict

from core.interfaces.storage_provider import StorageProvider

from ._shared import (
    AlertSeverity,
    MonitoringMetric,
    ProviderHealthMetrics,
    StorageOperationLog,
    and_,
)

logger = logging.getLogger(__name__)


class StorageHealthMixin:
    """Mixin providing health check methods for StorageMonitoringService."""

    async def perform_health_check(
        self,
        provider_type: StorageProvider,
        force_check: bool = False
    ) -> ProviderHealthMetrics:
        """
        Perform health check on a specific storage provider.

        Args:
            provider_type: The storage provider to check
            force_check: Force check even if recently checked

        Returns:
            ProviderHealthMetrics with current health status
        """
        # Check if we have a recent health check result
        if not force_check and provider_type in self._last_health_check:
            last_check_time = self._last_health_check[provider_type]
            if (datetime.now() - last_check_time).seconds < self._health_check_interval:
                return self._health_cache.get(provider_type)

        logger.info(f"Performing health check for provider {provider_type.value}")

        if not self._commercial_available or not self.provider_factory:
            return ProviderHealthMetrics(
                provider=provider_type,
                is_healthy=False,
                response_time_ms=None,
                success_rate_24h=0.0,
                error_count_24h=0,
                last_error="Commercial storage provider not available",
                circuit_breaker_state="disabled",
                uptime_percentage=0.0,
                last_check=datetime.now()
            )

        # Get provider instance
        provider = self.provider_factory.get_provider(provider_type)
        if not provider:
            # Provider not configured
            metrics = ProviderHealthMetrics(
                provider=provider_type,
                is_healthy=False,
                response_time_ms=None,
                success_rate_24h=0.0,
                error_count_24h=0,
                last_error="Provider not configured",
                circuit_breaker_state="disabled",
                uptime_percentage=0.0,
                last_check=datetime.now()
            )
            self._health_cache[provider_type] = metrics
            return metrics

        # Perform actual health check
        start_time = time.time()
        try:
            health_result = await provider.health_check()
            response_time_ms = int((time.time() - start_time) * 1000)

            # Get circuit breaker status
            circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(provider_type.value)
            circuit_state = circuit_breaker.get_state().value if circuit_breaker else "unknown"

            # Calculate success rate and error metrics from recent operations
            success_metrics = await self._calculate_provider_success_metrics(
                provider_type.value, hours=24
            )

            # Update consecutive counters
            if provider_type in self._health_cache:
                prev_metrics = self._health_cache[provider_type]
                if health_result.healthy:
                    consecutive_successes = prev_metrics.consecutive_successes + 1
                    consecutive_failures = 0
                else:
                    consecutive_successes = 0
                    consecutive_failures = prev_metrics.consecutive_failures + 1
            else:
                consecutive_successes = 1 if health_result.healthy else 0
                consecutive_failures = 0 if health_result.healthy else 1

            # Create health metrics
            metrics = ProviderHealthMetrics(
                provider=provider_type,
                is_healthy=health_result.healthy,
                response_time_ms=response_time_ms,
                success_rate_24h=success_metrics['success_rate'],
                error_count_24h=success_metrics['error_count'],
                last_error=health_result.error_message,
                circuit_breaker_state=circuit_state,
                uptime_percentage=success_metrics['uptime_percentage'],
                last_check=datetime.now(),
                consecutive_failures=consecutive_failures,
                consecutive_successes=consecutive_successes
            )

            # Cache the results
            self._health_cache[provider_type] = metrics
            self._last_health_check[provider_type] = datetime.now()

            # Check for alerts
            await self._check_health_alerts(metrics)

            logger.info(f"Health check completed for {provider_type.value}: healthy={health_result.healthy}, response_time={response_time_ms}ms")

            return metrics

        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Health check failed for {provider_type.value}: {e}")

            # Update consecutive failure counter
            if provider_type in self._health_cache:
                prev_metrics = self._health_cache[provider_type]
                consecutive_failures = prev_metrics.consecutive_failures + 1
            else:
                consecutive_failures = 1

            # Create failed health metrics
            metrics = ProviderHealthMetrics(
                provider=provider_type,
                is_healthy=False,
                response_time_ms=response_time_ms,
                success_rate_24h=0.0,
                error_count_24h=1,
                last_error=str(e),
                circuit_breaker_state="error",
                uptime_percentage=0.0,
                last_check=datetime.now(),
                consecutive_failures=consecutive_failures,
                consecutive_successes=0
            )

            self._health_cache[provider_type] = metrics
            self._last_health_check[provider_type] = datetime.now()

            # Generate critical alert for health check failure
            await self._generate_alert(
                AlertSeverity.CRITICAL,
                MonitoringMetric.HEALTH_STATUS,
                provider_type.value,
                None,
                f"Health check failed for provider {provider_type.value}: {str(e)}",
                {'error': str(e), 'response_time_ms': response_time_ms}
            )

            return metrics

    async def health_check_all_providers(self, force_check: bool = False) -> Dict[StorageProvider, ProviderHealthMetrics]:
        """
        Perform health check on all configured storage providers.

        Args:
            force_check: Force check even if recently checked

        Returns:
            Dictionary mapping provider types to health metrics
        """
        logger.info("Performing health check on all storage providers")

        results = {}

        if not self._commercial_available or not self.provider_factory:
            logger.info("Commercial storage not available, skipping health checks")
            return results

        # Get all configured providers
        configured_providers = self.provider_factory.get_configured_providers()

        # Perform health checks concurrently
        tasks = []
        for provider_type in configured_providers:
            task = self.perform_health_check(provider_type, force_check)
            tasks.append((provider_type, task))

        # Wait for all health checks to complete
        for provider_type, task in tasks:
            try:
                metrics = await task
                results[provider_type] = metrics
            except Exception as e:
                logger.error(f"Failed to get health check for {provider_type.value}: {e}")
                # Create error metrics
                results[provider_type] = ProviderHealthMetrics(
                    provider=provider_type,
                    is_healthy=False,
                    response_time_ms=None,
                    success_rate_24h=0.0,
                    error_count_24h=1,
                    last_error=str(e),
                    circuit_breaker_state="error",
                    uptime_percentage=0.0,
                    last_check=datetime.now()
                )

        return results

    async def _calculate_provider_success_metrics(
        self,
        provider: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Calculate success metrics for a provider over a time period.

        Args:
            provider: Provider name
            hours: Number of hours to analyze

        Returns:
            Dictionary with success rate, error count, and uptime percentage
        """
        start_time = datetime.now() - timedelta(hours=hours)

        # Query operation logs for the provider
        logs = self.db.query(StorageOperationLog).filter(
            and_(
                StorageOperationLog.provider == provider,
                StorageOperationLog.created_at >= start_time
            )
        ).all()

        if not logs:
            return {
                'success_rate': 1.0,
                'error_count': 0,
                'uptime_percentage': 100.0,
                'total_operations': 0
            }

        total_operations = len(logs)
        successful_operations = sum(1 for log in logs if log.success)
        error_count = total_operations - successful_operations

        success_rate = successful_operations / total_operations if total_operations > 0 else 1.0

        # Calculate uptime percentage based on operation success over time
        # Group operations by hour and check if each hour had successful operations
        hourly_success = defaultdict(bool)
        for log in logs:
            hour_key = log.created_at.replace(minute=0, second=0, microsecond=0)
            if log.success:
                hourly_success[hour_key] = True

        # Calculate uptime percentage
        total_hours = hours
        successful_hours = len([h for h, success in hourly_success.items() if success])
        uptime_percentage = (successful_hours / total_hours) * 100 if total_hours > 0 else 100.0

        return {
            'success_rate': success_rate,
            'error_count': error_count,
            'uptime_percentage': uptime_percentage,
            'total_operations': total_operations
        }

    async def check_all_providers_health(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health status of all configured storage providers.

        Returns:
            Dictionary mapping provider names to health status
        """
        try:
            health_results = await self.health_check_all_providers()

            formatted_results = {}
            for provider_type, metrics in health_results.items():
                formatted_results[provider_type.value] = {
                    'status': 'healthy' if metrics.is_healthy else 'unhealthy',
                    'response_time_ms': metrics.response_time_ms,
                    'error_message': metrics.error_message,
                    'timestamp': metrics.last_check.isoformat() if metrics.last_check else None
                }

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to check all providers health: {e}")
            return {}
