"""
Tests for the Scheduled Job Alerting Service.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

from core.services.scheduled_job_alerting_service import ScheduledJobAlertingService
from core.schemas.scheduled_job_alerts import (
    ScheduledJobAlertCreate,
    ScheduledJobAlertUpdate,
    AlertCondition,
    AlertOperator,
    AlertSeverity,
    AlertNotificationChannel,
)
from core.schemas.report import ReportResult, ReportData, ReportSummary, ReportMetadata, ExportFormat


def _make_report_result(success=True, total_records=100, total_amount=5000.0):
    """Helper to create a ReportResult for testing."""
    return ReportResult(
        success=success,
        report_id=1,
        data=ReportData(
            report_type="invoice",
            summary=ReportSummary(
                total_records=total_records,
                total_amount=total_amount,
                currency="USD",
            ),
            data=[],
            metadata=ReportMetadata(
                generated_at=datetime.now(timezone.utc),
                generated_by=1,
                export_format=ExportFormat.PDF,
                generation_time=2.5,
            ),
            filters={},
        ),
        error_message=None if success else "Something failed",
        generation_time=2.5,
    )


class TestConditionEvaluation:
    """Test alert condition evaluation logic."""

    def setup_method(self):
        self.db = MagicMock()
        self.service = ScheduledJobAlertingService(self.db)

    def test_greater_than_triggered(self):
        condition = AlertCondition(field="total_amount", operator=AlertOperator.GREATER_THAN, threshold=1000)
        result = self.service._evaluate_condition(condition, _make_report_result(total_amount=5000))
        assert result["triggered"] is True
        assert result["actual_value"] == 5000.0

    def test_greater_than_not_triggered(self):
        condition = AlertCondition(field="total_amount", operator=AlertOperator.GREATER_THAN, threshold=10000)
        result = self.service._evaluate_condition(condition, _make_report_result(total_amount=5000))
        assert result["triggered"] is False

    def test_less_than_triggered(self):
        condition = AlertCondition(field="total_records", operator=AlertOperator.LESS_THAN, threshold=50)
        result = self.service._evaluate_condition(condition, _make_report_result(total_records=10))
        assert result["triggered"] is True

    def test_equal_triggered(self):
        condition = AlertCondition(field="status", operator=AlertOperator.EQUAL, threshold="failed")
        result = self.service._evaluate_condition(condition, _make_report_result(success=False))
        assert result["triggered"] is True

    def test_status_is_operator(self):
        condition = AlertCondition(field="status", operator=AlertOperator.STATUS_IS, threshold="completed")
        result = self.service._evaluate_condition(condition, _make_report_result(success=True))
        assert result["triggered"] is True

    def test_not_equal_triggered(self):
        condition = AlertCondition(field="status", operator=AlertOperator.NOT_EQUAL, threshold="completed")
        result = self.service._evaluate_condition(condition, _make_report_result(success=False))
        assert result["triggered"] is True

    def test_field_not_found(self):
        condition = AlertCondition(field="nonexistent_field", operator=AlertOperator.GREATER_THAN, threshold=100)
        result = self.service._evaluate_condition(condition, _make_report_result())
        assert result["triggered"] is False
        assert "not found" in result.get("reason", "")

    def test_generation_time_field(self):
        condition = AlertCondition(field="generation_time", operator=AlertOperator.GREATER_THAN, threshold=2.0)
        result = self.service._evaluate_condition(condition, _make_report_result())
        assert result["triggered"] is True
        assert result["actual_value"] == 2.5

    def test_gte_operator(self):
        condition = AlertCondition(field="total_records", operator=AlertOperator.GREATER_THAN_OR_EQUAL, threshold=100)
        result = self.service._evaluate_condition(condition, _make_report_result(total_records=100))
        assert result["triggered"] is True

    def test_lte_operator(self):
        condition = AlertCondition(field="total_records", operator=AlertOperator.LESS_THAN_OR_EQUAL, threshold=100)
        result = self.service._evaluate_condition(condition, _make_report_result(total_records=100))
        assert result["triggered"] is True

    def test_contains_operator(self):
        condition = AlertCondition(field="error_message", operator=AlertOperator.CONTAINS, threshold="failed")
        result = self.service._evaluate_condition(condition, _make_report_result(success=False))
        assert result["triggered"] is True


class TestCooldownLogic:
    """Test alert cooldown mechanism."""

    def setup_method(self):
        self.db = MagicMock()
        self.service = ScheduledJobAlertingService(self.db)

    def test_cooldown_prevents_trigger(self):
        """An alert in cooldown should not be re-triggered."""
        mock_alert = MagicMock()
        mock_alert.id = 1
        mock_alert.is_active = True
        mock_alert.cooldown_minutes = 60
        mock_alert.last_triggered_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        mock_alert.condition = {"field": "total_amount", "operator": "gt", "threshold": 100}
        mock_alert.notification_channels = ["email"]
        mock_alert.recipients = ["test@example.com"]
        mock_alert.severity = "medium"
        mock_alert.name = "Test Alert"

        self.db.query.return_value.filter.return_value.all.return_value = [mock_alert]

        result = self.service.evaluate_alerts_for_schedule(1, _make_report_result(total_amount=5000))
        assert len(result) == 0

    def test_expired_cooldown_allows_trigger(self):
        """An alert past cooldown should be re-triggered."""
        mock_alert = MagicMock()
        mock_alert.id = 1
        mock_alert.is_active = True
        mock_alert.cooldown_minutes = 60
        mock_alert.last_triggered_at = datetime.now(timezone.utc) - timedelta(minutes=90)
        mock_alert.condition = {"field": "total_amount", "operator": "gt", "threshold": 100}
        mock_alert.notification_channels = ["email"]
        mock_alert.recipients = ["test@example.com"]
        mock_alert.severity = "medium"
        mock_alert.name = "Test Alert"

        self.db.query.return_value.filter.return_value.all.return_value = [mock_alert]

        with patch.object(self.service, '_dispatch_notification', return_value=None):
            result = self.service.evaluate_alerts_for_schedule(1, _make_report_result(total_amount=5000))
            assert len(result) == 1
            assert result[0]["alert_name"] == "Test Alert"


class TestCompareValues:
    """Test the _compare_values helper."""

    def setup_method(self):
        self.db = MagicMock()
        self.service = ScheduledJobAlertingService(self.db)

    def test_invalid_numeric_comparison(self):
        """Non-numeric values should not crash numeric comparisons."""
        result = self.service._compare_values("not_a_number", AlertOperator.GREATER_THAN, 100)
        assert result is False

    def test_string_equality(self):
        result = self.service._compare_values("hello", AlertOperator.EQUAL, "hello")
        assert result is True

    def test_contains_false(self):
        result = self.service._compare_values("hello world", AlertOperator.CONTAINS, "xyz")
        assert result is False
