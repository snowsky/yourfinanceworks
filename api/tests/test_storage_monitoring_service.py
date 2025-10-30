"""
Tests for Storage Monitoring Service.

This module tests the storage monitoring, health checking, alerting,
and reporting functionality.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from services.storage_monitoring_service import (
    StorageMonitoringService,
    AlertSeverity,
    MonitoringMetric,
    StorageAlert,
    AlertingConfig,
    ProviderHealthMetrics,
    StorageUsageMetrics,
    PerformanceMetrics
)
from services.cloud_storage.provider import StorageProvider, HealthCheckResult
from models.models import StorageOperationLog, Tenant
from storage_config.cloud_storage_config import CloudStorageConfig


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.query.return_value.filter.return_value.all.return_value = []
    return db


@pytest.fixture
def monitoring_service(mock_db):
    """Create monitoring service instance."""
    config = CloudStorageConfig()
    service = StorageMonitoringService(mock_db, config)
    return service


@pytest.mark.asyncio
async def test_health_check_single_provider(monitoring_service):
    """Test health check for a single provider."""
    # Mock provider factory
    mock_provider = AsyncMock()
    mock_provider.health_check.return_value = HealthCheckResult(
        provider=StorageProvider.AWS_S3,
        healthy=True,
        response_time_ms=150,
        error_message=None
    )
    
    with patch.object(monitoring_service.provider_factory, 'get_provider', return_value=mock_provider):
        with patch.object(monitoring_service, '_calculate_provider_success_metrics', 
                         return_value={'success_rate': 0.98, 'error_count': 5, 'uptime_percentage': 99.5}):
            
            metrics = await monitoring_service.perform_health_check(StorageProvider.AWS_S3)
            
            assert metrics.provider == StorageProvider.AWS_S3
            assert metrics.is_healthy == True
            assert metrics.response_time_ms == 150
            assert metrics.success_rate_24h == 0.98
            assert metrics.error_count_24h == 5
            assert metrics.uptime_percentage == 99.5


@pytest.mark.asyncio
async def test_health_check_failure(monitoring_service):
    """Test health check when provider fails."""
    # Mock provider factory to return None (provider not configured)
    with patch.object(monitoring_service.provider_factory, 'get_provider', return_value=None):
        
        metrics = await monitoring_service.perform_health_check(StorageProvider.AWS_S3)
        
        assert metrics.provider == StorageProvider.AWS_S3
        assert metrics.is_healthy == False
        assert metrics.response_time_ms is None
        assert metrics.last_error == "Provider not configured"


@pytest.mark.asyncio
async def test_alert_generation(monitoring_service):
    """Test alert generation and notification."""
    # Configure alerting
    alerting_config = AlertingConfig(
        email_enabled=False,  # Disable email for testing
        webhook_enabled=False,  # Disable webhook for testing
        alert_cooldown_minutes=0  # Disable cooldown for testing
    )
    monitoring_service.configure_alerting(alerting_config)
    
    # Generate an alert
    alert = await monitoring_service._generate_alert(
        AlertSeverity.WARNING,
        MonitoringMetric.OPERATION_SUCCESS_RATE,
        "aws_s3",
        "tenant_1",
        "Low success rate detected",
        {"success_rate": 0.85, "threshold": 0.90},
        0.90,
        0.85
    )
    
    assert alert.severity == AlertSeverity.WARNING
    assert alert.metric == MonitoringMetric.OPERATION_SUCCESS_RATE
    assert alert.provider == "aws_s3"
    assert alert.tenant_id == "tenant_1"
    assert alert.threshold_value == 0.90
    assert alert.current_value == 0.85
    
    # Check that alert is stored
    active_alerts = monitoring_service.get_active_alerts()
    assert len(active_alerts) == 1
    assert active_alerts[0].id == alert.id


def test_alert_cooldown(monitoring_service):
    """Test alert cooldown functionality."""
    # Configure alerting with cooldown
    alerting_config = AlertingConfig(
        email_enabled=False,
        webhook_enabled=False,
        alert_cooldown_minutes=30
    )
    monitoring_service.configure_alerting(alerting_config)
    
    # Create a mock existing alert
    existing_alert = StorageAlert(
        id="test_alert_1",
        severity=AlertSeverity.WARNING,
        metric=MonitoringMetric.OPERATION_SUCCESS_RATE,
        provider="aws_s3",
        tenant_id="tenant_1",
        message="Test alert",
        details={},
        created_at=datetime.now() - timedelta(minutes=15)  # 15 minutes ago
    )
    monitoring_service._active_alerts["test_alert_1"] = existing_alert
    
    # Try to generate similar alert (should be suppressed)
    with patch.object(monitoring_service, 'send_alert_notification') as mock_send:
        asyncio.run(monitoring_service._generate_alert(
            AlertSeverity.WARNING,
            MonitoringMetric.OPERATION_SUCCESS_RATE,
            "aws_s3",
            "tenant_1",
            "Another low success rate alert",
            {"success_rate": 0.80}
        ))
        
        # Should not send notification for suppressed alert
        mock_send.assert_not_called()
    
    # Should still have only one alert
    assert len(monitoring_service.get_active_alerts()) == 1


def test_alert_resolution(monitoring_service):
    """Test alert resolution."""
    # Create an alert
    alert = StorageAlert(
        id="test_alert_1",
        severity=AlertSeverity.ERROR,
        metric=MonitoringMetric.HEALTH_STATUS,
        provider="aws_s3",
        tenant_id=None,
        message="Provider health check failed",
        details={}
    )
    monitoring_service._active_alerts["test_alert_1"] = alert
    
    # Resolve the alert
    resolved = monitoring_service.resolve_alert("test_alert_1", "Issue fixed")
    
    assert resolved == True
    assert alert.is_resolved == True
    assert alert.resolved_at is not None
    assert alert.details["resolution_note"] == "Issue fixed"
    
    # Should be moved to resolved alerts
    assert "test_alert_1" not in monitoring_service._active_alerts
    assert "test_alert_1" in monitoring_service._resolved_alerts


@pytest.mark.asyncio
async def test_usage_metrics_calculation(monitoring_service):
    """Test storage usage metrics calculation."""
    # Mock database query results
    mock_logs = [
        Mock(
            tenant_id=1,
            operation_type="upload",
            success=True,
            file_size=1024000,  # 1MB
            content_type="image/jpeg",
            provider="aws_s3",
            created_at=datetime.now() - timedelta(days=1)
        ),
        Mock(
            tenant_id=1,
            operation_type="upload",
            success=True,
            file_size=2048000,  # 2MB
            content_type="application/pdf",
            provider="local",
            created_at=datetime.now() - timedelta(days=2)
        )
    ]
    
    monitoring_service.db.query.return_value.filter.return_value.all.return_value = mock_logs
    
    # Calculate usage metrics
    usage_metrics = await monitoring_service.get_storage_usage_metrics("1")
    
    assert "1" in usage_metrics
    tenant_metrics = usage_metrics["1"]
    
    assert tenant_metrics.tenant_id == "1"
    assert tenant_metrics.total_files == 2
    assert tenant_metrics.total_size_bytes == 3072000  # 3MB
    assert "aws_s3" in tenant_metrics.files_by_provider
    assert "local" in tenant_metrics.files_by_provider
    assert tenant_metrics.files_by_provider["aws_s3"] == 1
    assert tenant_metrics.files_by_provider["local"] == 1


@pytest.mark.asyncio
async def test_performance_metrics_calculation(monitoring_service):
    """Test performance metrics calculation."""
    # Mock database query results
    mock_logs = [
        Mock(
            provider="aws_s3",
            operation_type="upload",
            success=True,
            duration_ms=150,
            created_at=datetime.now() - timedelta(hours=1)
        ),
        Mock(
            provider="aws_s3",
            operation_type="upload",
            success=True,
            duration_ms=200,
            created_at=datetime.now() - timedelta(hours=2)
        ),
        Mock(
            provider="aws_s3",
            operation_type="upload",
            success=False,
            duration_ms=5000,
            created_at=datetime.now() - timedelta(hours=3)
        )
    ]
    
    monitoring_service.db.query.return_value.filter.return_value.all.return_value = mock_logs
    
    # Calculate performance metrics
    performance_metrics = await monitoring_service.get_performance_metrics(
        provider="aws_s3",
        operation_type="upload",
        hours=24
    )
    
    assert len(performance_metrics) == 1
    metrics = performance_metrics[0]
    
    assert metrics.provider == "aws_s3"
    assert metrics.operation_type == "upload"
    assert metrics.sample_count == 3
    assert metrics.success_rate == 2/3  # 2 out of 3 successful
    assert metrics.error_rate == 1/3
    assert metrics.avg_latency_ms == (150 + 200 + 5000) / 3


@pytest.mark.asyncio
async def test_report_generation(monitoring_service):
    """Test report generation."""
    # Mock health check results
    mock_health_results = {
        StorageProvider.AWS_S3: ProviderHealthMetrics(
            provider=StorageProvider.AWS_S3,
            is_healthy=True,
            response_time_ms=150,
            success_rate_24h=0.98,
            error_count_24h=5,
            last_error=None,
            circuit_breaker_state="closed",
            uptime_percentage=99.5,
            last_check=datetime.now()
        )
    }
    
    with patch.object(monitoring_service, 'health_check_all_providers', return_value=mock_health_results):
        with patch.object(monitoring_service, 'get_performance_metrics', return_value=[]):
            with patch.object(monitoring_service, 'get_storage_usage_metrics', return_value={}):
                
                # Generate daily summary report
                report = await monitoring_service.generate_report(
                    "daily_summary",
                    tenant_id=None,
                    start_date=datetime.now() - timedelta(days=1),
                    end_date=datetime.now()
                )
                
                assert report.report_type == "daily_summary"
                assert report.tenant_id is None
                assert "health_overview" in report.data
                assert "operation_metrics" in report.data
                assert "usage_summary" in report.data
                assert "alerts" in report.data


def test_alert_statistics(monitoring_service):
    """Test alert statistics calculation."""
    # Create some test alerts
    alerts = [
        StorageAlert(
            id="alert_1",
            severity=AlertSeverity.CRITICAL,
            metric=MonitoringMetric.HEALTH_STATUS,
            provider="aws_s3",
            tenant_id=None,
            message="Critical alert",
            details={},
            created_at=datetime.now() - timedelta(hours=2),
            resolved_at=datetime.now() - timedelta(hours=1),
            is_resolved=True
        ),
        StorageAlert(
            id="alert_2",
            severity=AlertSeverity.WARNING,
            metric=MonitoringMetric.OPERATION_SUCCESS_RATE,
            provider="local",
            tenant_id="tenant_1",
            message="Warning alert",
            details={},
            created_at=datetime.now() - timedelta(hours=1)
        )
    ]
    
    # Add to monitoring service
    monitoring_service._resolved_alerts["alert_1"] = alerts[0]
    monitoring_service._active_alerts["alert_2"] = alerts[1]
    
    # Get statistics
    stats = monitoring_service.get_alert_statistics(days=1)
    
    assert stats["total_alerts"] == 2
    assert stats["active_alerts"] == 1
    assert stats["resolved_alerts"] == 1
    assert stats["resolution_rate"] == 0.5
    assert stats["by_severity"]["critical"] == 1
    assert stats["by_severity"]["warning"] == 1
    assert stats["by_provider"]["aws_s3"] == 1
    assert stats["by_provider"]["local"] == 1


def test_monitoring_summary(monitoring_service):
    """Test monitoring summary generation."""
    # Add some mock health cache data
    monitoring_service._health_cache[StorageProvider.AWS_S3] = ProviderHealthMetrics(
        provider=StorageProvider.AWS_S3,
        is_healthy=True,
        response_time_ms=150,
        success_rate_24h=0.98,
        error_count_24h=5,
        last_error=None,
        circuit_breaker_state="closed",
        uptime_percentage=99.5,
        last_check=datetime.now()
    )
    
    monitoring_service._health_cache[StorageProvider.LOCAL] = ProviderHealthMetrics(
        provider=StorageProvider.LOCAL,
        is_healthy=False,
        response_time_ms=None,
        success_rate_24h=0.85,
        error_count_24h=15,
        last_error="Connection failed",
        circuit_breaker_state="open",
        uptime_percentage=85.0,
        last_check=datetime.now()
    )
    
    # Add some alerts
    monitoring_service._active_alerts["test_alert"] = StorageAlert(
        id="test_alert",
        severity=AlertSeverity.ERROR,
        metric=MonitoringMetric.HEALTH_STATUS,
        provider="local",
        tenant_id=None,
        message="Test alert",
        details={}
    )
    
    # Get summary
    summary = monitoring_service.get_monitoring_summary()
    
    assert summary["overall_health"]["total_providers"] == 2
    assert summary["overall_health"]["healthy_providers"] == 1
    assert summary["overall_health"]["health_percentage"] == 50.0
    
    assert "aws_s3" in summary["provider_health"]
    assert "local" in summary["provider_health"]
    assert summary["provider_health"]["aws_s3"]["healthy"] == True
    assert summary["provider_health"]["local"]["healthy"] == False
    
    assert summary["alerts"]["total"] == 1
    assert summary["alerts"]["error"] == 1
    
    assert summary["cache_status"]["health_cache_size"] == 2
    assert summary["cache_status"]["active_alerts"] == 1


@pytest.mark.asyncio
async def test_auto_resolve_alerts(monitoring_service):
    """Test automatic alert resolution."""
    # Create a health alert
    alert = StorageAlert(
        id="health_alert",
        severity=AlertSeverity.ERROR,
        metric=MonitoringMetric.HEALTH_STATUS,
        provider="aws_s3",
        tenant_id=None,
        message="Provider unhealthy",
        details={}
    )
    monitoring_service._active_alerts["health_alert"] = alert
    
    # Mock healthy provider state
    monitoring_service._health_cache[StorageProvider.AWS_S3] = ProviderHealthMetrics(
        provider=StorageProvider.AWS_S3,
        is_healthy=True,
        response_time_ms=150,
        success_rate_24h=0.98,
        error_count_24h=0,
        last_error=None,
        circuit_breaker_state="closed",
        uptime_percentage=99.5,
        last_check=datetime.now(),
        consecutive_successes=5  # Enough to trigger auto-resolution
    )
    
    # Run auto-resolution
    resolved_ids = monitoring_service.auto_resolve_alerts()
    
    assert "health_alert" in resolved_ids
    assert "health_alert" not in monitoring_service._active_alerts
    assert "health_alert" in monitoring_service._resolved_alerts
    assert monitoring_service._resolved_alerts["health_alert"].is_resolved == True


if __name__ == "__main__":
    pytest.main([__file__])