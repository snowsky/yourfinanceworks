"""
Encryption Monitoring Service

This service provides comprehensive monitoring and metrics collection for encryption operations,
including performance tracking, key access patterns, and failure monitoring.
"""

import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
from contextlib import contextmanager

from encryption_config import EncryptionConfig
from core.exceptions.encryption_exceptions import EncryptionMonitoringError


@dataclass
class EncryptionMetric:
    """Represents a single encryption operation metric"""
    operation_type: str  # 'encrypt', 'decrypt', 'key_access', 'key_rotation'
    tenant_id: int
    duration_ms: float
    success: bool
    timestamp: datetime
    data_size_bytes: Optional[int] = None
    error_type: Optional[str] = None
    key_id: Optional[str] = None


@dataclass
class PerformanceStats:
    """Performance statistics for encryption operations"""
    total_operations: int
    successful_operations: int
    failed_operations: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    operations_per_second: float
    error_rate: float


@dataclass
class KeyAccessPattern:
    """Key access pattern tracking"""
    tenant_id: int
    key_id: str
    access_count: int
    last_access: datetime
    access_frequency: float  # accesses per hour
    unusual_access_detected: bool


class EncryptionMonitoringService:
    """
    Service for monitoring encryption operations and collecting performance metrics
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = EncryptionConfig()
        
        # Thread-safe metrics storage
        self._metrics_lock = threading.RLock()
        self._metrics_buffer: deque = deque(maxlen=10000)  # Keep last 10k metrics
        
        # Performance tracking
        self._operation_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._success_counts: Dict[str, int] = defaultdict(int)
        
        # Key access tracking
        self._key_access_patterns: Dict[str, KeyAccessPattern] = {}
        self._suspicious_patterns: List[Dict[str, Any]] = []
        
        # Alerting thresholds
        self.error_rate_threshold = 0.05  # 5% error rate threshold
        self.performance_degradation_threshold = 2.0  # 2x normal response time
        self.unusual_access_threshold = 10  # 10x normal access frequency
        
        self.logger.info("Encryption monitoring service initialized")
    
    @contextmanager
    def monitor_operation(self, operation_type: str, tenant_id: int, 
                         data_size_bytes: Optional[int] = None, key_id: Optional[str] = None):
        """
        Context manager for monitoring encryption operations
        
        Args:
            operation_type: Type of operation ('encrypt', 'decrypt', 'key_access', 'key_rotation')
            tenant_id: Tenant ID for the operation
            data_size_bytes: Size of data being processed
            key_id: Key ID being accessed
        """
        start_time = time.time()
        success = False
        error_type = None
        
        try:
            yield
            success = True
        except Exception as e:
            error_type = type(e).__name__
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            metric = EncryptionMetric(
                operation_type=operation_type,
                tenant_id=tenant_id,
                duration_ms=duration_ms,
                success=success,
                timestamp=datetime.utcnow(),
                data_size_bytes=data_size_bytes,
                error_type=error_type,
                key_id=key_id
            )
            
            self._record_metric(metric)
    
    def _record_metric(self, metric: EncryptionMetric):
        """Record a metric and update internal tracking"""
        with self._metrics_lock:
            self._metrics_buffer.append(metric)
            
            # Update operation times
            self._operation_times[metric.operation_type].append(metric.duration_ms)
            
            # Update success/error counts
            if metric.success:
                self._success_counts[metric.operation_type] += 1
            else:
                self._error_counts[metric.operation_type] += 1
                self.logger.warning(
                    f"Encryption operation failed: {metric.operation_type} "
                    f"for tenant {metric.tenant_id}, error: {metric.error_type}"
                )
            
            # Track key access patterns
            if metric.key_id and metric.operation_type in ['encrypt', 'decrypt', 'key_access']:
                self._update_key_access_pattern(metric)
            
            # Check for alerts
            self._check_alert_conditions(metric)
    
    def _update_key_access_pattern(self, metric: EncryptionMetric):
        """Update key access patterns and detect anomalies"""
        pattern_key = f"{metric.tenant_id}:{metric.key_id}"
        
        if pattern_key not in self._key_access_patterns:
            self._key_access_patterns[pattern_key] = KeyAccessPattern(
                tenant_id=metric.tenant_id,
                key_id=metric.key_id,
                access_count=0,
                last_access=metric.timestamp,
                access_frequency=0.0,
                unusual_access_detected=False
            )
        
        pattern = self._key_access_patterns[pattern_key]
        pattern.access_count += 1
        
        # Calculate access frequency (accesses per hour)
        time_diff = (metric.timestamp - pattern.last_access).total_seconds() / 3600
        if time_diff > 0:
            pattern.access_frequency = 1 / time_diff
        
        pattern.last_access = metric.timestamp
        
        # Detect unusual access patterns
        avg_frequency = self._calculate_average_access_frequency(metric.tenant_id)
        if pattern.access_frequency > avg_frequency * self.unusual_access_threshold:
            pattern.unusual_access_detected = True
            self._record_suspicious_activity(metric, "unusual_key_access_frequency")
    
    def _calculate_average_access_frequency(self, tenant_id: int) -> float:
        """Calculate average access frequency for a tenant"""
        tenant_patterns = [
            p for p in self._key_access_patterns.values() 
            if p.tenant_id == tenant_id
        ]
        
        if not tenant_patterns:
            return 1.0
        
        frequencies = [p.access_frequency for p in tenant_patterns if p.access_frequency > 0]
        return sum(frequencies) / len(frequencies) if frequencies else 1.0
    
    def _record_suspicious_activity(self, metric: EncryptionMetric, activity_type: str):
        """Record suspicious activity for security alerting"""
        suspicious_event = {
            'timestamp': metric.timestamp.isoformat(),
            'tenant_id': metric.tenant_id,
            'activity_type': activity_type,
            'key_id': metric.key_id,
            'operation_type': metric.operation_type,
            'details': asdict(metric)
        }
        
        self._suspicious_patterns.append(suspicious_event)
        
        self.logger.warning(
            f"Suspicious encryption activity detected: {activity_type} "
            f"for tenant {metric.tenant_id}, key {metric.key_id}"
        )
    
    def _check_alert_conditions(self, metric: EncryptionMetric):
        """Check if current metric triggers any alert conditions"""
        operation_type = metric.operation_type
        
        # Check error rate
        total_ops = self._success_counts[operation_type] + self._error_counts[operation_type]
        if total_ops >= 10:  # Only check after minimum operations
            error_rate = self._error_counts[operation_type] / total_ops
            if error_rate > self.error_rate_threshold:
                self._trigger_alert(
                    'high_error_rate',
                    f"High error rate detected for {operation_type}: {error_rate:.2%}",
                    {'operation_type': operation_type, 'error_rate': error_rate}
                )
        
        # Check performance degradation
        if len(self._operation_times[operation_type]) >= 10:
            recent_times = list(self._operation_times[operation_type])[-10:]
            avg_recent = sum(recent_times) / len(recent_times)
            
            all_times = list(self._operation_times[operation_type])
            avg_all = sum(all_times) / len(all_times)
            
            if avg_recent > avg_all * self.performance_degradation_threshold:
                self._trigger_alert(
                    'performance_degradation',
                    f"Performance degradation detected for {operation_type}: "
                    f"{avg_recent:.2f}ms vs {avg_all:.2f}ms average",
                    {
                        'operation_type': operation_type,
                        'recent_avg_ms': avg_recent,
                        'overall_avg_ms': avg_all
                    }
                )
    
    def _trigger_alert(self, alert_type: str, message: str, details: Dict[str, Any]):
        """Trigger an alert for monitoring systems"""
        alert = {
            'timestamp': datetime.utcnow().isoformat(),
            'alert_type': alert_type,
            'message': message,
            'details': details,
            'severity': 'warning' if alert_type == 'performance_degradation' else 'critical'
        }
        
        self.logger.error(f"ENCRYPTION ALERT: {message}")
        
        # Here you would integrate with your alerting system
        # For example: send to Slack, PagerDuty, email, etc.
        self._send_to_monitoring_system(alert)
    
    def _send_to_monitoring_system(self, alert: Dict[str, Any]):
        """Send alert to external monitoring system"""
        # Placeholder for integration with monitoring systems
        # This could be Prometheus, Grafana, DataDog, etc.
        pass
    
    def get_performance_stats(self, operation_type: Optional[str] = None, 
                            time_window_hours: int = 24) -> Dict[str, PerformanceStats]:
        """
        Get performance statistics for encryption operations
        
        Args:
            operation_type: Specific operation type to get stats for
            time_window_hours: Time window for statistics calculation
            
        Returns:
            Dictionary of performance statistics by operation type
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        with self._metrics_lock:
            # Filter metrics by time window
            recent_metrics = [
                m for m in self._metrics_buffer 
                if m.timestamp >= cutoff_time
            ]
            
            if operation_type:
                recent_metrics = [m for m in recent_metrics if m.operation_type == operation_type]
            
            # Group by operation type
            metrics_by_type = defaultdict(list)
            for metric in recent_metrics:
                metrics_by_type[metric.operation_type].append(metric)
            
            stats = {}
            for op_type, metrics in metrics_by_type.items():
                stats[op_type] = self._calculate_performance_stats(metrics)
            
            return stats
    
    def _calculate_performance_stats(self, metrics: List[EncryptionMetric]) -> PerformanceStats:
        """Calculate performance statistics from a list of metrics"""
        if not metrics:
            return PerformanceStats(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        
        successful = [m for m in metrics if m.success]
        failed = [m for m in metrics if not m.success]
        durations = [m.duration_ms for m in metrics]
        
        # Calculate time span for operations per second
        time_span_hours = (max(m.timestamp for m in metrics) - 
                          min(m.timestamp for m in metrics)).total_seconds() / 3600
        ops_per_second = len(metrics) / (time_span_hours * 3600) if time_span_hours > 0 else 0
        
        # Calculate percentiles
        sorted_durations = sorted(durations)
        p95_idx = int(len(sorted_durations) * 0.95)
        p99_idx = int(len(sorted_durations) * 0.99)
        
        return PerformanceStats(
            total_operations=len(metrics),
            successful_operations=len(successful),
            failed_operations=len(failed),
            avg_duration_ms=sum(durations) / len(durations),
            min_duration_ms=min(durations),
            max_duration_ms=max(durations),
            p95_duration_ms=sorted_durations[p95_idx] if sorted_durations else 0.0,
            p99_duration_ms=sorted_durations[p99_idx] if sorted_durations else 0.0,
            operations_per_second=ops_per_second,
            error_rate=len(failed) / len(metrics) if metrics else 0.0
        )
    
    def get_key_access_patterns(self, tenant_id: Optional[int] = None) -> List[KeyAccessPattern]:
        """
        Get key access patterns, optionally filtered by tenant
        
        Args:
            tenant_id: Optional tenant ID to filter patterns
            
        Returns:
            List of key access patterns
        """
        patterns = list(self._key_access_patterns.values())
        
        if tenant_id is not None:
            patterns = [p for p in patterns if p.tenant_id == tenant_id]
        
        return patterns
    
    def get_suspicious_activities(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Get suspicious activities detected in the specified time window
        
        Args:
            hours_back: Number of hours to look back
            
        Returns:
            List of suspicious activity events
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        return [
            activity for activity in self._suspicious_patterns
            if datetime.fromisoformat(activity['timestamp']) >= cutoff_time
        ]
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get overall health status of the encryption system
        
        Returns:
            Dictionary containing health status information
        """
        stats = self.get_performance_stats(time_window_hours=1)  # Last hour
        
        overall_error_rate = 0.0
        overall_avg_duration = 0.0
        total_operations = 0
        
        for op_stats in stats.values():
            total_operations += op_stats.total_operations
            overall_error_rate += op_stats.error_rate * op_stats.total_operations
            overall_avg_duration += op_stats.avg_duration_ms * op_stats.total_operations
        
        if total_operations > 0:
            overall_error_rate /= total_operations
            overall_avg_duration /= total_operations
        
        # Determine health status
        health_status = "healthy"
        issues = []
        
        if overall_error_rate > self.error_rate_threshold:
            health_status = "degraded"
            issues.append(f"High error rate: {overall_error_rate:.2%}")
        
        if overall_avg_duration > 1000:  # More than 1 second average
            health_status = "degraded"
            issues.append(f"High latency: {overall_avg_duration:.2f}ms")
        
        suspicious_count = len(self.get_suspicious_activities(hours_back=1))
        if suspicious_count > 0:
            health_status = "warning"
            issues.append(f"Suspicious activities detected: {suspicious_count}")
        
        return {
            'status': health_status,
            'timestamp': datetime.utcnow().isoformat(),
            'total_operations_last_hour': total_operations,
            'overall_error_rate': overall_error_rate,
            'overall_avg_duration_ms': overall_avg_duration,
            'suspicious_activities_count': suspicious_count,
            'issues': issues,
            'operation_stats': {op: asdict(stat) for op, stat in stats.items()}
        }
    
    def export_metrics(self, format_type: str = 'json', time_window_hours: int = 24) -> str:
        """
        Export metrics in specified format for external monitoring systems
        
        Args:
            format_type: Export format ('json', 'prometheus', 'csv')
            time_window_hours: Time window for metrics export
            
        Returns:
            Formatted metrics string
        """
        if format_type == 'json':
            return self._export_json_metrics(time_window_hours)
        elif format_type == 'prometheus':
            return self._export_prometheus_metrics(time_window_hours)
        elif format_type == 'csv':
            return self._export_csv_metrics(time_window_hours)
        else:
            raise EncryptionMonitoringError(f"Unsupported export format: {format_type}")
    
    def _export_json_metrics(self, time_window_hours: int) -> str:
        """Export metrics in JSON format"""
        import json
        
        stats = self.get_performance_stats(time_window_hours=time_window_hours)
        health = self.get_health_status()
        patterns = self.get_key_access_patterns()
        suspicious = self.get_suspicious_activities(hours_back=time_window_hours)
        
        export_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'time_window_hours': time_window_hours,
            'health_status': health,
            'performance_stats': {op: asdict(stat) for op, stat in stats.items()},
            'key_access_patterns': [asdict(p) for p in patterns],
            'suspicious_activities': suspicious
        }
        
        return json.dumps(export_data, indent=2, default=str)
    
    def _export_prometheus_metrics(self, time_window_hours: int) -> str:
        """Export metrics in Prometheus format"""
        stats = self.get_performance_stats(time_window_hours=time_window_hours)
        
        metrics_lines = []
        
        for op_type, stat in stats.items():
            metrics_lines.extend([
                f'encryption_operations_total{{operation="{op_type}"}} {stat.total_operations}',
                f'encryption_operations_successful{{operation="{op_type}"}} {stat.successful_operations}',
                f'encryption_operations_failed{{operation="{op_type}"}} {stat.failed_operations}',
                f'encryption_duration_avg_ms{{operation="{op_type}"}} {stat.avg_duration_ms}',
                f'encryption_duration_p95_ms{{operation="{op_type}"}} {stat.p95_duration_ms}',
                f'encryption_duration_p99_ms{{operation="{op_type}"}} {stat.p99_duration_ms}',
                f'encryption_error_rate{{operation="{op_type}"}} {stat.error_rate}',
                f'encryption_ops_per_second{{operation="{op_type}"}} {stat.operations_per_second}'
            ])
        
        return '\n'.join(metrics_lines)
    
    def _export_csv_metrics(self, time_window_hours: int) -> str:
        """Export metrics in CSV format"""
        import csv
        import io
        
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        with self._metrics_lock:
            recent_metrics = [
                m for m in self._metrics_buffer 
                if m.timestamp >= cutoff_time
            ]
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'timestamp', 'operation_type', 'tenant_id', 'duration_ms', 
            'success', 'data_size_bytes', 'error_type', 'key_id'
        ])
        
        # Write data
        for metric in recent_metrics:
            writer.writerow([
                metric.timestamp.isoformat(),
                metric.operation_type,
                metric.tenant_id,
                metric.duration_ms,
                metric.success,
                metric.data_size_bytes,
                metric.error_type,
                metric.key_id
            ])
        
        return output.getvalue()


# Global monitoring service instance
monitoring_service = EncryptionMonitoringService()