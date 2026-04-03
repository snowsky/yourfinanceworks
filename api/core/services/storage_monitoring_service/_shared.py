"""
Shared types, enums, and dataclasses for the storage monitoring service.
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

from core.interfaces.storage_provider import (
    CloudStorageProvider, StorageProvider, HealthCheckResult
)
# from commercial.cloud_storage.providers.factory import StorageProviderFactory  # Moved to conditional import
# from commercial.cloud_storage.providers.circuit_breaker import (
#     StorageCircuitBreakerManager, storage_circuit_breaker_manager
# )  # Moved to conditional import
from core.models.models import Tenant
from core.models.models_per_tenant import StorageOperationLog, CloudStorageConfiguration
# from commercial.cloud_storage.config import CloudStorageConfig  # Moved to conditional import

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


__all__ = [
    "EMAIL_AVAILABLE",
    "MimeText",
    "MimeMultipart",
    "smtplib",
    "logger",
    "logging",
    "time",
    "json",
    "Dict",
    "Any",
    "List",
    "Optional",
    "Tuple",
    "Callable",
    "datetime",
    "timedelta",
    "dataclass",
    "field",
    "Enum",
    "defaultdict",
    "deque",
    "statistics",
    "Session",
    "func",
    "and_",
    "or_",
    "desc",
    "CloudStorageProvider",
    "StorageProvider",
    "HealthCheckResult",
    "Tenant",
    "StorageOperationLog",
    "CloudStorageConfiguration",
    "AlertSeverity",
    "MonitoringMetric",
    "StorageAlert",
    "AlertingConfig",
    "StorageReport",
    "ProviderHealthMetrics",
    "StorageUsageMetrics",
    "PerformanceMetrics",
]
