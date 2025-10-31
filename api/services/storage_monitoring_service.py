"""
Storage Monitoring Service - Comprehensive monitoring and health checking for cloud storage.

This service provides health checking, usage monitoring, quota tracking, and performance
monitoring for all storage providers. It integrates with circuit breakers and provides
comprehensive metrics collection and analysis.
"""

import logging
import time
import json
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import statistics

# Optional email imports (for alerting)
try:
    import smtplib
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    MimeText = None
    MimeMultipart = None
    smtplib = None

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from services.cloud_storage.provider import (
    CloudStorageProvider, StorageProvider, HealthCheckResult
)
from services.cloud_storage.factory import StorageProviderFactory
from services.cloud_storage.circuit_breaker import (
    StorageCircuitBreakerManager, storage_circuit_breaker_manager
)
from models.models import Tenant
from models.models_per_tenant import StorageOperationLog, CloudStorageConfiguration
from settings.cloud_storage_config import CloudStorageConfig

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MonitoringMetric(Enum):
    """Types of monitoring metrics."""
    HEALTH_STATUS = "health_status"
    OPERATION_SUCCESS_RATE = "operation_success_rate"
    OPERATION_LATENCY = "operation_latency"
    STORAGE_USAGE = "storage_usage"
    ERROR_RATE = "error_rate"
    QUOTA_USAGE = "quota_usage"
    PROVIDER_AVAILABILITY = "provider_availability"


@dataclass
class StorageAlert:
    """Storage monitoring alert."""
    id: str
    severity: AlertSeverity
    metric: MonitoringMetric
    provider: Optional[str]
    tenant_id: Optional[str]
    message: str
    details: Dict[str, Any]
    threshold_value: Optional[float] = None
    current_value: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    is_resolved: bool = False
    notification_sent: bool = False
    escalation_level: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            'id': self.id,
            'severity': self.severity.value,
            'metric': self.metric.value,
            'provider': self.provider,
            'tenant_id': self.tenant_id,
            'message': self.message,
            'details': self.details,
            'threshold_value': self.threshold_value,
            'current_value': self.current_value,
            'created_at': self.created_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'is_resolved': self.is_resolved,
            'notification_sent': self.notification_sent,
            'escalation_level': self.escalation_level
        }


@dataclass
class AlertingConfig:
    """Configuration for alerting system."""
    email_enabled: bool = False
    email_smtp_server: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_from_address: Optional[str] = None
    email_to_addresses: List[str] = field(default_factory=list)
    
    webhook_enabled: bool = False
    webhook_url: Optional[str] = None
    webhook_headers: Dict[str, str] = field(default_factory=dict)
    
    escalation_enabled: bool = True
    escalation_interval_minutes: int = 60
    max_escalation_level: int = 3
    
    alert_cooldown_minutes: int = 30
    batch_alerts: bool = True
    batch_interval_minutes: int = 15


@dataclass
class StorageReport:
    """Storage monitoring report."""
    report_id: str
    report_type: str
    tenant_id: Optional[str]
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    data: Dict[str, Any]
    format: str = "json"  # json, html, csv
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            'report_id': self.report_id,
            'report_type': self.report_type,
            'tenant_id': self.tenant_id,
            'generated_at': self.generated_at.isoformat(),
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'data': self.data,
            'format': self.format
        }


@dataclass
class ProviderHealthMetrics:
    """Health metrics for a storage provider."""
    provider: StorageProvider
    is_healthy: bool
    response_time_ms: Optional[int]
    success_rate_24h: float
    error_count_24h: int
    last_error: Optional[str]
    circuit_breaker_state: str
    uptime_percentage: float
    last_check: datetime
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class StorageUsageMetrics:
    """Storage usage metrics for a tenant."""
    tenant_id: str
    total_files: int
    total_size_bytes: int
    files_by_provider: Dict[str, int]
    size_by_provider: Dict[str, int]
    files_by_type: Dict[str, int]
    size_by_type: Dict[str, int]
    growth_rate_files_per_day: float
    growth_rate_bytes_per_day: float
    last_updated: datetime


@dataclass
class PerformanceMetrics:
    """Performance metrics for storage operations."""
    provider: str
    operation_type: str
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    success_rate: float
    throughput_ops_per_minute: float
    error_rate: float
    sample_count: int
    time_period_hours: int


