"""
Integration tests for the Report Scheduler Service

These tests verify the integration between the scheduler, database,
email service, and report generation components.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from api.services.report_scheduler import ReportScheduler, ReportSchedulerError
from api.services.scheduled_report_service import ScheduledReportService
from api.services.report_service import ReportService
from api.services.email_service import EmailService
from api.services.report_exporter import ReportExportService
from api.models.models_per_tenant import ScheduledReport, ReportTemplate, ReportHistory
from api.schemas.report import (
    ScheduledReportCreate, ScheduleConfig, ScheduleType, ExportFormat,
    ReportResult, ReportData, ReportSummary, ReportMetadata
)


class TestReportSchedulerIntegration:
    """Integration test cases for ReportScheduler with real-like scenarios"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session with realistic behavior"""
        session = Mock(spec=Session)
        
        # Mock query builder pattern
        query_mock = Mock()
        filter_mock = Mock()
        join_mock = Mock()
        
        session.query.return_value = query_mock
        query_mock.filter.return_value = filter_mock
        query_mock.join.return_value = join_mock
        join_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = None
        filter_mock.all.return_value = []
        filter_mock.count.return_value = 0
        
        return session
    
    @pytest.fixture
    def mock_report_service(self):
        """Mock report service with realistic responses"""
        service = Mock(spec=ReportService)
        
        # Mock successful report generation
        service.generate_report_from_template.return_value = ReportResult(
            success=True,
            data=ReportData(
                report_type="invoice",
                summary=ReportSummary(
                    total_records=10,
                    total_amount=1000.0,
                    currency="USD"
                ),
                data=[
                    {"id": 1, "amount": 100.0, "status": "paid"},
                    {"id": 2, "amount": 200.0, "status": "pending"}
                ],
                metadata=ReportMetadata(
                    generated_at=datetime.now(timezone.utc),
                    generated_by=1,
                    export_format=ExportFormat.PDF
                )
            )
        )
        
        return service
    
    @pytest.fixture
    def mock_email_service(self):
        """Mock email service"""
        service = Mock(spec=EmailService)
        service.send_email.return_value = True
        return service
    
    @pytest.fixture
    def mock_report_exporter(self):
        """Mock report exporter"""
        service = Mock(spec=ReportExportService)
        service.export_report.return_value = b"PDF content here"
        return service
    
    @pytest.fixture
    def sample_template(self):
        """Sample report template"""
        return ReportTemplate(
            id=1,
            name="Monthly Invoice Report",
            report_type="invoice",
            filters={"date_from": "2024-01-01", "status": ["paid", "pending"]},
            columns=["id", "amount", "status", "client_name"],
            formatting={"currency": "USD"},
            user_id=1,
            is_shared=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def scheduler_service(self, mock_db_session, mock_report_service, mock_email_service, mock_report_exporter):
        """Create ReportScheduler with mocked dependencies"""
        return ReportScheduler(
            db=mock_db_session,
            report_service=mock_report_service,
            email_service=mock_email_service,
            report_exporter=mock_report_exporter
        )
    
    @pytest.fixture
    def scheduled_report_service(self, mock_db_session, scheduler_service):
        """Create ScheduledReportService with mocked dependencies"""
        return ScheduledReportService(
            db=mock_db_session,
            report_scheduler=scheduler_service
        )

    def test_end_to_end_schedule_creation_and_execution(
        self, 
        scheduler_service, 
        mock_db_session, 
        sample_template,
        mock_report_service,
        mock_email_service,
        mock_report_exporter
    ):
        """Test complete workflow from schedule creation to execution"""
        
        # Setup: Mock database to return template
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_template
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_db_session.refresh = Mock()
        
        # Step 1: Create scheduled report
        schedule_data = ScheduledReportCreate(
            template_id=1,
            schedule_config=ScheduleConfig(
                schedule_type=ScheduleType.DAILY,
                time_of_day="09:00",
                timezone="UTC"
            ),
            recipients=["manager@company.com", "analyst@company.com"],
            export_format=ExportFormat.PDF,
            is_active=True
        )
        
        # Create the schedule
        created_schedule = scheduler_service.create_scheduled_report(schedule_data, user_id=1)
        
        # Verify schedule was created
        assert created_schedule is not None
        assert created_schedule.template_id == 1
        assert created_schedule.recipients == ["manager@company.com", "analyst@company.com"]
        assert created_schedule.is_active == True
        
        # Step 2: Mock the created schedule for execution
        mock_scheduled_report = ScheduledReport(
            id=1,
            template_id=1,
            is_active=True,
            schedule_config={
                "schedule_type": "daily",
                "time_of_day": "09:00",
                "export_format": "pdf"
            },
            recipients=["manager@company.com", "analyst@company.com"]
        )
        
        # Mock database queries for execution
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_scheduled_report,  # First call for scheduled report
            sample_template         # Second call for template
        ]
        
        # Step 3: Execute the scheduled report
        execution_result = scheduler_service.execute_scheduled_report(1)
        
        # Verify execution was successful
        assert execution_result.success == True
        
        # Verify report service was called
        mock_report_service.generate_report_from_template.assert_called_once()
        
        # Verify email service was called (should be called twice for two recipients)
        assert mock_email_service.send_email.call_count >= 1
        
        # Verify database was updated
        mock_db_session.commit.assert_called()

    def test_scheduled_report_service_crud_operations(
        self, 
        scheduled_report_service, 
        mock_db_session, 
        sample_template
    ):
        """Test CRUD operations through ScheduledReportService"""
        
        # Setup mocks
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_template
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_db_session.refresh = Mock()
        
        # Test Create
        schedule_data = ScheduledReportCreate(
            template_id=1,
            schedule_config=ScheduleConfig(
                schedule_type=ScheduleType.WEEKLY,
                time_of_day="10:00",
                day_of_week=1,  # Tuesday
                timezone="UTC"
            ),
            recipients=["weekly-report@company.com"],
            export_format=ExportFormat.EXCEL
        )
        
        created_schedule = scheduled_report_service.create_scheduled_report(schedule_data, user_id=1)
        assert created_schedule is not None
        
        # Test Read - Mock existing schedule
        existing_schedule = ScheduledReport(
            id=1,
            template_id=1,
            schedule_type="weekly",
            schedule_config={
                "schedule_type": "weekly",
                "time_of_day": "10:00",
                "day_of_week": 1
            },
            recipients=["weekly-report@company.com"],
            is_active=True
        )
        
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = existing_schedule
        
        retrieved_schedule = scheduled_report_service.get_scheduled_report(1, user_id=1)
        assert retrieved_schedule.id == 1
        assert retrieved_schedule.template_id == 1
        
        # Test Update
        from api.schemas.report import ScheduledReportUpdate
        update_data = ScheduledReportUpdate(
            recipients=["updated-report@company.com"],
            is_active=False
        )
        
        updated_schedule = scheduled_report_service.update_scheduled_report(1, update_data, user_id=1)
        assert updated_schedule is not None
        
        # Test Delete
        delete_result = scheduled_report_service.delete_scheduled_report(1, user_id=1)
        assert delete_result == True

    def test_multiple_schedule_execution_with_different_formats(
        self, 
        scheduler_service, 
        mock_db_session, 
        sample_template,
        mock_report_service,
        mock_email_service,
        mock_report_exporter
    ):
        """Test execution of multiple schedules with different export formats"""
        
        # Create schedules with different formats
        schedules = [
            ScheduledReport(
                id=1, template_id=1, is_active=True,
                schedule_config={"export_format": "pdf"},
                recipients=["pdf@company.com"]
            ),
            ScheduledReport(
                id=2, template_id=1, is_active=True,
                schedule_config={"export_format": "csv"},
                recipients=["csv@company.com"]
            ),
            ScheduledReport(
                id=3, template_id=1, is_active=True,
                schedule_config={"export_format": "excel"},
                recipients=["excel@company.com"]
            )
        ]
        
        # Mock different export results
        mock_report_exporter.export_report.side_effect = [
            b"PDF content",
            "CSV,content,here",
            b"Excel content"
        ]
        
        # Execute each schedule
        for schedule in schedules:
            # Mock database queries
            mock_db_session.query.return_value.filter.return_value.first.side_effect = [
                schedule, sample_template
            ]
            
            result = scheduler_service.execute_scheduled_report(schedule.id)
            assert result.success == True
        
        # Verify all formats were exported
        assert mock_report_exporter.export_report.call_count == 3
        
        # Verify emails were sent
        assert mock_email_service.send_email.call_count >= 3

    def test_error_handling_in_schedule_execution(
        self, 
        scheduler_service, 
        mock_db_session, 
        sample_template,
        mock_report_service,
        mock_email_service
    ):
        """Test error handling during schedule execution"""
        
        # Test 1: Report generation failure
        mock_report_service.generate_report_from_template.return_value = ReportResult(
            success=False,
            error_message="Database connection failed"
        )
        
        mock_schedule = ScheduledReport(
            id=1, template_id=1, is_active=True,
            schedule_config={"export_format": "pdf"},
            recipients=["test@company.com"]
        )
        
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_schedule, sample_template
        ]
        
        result = scheduler_service.execute_scheduled_report(1)
        assert result.success == False
        assert "Database connection failed" in result.error_message
        
        # Test 2: Email sending failure
        mock_report_service.generate_report_from_template.return_value = ReportResult(success=True)
        mock_email_service.send_email.return_value = False
        
        # Should still complete execution even if email fails
        result = scheduler_service.execute_scheduled_report(1)
        # The scheduler should handle email failures gracefully

    def test_schedule_time_calculations(self, scheduler_service):
        """Test various schedule time calculations"""
        
        # Test daily schedule
        daily_config = ScheduleConfig(
            schedule_type=ScheduleType.DAILY,
            time_of_day="14:30"
        )
        
        with patch('api.services.report_scheduler.datetime') as mock_datetime:
            # Mock current time to be 10:00 AM
            mock_now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            next_run = scheduler_service._calculate_next_run(daily_config)
            
            # Should be today at 2:30 PM
            expected = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
            assert next_run == expected
        
        # Test weekly schedule
        weekly_config = ScheduleConfig(
            schedule_type=ScheduleType.WEEKLY,
            time_of_day="09:00",
            day_of_week=0  # Monday
        )
        
        with patch('api.services.report_scheduler.datetime') as mock_datetime:
            # Mock current time to be Wednesday
            mock_now = datetime(2024, 1, 17, 10, 0, 0, tzinfo=timezone.utc)  # Wednesday
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            next_run = scheduler_service._calculate_next_run(weekly_config)
            
            # Should be next Monday at 9:00 AM
            expected = datetime(2024, 1, 22, 9, 0, 0, tzinfo=timezone.utc)
            assert next_run == expected
        
        # Test cron schedule
        cron_config = ScheduleConfig(
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * 1"  # Every Monday at 9 AM
        )
        
        with patch('croniter.croniter') as mock_croniter:
            mock_cron_instance = Mock()
            mock_next_time = datetime(2024, 1, 22, 9, 0, 0, tzinfo=timezone.utc)
            mock_cron_instance.get_next.return_value = mock_next_time
            mock_croniter.return_value = mock_cron_instance
            
            next_run = scheduler_service._calculate_next_run(cron_config)
            assert next_run == mock_next_time

    def test_due_schedules_detection(self, scheduler_service, mock_db_session):
        """Test detection of schedules that are due for execution"""
        
        current_time = datetime.now(timezone.utc)
        
        # Create schedules with different due times
        schedules = [
            ScheduledReport(
                id=1, is_active=True,
                next_run=current_time - timedelta(minutes=5)  # Due 5 minutes ago
            ),
            ScheduledReport(
                id=2, is_active=True,
                next_run=current_time + timedelta(minutes=5)  # Due in 5 minutes
            ),
            ScheduledReport(
                id=3, is_active=False,
                next_run=current_time - timedelta(minutes=5)  # Due but inactive
            ),
            ScheduledReport(
                id=4, is_active=True,
                next_run=current_time - timedelta(seconds=30)  # Due 30 seconds ago
            )
        ]
        
        # Mock database to return only due and active schedules
        due_schedules = [s for s in schedules if s.is_active and s.next_run <= current_time]
        mock_db_session.query.return_value.filter.return_value.all.return_value = due_schedules
        
        result = scheduler_service.get_due_schedules(current_time)
        
        # Should return schedules 1 and 4 (due and active)
        assert len(result) == 2
        assert result[0].id in [1, 4]
        assert result[1].id in [1, 4]

    def test_email_content_generation(self, scheduler_service, sample_template):
        """Test generation of email content for scheduled reports"""
        
        report_result = ReportResult(
            success=True,
            data=ReportData(
                report_type="invoice",
                summary=ReportSummary(total_records=5, total_amount=500.0),
                data=[],
                metadata=ReportMetadata(
                    generated_at=datetime.now(timezone.utc),
                    generated_by=1,
                    export_format=ExportFormat.PDF
                )
            )
        )
        
        # Test HTML email generation
        html_content = scheduler_service._create_scheduled_report_html(sample_template, report_result)
        
        assert "Monthly Invoice Report" in html_content
        assert "Success" in html_content
        assert "<!DOCTYPE html>" in html_content
        assert "Invoice" in html_content
        
        # Test text email generation
        text_content = scheduler_service._create_scheduled_report_text(sample_template, report_result)
        
        assert "Monthly Invoice Report" in text_content
        assert "Success" in text_content
        assert "automated email" in text_content.lower()
        
        # Test failed report email
        failed_result = ReportResult(
            success=False,
            error_message="Database timeout"
        )
        
        html_failed = scheduler_service._create_scheduled_report_html(sample_template, failed_result)
        text_failed = scheduler_service._create_scheduled_report_text(sample_template, failed_result)
        
        assert "Failed" in html_failed
        assert "Database timeout" in html_failed
        assert "Failed" in text_failed
        assert "Database timeout" in text_failed