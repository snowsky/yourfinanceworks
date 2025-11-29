"""
Encryption Security Alerting Service

This service provides comprehensive security alerting for encryption operations,
including failure detection, unauthorized access monitoring, and anomaly detection.
"""

import logging
import json
import smtplib
import requests
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import threading
import time
from collections import defaultdict, deque

from encryption_config import EncryptionConfig
from core.exceptions.encryption_exceptions import AlertingError
from core.services.encryption_monitoring_service import EncryptionMonitoringService


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of security alerts"""
    ENCRYPTION_FAILURE = "encryption_failure"
    DECRYPTION_FAILURE = "decryption_failure"
    KEY_ACCESS_FAILURE = "key_access_failure"
    UNAUTHORIZED_KEY_ACCESS = "unauthorized_key_access"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    HIGH_ERROR_RATE = "high_error_rate"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    KEY_ROTATION_FAILURE = "key_rotation_failure"
    COMPLIANCE_VIOLATION = "compliance_violation"
    SECURITY_INCIDENT = "security_incident"


class AlertChannel(Enum):
    """Alert delivery channels"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    PAGERDUTY = "pagerduty"
    LOG = "log"


@dataclass
class SecurityAlert:
    """Security alert data structure"""
    id: str
    timestamp: datetime
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    tenant_id: Optional[int]
    affected_systems: List[str]
    details: Dict[str, Any]
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None
    resolution_notes: Optional[str] = None


@dataclass
class AlertRule:
    """Alert rule configuration"""
    id: str
    name: str
    alert_type: AlertType
    severity: AlertSeverity
    condition: str  # JSON string describing the condition
    threshold: float
    time_window_minutes: int
    channels: List[AlertChannel]
    enabled: bool = True
    tenant_id: Optional[int] = None  # None for global rules


@dataclass
class AlertChannelConfig:
    """Configuration for alert delivery channels"""
    channel: AlertChannel
    config: Dict[str, Any]
    enabled: bool = True


