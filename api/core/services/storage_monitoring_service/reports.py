"""
Storage reports mixin for StorageMonitoringService.
"""

import logging
import time
import json
import statistics
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from ._shared import (
    AlertSeverity,
    StorageReport,
)

logger = logging.getLogger(__name__)


class StorageReportsMixin:
    """Mixin providing report generation methods for StorageMonitoringService."""

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
