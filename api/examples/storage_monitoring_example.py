#!/usr/bin/env python3
"""
Storage Monitoring Service Usage Example.

This example demonstrates how to use the Storage Monitoring Service
for health checking, alerting, and reporting.
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from services.storage_monitoring_service import (
    StorageMonitoringService,
    AlertSeverity,
    MonitoringMetric,
    AlertingConfig
)
from services.cloud_storage.provider import StorageProvider
from settings.cloud_storage_config import CloudStorageConfig


async def main():
    """Main example function."""
    
    # Initialize the monitoring service
    # In a real application, you would pass a real database session
    db = None  # Replace with actual database session
    config = CloudStorageConfig()
    
    monitoring_service = StorageMonitoringService(db, config)
    
    print("=== Storage Monitoring Service Example ===\n")
    
    # 1. Configure Alerting
    print("1. Configuring alerting...")
    alerting_config = AlertingConfig(
        email_enabled=True,
        email_smtp_server="smtp.gmail.com",
        email_smtp_port=587,
        email_username="alerts@yourcompany.com",
        email_password="your-app-password",
        email_from_address="alerts@yourcompany.com",
        email_to_addresses=["admin@yourcompany.com", "ops@yourcompany.com"],
        
        webhook_enabled=True,
        webhook_url="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
        webhook_headers={"Content-Type": "application/json"},
        
        escalation_enabled=True,
        escalation_interval_minutes=60,
        max_escalation_level=3,
        
        alert_cooldown_minutes=30
    )
    
    monitoring_service.configure_alerting(alerting_config)
    print("✓ Alerting configured")
    
    # 2. Add custom alert callback
    def custom_alert_handler(alert):
        """Custom alert handler function."""
        print(f"🚨 Custom Alert Handler: {alert.severity.value} - {alert.message}")
        
        # You could integrate with other systems here:
        # - Send to PagerDuty
        # - Update status page
        # - Log to external monitoring system
        # - etc.
    
    monitoring_service.add_alert_callback(custom_alert_handler)
    print("✓ Custom alert handler registered")
    
    # 3. Perform Health Checks
    print("\n2. Performing health checks...")
    try:
        # Check all providers
        health_results = await monitoring_service.health_check_all_providers(force_check=True)
        
        for provider, metrics in health_results.items():
            status = "✓ Healthy" if metrics.is_healthy else "✗ Unhealthy"
            print(f"   {provider.value}: {status} (Response: {metrics.response_time_ms}ms)")
    
    except Exception as e:
        print(f"   Health check failed: {e}")
    
    # 4. Generate Sample Alert
    print("\n3. Generating sample alert...")
    sample_alert = await monitoring_service._generate_alert(
        AlertSeverity.WARNING,
        MonitoringMetric.OPERATION_SUCCESS_RATE,
        "aws_s3",
        "tenant_123",
        "Success rate dropped below threshold",
        {
            "current_success_rate": 0.85,
            "threshold": 0.90,
            "time_period": "last_24_hours"
        },
        threshold_value=0.90,
        current_value=0.85
    )
    print(f"✓ Generated alert: {sample_alert.id}")
    
    # 5. Check Active Alerts
    print("\n4. Checking active alerts...")
    active_alerts = monitoring_service.get_active_alerts()
    print(f"   Active alerts: {len(active_alerts)}")
    
    for alert in active_alerts:
        print(f"   - {alert.severity.value}: {alert.message}")
    
    # 6. Get Alert Statistics
    print("\n5. Getting alert statistics...")
    alert_stats = monitoring_service.get_alert_statistics(days=7)
    print(f"   Total alerts (7 days): {alert_stats['total_alerts']}")
    print(f"   Resolution rate: {alert_stats['resolution_rate']:.2%}")
    print(f"   Average resolution time: {alert_stats['avg_resolution_time_minutes']:.1f} minutes")
    
    # 7. Generate Reports
    print("\n6. Generating reports...")
    try:
        # Daily summary report
        daily_report = await monitoring_service.generate_report(
            "daily_summary",
            tenant_id=None,
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now()
        )
        print(f"✓ Generated daily summary report: {daily_report.report_id}")
        
        # Weekly performance report
        weekly_report = await monitoring_service.generate_report(
            "weekly_performance",
            tenant_id=None,
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now()
        )
        print(f"✓ Generated weekly performance report: {weekly_report.report_id}")
        
    except Exception as e:
        print(f"   Report generation failed: {e}")
    
    # 8. Export Report
    print("\n7. Exporting reports...")
    reports = monitoring_service.list_reports(limit=1)
    if reports:
        report = reports[0]
        
        # Export as JSON
        json_export = monitoring_service.export_report(report.report_id, "json")
        print(f"✓ Exported report as JSON ({len(json_export)} characters)")
        
        # Export as HTML
        html_export = monitoring_service.export_report(report.report_id, "html")
        print(f"✓ Exported report as HTML ({len(html_export)} characters)")
    
    # 9. Get Monitoring Summary
    print("\n8. Getting monitoring summary...")
    summary = monitoring_service.get_monitoring_summary()
    
    print(f"   Overall health: {summary['overall_health']['health_percentage']:.1f}%")
    print(f"   Active alerts: {summary['alerts']['total']}")
    print(f"   Healthy providers: {summary['overall_health']['healthy_providers']}/{summary['overall_health']['total_providers']}")
    
    # 10. Run Monitoring Cycle
    print("\n9. Running complete monitoring cycle...")
    try:
        cycle_results = await monitoring_service.run_monitoring_cycle()
        print(f"✓ Monitoring cycle completed in {cycle_results['cycle_duration_seconds']:.2f} seconds")
        print(f"   Health checks: {len(cycle_results['health_checks'])}")
        print(f"   Performance metrics: {len(cycle_results['performance_metrics'])}")
        print(f"   Usage metrics: {len(cycle_results['usage_metrics'])}")
        print(f"   New alerts: {cycle_results['alerts_generated']}")
        
    except Exception as e:
        print(f"   Monitoring cycle failed: {e}")
    
    # 11. Resolve Alert
    print("\n10. Resolving sample alert...")
    if active_alerts:
        alert_to_resolve = active_alerts[0]
        resolved = monitoring_service.resolve_alert(
            alert_to_resolve.id, 
            "Issue resolved by manual intervention"
        )
        print(f"✓ Alert resolved: {resolved}")
    
    # 12. Auto-resolve Alerts
    print("\n11. Running auto-resolution...")
    auto_resolved = monitoring_service.auto_resolve_alerts()
    print(f"✓ Auto-resolved {len(auto_resolved)} alerts")
    
    # 13. Escalate Alerts
    print("\n12. Checking for alert escalation...")
    escalated = await monitoring_service.escalate_alerts()
    print(f"✓ Escalated {len(escalated)} alerts")
    
    print("\n=== Example completed successfully! ===")


def setup_periodic_monitoring():
    """
    Example of how to set up periodic monitoring in a real application.
    """
    import threading
    import time
    
    def monitoring_worker():
        """Background worker for periodic monitoring."""
        while True:
            try:
                # Run monitoring cycle every 5 minutes
                asyncio.run(monitoring_service.run_monitoring_cycle())
                
                # Run escalation check every 15 minutes
                if int(time.time()) % 900 == 0:  # Every 15 minutes
                    asyncio.run(monitoring_service.escalate_alerts())
                
                # Auto-resolve alerts every 10 minutes
                if int(time.time()) % 600 == 0:  # Every 10 minutes
                    monitoring_service.auto_resolve_alerts()
                
                # Clean up old reports daily
                if int(time.time()) % 86400 == 0:  # Every 24 hours
                    monitoring_service.cleanup_old_reports(days_to_keep=30)
                
            except Exception as e:
                print(f"Monitoring worker error: {e}")
            
            time.sleep(300)  # Sleep for 5 minutes
    
    # Start monitoring worker in background thread
    monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
    monitoring_thread.start()
    
    print("✓ Periodic monitoring started in background")


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
    
    # Uncomment to set up periodic monitoring
    # setup_periodic_monitoring()