class EncryptionAlertingService:
    """
    Service for security alerting related to encryption operations
    """
    
    def __init__(self, monitoring_service: EncryptionMonitoringService):
        self.logger = logging.getLogger(__name__)
        self.config = EncryptionConfig()
        self.monitoring_service = monitoring_service
        
        # Alert storage
        self._alerts: List[SecurityAlert] = []
        self._alert_rules: Dict[str, AlertRule] = {}
        self._channel_configs: Dict[AlertChannel, AlertChannelConfig] = {}
        
        # Alert processing
        self._alert_queue: deque = deque()
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_processing = threading.Event()
        
        # Rate limiting
        self._alert_rate_limits: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Initialize default alert rules
        self._initialize_default_rules()
        
        # Initialize default channel configurations
        self._initialize_default_channels()
        
        # Start alert processing thread
        self._start_alert_processing()
        
        self.logger.info("Encryption alerting service initialized")
    
    def _initialize_default_rules(self):
        """Initialize default alert rules"""
        default_rules = [
            AlertRule(
                id="high_encryption_error_rate",
                name="High Encryption Error Rate",
                alert_type=AlertType.HIGH_ERROR_RATE,
                severity=AlertSeverity.HIGH,
                condition=json.dumps({"error_rate": ">", "threshold": 0.05}),
                threshold=0.05,
                time_window_minutes=5,
                channels=[AlertChannel.EMAIL, AlertChannel.LOG]
            ),
            AlertRule(
                id="encryption_performance_degradation",
                name="Encryption Performance Degradation",
                alert_type=AlertType.PERFORMANCE_DEGRADATION,
                severity=AlertSeverity.MEDIUM,
                condition=json.dumps({"avg_duration_ms": ">", "threshold": 1000}),
                threshold=1000.0,
                time_window_minutes=10,
                channels=[AlertChannel.EMAIL, AlertChannel.LOG]
            ),
            AlertRule(
                id="unauthorized_key_access",
                name="Unauthorized Key Access Attempt",
                alert_type=AlertType.UNAUTHORIZED_KEY_ACCESS,
                severity=AlertSeverity.CRITICAL,
                condition=json.dumps({"failed_key_access": ">", "threshold": 3}),
                threshold=3.0,
                time_window_minutes=1,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.LOG]
            ),
            AlertRule(
                id="key_rotation_failure",
                name="Key Rotation Failure",
                alert_type=AlertType.KEY_ROTATION_FAILURE,
                severity=AlertSeverity.CRITICAL,
                condition=json.dumps({"key_rotation_failed": "==", "threshold": 1}),
                threshold=1.0,
                time_window_minutes=60,
                channels=[AlertChannel.EMAIL, AlertChannel.PAGERDUTY, AlertChannel.LOG]
            ),
            AlertRule(
                id="suspicious_encryption_activity",
                name="Suspicious Encryption Activity",
                alert_type=AlertType.SUSPICIOUS_ACTIVITY,
                severity=AlertSeverity.HIGH,
                condition=json.dumps({"unusual_pattern": "==", "threshold": 1}),
                threshold=1.0,
                time_window_minutes=15,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.LOG]
            )
        ]
        
        for rule in default_rules:
            self._alert_rules[rule.id] = rule
    
    def _initialize_default_channels(self):
        """Initialize default alert channel configurations"""
        self._channel_configs[AlertChannel.LOG] = AlertChannelConfig(
            channel=AlertChannel.LOG,
            config={},
            enabled=True
        )
        
        self._channel_configs[AlertChannel.EMAIL] = AlertChannelConfig(
            channel=AlertChannel.EMAIL,
            config={
                "smtp_server": "localhost",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "from_email": "alerts@example.com",
                "to_emails": ["admin@example.com"]
            },
            enabled=False  # Disabled by default, needs configuration
        )
        
        self._channel_configs[AlertChannel.SLACK] = AlertChannelConfig(
            channel=AlertChannel.SLACK,
            config={
                "webhook_url": "",
                "channel": "#security-alerts",
                "username": "Encryption Alert Bot"
            },
            enabled=False  # Disabled by default, needs configuration
        )
        
        self._channel_configs[AlertChannel.WEBHOOK] = AlertChannelConfig(
            channel=AlertChannel.WEBHOOK,
            config={
                "url": "",
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "timeout": 30
            },
            enabled=False  # Disabled by default, needs configuration
        )
    
    def _start_alert_processing(self):
        """Start the alert processing thread"""
        self._processing_thread = threading.Thread(
            target=self._process_alerts,
            daemon=True,
            name="EncryptionAlertProcessor"
        )
        self._processing_thread.start()
    
    def _process_alerts(self):
        """Process alerts from the queue"""
        while not self._stop_processing.is_set():
            try:
                if self._alert_queue:
                    alert = self._alert_queue.popleft()
                    self._deliver_alert(alert)
                else:
                    time.sleep(1)  # Wait for alerts
            except Exception as e:
                self.logger.error(f"Error processing alert: {str(e)}")
    
    def trigger_alert(self, alert_type: AlertType, severity: AlertSeverity,
                     title: str, description: str, tenant_id: Optional[int] = None,
                     affected_systems: Optional[List[str]] = None,
                     details: Optional[Dict[str, Any]] = None):
        """
        Trigger a security alert
        
        Args:
            alert_type: Type of alert
            severity: Severity level
            title: Alert title
            description: Alert description
            tenant_id: Optional tenant ID
            affected_systems: List of affected systems
            details: Additional alert details
        """
        import uuid
        
        alert = SecurityAlert(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            tenant_id=tenant_id,
            affected_systems=affected_systems or [],
            details=details or {}
        )
        
        # Check rate limiting
        if self._is_rate_limited(alert):
            self.logger.debug(f"Alert rate limited: {alert.title}")
            return
        
        # Store alert
        self._alerts.append(alert)
        
        # Queue for delivery
        self._alert_queue.append(alert)
        
        self.logger.warning(f"Security alert triggered: {alert.title} ({alert.severity.value})")
    
    def _is_rate_limited(self, alert: SecurityAlert) -> bool:
        """Check if alert should be rate limited"""
        rate_limit_key = f"{alert.alert_type.value}:{alert.tenant_id}"
        now = datetime.utcnow()
        
        # Clean old entries (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        rate_limit_queue = self._alert_rate_limits[rate_limit_key]
        
        while rate_limit_queue and rate_limit_queue[0] < cutoff:
            rate_limit_queue.popleft()
        
        # Check if we've exceeded the rate limit (max 10 alerts per hour per type/tenant)
        if len(rate_limit_queue) >= 10:
            return True
        
        # Add current alert to rate limit tracking
        rate_limit_queue.append(now)
        return False
    
    def _deliver_alert(self, alert: SecurityAlert):
        """Deliver alert through configured channels"""
        # Find applicable alert rules
        applicable_rules = self._find_applicable_rules(alert)
        
        if not applicable_rules:
            # Use default channels for unmatched alerts
            channels = [AlertChannel.LOG]
        else:
            # Collect all channels from applicable rules
            channels = set()
            for rule in applicable_rules:
                channels.update(rule.channels)
            channels = list(channels)
        
        # Deliver through each channel
        for channel in channels:
            try:
                self._deliver_to_channel(alert, channel)
            except Exception as e:
                self.logger.error(f"Failed to deliver alert to {channel.value}: {str(e)}")
    
    def _find_applicable_rules(self, alert: SecurityAlert) -> List[AlertRule]:
        """Find alert rules that apply to the given alert"""
        applicable_rules = []
        
        for rule in self._alert_rules.values():
            if not rule.enabled:
                continue
            
            # Check alert type match
            if rule.alert_type != alert.alert_type:
                continue
            
            # Check tenant match (None means global rule)
            if rule.tenant_id is not None and rule.tenant_id != alert.tenant_id:
                continue
            
            applicable_rules.append(rule)
        
        return applicable_rules
    
    def _deliver_to_channel(self, alert: SecurityAlert, channel: AlertChannel):
        """Deliver alert to a specific channel"""
        channel_config = self._channel_configs.get(channel)
        
        if not channel_config or not channel_config.enabled:
            return
        
        if channel == AlertChannel.LOG:
            self._deliver_to_log(alert)
        elif channel == AlertChannel.EMAIL:
            self._deliver_to_email(alert, channel_config)
        elif channel == AlertChannel.SLACK:
            self._deliver_to_slack(alert, channel_config)
        elif channel == AlertChannel.WEBHOOK:
            self._deliver_to_webhook(alert, channel_config)
        else:
            self.logger.warning(f"Unsupported alert channel: {channel.value}")
    
    def _deliver_to_log(self, alert: SecurityAlert):
        """Deliver alert to application logs"""
        log_level = {
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }.get(alert.severity, logging.WARNING)
        
        self.logger.log(
            log_level,
            f"SECURITY ALERT [{alert.severity.value.upper()}]: {alert.title} - {alert.description}"
        )
    
    def _deliver_to_email(self, alert: SecurityAlert, channel_config: AlertChannelConfig):
        """Deliver alert via email"""
        config = channel_config.config
        
        if not config.get("to_emails"):
            return
        
        try:
            msg = MimeMultipart()
            msg['From'] = config.get("from_email", "alerts@example.com")
            msg['To'] = ", ".join(config["to_emails"])
            msg['Subject'] = f"[{alert.severity.value.upper()}] Encryption Security Alert: {alert.title}"
            
            body = self._format_alert_email(alert)
            msg.attach(MimeText(body, 'html'))
            
            server = smtplib.SMTP(config.get("smtp_server", "localhost"), 
                                config.get("smtp_port", 587))
            
            if config.get("username") and config.get("password"):
                server.starttls()
                server.login(config["username"], config["password"])
            
            server.send_message(msg)
            server.quit()
            
            self.logger.info(f"Alert email sent for: {alert.title}")
            
        except Exception as e:
            self.logger.error(f"Failed to send alert email: {str(e)}")
    
    def _format_alert_email(self, alert: SecurityAlert) -> str:
        """Format alert for email delivery"""
        severity_colors = {
            AlertSeverity.LOW: "#28a745",
            AlertSeverity.MEDIUM: "#ffc107",
            AlertSeverity.HIGH: "#fd7e14",
            AlertSeverity.CRITICAL: "#dc3545"
        }
        
        color = severity_colors.get(alert.severity, "#6c757d")
        
        html = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <div style="background-color: {color}; color: white; padding: 20px; border-radius: 5px 5px 0 0;">
                    <h2 style="margin: 0;">🔒 Encryption Security Alert</h2>
                    <p style="margin: 5px 0 0 0; font-size: 14px;">Severity: {alert.severity.value.upper()}</p>
                </div>
                
                <div style="border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 5px 5px;">
                    <h3 style="color: #333; margin-top: 0;">{alert.title}</h3>
                    <p style="color: #666; line-height: 1.5;">{alert.description}</p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold; width: 150px;">Alert ID:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.id}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Timestamp:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.timestamp.isoformat()}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Alert Type:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.alert_type.value}</td>
                        </tr>
                        {f'<tr><td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Tenant ID:</td><td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.tenant_id}</td></tr>' if alert.tenant_id else ''}
                        {f'<tr><td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Affected Systems:</td><td style="padding: 8px; border-bottom: 1px solid #eee;">{", ".join(alert.affected_systems)}</td></tr>' if alert.affected_systems else ''}
                    </table>
                    
                    {f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;"><h4 style="margin-top: 0;">Additional Details:</h4><pre style="white-space: pre-wrap; font-size: 12px;">{json.dumps(alert.details, indent=2)}</pre></div>' if alert.details else ''}
                    
                    <p style="color: #666; font-size: 12px; margin-top: 30px;">
                        This is an automated security alert from the Encryption Monitoring System.
                        Please investigate this alert promptly.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _deliver_to_slack(self, alert: SecurityAlert, channel_config: AlertChannelConfig):
        """Deliver alert to Slack"""
        config = channel_config.config
        webhook_url = config.get("webhook_url")
        
        if not webhook_url:
            return
        
        try:
            severity_colors = {
                AlertSeverity.LOW: "good",
                AlertSeverity.MEDIUM: "warning",
                AlertSeverity.HIGH: "danger",
                AlertSeverity.CRITICAL: "danger"
            }
            
            severity_emojis = {
                AlertSeverity.LOW: "🟢",
                AlertSeverity.MEDIUM: "🟡",
                AlertSeverity.HIGH: "🟠",
                AlertSeverity.CRITICAL: "🔴"
            }
            
            color = severity_colors.get(alert.severity, "warning")
            emoji = severity_emojis.get(alert.severity, "⚠️")
            
            fields = [
                {
                    "title": "Alert Type",
                    "value": alert.alert_type.value,
                    "short": True
                },
                {
                    "title": "Severity",
                    "value": alert.severity.value.upper(),
                    "short": True
                },
                {
                    "title": "Timestamp",
                    "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "short": True
                }
            ]
            
            if alert.tenant_id:
                fields.append({
                    "title": "Tenant ID",
                    "value": str(alert.tenant_id),
                    "short": True
                })
            
            if alert.affected_systems:
                fields.append({
                    "title": "Affected Systems",
                    "value": ", ".join(alert.affected_systems),
                    "short": False
                })
            
            payload = {
                "channel": config.get("channel", "#security-alerts"),
                "username": config.get("username", "Encryption Alert Bot"),
                "icon_emoji": ":lock:",
                "attachments": [
                    {
                        "color": color,
                        "title": f"{emoji} {alert.title}",
                        "text": alert.description,
                        "fields": fields,
                        "footer": "Encryption Security Monitoring",
                        "ts": int(alert.timestamp.timestamp())
                    }
                ]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            
            self.logger.info(f"Alert sent to Slack for: {alert.title}")
            
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {str(e)}")
    
    def _deliver_to_webhook(self, alert: SecurityAlert, channel_config: AlertChannelConfig):
        """Deliver alert to webhook"""
        config = channel_config.config
        url = config.get("url")
        
        if not url:
            return
        
        try:
            payload = {
                "alert": asdict(alert),
                "timestamp": alert.timestamp.isoformat()
            }
            
            headers = config.get("headers", {"Content-Type": "application/json"})
            method = config.get("method", "POST").upper()
            timeout = config.get("timeout", 30)
            
            if method == "POST":
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            elif method == "PUT":
                response = requests.put(url, json=payload, headers=headers, timeout=timeout)
            else:
                raise AlertingError(f"Unsupported webhook method: {method}")
            
            response.raise_for_status()
            
            self.logger.info(f"Alert sent to webhook for: {alert.title}")
            
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {str(e)}")
    
    def configure_channel(self, channel: AlertChannel, config: Dict[str, Any], 
                         enabled: bool = True):
        """
        Configure an alert delivery channel
        
        Args:
            channel: Alert channel to configure
            config: Channel configuration
            enabled: Whether the channel is enabled
        """
        self._channel_configs[channel] = AlertChannelConfig(
            channel=channel,
            config=config,
            enabled=enabled
        )
        
        self.logger.info(f"Configured alert channel: {channel.value}")
    
    def add_alert_rule(self, rule: AlertRule):
        """
        Add a new alert rule
        
        Args:
            rule: Alert rule to add
        """
        self._alert_rules[rule.id] = rule
        self.logger.info(f"Added alert rule: {rule.name}")
    
    def remove_alert_rule(self, rule_id: str):
        """
        Remove an alert rule
        
        Args:
            rule_id: ID of the rule to remove
        """
        if rule_id in self._alert_rules:
            del self._alert_rules[rule_id]
            self.logger.info(f"Removed alert rule: {rule_id}")
    
    def get_alerts(self, tenant_id: Optional[int] = None, 
                  alert_type: Optional[AlertType] = None,
                  severity: Optional[AlertSeverity] = None,
                  resolved: Optional[bool] = None,
                  limit: int = 100) -> List[SecurityAlert]:
        """
        Get alerts with optional filtering
        
        Args:
            tenant_id: Optional tenant ID filter
            alert_type: Optional alert type filter
            severity: Optional severity filter
            resolved: Optional resolved status filter
            limit: Maximum number of alerts to return
            
        Returns:
            List of alerts matching the criteria
        """
        filtered_alerts = self._alerts
        
        if tenant_id is not None:
            filtered_alerts = [a for a in filtered_alerts if a.tenant_id == tenant_id]
        
        if alert_type is not None:
            filtered_alerts = [a for a in filtered_alerts if a.alert_type == alert_type]
        
        if severity is not None:
            filtered_alerts = [a for a in filtered_alerts if a.severity == severity]
        
        if resolved is not None:
            filtered_alerts = [a for a in filtered_alerts if a.resolved == resolved]
        
        # Sort by timestamp (newest first) and apply limit
        filtered_alerts.sort(key=lambda x: x.timestamp, reverse=True)
        
        return filtered_alerts[:limit]
    
    def resolve_alert(self, alert_id: str, resolution_notes: str):
        """
        Mark an alert as resolved
        
        Args:
            alert_id: ID of the alert to resolve
            resolution_notes: Notes about the resolution
        """
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.resolved = True
                alert.resolution_timestamp = datetime.utcnow()
                alert.resolution_notes = resolution_notes
                
                self.logger.info(f"Resolved alert: {alert.title}")
                return
        
        raise AlertingError(f"Alert not found: {alert_id}")
    
    def get_alert_statistics(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Get alert statistics for the specified time period
        
        Args:
            hours_back: Number of hours to look back
            
        Returns:
            Dictionary containing alert statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        recent_alerts = [a for a in self._alerts if a.timestamp >= cutoff_time]
        
        stats = {
            'total_alerts': len(recent_alerts),
            'resolved_alerts': len([a for a in recent_alerts if a.resolved]),
            'unresolved_alerts': len([a for a in recent_alerts if not a.resolved]),
            'alerts_by_severity': {},
            'alerts_by_type': {},
            'alerts_by_tenant': {},
            'time_period_hours': hours_back
        }
        
        # Count by severity
        for severity in AlertSeverity:
            count = len([a for a in recent_alerts if a.severity == severity])
            stats['alerts_by_severity'][severity.value] = count
        
        # Count by type
        for alert_type in AlertType:
            count = len([a for a in recent_alerts if a.alert_type == alert_type])
            stats['alerts_by_type'][alert_type.value] = count
        
        # Count by tenant
        tenant_counts = defaultdict(int)
        for alert in recent_alerts:
            tenant_id = alert.tenant_id or 'global'
            tenant_counts[str(tenant_id)] += 1
        stats['alerts_by_tenant'] = dict(tenant_counts)
        
        return stats
    
    def shutdown(self):
        """Shutdown the alerting service"""
        self._stop_processing.set()
        if self._processing_thread:
            self._processing_thread.join(timeout=5)
        
        self.logger.info("Encryption alerting service shutdown")


# Global alerting service instance
def get_alerting_service() -> EncryptionAlertingService:
    """Get the alerting service instance"""
    from core.services.encryption_monitoring_service import monitoring_service
    
    return EncryptionAlertingService(monitoring_service)