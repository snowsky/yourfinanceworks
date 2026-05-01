"""
Scheduled Job Alerting Service

Evaluates alert conditions against scheduled report execution results
and dispatches notifications when conditions are met.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models.models_per_tenant import (
    ScheduledJobAlert,
    ScheduledJobAlertHistory,
    ScheduledReport,
)
from core.schemas.scheduled_job_alerts import (
    ScheduledJobAlertCreate,
    ScheduledJobAlertUpdate,
    ScheduledJobAlertResponse,
    AlertCondition,
    AlertOperator,
)
from core.schemas.report import ReportResult

logger = logging.getLogger(__name__)


class ScheduledJobAlertingService:
    """
    Service for managing and evaluating scheduled job alert rules.

    Responsibilities:
    - CRUD operations for alert rules
    - Evaluating alert conditions against report outputs
    - Dispatching notifications on triggered alerts
    - Cooldown management to prevent alert storms
    """

    def __init__(self, db: Session):
        self.db = db

    # --- CRUD Operations ---

    def create_alert(self, data: ScheduledJobAlertCreate, user_id: int) -> ScheduledJobAlert:
        """Create a new alert rule for a scheduled report."""
        # Verify the scheduled report exists
        scheduled_report = self.db.query(ScheduledReport).filter(
            ScheduledReport.id == data.scheduled_report_id
        ).first()
        if not scheduled_report:
            raise ValueError(f"Scheduled report {data.scheduled_report_id} not found")

        alert = ScheduledJobAlert(
            scheduled_report_id=data.scheduled_report_id,
            name=data.name,
            description=data.description,
            condition=data.condition.model_dump(),
            notification_channels=[ch.value for ch in data.notification_channels],
            recipients=data.recipients,
            severity=data.severity.value,
            is_active=data.is_active if data.is_active is not None else True,
            cooldown_minutes=data.cooldown_minutes or 60,
            created_by=user_id,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_alert(self, alert_id: int, user_id: int) -> ScheduledJobAlert:
        """Get a specific alert by ID."""
        alert = self.db.query(ScheduledJobAlert).filter(
            and_(
                ScheduledJobAlert.id == alert_id,
                ScheduledJobAlert.created_by == user_id,
            )
        ).first()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found or access denied")
        return alert

    def list_alerts(
        self,
        user_id: int,
        scheduled_report_id: Optional[int] = None,
        active_only: bool = False,
    ) -> List[ScheduledJobAlert]:
        """List alerts for a user, optionally filtered by scheduled report."""
        query = self.db.query(ScheduledJobAlert).filter(
            ScheduledJobAlert.created_by == user_id
        )
        if scheduled_report_id is not None:
            query = query.filter(ScheduledJobAlert.scheduled_report_id == scheduled_report_id)
        if active_only:
            query = query.filter(ScheduledJobAlert.is_active == True)
        return query.order_by(ScheduledJobAlert.created_at.desc()).all()

    def update_alert(self, alert_id: int, data: ScheduledJobAlertUpdate, user_id: int) -> ScheduledJobAlert:
        """Update an existing alert rule."""
        alert = self.get_alert(alert_id, user_id)

        if data.name is not None:
            alert.name = data.name
        if data.description is not None:
            alert.description = data.description
        if data.condition is not None:
            alert.condition = data.condition.model_dump()
        if data.notification_channels is not None:
            alert.notification_channels = [ch.value for ch in data.notification_channels]
        if data.recipients is not None:
            alert.recipients = data.recipients
        if data.severity is not None:
            alert.severity = data.severity.value
        if data.is_active is not None:
            alert.is_active = data.is_active
        if data.cooldown_minutes is not None:
            alert.cooldown_minutes = data.cooldown_minutes

        self.db.commit()
        self.db.refresh(alert)
        return alert

    def delete_alert(self, alert_id: int, user_id: int) -> bool:
        """Delete an alert rule."""
        alert = self.get_alert(alert_id, user_id)
        self.db.delete(alert)
        self.db.commit()
        return True

    # --- Alert Evaluation ---

    def evaluate_alerts_for_schedule(
        self,
        schedule_id: int,
        report_result: ReportResult,
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all active alerts for a given scheduled report after execution.

        Args:
            schedule_id: ID of the scheduled report that was just executed
            report_result: The result of the report execution

        Returns:
            List of triggered alert summaries
        """
        alerts = self.db.query(ScheduledJobAlert).filter(
            and_(
                ScheduledJobAlert.scheduled_report_id == schedule_id,
                ScheduledJobAlert.is_active == True,
            )
        ).all()

        if not alerts:
            return []

        triggered = []
        now = datetime.now(timezone.utc)

        for alert in alerts:
            # Check cooldown
            if alert.last_triggered_at:
                cooldown_end = alert.last_triggered_at + timedelta(minutes=alert.cooldown_minutes)
                if now < cooldown_end:
                    logger.debug(
                        f"Alert {alert.id} '{alert.name}' is in cooldown until {cooldown_end.isoformat()}"
                    )
                    continue

            # Evaluate condition
            condition = AlertCondition(**alert.condition)
            evaluation = self._evaluate_condition(condition, report_result)

            if evaluation["triggered"]:
                logger.info(f"Alert {alert.id} '{alert.name}' triggered for schedule {schedule_id}")

                # Record the trigger
                alert.last_triggered_at = now
                history_entry = ScheduledJobAlertHistory(
                    alert_id=alert.id,
                    triggered_at=now,
                    condition_result=evaluation,
                    notification_sent=False,
                )
                self.db.add(history_entry)
                self.db.commit()
                self.db.refresh(history_entry)

                # Dispatch notification
                notification_error = self._dispatch_notification(alert, evaluation, report_result)
                history_entry.notification_sent = notification_error is None
                history_entry.notification_error = notification_error
                self.db.commit()

                triggered.append({
                    "alert_id": alert.id,
                    "alert_name": alert.name,
                    "severity": alert.severity,
                    "condition_result": evaluation,
                    "notification_sent": history_entry.notification_sent,
                })

        return triggered

    def _evaluate_condition(self, condition: AlertCondition, report_result: ReportResult) -> Dict[str, Any]:
        """
        Evaluate a single condition against the report result.

        Supports evaluating fields from:
        - report_result top-level (success, error_message)
        - report_result.data.summary (total_records, total_amount)
        - report_result.data.metadata (generation_time)
        """
        field = condition.field
        operator = condition.operator
        threshold = condition.threshold

        # Resolve the field value from the report result
        actual_value = self._resolve_field_value(field, report_result)

        if actual_value is None:
            return {
                "triggered": False,
                "field": field,
                "actual_value": None,
                "threshold": threshold,
                "reason": f"Field '{field}' not found in report result",
            }

        triggered = self._compare_values(actual_value, operator, threshold)

        return {
            "triggered": triggered,
            "field": field,
            "operator": operator.value,
            "actual_value": actual_value,
            "threshold": threshold,
        }

    def _resolve_field_value(self, field: str, report_result: ReportResult) -> Any:
        """Resolve a field name to its value from the report result."""
        # Top-level fields
        if field == "success":
            return report_result.success
        if field == "error_message":
            return report_result.error_message
        if field == "status":
            return "failed" if not report_result.success else "completed"
        if field == "generation_time":
            return report_result.generation_time

        # Summary fields (from report data)
        if report_result.data and report_result.data.summary:
            summary = report_result.data.summary
            if field == "total_records":
                return summary.total_records
            if field == "total_amount":
                return summary.total_amount
            # Check key_metrics
            if field in (summary.key_metrics or {}):
                return summary.key_metrics[field]

        return None

    def _compare_values(self, actual: Any, operator: AlertOperator, threshold: Any) -> bool:
        """Compare actual value against threshold using the given operator."""
        try:
            if operator == AlertOperator.GREATER_THAN:
                return float(actual) > float(threshold)
            elif operator == AlertOperator.GREATER_THAN_OR_EQUAL:
                return float(actual) >= float(threshold)
            elif operator == AlertOperator.LESS_THAN:
                return float(actual) < float(threshold)
            elif operator == AlertOperator.LESS_THAN_OR_EQUAL:
                return float(actual) <= float(threshold)
            elif operator == AlertOperator.EQUAL:
                return str(actual) == str(threshold)
            elif operator == AlertOperator.NOT_EQUAL:
                return str(actual) != str(threshold)
            elif operator == AlertOperator.CONTAINS:
                return str(threshold) in str(actual)
            elif operator == AlertOperator.STATUS_IS:
                return str(actual).lower() == str(threshold).lower()
        except (ValueError, TypeError) as e:
            logger.warning(f"Comparison error: {e}")
            return False
        return False

    # --- Notification Dispatch ---

    def _dispatch_notification(
        self,
        alert: ScheduledJobAlert,
        evaluation: Dict[str, Any],
        report_result: ReportResult,
    ) -> Optional[str]:
        """
        Dispatch alert notification through configured channels.

        Returns error message on failure, None on success.
        """
        try:
            for channel in alert.notification_channels:
                if channel == "email":
                    self._send_email_notification(alert, evaluation, report_result)
                elif channel == "webhook":
                    self._send_webhook_notification(alert, evaluation, report_result)
                elif channel == "slack":
                    self._send_slack_notification(alert, evaluation, report_result)
                else:
                    logger.warning(f"Unknown notification channel: {channel}")
            return None
        except Exception as e:
            error_msg = f"Failed to dispatch notification: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def _send_email_notification(
        self,
        alert: ScheduledJobAlert,
        evaluation: Dict[str, Any],
        report_result: ReportResult,
    ) -> None:
        """Send alert notification via email."""
        from core.services.email_service import EmailService, EmailMessage

        subject = f"[{alert.severity.upper()}] Alert: {alert.name}"
        body = self._format_alert_email(alert, evaluation, report_result)

        try:
            from core.services.report_scheduler_background import ReportSchedulerBackgroundService
            email_config = ReportSchedulerBackgroundService()._get_email_config()
            if not email_config:
                logger.warning("No email configuration available for alert notifications")
                return

            email_service = EmailService(email_config)
            message = EmailMessage(
                to=alert.recipients,
                subject=subject,
                body=body,
                is_html=True,
            )
            email_service.send(message)
            logger.info(f"Alert email sent to {alert.recipients} for alert '{alert.name}'")
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")
            raise

    def _send_webhook_notification(
        self,
        alert: ScheduledJobAlert,
        evaluation: Dict[str, Any],
        report_result: ReportResult,
    ) -> None:
        """Send alert notification via webhook."""
        import requests as http_requests

        payload = {
            "alert_id": alert.id,
            "alert_name": alert.name,
            "severity": alert.severity,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "condition": alert.condition,
            "evaluation": evaluation,
            "report_success": report_result.success,
        }

        for recipient in alert.recipients:
            if recipient.startswith("http"):
                try:
                    resp = http_requests.post(recipient, json=payload, timeout=10)
                    resp.raise_for_status()
                except Exception as e:
                    logger.error(f"Webhook notification failed for {recipient}: {e}")
                    raise

    def _send_slack_notification(
        self,
        alert: ScheduledJobAlert,
        evaluation: Dict[str, Any],
        report_result: ReportResult,
    ) -> None:
        """Send alert notification via Slack webhook."""
        import requests as http_requests

        severity_emoji = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔶",
            "critical": "🚨",
        }
        emoji = severity_emoji.get(alert.severity, "⚠️")

        text = (
            f"{emoji} *Scheduled Job Alert: {alert.name}*\n"
            f"Severity: `{alert.severity}`\n"
            f"Condition: `{evaluation.get('field')}` {evaluation.get('operator', '')} `{evaluation.get('threshold')}`\n"
            f"Actual value: `{evaluation.get('actual_value')}`\n"
            f"Report status: {'✅ Success' if report_result.success else '❌ Failed'}"
        )

        payload = {"text": text}

        for recipient in alert.recipients:
            if recipient.startswith("http"):
                try:
                    resp = http_requests.post(recipient, json=payload, timeout=10)
                    resp.raise_for_status()
                except Exception as e:
                    logger.error(f"Slack notification failed for {recipient}: {e}")
                    raise

    def _format_alert_email(
        self,
        alert: ScheduledJobAlert,
        evaluation: Dict[str, Any],
        report_result: ReportResult,
    ) -> str:
        """Format the alert email body as HTML."""
        severity_colors = {
            "low": "#17a2b8",
            "medium": "#ffc107",
            "high": "#fd7e14",
            "critical": "#dc3545",
        }
        color = severity_colors.get(alert.severity, "#6c757d")

        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: {color}; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">⚠️ Scheduled Job Alert Triggered</h2>
                <p style="margin: 4px 0 0 0; opacity: 0.9;">Severity: {alert.severity.upper()}</p>
            </div>
            <div style="border: 1px solid #dee2e6; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
                <h3 style="margin-top: 0;">{alert.name}</h3>
                {f'<p>{alert.description}</p>' if alert.description else ''}
                <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Field</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{evaluation.get('field', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Condition</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{evaluation.get('operator', 'N/A')} {evaluation.get('threshold', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Actual Value</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{evaluation.get('actual_value', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Report Status</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{'Success' if report_result.success else 'Failed'}</td>
                    </tr>
                </table>
                <p style="color: #6c757d; font-size: 12px; margin-bottom: 0;">
                    This alert was triggered at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.
                    Cooldown period: {alert.cooldown_minutes} minutes.
                </p>
            </div>
        </div>
        """

    # --- Alert History ---

    def get_alert_history(
        self,
        alert_id: int,
        user_id: int,
        limit: int = 20,
    ) -> List[ScheduledJobAlertHistory]:
        """Get trigger history for an alert."""
        # Verify access
        self.get_alert(alert_id, user_id)

        return (
            self.db.query(ScheduledJobAlertHistory)
            .filter(ScheduledJobAlertHistory.alert_id == alert_id)
            .order_by(ScheduledJobAlertHistory.triggered_at.desc())
            .limit(limit)
            .all()
        )
