"""
Unit tests for the Report Scheduler Service
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from api.services.report_scheduler import ReportScheduler, ReportSchedulerError
from api.services.report_service import ReportService
from api.services.email_service import EmailService
from api.services.report_exporter import ReportExportService
from api.models.models_per_tenant import ScheduledReport, ReportTemplate, User
from api.schemas.report import (
    ScheduledReportCreate, ScheduledReportUpdate, ScheduleConfig, 
    ScheduleType, ExportFormat, ReportResult, ReportData, ReportSummary, ReportMetadata
)


class TestReportScheduler:
    """Test cases for ReportScheduler service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_report_service(self):
        """Mock report service"""
        return Mock(spec=ReportService)
    
    @pytest.fixture
    def mock_email_service(self):
        """Mock email service"""
        return Mock(spec=EmailService)
    
    @pytest.fixture
    def mock_report_exporter(self):
        """Mock report exporter"""
        return Mock(spec=ReportExportService)
    
    @pytest.fixture
    def scheduler(self, mock_db, mock_report_service, mock_email_service, mock_report_exporter):
        """Create ReportScheduler instance with mocked dependencies"""
        return ReportScheduler(
            db=mock_db,
            report_service=mock_report_service,
            email_service=mock_email_service,
            report_exporter=mock_report_exporter
        )
    
    @pytest.fixture
    def sample_template(self):
        """Sample report template"""
        return ReportTemplate(
            id=1,
            name="Test Template",
            report_type="invoice",
            filters={"date_from": "2024-01-01"},
            columns=["id", "amount", "status"],
            formatting={},
            user_id=1,
            is_shared=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def sample_schedule_config(self):
        """Sample schedule configuration"""
        return ScheduleConfig(
            schedule_type=ScheduleType.DAILY,
            time_of_day="09:00",
            timezone="UTC"
        )
    
    @pytest.fixture
    def sample_schedule_create(self, sample_schedule_config):
        """Sample schedule creation data"""
        return ScheduledReportCreate(
            template_id=1,
            schedule_config=sample_schedule_config,
            recipients=["test@example.com"],
            export_format=ExportFormat.PDF,
            is_active=True
        )

    def test_create_scheduled_report_success(self, scheduler, mock_db, sample_template, sample_schedule_create):
        """Test successful creation of scheduled report"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Create scheduled report
        result = scheduler.create_scheduled_report(sample_schedule_create, user_id=1)
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        
        # Verify the scheduled report was created with correct data
        added_report = mock_db.add.call_args[0][0]
        assert added_report.template_id == 1
        assert added_report.schedule_type == "daily"
        assert added_report.recipients == ["test@example.com"]
        assert added_report.is_active == True
        assert added_report.next_run is not None

    def test_create_scheduled_report_template_not_found(self, scheduler, mock_db, sample_schedule_create):
        """Test creation fails when template not found"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Attempt to create scheduled report
        with pytest.raises(ReportSchedulerError, match="Template 1 not found or access denied"):
            scheduler.create_scheduled_report(sample_schedule_create, user_id=1)

    def test_create_scheduled_report_invalid_cron(self, scheduler, mock_db, sample_template):
        """Test creation fails with invalid cron expression"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Create schedule with invalid cron
        invalid_schedule = ScheduledReportCreate(
            template_id=1,
            schedule_config=ScheduleConfig(
                schedule_type=ScheduleType.CRON,
                cron_expression="invalid cron"
            ),
            recipients=["test@example.com"]
        )
        
        # Attempt to create scheduled report
        with pytest.raises(ReportSchedulerError, match="Invalid cron expression"):
            scheduler.create_scheduled_report(invalid_schedule, user_id=1)

    def test_create_scheduled_report_invalid_email(self, scheduler, mock_db, sample_template, sample_schedule_config):
        """Test creation fails with invalid email address"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Create schedule with invalid email
        invalid_schedule = ScheduledReportCreate(
            template_id=1,
            schedule_config=sample_schedule_config,
            recipients=["invalid-email"]
        )
        
        # Attempt to create scheduled report
        with pytest.raises(ReportSchedulerError, match="Invalid email address"):
            scheduler.create_scheduled_report(invalid_schedule, user_id=1)

    def test_update_scheduled_report_success(self, scheduler, mock_db, sample_template):
        """Test successful update of scheduled report"""
        # Create existing scheduled report
        existing_report = ScheduledReport(
            id=1,
            template_id=1,
            schedule_type="daily",
            schedule_config={"schedule_type": "daily", "time_of_day": "09:00"},
            recipients=["old@example.com"],
            is_active=True
        )
        
        # Setup mocks
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = existing_report
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Update data
        update_data = ScheduledReportUpdate(
            recipients=["new@example.com"],
            is_active=False
        )
        
        # Update scheduled report
        result = scheduler.update_scheduled_report(1, update_data, user_id=1)
        
        # Verify updates
        assert existing_report.recipients == ["new@example.com"]
        assert existing_report.is_active == False
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_delete_scheduled_report_success(self, scheduler, mock_db):
        """Test successful deletion of scheduled report"""
        # Create existing scheduled report
        existing_report = ScheduledReport(id=1, template_id=1)
        
        # Setup mocks
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = existing_report
        mock_db.delete = Mock()
        mock_db.commit = Mock()
        
        # Delete scheduled report
        result = scheduler.delete_scheduled_report(1, user_id=1)
        
        # Verify deletion
        assert result == True
        mock_db.delete.assert_called_once_with(existing_report)
        mock_db.commit.assert_called_once()

    def test_get_due_schedules(self, scheduler, mock_db):
        """Test getting schedules that are due for execution"""
        # Create due and not-due schedules
        due_schedule = ScheduledReport(
            id=1,
            is_active=True,
            next_run=datetime.now(timezone.utc) - timedelta(minutes=5)
        )
        not_due_schedule = ScheduledReport(
            id=2,
            is_active=True,
            next_run=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        inactive_schedule = ScheduledReport(
            id=3,
            is_active=False,
            next_run=datetime.now(timezone.utc) - timedelta(minutes=5)
        )
        
        # Setup mocks
        mock_db.query.return_value.filter.return_value.all.return_value = [due_schedule]
        
        # Get due schedules
        current_time = datetime.now(timezone.utc)
        result = scheduler.get_due_schedules(current_time)
        
        # Verify only active and due schedules are returned
        assert len(result) == 1
        assert result[0].id == 1

    def test_execute_scheduled_report_success(self, scheduler, mock_db, mock_report_service, mock_email_service, sample_template):
        """Test successful execution of scheduled report"""
        # Create scheduled report
        scheduled_report = ScheduledReport(
            id=1,
            template_id=1,
            is_active=True,
            schedule_config={
                "schedule_type": "daily",
                "time_of_day": "09:00",
                "export_format": "pdf"
            },
            recipients=["test@example.com"]
        )
        
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            scheduled_report,  # First call for scheduled report
            sample_template    # Second call for template
        ]
        mock_db.commit = Mock()
        
        # Mock successful report generation
        mock_report_result = ReportResult(
            success=True,
            data=ReportData(
                report_type="invoice",
                summary=ReportSummary(total_records=10, total_amount=1000.0),
                data=[{"id": 1, "amount": 100.0}],
                metadata=ReportMetadata(
                    generated_at=datetime.now(timezone.utc),
                    generated_by=1,
                    export_format=ExportFormat.PDF
                )
            )
        )
        mock_report_service.generate_report_from_template.return_value = mock_report_result
        
        # Mock email service
        mock_email_service.send_email.return_value = True
        
        # Execute scheduled report
        result = scheduler.execute_scheduled_report(1)
        
        # Verify success
        assert result.success == True
        mock_report_service.generate_report_from_template.assert_called_once()
        mock_email_service.send_email.assert_called()
        mock_db.commit.assert_called()

    def test_execute_scheduled_report_not_found(self, scheduler, mock_db):
        """Test execution fails when scheduled report not found"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute scheduled report
        result = scheduler.execute_scheduled_report(999)
        
        # Verify failure
        assert result.success == False
        assert "not found" in result.error_message

    def test_execute_scheduled_report_inactive(self, scheduler, mock_db):
        """Test execution fails when scheduled report is inactive"""
        # Create inactive scheduled report
        scheduled_report = ScheduledReport(
            id=1,
            template_id=1,
            is_active=False
        )
        
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = scheduled_report
        
        # Execute scheduled report
        result = scheduler.execute_scheduled_report(1)
        
        # Verify failure
        assert result.success == False
        assert "not active" in result.error_message

    def test_validate_schedule_config_daily(self, scheduler):
        """Test validation of daily schedule configuration"""
        # Valid daily config
        valid_config = ScheduleConfig(
            schedule_type=ScheduleType.DAILY,
            time_of_day="09:30"
        )
        
        # Should not raise exception
        scheduler._validate_schedule_config(valid_config)
        
        # Invalid daily config (missing time)
        invalid_config = ScheduleConfig(
            schedule_type=ScheduleType.DAILY
        )
        
        with pytest.raises(ReportSchedulerError, match="time_of_day is required"):
            scheduler._validate_schedule_config(invalid_config)

    def test_validate_schedule_config_cron(self, scheduler):
        """Test validation of cron schedule configuration"""
        # Valid cron config
        valid_config = ScheduleConfig(
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *"  # Daily at 9 AM
        )
        
        # Should not raise exception
        scheduler._validate_schedule_config(valid_config)
        
        # Invalid cron config (missing expression)
        invalid_config = ScheduleConfig(
            schedule_type=ScheduleType.CRON
        )
        
        with pytest.raises(ReportSchedulerError, match="Cron expression is required"):
            scheduler._validate_schedule_config(invalid_config)

    def test_validate_recipients(self, scheduler):
        """Test validation of email recipients"""
        # Valid recipients
        valid_recipients = ["test@example.com", "user@domain.org"]
        scheduler._validate_recipients(valid_recipients)
        
        # Empty recipients
        with pytest.raises(ReportSchedulerError, match="At least one recipient email is required"):
            scheduler._validate_recipients([])
        
        # Invalid email format
        with pytest.raises(ReportSchedulerError, match="Invalid email address"):
            scheduler._validate_recipients(["invalid-email"])

    def test_calculate_next_run_daily(self, scheduler):
        """Test calculation of next run time for daily schedule"""
        config = ScheduleConfig(
            schedule_type=ScheduleType.DAILY,
            time_of_day="14:30"
        )
        
        # Mock current time to be before the scheduled time
        with patch('api.services.report_scheduler.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            next_run = scheduler._calculate_next_run(config)
            
            # Should be today at 14:30
            expected = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
            assert next_run == expected

    def test_calculate_next_run_weekly(self, scheduler):
        """Test calculation of next run time for weekly schedule"""
        config = ScheduleConfig(
            schedule_type=ScheduleType.WEEKLY,
            time_of_day="09:00",
            day_of_week=0  # Monday
        )
        
        # Mock current time to be Wednesday
        with patch('api.services.report_scheduler.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 17, 10, 0, 0, tzinfo=timezone.utc)  # Wednesday
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            next_run = scheduler._calculate_next_run(config)
            
            # Should be next Monday at 09:00
            expected = datetime(2024, 1, 22, 9, 0, 0, tzinfo=timezone.utc)
            assert next_run == expected

    def test_calculate_next_run_cron(self, scheduler):
        """Test calculation of next run time for cron schedule"""
        config = ScheduleConfig(
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *"  # Daily at 9 AM
        )
        
        with patch('croniter.croniter') as mock_croniter:
            mock_cron_instance = Mock()
            mock_next_time = datetime(2024, 1, 16, 9, 0, 0, tzinfo=timezone.utc)
            mock_cron_instance.get_next.return_value = mock_next_time
            mock_croniter.return_value = mock_cron_instance
            
            next_run = scheduler._calculate_next_run(config)
            
            assert next_run == mock_next_time
            mock_croniter.assert_called_once()

    def test_execute_due_schedules(self, scheduler, mock_db):
        """Test execution of multiple due schedules"""
        # Create multiple due schedules
        due_schedules = [
            ScheduledReport(id=1, is_active=True),
            ScheduledReport(id=2, is_active=True),
            ScheduledReport(id=3, is_active=True)
        ]
        
        # Setup mocks
        mock_db.query.return_value.filter.return_value.all.return_value = due_schedules
        
        # Mock execute_scheduled_report to return success for first two, failure for third
        def mock_execute(schedule_id):
            if schedule_id in [1, 2]:
                return ReportResult(success=True)
            else:
                return ReportResult(success=False, error_message="Test error")
        
        scheduler.execute_scheduled_report = Mock(side_effect=mock_execute)
        
        # Execute due schedules
        result = scheduler.execute_due_schedules()
        
        # Verify results
        assert result["total_schedules"] == 3
        assert result["successful"] == 2
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["schedule_id"] == 3

    def test_get_content_type(self, scheduler):
        """Test getting MIME content type for file extensions"""
        assert scheduler._get_content_type("pdf") == "application/pdf"
        assert scheduler._get_content_type("csv") == "text/csv"
        assert scheduler._get_content_type("xlsx") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert scheduler._get_content_type("json") == "application/json"
        assert scheduler._get_content_type("unknown") == "application/octet-stream"

    def test_create_scheduled_report_html_email(self, scheduler, sample_template):
        """Test creation of HTML email body"""
        report_result = ReportResult(success=True)
        
        html_body = scheduler._create_scheduled_report_html(sample_template, report_result)
        
        assert "Test Template" in html_body
        assert "invoice" in html_body.lower()
        assert "Success" in html_body
        assert "<!DOCTYPE html>" in html_body

    def test_create_scheduled_report_text_email(self, scheduler, sample_template):
        """Test creation of plain text email body"""
        report_result = ReportResult(success=True)
        
        text_body = scheduler._create_scheduled_report_text(sample_template, report_result)
        
        assert "Test Template" in text_body
        assert "Invoice" in text_body
        assert "Success" in text_body
        assert "automated email" in text_body.lower()