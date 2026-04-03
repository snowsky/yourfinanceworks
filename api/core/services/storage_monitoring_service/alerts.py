"""
Storage alerts mixin for StorageMonitoringService.
"""

import logging
import time
import json
import statistics
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict

from core.interfaces.storage_provider import StorageProvider

from ._shared import (
    EMAIL_AVAILABLE,
    MimeText,
    MimeMultipart,
    smtplib,
    AlertSeverity,
    MonitoringMetric,
    StorageAlert,
    AlertingConfig,
    ProviderHealthMetrics,
    StorageUsageMetrics,
    PerformanceMetrics,
)

logger = logging.getLogger(__name__)


class StorageAlertsMixin:
    """Mixin providing alert management methods for StorageMonitoringService."""

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
