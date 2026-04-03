"""
Storage Monitoring Service package.

Split from the original monolithic storage_monitoring_service.py (2,176 lines) into focused modules:
  - _shared.py  — Imports, enums, and dataclasses (AlertSeverity, MonitoringMetric,
                  StorageAlert, AlertingConfig, StorageReport, ProviderHealthMetrics,
                  StorageUsageMetrics, PerformanceMetrics)
  - health.py   — StorageHealthMixin: health checks and provider success metrics
  - metrics.py  — StorageMetricsMixin: usage and performance metrics collection
  - alerts.py   — StorageAlertsMixin: alert generation, routing, notifications
  - reports.py  — StorageReportsMixin: report generation and export
"""

import logging
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from .health import StorageHealthMixin
from .metrics import StorageMetricsMixin
from .alerts import StorageAlertsMixin
from .reports import StorageReportsMixin

# Re-export shared types for backward compatibility
from ._shared import (  # noqa: F401
    AlertSeverity,
    MonitoringMetric,
    StorageAlert,
    AlertingConfig,
    StorageReport,
    ProviderHealthMetrics,
    StorageUsageMetrics,
    PerformanceMetrics,
)

from core.interfaces.storage_provider import StorageProvider

logger = logging.getLogger(__name__)


class StorageMonitoringService(
    StorageHealthMixin,
    StorageMetricsMixin,
    StorageAlertsMixin,
    StorageReportsMixin,
):
    """
    Comprehensive storage monitoring service with health checking,
    usage tracking, performance monitoring, and alerting capabilities.
    """

    def __init__(self, db: Session, config: Optional[Any] = None):
        """
        Initialize the storage monitoring service.

        Args:
            db: Database session for accessing logs and configurations
            config: Cloud storage configuration (uses default if None)
        """
        self.db = db

        # Initialize commercial components conditionally
        try:
            from commercial.cloud_storage.config import CloudStorageConfig
            from commercial.cloud_storage.providers.factory import StorageProviderFactory
            from commercial.cloud_storage.providers.circuit_breaker import storage_circuit_breaker_manager

            self.config = config or CloudStorageConfig()
            self.provider_factory = StorageProviderFactory(self.config)
            self.circuit_breaker_manager = storage_circuit_breaker_manager
            self._commercial_available = True
        except ImportError:
            logger.info("Commercial storage components not found, monitoring service limited")
            self.config = None
            self.provider_factory = None
            self.circuit_breaker_manager = None
            self._commercial_available = False

        # Health check cache and metrics
        self._health_cache: Dict[StorageProvider, ProviderHealthMetrics] = {}
        self._health_check_interval = 300  # 5 minutes
        self._last_health_check = {}

        # Performance metrics cache
        self._performance_cache: Dict[str, PerformanceMetrics] = {}
        self._performance_cache_ttl = 600  # 10 minutes

        # Usage metrics cache
        self._usage_cache: Dict[str, StorageUsageMetrics] = {}
        self._usage_cache_ttl = 3600  # 1 hour

        # Alert management
        self._active_alerts: Dict[str, StorageAlert] = {}
        self._resolved_alerts: Dict[str, StorageAlert] = {}
        self._alert_thresholds = self._get_default_alert_thresholds()
        self._alerting_config = AlertingConfig()
        self._alert_callbacks: List[Callable[[StorageAlert], None]] = []

        # Metrics history for trend analysis
        self._metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Report generation
        self._generated_reports: Dict[str, StorageReport] = {}
        self._report_templates = self._get_default_report_templates()

        logger.info("Storage monitoring service initialized")

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring summary.

        Returns:
            Dictionary with overall monitoring status and metrics
        """
        # Get health status for all providers
        health_summary = {}
        healthy_providers = 0
        total_providers = 0

        for provider_type, metrics in self._health_cache.items():
            health_summary[provider_type.value] = {
                'healthy': metrics.is_healthy,
                'success_rate_24h': metrics.success_rate_24h,
                'response_time_ms': metrics.response_time_ms,
                'last_check': metrics.last_check.isoformat() if metrics.last_check else None
            }

            total_providers += 1
            if metrics.is_healthy:
                healthy_providers += 1

        # Get alert summary
        active_alerts = list(self._active_alerts.values())
        alert_summary = {
            'total': len(active_alerts),
            'critical': len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]),
            'error': len([a for a in active_alerts if a.severity == AlertSeverity.ERROR]),
            'warning': len([a for a in active_alerts if a.severity == AlertSeverity.WARNING]),
            'info': len([a for a in active_alerts if a.severity == AlertSeverity.INFO])
        }

        # Get circuit breaker status
        circuit_breaker_status = self.circuit_breaker_manager.get_all_status()

        return {
            'timestamp': datetime.now().isoformat(),
            'overall_health': {
                'healthy_providers': healthy_providers,
                'total_providers': total_providers,
                'health_percentage': (healthy_providers / total_providers * 100) if total_providers > 0 else 0
            },
            'provider_health': health_summary,
            'alerts': alert_summary,
            'circuit_breakers': circuit_breaker_status,
            'cache_status': {
                'health_cache_size': len(self._health_cache),
                'performance_cache_size': len(self._performance_cache),
                'usage_cache_size': len(self._usage_cache),
                'active_alerts': len(self._active_alerts)
            }
        }

    async def run_monitoring_cycle(self) -> Dict[str, Any]:
        """
        Run a complete monitoring cycle including health checks, metrics collection, and alerting.

        Returns:
            Dictionary with monitoring cycle results
        """
        logger.info("Starting storage monitoring cycle")
        start_time = time.time()

        results = {
            'cycle_start': datetime.now().isoformat(),
            'health_checks': {},
            'performance_metrics': [],
            'usage_metrics': {},
            'alerts_generated': 0,
            'errors': []
        }

        try:
            # Perform health checks on all providers
            health_results = await self.health_check_all_providers(force_check=True)
            results['health_checks'] = {
                provider.value: {
                    'healthy': metrics.is_healthy,
                    'response_time_ms': metrics.response_time_ms,
                    'success_rate_24h': metrics.success_rate_24h,
                    'error_count_24h': metrics.error_count_24h
                }
                for provider, metrics in health_results.items()
            }

            # Collect performance metrics
            performance_metrics = await self.get_performance_metrics(force_refresh=True)
            results['performance_metrics'] = [
                {
                    'provider': m.provider,
                    'operation_type': m.operation_type,
                    'avg_latency_ms': m.avg_latency_ms,
                    'success_rate': m.success_rate,
                    'error_rate': m.error_rate,
                    'sample_count': m.sample_count
                }
                for m in performance_metrics
            ]

            # Collect usage metrics
            usage_metrics = await self.get_storage_usage_metrics(force_refresh=True)
            results['usage_metrics'] = {
                tenant_id: {
                    'total_files': metrics.total_files,
                    'total_size_gb': metrics.total_size_bytes / (1024 ** 3),
                    'growth_rate_files_per_day': metrics.growth_rate_files_per_day,
                    'growth_rate_gb_per_day': metrics.growth_rate_bytes_per_day / (1024 ** 3)
                }
                for tenant_id, metrics in usage_metrics.items()
            }

            # Count alerts generated during this cycle
            initial_alert_count = len(self._active_alerts)

        except Exception as e:
            logger.error(f"Error during monitoring cycle: {e}")
            results['errors'].append(str(e))

        # Calculate cycle duration
        cycle_duration = time.time() - start_time
        results['cycle_duration_seconds'] = cycle_duration
        results['cycle_end'] = datetime.now().isoformat()

        # Count new alerts
        final_alert_count = len(self._active_alerts)
        results['alerts_generated'] = max(0, final_alert_count - initial_alert_count)

        logger.info(f"Storage monitoring cycle completed in {cycle_duration:.2f} seconds")

        return results

    async def cleanup_orphaned_files(
        self,
        tenant_id: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Clean up orphaned files (files without database records).

        Args:
            tenant_id: Tenant identifier
            dry_run: If True, only identify orphaned files without deleting

        Returns:
            Dictionary with cleanup results
        """
        try:
            # This is a placeholder implementation
            # In a real implementation, you would:
            # 1. List all files in storage for the tenant
            # 2. Check which files have corresponding database records
            # 3. Identify orphaned files
            # 4. Delete orphaned files if not dry_run

            logger.info(f"Cleanup orphaned files for tenant {tenant_id} (dry_run: {dry_run})")

            # For now, return a mock result
            return {
                'orphaned_files': 0,
                'files_cleaned': 0,
                'space_freed_bytes': 0,
                'errors': []
            }

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned files for tenant {tenant_id}: {e}")
            return {
                'orphaned_files': 0,
                'files_cleaned': 0,
                'space_freed_bytes': 0,
                'errors': [str(e)]
            }


__all__ = [
    "StorageMonitoringService",
    "AlertSeverity",
    "MonitoringMetric",
    "StorageAlert",
    "AlertingConfig",
    "StorageReport",
    "ProviderHealthMetrics",
    "StorageUsageMetrics",
    "PerformanceMetrics",
]