class StorageMonitoringService:
    """
    Comprehensive storage monitoring service with health checking,
    usage tracking, performance monitoring, and alerting capabilities.
    """
    
    def __init__(self, db: Session, config: Optional[CloudStorageConfig] = None):
        """
        Initialize the storage monitoring service.
        
        Args:
            db: Database session for accessing logs and configurations
            config: Cloud storage configuration (uses default if None)
        """
        self.db = db
        self.config = config or CloudStorageConfig()
        
        # Initialize provider factory and circuit breaker manager
        self.provider_factory = StorageProviderFactory(self.config)
        self.circuit_breaker_manager = storage_circuit_breaker_manager
        
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
    
    def _get_default_alert_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Get default alert thresholds for various metrics."""
        return {
            'success_rate': {
                'warning': 0.95,  # Below 95% success rate
                'error': 0.90,    # Below 90% success rate
                'critical': 0.80  # Below 80% success rate
            },
            'response_time_ms': {
                'warning': 5000,   # Above 5 seconds
                'error': 10000,    # Above 10 seconds
                'critical': 30000  # Above 30 seconds
            },
            'error_rate': {
                'warning': 0.05,   # Above 5% error rate
                'error': 0.10,     # Above 10% error rate
                'critical': 0.20   # Above 20% error rate
            },
            'storage_usage_gb': {
                'warning': 50,     # Above 50GB per tenant
                'error': 100,      # Above 100GB per tenant
                'critical': 200    # Above 200GB per tenant
            },
            'quota_usage_percentage': {
                'warning': 0.80,   # Above 80% quota usage
                'error': 0.90,     # Above 90% quota usage
                'critical': 0.95   # Above 95% quota usage
            }
        }
    
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
    
    async def get_storage_usage_metrics(
        self, 
        tenant_id: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, StorageUsageMetrics]:
        """
        Get storage usage metrics for tenants.
        
        Args:
            tenant_id: Specific tenant ID (None for all tenants)
            force_refresh: Force refresh of cached metrics
            
        Returns:
            Dictionary mapping tenant IDs to usage metrics
        """
        cache_key = tenant_id or "all_tenants"
        
        # Check cache first
        if not force_refresh and cache_key in self._usage_cache:
            cached_metrics = self._usage_cache[cache_key]
            if (datetime.now() - cached_metrics.last_updated).seconds < self._usage_cache_ttl:
                return {cached_metrics.tenant_id: cached_metrics} if tenant_id else self._usage_cache
        
        logger.info(f"Calculating storage usage metrics for tenant: {tenant_id or 'all'}")
        
        # Build query
        query = self.db.query(StorageOperationLog)
        if tenant_id:
            query = query.filter(StorageOperationLog.tenant_id == tenant_id)
        
        # Get successful upload operations (these represent stored files)
        upload_logs = query.filter(
            and_(
                StorageOperationLog.operation_type == "upload",
                StorageOperationLog.success == True
            )
        ).all()
        
        # Group by tenant
        tenant_metrics = {}
        tenant_data = defaultdict(list)
        
        for log in upload_logs:
            tenant_data[str(log.tenant_id)].append(log)
        
        for tid, logs in tenant_data.items():
            # Calculate metrics for this tenant
            total_files = len(logs)
            total_size_bytes = sum(log.file_size or 0 for log in logs)
            
            # Group by provider
            files_by_provider = defaultdict(int)
            size_by_provider = defaultdict(int)
            for log in logs:
                files_by_provider[log.provider] += 1
                size_by_provider[log.provider] += log.file_size or 0
            
            # Group by file type (based on content_type)
            files_by_type = defaultdict(int)
            size_by_type = defaultdict(int)
            for log in logs:
                content_type = log.content_type or "unknown"
                file_type = content_type.split('/')[0] if '/' in content_type else content_type
                files_by_type[file_type] += 1
                size_by_type[file_type] += log.file_size or 0
            
            # Calculate growth rate (files and bytes per day over last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_logs = [log for log in logs if log.created_at >= thirty_days_ago]
            
            growth_rate_files_per_day = len(recent_logs) / 30 if recent_logs else 0
            growth_rate_bytes_per_day = sum(log.file_size or 0 for log in recent_logs) / 30
            
            # Create usage metrics
            usage_metrics = StorageUsageMetrics(
                tenant_id=tid,
                total_files=total_files,
                total_size_bytes=total_size_bytes,
                files_by_provider=dict(files_by_provider),
                size_by_provider=dict(size_by_provider),
                files_by_type=dict(files_by_type),
                size_by_type=dict(size_by_type),
                growth_rate_files_per_day=growth_rate_files_per_day,
                growth_rate_bytes_per_day=growth_rate_bytes_per_day,
                last_updated=datetime.now()
            )
            
            tenant_metrics[tid] = usage_metrics
            self._usage_cache[tid] = usage_metrics
            
            # Check for usage alerts
            await self._check_usage_alerts(usage_metrics)
        
        # Cache all tenants result if requested
        if not tenant_id:
            self._usage_cache["all_tenants"] = tenant_metrics
        
        return tenant_metrics
    
    async def get_performance_metrics(
        self,
        provider: Optional[str] = None,
        operation_type: Optional[str] = None,
        hours: int = 24,
        force_refresh: bool = False
    ) -> List[PerformanceMetrics]:
        """
        Get performance metrics for storage operations.
        
        Args:
            provider: Filter by specific provider
            operation_type: Filter by operation type (upload, download, delete)
            hours: Number of hours to analyze
            force_refresh: Force refresh of cached metrics
            
        Returns:
            List of performance metrics
        """
        cache_key = f"{provider or 'all'}_{operation_type or 'all'}_{hours}h"
        
        # Check cache first
        if not force_refresh and cache_key in self._performance_cache:
            cached_time = getattr(self._performance_cache[cache_key], 'cached_at', datetime.min)
            if (datetime.now() - cached_time).seconds < self._performance_cache_ttl:
                return [self._performance_cache[cache_key]]
        
        logger.info(f"Calculating performance metrics for provider: {provider or 'all'}, operation: {operation_type or 'all'}")
        
        start_time = datetime.now() - timedelta(hours=hours)
        
        # Build query
        query = self.db.query(StorageOperationLog).filter(
            StorageOperationLog.created_at >= start_time
        )
        
        if provider:
            query = query.filter(StorageOperationLog.provider == provider)
        if operation_type:
            query = query.filter(StorageOperationLog.operation_type == operation_type)
        
        logs = query.all()
        
        if not logs:
            return []
        
        # Group by provider and operation type
        grouped_logs = defaultdict(list)
        for log in logs:
            key = (log.provider, log.operation_type)
            grouped_logs[key].append(log)
        
        performance_metrics = []
        
        for (prov, op_type), group_logs in grouped_logs.items():
            # Calculate latency metrics
            latencies = [log.duration_ms for log in group_logs if log.duration_ms is not None]
            
            if latencies:
                latencies.sort()
                avg_latency = sum(latencies) / len(latencies)
                p95_index = int(len(latencies) * 0.95)
                p99_index = int(len(latencies) * 0.99)
                p95_latency = latencies[p95_index] if p95_index < len(latencies) else latencies[-1]
                p99_latency = latencies[p99_index] if p99_index < len(latencies) else latencies[-1]
            else:
                avg_latency = p95_latency = p99_latency = 0.0
            
            # Calculate success rate and error rate
            total_ops = len(group_logs)
            successful_ops = sum(1 for log in group_logs if log.success)
            success_rate = successful_ops / total_ops if total_ops > 0 else 0.0
            error_rate = 1.0 - success_rate
            
            # Calculate throughput (operations per minute)
            time_span_minutes = hours * 60
            throughput_ops_per_minute = total_ops / time_span_minutes if time_span_minutes > 0 else 0.0
            
            metrics = PerformanceMetrics(
                provider=prov,
                operation_type=op_type,
                avg_latency_ms=avg_latency,
                p95_latency_ms=p95_latency,
                p99_latency_ms=p99_latency,
                success_rate=success_rate,
                throughput_ops_per_minute=throughput_ops_per_minute,
                error_rate=error_rate,
                sample_count=total_ops,
                time_period_hours=hours
            )
            
            # Add to cache
            metrics.cached_at = datetime.now()
            self._performance_cache[f"{prov}_{op_type}_{hours}h"] = metrics
            
            performance_metrics.append(metrics)
            
            # Check for performance alerts
            await self._check_performance_alerts(metrics)
        
        return performance_metrics
    
    async def _check_health_alerts(self, metrics: ProviderHealthMetrics) -> None:
        """Check health metrics against thresholds and generate alerts."""
        provider = metrics.provider.value
        
        # Check success rate
        if metrics.success_rate_24h < self._alert_thresholds['success_rate']['critical']:
            await self._generate_alert(
                AlertSeverity.CRITICAL,
                MonitoringMetric.OPERATION_SUCCESS_RATE,
                provider,
                None,
                f"Critical success rate for {provider}: {metrics.success_rate_24h:.2%}",
                {
                    'success_rate': metrics.success_rate_24h,
                    'threshold': self._alert_thresholds['success_rate']['critical'],
                    'error_count_24h': metrics.error_count_24h
                },
                self._alert_thresholds['success_rate']['critical'],
                metrics.success_rate_24h
            )
        elif metrics.success_rate_24h < self._alert_thresholds['success_rate']['error']:
            await self._generate_alert(
                AlertSeverity.ERROR,
                MonitoringMetric.OPERATION_SUCCESS_RATE,
                provider,
                None,
                f"Low success rate for {provider}: {metrics.success_rate_24h:.2%}",
                {
                    'success_rate': metrics.success_rate_24h,
                    'threshold': self._alert_thresholds['success_rate']['error'],
                    'error_count_24h': metrics.error_count_24h
                },
                self._alert_thresholds['success_rate']['error'],
                metrics.success_rate_24h
            )
        
        # Check response time
        if metrics.response_time_ms and metrics.response_time_ms > self._alert_thresholds['response_time_ms']['critical']:
            await self._generate_alert(
                AlertSeverity.CRITICAL,
                MonitoringMetric.OPERATION_LATENCY,
                provider,
                None,
                f"Critical response time for {provider}: {metrics.response_time_ms}ms",
                {
                    'response_time_ms': metrics.response_time_ms,
                    'threshold': self._alert_thresholds['response_time_ms']['critical']
                },
                self._alert_thresholds['response_time_ms']['critical'],
                metrics.response_time_ms
            )
        elif metrics.response_time_ms and metrics.response_time_ms > self._alert_thresholds['response_time_ms']['warning']:
            await self._generate_alert(
                AlertSeverity.WARNING,
                MonitoringMetric.OPERATION_LATENCY,
                provider,
                None,
                f"High response time for {provider}: {metrics.response_time_ms}ms",
                {
                    'response_time_ms': metrics.response_time_ms,
                    'threshold': self._alert_thresholds['response_time_ms']['warning']
                },
                self._alert_thresholds['response_time_ms']['warning'],
                metrics.response_time_ms
            )
        
        # Check consecutive failures
        if metrics.consecutive_failures >= 5:
            await self._generate_alert(
                AlertSeverity.CRITICAL,
                MonitoringMetric.PROVIDER_AVAILABILITY,
                provider,
                None,
                f"Provider {provider} has {metrics.consecutive_failures} consecutive failures",
                {
                    'consecutive_failures': metrics.consecutive_failures,
                    'last_error': metrics.last_error,
                    'circuit_breaker_state': metrics.circuit_breaker_state
                }
            )
    
    async def _check_usage_alerts(self, metrics: StorageUsageMetrics) -> None:
        """Check usage metrics against thresholds and generate alerts."""
        tenant_id = metrics.tenant_id
        
        # Convert bytes to GB for threshold comparison
        total_size_gb = metrics.total_size_bytes / (1024 ** 3)
        
        # Check storage usage
        if total_size_gb > self._alert_thresholds['storage_usage_gb']['critical']:
            await self._generate_alert(
                AlertSeverity.CRITICAL,
                MonitoringMetric.STORAGE_USAGE,
                None,
                tenant_id,
                f"Critical storage usage for tenant {tenant_id}: {total_size_gb:.2f}GB",
                {
                    'total_size_gb': total_size_gb,
                    'total_files': metrics.total_files,
                    'threshold': self._alert_thresholds['storage_usage_gb']['critical'],
                    'growth_rate_gb_per_day': metrics.growth_rate_bytes_per_day / (1024 ** 3)
                },
                self._alert_thresholds['storage_usage_gb']['critical'],
                total_size_gb
            )
        elif total_size_gb > self._alert_thresholds['storage_usage_gb']['warning']:
            await self._generate_alert(
                AlertSeverity.WARNING,
                MonitoringMetric.STORAGE_USAGE,
                None,
                tenant_id,
                f"High storage usage for tenant {tenant_id}: {total_size_gb:.2f}GB",
                {
                    'total_size_gb': total_size_gb,
                    'total_files': metrics.total_files,
                    'threshold': self._alert_thresholds['storage_usage_gb']['warning'],
                    'growth_rate_gb_per_day': metrics.growth_rate_bytes_per_day / (1024 ** 3)
                },
                self._alert_thresholds['storage_usage_gb']['warning'],
                total_size_gb
            )
    
    async def _check_performance_alerts(self, metrics: PerformanceMetrics) -> None:
        """Check performance metrics against thresholds and generate alerts."""
        # Check error rate
        if metrics.error_rate > self._alert_thresholds['error_rate']['critical']:
            await self._generate_alert(
                AlertSeverity.CRITICAL,
                MonitoringMetric.ERROR_RATE,
                metrics.provider,
                None,
                f"Critical error rate for {metrics.provider} {metrics.operation_type}: {metrics.error_rate:.2%}",
                {
                    'error_rate': metrics.error_rate,
                    'success_rate': metrics.success_rate,
                    'threshold': self._alert_thresholds['error_rate']['critical'],
                    'sample_count': metrics.sample_count,
                    'avg_latency_ms': metrics.avg_latency_ms
                },
                self._alert_thresholds['error_rate']['critical'],
                metrics.error_rate
            )
        elif metrics.error_rate > self._alert_thresholds['error_rate']['warning']:
            await self._generate_alert(
                AlertSeverity.WARNING,
                MonitoringMetric.ERROR_RATE,
                metrics.provider,
                None,
                f"High error rate for {metrics.provider} {metrics.operation_type}: {metrics.error_rate:.2%}",
                {
                    'error_rate': metrics.error_rate,
                    'success_rate': metrics.success_rate,
                    'threshold': self._alert_thresholds['error_rate']['warning'],
                    'sample_count': metrics.sample_count,
                    'avg_latency_ms': metrics.avg_latency_ms
                },
                self._alert_thresholds['error_rate']['warning'],
                metrics.error_rate
            )
    
    async def _generate_alert(
        self,
        severity: AlertSeverity,
        metric: MonitoringMetric,
        provider: Optional[str],
        tenant_id: Optional[str],
        message: str,
        details: Dict[str, Any],
        threshold_value: Optional[float] = None,
        current_value: Optional[float] = None
    ) -> StorageAlert:
        """Generate and store a storage monitoring alert."""
        alert_id = f"{metric.value}_{provider or 'global'}_{tenant_id or 'global'}_{int(time.time())}"
        
        # Check for alert cooldown to prevent spam
        cooldown_minutes = self._alerting_config.alert_cooldown_minutes
        if cooldown_minutes > 0:
            cutoff_time = datetime.now() - timedelta(minutes=cooldown_minutes)
            
            # Check if similar alert exists within cooldown period
            similar_alerts = [
                a for a in self._active_alerts.values()
                if (a.metric == metric and 
                    a.provider == provider and 
                    a.tenant_id == tenant_id and
                    a.created_at > cutoff_time)
            ]
            
            if similar_alerts:
                logger.debug(f"Alert suppressed due to cooldown: {message}")
                return similar_alerts[0]  # Return existing similar alert
        
        alert = StorageAlert(
            id=alert_id,
            severity=severity,
            metric=metric,
            provider=provider,
            tenant_id=tenant_id,
            message=message,
            details=details,
            threshold_value=threshold_value,
            current_value=current_value
        )
        
        # Store in active alerts
        self._active_alerts[alert_id] = alert
        
        # Log the alert
        logger.warning(f"Storage alert generated: {severity.value} - {message}")
        
        # Send notification asynchronously
        try:
            await self.send_alert_notification(alert)
        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
        
        return alert
    
    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        provider: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[StorageAlert]:
        """
        Get active storage alerts with optional filtering.
        
        Args:
            severity: Filter by alert severity
            provider: Filter by provider
            tenant_id: Filter by tenant ID
            
        Returns:
            List of matching active alerts
        """
        alerts = list(self._active_alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if provider:
            alerts = [a for a in alerts if a.provider == provider]
        if tenant_id:
            alerts = [a for a in alerts if a.tenant_id == tenant_id]
        
        # Sort by severity and creation time
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.ERROR: 1,
            AlertSeverity.WARNING: 2,
            AlertSeverity.INFO: 3
        }
        
        alerts.sort(key=lambda a: (severity_order[a.severity], a.created_at), reverse=True)
        
        return alerts
    
    def resolve_alert(self, alert_id: str, resolution_note: Optional[str] = None) -> bool:
        """
        Resolve an active alert.
        
        Args:
            alert_id: ID of the alert to resolve
            resolution_note: Optional note about the resolution
            
        Returns:
            True if alert was found and resolved
        """
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.is_resolved = True
            alert.resolved_at = datetime.now()
            
            # Add resolution note to details
            if resolution_note:
                alert.details['resolution_note'] = resolution_note
            
            # Move to resolved alerts
            self._resolved_alerts[alert_id] = alert
            
            # Remove from active alerts
            del self._active_alerts[alert_id]
            
            logger.info(f"Alert resolved: {alert_id}")
            return True
        
        return False
    
    def auto_resolve_alerts(self) -> List[str]:
        """
        Automatically resolve alerts that are no longer valid.
        
        Returns:
            List of alert IDs that were auto-resolved
        """
        resolved_alert_ids = []
        
        for alert_id, alert in list(self._active_alerts.items()):
            should_resolve = False
            
            # Auto-resolve health alerts if provider is now healthy
            if alert.metric == MonitoringMetric.HEALTH_STATUS:
                if alert.provider and alert.provider in [p.value for p in StorageProvider]:
                    provider_type = StorageProvider(alert.provider)
                    if provider_type in self._health_cache:
                        current_health = self._health_cache[provider_type]
                        if current_health.is_healthy and current_health.consecutive_successes >= 3:
                            should_resolve = True
            
            # Auto-resolve success rate alerts if rate has improved
            elif alert.metric == MonitoringMetric.OPERATION_SUCCESS_RATE:
                if alert.provider and alert.threshold_value:
                    # Check current success rate (simplified check)
                    if alert.provider in [p.value for p in StorageProvider]:
                        provider_type = StorageProvider(alert.provider)
                        if provider_type in self._health_cache:
                            current_health = self._health_cache[provider_type]
                            if current_health.success_rate_24h > alert.threshold_value:
                                should_resolve = True
            
            if should_resolve:
                self.resolve_alert(alert_id, "Auto-resolved: condition no longer met")
                resolved_alert_ids.append(alert_id)
        
        if resolved_alert_ids:
            logger.info(f"Auto-resolved {len(resolved_alert_ids)} alerts")
        
        return resolved_alert_ids
    
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
    
    # ===== ALERTING METHODS =====
    
    def configure_alerting(self, config: AlertingConfig) -> None:
        """
        Configure alerting system settings.
        
        Args:
            config: Alerting configuration
        """
        self._alerting_config = config
        logger.info("Alerting configuration updated")
    
    def add_alert_callback(self, callback: Callable[[StorageAlert], None]) -> None:
        """
        Add a callback function to be called when alerts are generated.
        
        Args:
            callback: Function to call with StorageAlert parameter
        """
        self._alert_callbacks.append(callback)
    
    async def send_alert_notification(self, alert: StorageAlert) -> bool:
        """
        Send notification for an alert via configured channels.
        
        Args:
            alert: The alert to send notification for
            
        Returns:
            True if notification was sent successfully
        """
        if alert.notification_sent:
            return True
        
        success = False
        
        try:
            # Send email notification
            if self._alerting_config.email_enabled:
                email_success = await self._send_email_alert(alert)
                success = success or email_success
            
            # Send webhook notification
            if self._alerting_config.webhook_enabled:
                webhook_success = await self._send_webhook_alert(alert)
                success = success or webhook_success
            
            # Call registered callbacks
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                    success = True
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")
            
            if success:
                alert.notification_sent = True
                logger.info(f"Alert notification sent: {alert.id}")
            
        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
        
        return success
    
    async def _send_email_alert(self, alert: StorageAlert) -> bool:
        """Send alert via email."""
        if not EMAIL_AVAILABLE:
            logger.warning("Email functionality not available - email packages not installed")
            return False
            
        if not self._alerting_config.email_enabled or not self._alerting_config.email_to_addresses:
            return False
        
        try:
            # Create email message
            msg = MimeMultipart()
            msg['From'] = self._alerting_config.email_from_address
            msg['To'] = ', '.join(self._alerting_config.email_to_addresses)
            msg['Subject'] = f"Storage Alert: {alert.severity.value.upper()} - {alert.metric.value}"
            
            # Create email body
            body = self._format_alert_email(alert)
            msg.attach(MimeText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(self._alerting_config.email_smtp_server, self._alerting_config.email_smtp_port) as server:
                server.starttls()
                if self._alerting_config.email_username and self._alerting_config.email_password:
                    server.login(self._alerting_config.email_username, self._alerting_config.email_password)
                
                server.send_message(msg)
            
            logger.info(f"Email alert sent for {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    async def _send_webhook_alert(self, alert: StorageAlert) -> bool:
        """Send alert via webhook."""
        if not self._alerting_config.webhook_enabled or not self._alerting_config.webhook_url:
            return False
        
        try:
            # Try to import aiohttp (optional dependency)
            try:
                import aiohttp
            except ImportError:
                logger.warning("aiohttp not available - webhook functionality disabled")
                return False
            
            payload = {
                'alert': alert.to_dict(),
                'timestamp': datetime.now().isoformat(),
                'source': 'storage_monitoring_service'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._alerting_config.webhook_url,
                    json=payload,
                    headers=self._alerting_config.webhook_headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status < 400:
                        logger.info(f"Webhook alert sent for {alert.id}")
                        return True
                    else:
                        logger.error(f"Webhook alert failed with status {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False
    
    def _format_alert_email(self, alert: StorageAlert) -> str:
        """Format alert as HTML email."""
        severity_colors = {
            AlertSeverity.CRITICAL: '#dc3545',
            AlertSeverity.ERROR: '#fd7e14',
            AlertSeverity.WARNING: '#ffc107',
            AlertSeverity.INFO: '#17a2b8'
        }
        
        color = severity_colors.get(alert.severity, '#6c757d')
        
        html = f"""
        <html>
        <body>
            <h2 style="color: {color};">Storage Alert: {alert.severity.value.upper()}</h2>
            
            <table style="border-collapse: collapse; width: 100%;">
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Alert ID:</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.id}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Metric:</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.metric.value}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Provider:</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.provider or 'N/A'}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Tenant:</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.tenant_id or 'N/A'}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Message:</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.message}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Created:</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                </tr>
        """
        
        if alert.threshold_value is not None and alert.current_value is not None:
            html += f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Threshold:</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.threshold_value}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Current Value:</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.current_value}</td>
                </tr>
            """
        
        if alert.details:
            html += f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Details:</td>
                    <td style="border: 1px solid #ddd; padding: 8px;"><pre>{json.dumps(alert.details, indent=2)}</pre></td>
                </tr>
            """
        
        html += """
            </table>
            
            <p><em>This is an automated alert from the Storage Monitoring Service.</em></p>
        </body>
        </html>
        """
        
        return html
    
    async def escalate_alerts(self) -> List[StorageAlert]:
        """
        Check for alerts that need escalation and escalate them.
        
        Returns:
            List of alerts that were escalated
        """
        if not self._alerting_config.escalation_enabled:
            return []
        
        escalated_alerts = []
        escalation_threshold = timedelta(minutes=self._alerting_config.escalation_interval_minutes)
        
        for alert in self._active_alerts.values():
            if alert.is_resolved or alert.escalation_level >= self._alerting_config.max_escalation_level:
                continue
            
            time_since_created = datetime.now() - alert.created_at
            if time_since_created >= escalation_threshold * (alert.escalation_level + 1):
                # Escalate the alert
                alert.escalation_level += 1
                alert.notification_sent = False  # Reset to send escalated notification
                
                # Update alert message to indicate escalation
                alert.message = f"[ESCALATED L{alert.escalation_level}] {alert.message}"
                
                # Send escalated notification
                await self.send_alert_notification(alert)
                
                escalated_alerts.append(alert)
                logger.warning(f"Alert escalated to level {alert.escalation_level}: {alert.id}")
        
        return escalated_alerts
    
    def get_alert_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get alert statistics for the specified period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with alert statistics
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Combine active and resolved alerts
        all_alerts = list(self._active_alerts.values()) + list(self._resolved_alerts.values())
        
        # Filter by date
        period_alerts = [a for a in all_alerts if a.created_at >= cutoff_date]
        
        # Calculate statistics
        total_alerts = len(period_alerts)
        resolved_alerts = len([a for a in period_alerts if a.is_resolved])
        
        # Group by severity
        by_severity = defaultdict(int)
        for alert in period_alerts:
            by_severity[alert.severity.value] += 1
        
        # Group by metric
        by_metric = defaultdict(int)
        for alert in period_alerts:
            by_metric[alert.metric.value] += 1
        
        # Group by provider
        by_provider = defaultdict(int)
        for alert in period_alerts:
            if alert.provider:
                by_provider[alert.provider] += 1
        
        # Calculate resolution time statistics
        resolved_alert_objects = [a for a in period_alerts if a.is_resolved and a.resolved_at]
        resolution_times = []
        for alert in resolved_alert_objects:
            resolution_time = (alert.resolved_at - alert.created_at).total_seconds() / 60  # minutes
            resolution_times.append(resolution_time)
        
        avg_resolution_time = statistics.mean(resolution_times) if resolution_times else 0
        median_resolution_time = statistics.median(resolution_times) if resolution_times else 0
        
        return {
            'period_days': days,
            'total_alerts': total_alerts,
            'active_alerts': total_alerts - resolved_alerts,
            'resolved_alerts': resolved_alerts,
            'resolution_rate': (resolved_alerts / total_alerts) if total_alerts > 0 else 0,
            'avg_resolution_time_minutes': avg_resolution_time,
            'median_resolution_time_minutes': median_resolution_time,
            'by_severity': dict(by_severity),
            'by_metric': dict(by_metric),
            'by_provider': dict(by_provider),
            'escalated_alerts': len([a for a in period_alerts if a.escalation_level > 0])
        }
    
    # ===== REPORTING METHODS =====
    
    def _get_default_report_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get default report templates."""
        return {
            'daily_summary': {
                'name': 'Daily Storage Summary',
                'description': 'Daily summary of storage operations and health',
                'sections': ['health_overview', 'operation_metrics', 'usage_summary', 'alerts']
            },
            'weekly_performance': {
                'name': 'Weekly Performance Report',
                'description': 'Weekly performance analysis across all providers',
                'sections': ['performance_trends', 'provider_comparison', 'error_analysis']
            },
            'monthly_usage': {
                'name': 'Monthly Usage Report',
                'description': 'Monthly storage usage and growth analysis',
                'sections': ['usage_trends', 'tenant_breakdown', 'cost_analysis', 'capacity_planning']
            },
            'incident_report': {
                'name': 'Incident Report',
                'description': 'Detailed analysis of storage incidents and alerts',
                'sections': ['incident_timeline', 'impact_analysis', 'root_cause', 'remediation']
            }
        }
    
    async def generate_report(
        self,
        report_type: str,
        tenant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json"
    ) -> StorageReport:
        """
        Generate a storage monitoring report.
        
        Args:
            report_type: Type of report to generate
            tenant_id: Filter by specific tenant
            start_date: Report period start date
            end_date: Report period end date
            format: Output format (json, html, csv)
            
        Returns:
            Generated StorageReport
        """
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=1)  # Default to 1 day
        
        report_id = f"{report_type}_{tenant_id or 'all'}_{int(time.time())}"
        
        logger.info(f"Generating report: {report_type} for period {start_date} to {end_date}")
        
        # Generate report data based on type
        if report_type == 'daily_summary':
            data = await self._generate_daily_summary_report(tenant_id, start_date, end_date)
        elif report_type == 'weekly_performance':
            data = await self._generate_weekly_performance_report(tenant_id, start_date, end_date)
        elif report_type == 'monthly_usage':
            data = await self._generate_monthly_usage_report(tenant_id, start_date, end_date)
        elif report_type == 'incident_report':
            data = await self._generate_incident_report(tenant_id, start_date, end_date)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
        
        # Create report object
        report = StorageReport(
            report_id=report_id,
            report_type=report_type,
            tenant_id=tenant_id,
            generated_at=datetime.now(),
            period_start=start_date,
            period_end=end_date,
            data=data,
            format=format
        )
        
        # Store report
        self._generated_reports[report_id] = report
        
        logger.info(f"Report generated: {report_id}")
        
        return report
    
    async def _generate_daily_summary_report(
        self,
        tenant_id: Optional[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate daily summary report data."""
        # Health overview
        health_results = await self.health_check_all_providers()
        health_overview = {
            provider.value: {
                'healthy': metrics.is_healthy,
                'success_rate_24h': metrics.success_rate_24h,
                'response_time_ms': metrics.response_time_ms,
                'uptime_percentage': metrics.uptime_percentage
            }
            for provider, metrics in health_results.items()
        }
        
        # Operation metrics
        performance_metrics = await self.get_performance_metrics(hours=24)
        operation_metrics = {
            f"{m.provider}_{m.operation_type}": {
                'success_rate': m.success_rate,
                'avg_latency_ms': m.avg_latency_ms,
                'throughput_ops_per_minute': m.throughput_ops_per_minute,
                'sample_count': m.sample_count
            }
            for m in performance_metrics
        }
        
        # Usage summary
        usage_metrics = await self.get_storage_usage_metrics(tenant_id)
        usage_summary = {}
        for tid, metrics in usage_metrics.items():
            usage_summary[tid] = {
                'total_files': metrics.total_files,
                'total_size_gb': metrics.total_size_bytes / (1024 ** 3),
                'growth_rate_files_per_day': metrics.growth_rate_files_per_day,
                'growth_rate_gb_per_day': metrics.growth_rate_bytes_per_day / (1024 ** 3)
            }
        
        # Alert summary
        alert_stats = self.get_alert_statistics(days=1)
        
        return {
            'health_overview': health_overview,
            'operation_metrics': operation_metrics,
            'usage_summary': usage_summary,
            'alerts': alert_stats,
            'summary': {
                'total_providers': len(health_overview),
                'healthy_providers': len([h for h in health_overview.values() if h['healthy']]),
                'total_operations': sum(m['sample_count'] for m in operation_metrics.values()),
                'avg_success_rate': statistics.mean([m['success_rate'] for m in operation_metrics.values()]) if operation_metrics else 0
            }
        }
    
    async def _generate_weekly_performance_report(
        self,
        tenant_id: Optional[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate weekly performance report data."""
        # Get performance metrics for the week
        hours = int((end_date - start_date).total_seconds() / 3600)
        performance_metrics = await self.get_performance_metrics(hours=hours)
        
        # Group by provider for comparison
        provider_performance = defaultdict(list)
        for metric in performance_metrics:
            provider_performance[metric.provider].append(metric)
        
        # Calculate trends (simplified - would need historical data for real trends)
        performance_trends = {}
        provider_comparison = {}
        
        for provider, metrics in provider_performance.items():
            avg_success_rate = statistics.mean([m.success_rate for m in metrics])
            avg_latency = statistics.mean([m.avg_latency_ms for m in metrics])
            total_operations = sum(m.sample_count for m in metrics)
            
            provider_comparison[provider] = {
                'avg_success_rate': avg_success_rate,
                'avg_latency_ms': avg_latency,
                'total_operations': total_operations,
                'operations_by_type': {
                    m.operation_type: m.sample_count for m in metrics
                }
            }
        
        # Error analysis
        error_analysis = {}
        for provider, metrics in provider_performance.items():
            total_ops = sum(m.sample_count for m in metrics)
            total_errors = sum(int(m.sample_count * m.error_rate) for m in metrics)
            error_analysis[provider] = {
                'total_operations': total_ops,
                'total_errors': total_errors,
                'error_rate': total_errors / total_ops if total_ops > 0 else 0
            }
        
        return {
            'performance_trends': performance_trends,
            'provider_comparison': provider_comparison,
            'error_analysis': error_analysis,
            'period_summary': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_providers': len(provider_comparison),
                'best_performing_provider': max(provider_comparison.keys(), 
                                              key=lambda p: provider_comparison[p]['avg_success_rate']) if provider_comparison else None
            }
        }
    
    async def _generate_monthly_usage_report(
        self,
        tenant_id: Optional[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate monthly usage report data."""
        usage_metrics = await self.get_storage_usage_metrics(tenant_id)
        
        # Calculate usage trends and projections
        usage_trends = {}
        tenant_breakdown = {}
        cost_analysis = {}
        capacity_planning = {}
        
        total_files = 0
        total_size_gb = 0
        
        for tid, metrics in usage_metrics.items():
            size_gb = metrics.total_size_bytes / (1024 ** 3)
            total_files += metrics.total_files
            total_size_gb += size_gb
            
            tenant_breakdown[tid] = {
                'files': metrics.total_files,
                'size_gb': size_gb,
                'growth_rate_files_per_day': metrics.growth_rate_files_per_day,
                'growth_rate_gb_per_day': metrics.growth_rate_bytes_per_day / (1024 ** 3),
                'files_by_provider': metrics.files_by_provider,
                'size_by_provider': {k: v / (1024 ** 3) for k, v in metrics.size_by_provider.items()}
            }
            
            # Simple cost estimation (would need actual provider pricing)
            estimated_monthly_cost = size_gb * 0.023  # Rough AWS S3 standard pricing
            cost_analysis[tid] = {
                'estimated_monthly_cost_usd': estimated_monthly_cost,
                'cost_per_gb': 0.023,
                'projected_annual_cost': estimated_monthly_cost * 12
            }
            
            # Capacity planning projections
            monthly_growth_gb = metrics.growth_rate_bytes_per_day * 30 / (1024 ** 3)
            capacity_planning[tid] = {
                'current_size_gb': size_gb,
                'monthly_growth_gb': monthly_growth_gb,
                'projected_size_6_months': size_gb + (monthly_growth_gb * 6),
                'projected_size_12_months': size_gb + (monthly_growth_gb * 12)
            }
        
        return {
            'usage_trends': usage_trends,
            'tenant_breakdown': tenant_breakdown,
            'cost_analysis': cost_analysis,
            'capacity_planning': capacity_planning,
            'summary': {
                'total_tenants': len(usage_metrics),
                'total_files': total_files,
                'total_size_gb': total_size_gb,
                'avg_files_per_tenant': total_files / len(usage_metrics) if usage_metrics else 0,
                'avg_size_per_tenant_gb': total_size_gb / len(usage_metrics) if usage_metrics else 0
            }
        }
    
    async def _generate_incident_report(
        self,
        tenant_id: Optional[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate incident report data."""
        # Get alerts for the period
        all_alerts = list(self._active_alerts.values()) + list(self._resolved_alerts.values())
        period_alerts = [
            a for a in all_alerts 
            if start_date <= a.created_at <= end_date
            and (not tenant_id or a.tenant_id == tenant_id)
        ]
        
        # Create incident timeline
        incident_timeline = []
        for alert in sorted(period_alerts, key=lambda a: a.created_at):
            incident_timeline.append({
                'timestamp': alert.created_at.isoformat(),
                'alert_id': alert.id,
                'severity': alert.severity.value,
                'metric': alert.metric.value,
                'provider': alert.provider,
                'message': alert.message,
                'resolved': alert.is_resolved,
                'resolution_time_minutes': (
                    (alert.resolved_at - alert.created_at).total_seconds() / 60
                    if alert.resolved_at else None
                )
            })
        
        # Impact analysis
        critical_alerts = [a for a in period_alerts if a.severity == AlertSeverity.CRITICAL]
        error_alerts = [a for a in period_alerts if a.severity == AlertSeverity.ERROR]
        
        impact_analysis = {
            'total_incidents': len(period_alerts),
            'critical_incidents': len(critical_alerts),
            'error_incidents': len(error_alerts),
            'affected_providers': list(set(a.provider for a in period_alerts if a.provider)),
            'affected_tenants': list(set(a.tenant_id for a in period_alerts if a.tenant_id)),
            'avg_resolution_time_minutes': statistics.mean([
                (a.resolved_at - a.created_at).total_seconds() / 60
                for a in period_alerts if a.resolved_at
            ]) if any(a.resolved_at for a in period_alerts) else 0
        }
        
        # Root cause analysis (simplified)
        root_cause = defaultdict(int)
        for alert in period_alerts:
            root_cause[alert.metric.value] += 1
        
        return {
            'incident_timeline': incident_timeline,
            'impact_analysis': impact_analysis,
            'root_cause': dict(root_cause),
            'remediation': {
                'recommendations': [
                    'Monitor provider health more frequently',
                    'Implement automated failover procedures',
                    'Review alert thresholds for accuracy',
                    'Improve incident response procedures'
                ]
            }
        }
    
    def get_report(self, report_id: str) -> Optional[StorageReport]:
        """Get a generated report by ID."""
        return self._generated_reports.get(report_id)
    
    def list_reports(
        self,
        report_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50
    ) -> List[StorageReport]:
        """
        List generated reports with optional filtering.
        
        Args:
            report_type: Filter by report type
            tenant_id: Filter by tenant ID
            limit: Maximum number of reports to return
            
        Returns:
            List of matching reports
        """
        reports = list(self._generated_reports.values())
        
        if report_type:
            reports = [r for r in reports if r.report_type == report_type]
        if tenant_id:
            reports = [r for r in reports if r.tenant_id == tenant_id]
        
        # Sort by generation time (newest first)
        reports.sort(key=lambda r: r.generated_at, reverse=True)
        
        return reports[:limit]
    
    def export_report(self, report_id: str, format: str = "json") -> str:
        """
        Export a report in the specified format.
        
        Args:
            report_id: ID of the report to export
            format: Export format (json, html, csv)
            
        Returns:
            Formatted report content
        """
        report = self.get_report(report_id)
        if not report:
            raise ValueError(f"Report not found: {report_id}")
        
        if format == "json":
            return json.dumps(report.to_dict(), indent=2, default=str)
        elif format == "html":
            return self._format_report_html(report)
        elif format == "csv":
            return self._format_report_csv(report)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _format_report_html(self, report: StorageReport) -> str:
        """Format report as HTML."""
        html = f"""
        <html>
        <head>
            <title>{report.report_type.replace('_', ' ').title()} Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .header {{ background-color: #4CAF50; color: white; padding: 10px; }}
                .section {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{report.report_type.replace('_', ' ').title()} Report</h1>
                <p>Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p>Period: {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}</p>
            </div>
            
            <div class="section">
                <h2>Report Data</h2>
                <pre>{json.dumps(report.data, indent=2, default=str)}</pre>
            </div>
        </body>
        </html>
        """
        return html
    
    def _format_report_csv(self, report: StorageReport) -> str:
        """Format report as CSV (simplified)."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Report Type', 'Generated At', 'Period Start', 'Period End'])
        writer.writerow([
            report.report_type,
            report.generated_at.isoformat(),
            report.period_start.isoformat(),
            report.period_end.isoformat()
        ])
        
        # Write data (flattened)
        writer.writerow([])
        writer.writerow(['Key', 'Value'])
        
        def flatten_dict(d, prefix=''):
            for key, value in d.items():
                if isinstance(value, dict):
                    yield from flatten_dict(value, f"{prefix}{key}.")
                else:
                    yield f"{prefix}{key}", str(value)
        
        for key, value in flatten_dict(report.data):
            writer.writerow([key, value])
        
        return output.getvalue()
    
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

    async def get_tenant_usage_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get storage usage statistics for a specific tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with usage statistics
        """
        try:
            usage_metrics = await self.get_storage_usage_metrics(tenant_id=tenant_id)
            
            # Aggregate statistics
            total_files = 0
            total_size_bytes = 0
            by_provider = {}
            by_type = {}
            
            for metrics in usage_metrics:
                total_files += metrics.file_count
                total_size_bytes += metrics.total_size_bytes
                
                # Group by provider (if available in metrics)
                provider = getattr(metrics, 'provider', 'unknown')
                if provider not in by_provider:
                    by_provider[provider] = {'files': 0, 'size_bytes': 0}
                by_provider[provider]['files'] += metrics.file_count
                by_provider[provider]['size_bytes'] += metrics.total_size_bytes
                
                # Group by attachment type (if available in metrics)
                attachment_type = getattr(metrics, 'attachment_type', 'unknown')
                if attachment_type not in by_type:
                    by_type[attachment_type] = {'files': 0, 'size_bytes': 0}
                by_type[attachment_type]['files'] += metrics.file_count
                by_type[attachment_type]['size_bytes'] += metrics.total_size_bytes
            
            return {
                'total_files': total_files,
                'total_size_bytes': total_size_bytes,
                'by_provider': by_provider,
                'by_type': by_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get tenant usage stats for {tenant_id}: {e}")
            return {
                'total_files': 0,
                'total_size_bytes': 0,
                'by_provider': {},
                'by_type': {}
            }

    async def get_operation_logs(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
        operation_type: Optional[str] = None,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get storage operation logs for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            operation_type: Filter by operation type
            provider: Filter by provider
            
        Returns:
            List of operation log entries
        """
        try:
            from models.models import StorageOperationLog
            from sqlalchemy import desc
            
            # Build query
            query = self.db.query(StorageOperationLog).filter(
                StorageOperationLog.tenant_id == tenant_id
            )
            
            if operation_type:
                query = query.filter(StorageOperationLog.operation_type == operation_type)
            
            if provider:
                query = query.filter(StorageOperationLog.provider == provider)
            
            # Execute query with pagination
            logs = query.order_by(desc(StorageOperationLog.created_at)).offset(offset).limit(limit).all()
            
            # Convert to dictionaries
            log_entries = []
            for log in logs:
                log_entries.append({
                    'id': log.id,
                    'operation_type': log.operation_type,
                    'file_key': log.file_key,
                    'provider': log.provider,
                    'success': log.success,
                    'file_size': log.file_size,
                    'duration_ms': log.duration_ms,
                    'error_message': log.error_message,
                    'user_id': log.user_id,
                    'ip_address': log.ip_address,
                    'created_at': log.created_at.isoformat() if log.created_at else None
                })
            
            return log_entries
            
        except Exception as e:
            logger.error(f"Failed to get operation logs for tenant {tenant_id}: {e}")
            return []

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

    def cleanup_old_reports(self, days_to_keep: int = 30) -> int:
        """
        Clean up old reports to manage memory usage.
        
        Args:
            days_to_keep: Number of days of reports to retain
            
        Returns:
            Number of reports deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        reports_to_delete = [
            report_id for report_id, report in self._generated_reports.items()
            if report.generated_at < cutoff_date
        ]
        
        for report_id in reports_to_delete:
            del self._generated_reports[report_id]
        
        logger.info(f"Cleaned up {len(reports_to_delete)} old reports")
        
        return len(reports_to_delete)
