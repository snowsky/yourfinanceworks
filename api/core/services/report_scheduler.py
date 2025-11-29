"""
Report Scheduler Service

This service handles the scheduling and automated execution of reports.
It supports cron-based scheduling, email delivery, and background task execution.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from croniter import croniter
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models.models_per_tenant import ScheduledReport, ReportTemplate, ReportHistory, User
from core.schemas.report import (
    ScheduledReportCreate, ScheduledReportUpdate, ScheduleConfig, 
    ReportResult, ReportStatus, ExportFormat
)
from core.services.report_service import ReportService
from core.services.email_service import EmailService, EmailMessage, EmailAttachment
from core.services.report_exporter import ReportExportService
from config import get_settings

logger = logging.getLogger(__name__)

class ReportSchedulerError(Exception):
    """Custom exception for report scheduler errors"""
    pass

class ReportScheduler:
    """
    Service for managing scheduled reports and automated report execution.
    
    Features:
    - Cron-based scheduling with flexible schedule types
    - Background task execution for report generation
    - Email delivery integration with attachments
    - Schedule management (CRUD operations)
    - Error handling and retry logic
    """
    
    def __init__(
        self, 
        db: Session, 
        report_service: ReportService,
        email_service: EmailService,
        report_exporter: ReportExportService
    ):
        self.db = db
        self.report_service = report_service
        self.email_service = email_service
        self.report_exporter = report_exporter
        self.settings = get_settings()
        
    def create_scheduled_report(
        self, 
        schedule_data: ScheduledReportCreate, 
        user_id: int
    ) -> ScheduledReport:
        """
        Create a new scheduled report.
        
        Args:
            schedule_data: Schedule configuration data
            user_id: ID of the user creating the schedule
            
        Returns:
            Created ScheduledReport instance
            
        Raises:
            ReportSchedulerError: If schedule creation fails
        """
        try:
            # Validate template exists and user has access
            template = self.db.query(ReportTemplate).filter(
                and_(
                    ReportTemplate.id == schedule_data.template_id,
                    or_(
                        ReportTemplate.user_id == user_id,
                        ReportTemplate.is_shared == True
                    )
                )
            ).first()
            
            if not template:
                raise ReportSchedulerError(f"Template {schedule_data.template_id} not found or access denied")
            
            # Validate schedule configuration
            self._validate_schedule_config(schedule_data.schedule_config)
            
            # Validate recipients
            self._validate_recipients(schedule_data.recipients)
            
            # Calculate next run time
            next_run = self._calculate_next_run(schedule_data.schedule_config)
            
            # Create scheduled report
            scheduled_report = ScheduledReport(
                template_id=schedule_data.template_id,
                schedule_type=schedule_data.schedule_config.schedule_type.value,
                schedule_config=schedule_data.schedule_config.model_dump(),
                recipients=schedule_data.recipients,
                is_active=schedule_data.is_active,
                next_run=next_run
            )
            
            self.db.add(scheduled_report)
            self.db.commit()
            self.db.refresh(scheduled_report)
            
            logger.info(f"Created scheduled report {scheduled_report.id} for template {template.id}")
            return scheduled_report
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create scheduled report: {str(e)}")
            raise ReportSchedulerError(f"Failed to create scheduled report: {str(e)}")
    
    def update_scheduled_report(
        self, 
        schedule_id: int, 
        update_data: ScheduledReportUpdate, 
        user_id: int
    ) -> ScheduledReport:
        """
        Update an existing scheduled report.
        
        Args:
            schedule_id: ID of the schedule to update
            update_data: Updated schedule data
            user_id: ID of the user updating the schedule
            
        Returns:
            Updated ScheduledReport instance
            
        Raises:
            ReportSchedulerError: If update fails
        """
        try:
            # Get existing schedule with access check
            scheduled_report = self._get_scheduled_report_with_access(schedule_id, user_id)
            
            # Update fields if provided
            if update_data.schedule_config is not None:
                self._validate_schedule_config(update_data.schedule_config)
                scheduled_report.schedule_config = update_data.schedule_config.model_dump()
                scheduled_report.schedule_type = update_data.schedule_config.schedule_type.value
                # Recalculate next run time
                scheduled_report.next_run = self._calculate_next_run(update_data.schedule_config)
            
            if update_data.recipients is not None:
                self._validate_recipients(update_data.recipients)
                scheduled_report.recipients = update_data.recipients
            
            if update_data.export_format is not None:
                scheduled_report.schedule_config["export_format"] = update_data.export_format.value
            
            if update_data.is_active is not None:
                scheduled_report.is_active = update_data.is_active
            
            scheduled_report.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(scheduled_report)
            
            logger.info(f"Updated scheduled report {schedule_id}")
            return scheduled_report
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update scheduled report {schedule_id}: {str(e)}")
            raise ReportSchedulerError(f"Failed to update scheduled report: {str(e)}")
    
    def delete_scheduled_report(self, schedule_id: int, user_id: int) -> bool:
        """
        Delete a scheduled report.
        
        Args:
            schedule_id: ID of the schedule to delete
            user_id: ID of the user deleting the schedule
            
        Returns:
            True if deletion was successful
            
        Raises:
            ReportSchedulerError: If deletion fails
        """
        try:
            scheduled_report = self._get_scheduled_report_with_access(schedule_id, user_id)
            
            self.db.delete(scheduled_report)
            self.db.commit()
            
            logger.info(f"Deleted scheduled report {schedule_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete scheduled report {schedule_id}: {str(e)}")
            raise ReportSchedulerError(f"Failed to delete scheduled report: {str(e)}")
    
    def get_scheduled_reports(
        self, 
        user_id: int, 
        active_only: bool = False
    ) -> List[ScheduledReport]:
        """
        Get all scheduled reports for a user.
        
        Args:
            user_id: ID of the user
            active_only: If True, only return active schedules
            
        Returns:
            List of ScheduledReport instances
        """
        query = self.db.query(ScheduledReport).join(ScheduledReport.template).filter(
            or_(
                ReportTemplate.user_id == user_id,
                ReportTemplate.is_shared == True
            )
        )
        
        if active_only:
            query = query.filter(ScheduledReport.is_active == True)
        
        return query.all()
    
    def get_scheduled_report(self, schedule_id: int, user_id: int) -> ScheduledReport:
        """
        Get a specific scheduled report.
        
        Args:
            schedule_id: ID of the schedule
            user_id: ID of the user
            
        Returns:
            ScheduledReport instance
            
        Raises:
            ReportSchedulerError: If schedule not found or access denied
        """
        return self._get_scheduled_report_with_access(schedule_id, user_id)
    
    def get_due_schedules(self, current_time: Optional[datetime] = None) -> List[ScheduledReport]:
        """
        Get all schedules that are due for execution.
        
        Args:
            current_time: Current time (defaults to now)
            
        Returns:
            List of ScheduledReport instances that are due
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        return self.db.query(ScheduledReport).filter(
            and_(
                ScheduledReport.is_active == True,
                ScheduledReport.next_run <= current_time
            )
        ).all()
    
    def execute_scheduled_report(self, schedule_id: int) -> ReportResult:
        """
        Execute a scheduled report and send it via email.
        
        Args:
            schedule_id: ID of the schedule to execute
            
        Returns:
            ReportResult with execution details
        """
        try:
            # Get the scheduled report
            scheduled_report = self.db.query(ScheduledReport).filter(
                ScheduledReport.id == schedule_id
            ).first()
            
            if not scheduled_report:
                raise ReportSchedulerError(f"Scheduled report {schedule_id} not found")
            
            if not scheduled_report.is_active:
                raise ReportSchedulerError(f"Scheduled report {schedule_id} is not active")
            
            # Get the template
            template = self.db.query(ReportTemplate).filter(
                ReportTemplate.id == scheduled_report.template_id
            ).first()
            
            if not template:
                raise ReportSchedulerError(f"Template {scheduled_report.template_id} not found")
            
            logger.info(f"Executing scheduled report {schedule_id} for template {template.id}")
            
            # Generate the report using template
            export_format = ExportFormat(
                scheduled_report.schedule_config.get("export_format", "pdf")
            )
            
            # Create template schema object
            from core.schemas.report import ReportTemplate as ReportTemplateSchema
            template_schema = ReportTemplateSchema(
                id=template.id,
                name=template.name,
                report_type=template.report_type,
                filters=template.filters or {},
                columns=template.columns,
                formatting=template.formatting,
                is_shared=template.is_shared,
                user_id=template.user_id,
                created_at=template.created_at,
                updated_at=template.updated_at
            )
            
            report_result = self.report_service.generate_report_from_template(
                template=template_schema,
                export_format=export_format,
                user_id=template.user_id
            )
            
            if not report_result.success:
                raise ReportSchedulerError(f"Report generation failed: {report_result.error_message}")
            
            # Send email with report attachment
            self._send_scheduled_report_email(
                scheduled_report=scheduled_report,
                template=template,
                report_result=report_result
            )
            
            # Update schedule execution info
            scheduled_report.last_run = datetime.now(timezone.utc)
            scheduled_report.next_run = self._calculate_next_run(
                ScheduleConfig(**scheduled_report.schedule_config)
            )
            
            self.db.commit()
            
            logger.info(f"Successfully executed scheduled report {schedule_id}")
            return report_result
            
        except Exception as e:
            logger.error(f"Failed to execute scheduled report {schedule_id}: {str(e)}")
            # Update next run time even on failure to prevent infinite retries
            if 'scheduled_report' in locals():
                scheduled_report.next_run = self._calculate_next_run(
                    ScheduleConfig(**scheduled_report.schedule_config)
                )
                self.db.commit()
            
            return ReportResult(
                success=False,
                error_message=str(e)
            )
    
    def execute_due_schedules(self) -> Dict[str, Any]:
        """
        Execute all schedules that are currently due.
        
        Returns:
            Dictionary with execution summary
        """
        current_time = datetime.now(timezone.utc)
        due_schedules = self.get_due_schedules(current_time)
        
        results = {
            "total_schedules": len(due_schedules),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        logger.info(f"Found {len(due_schedules)} due schedules to execute")
        
        for schedule in due_schedules:
            try:
                result = self.execute_scheduled_report(schedule.id)
                if result.success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "schedule_id": schedule.id,
                        "error": result.error_message
                    })
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "schedule_id": schedule.id,
                    "error": str(e)
                })
                logger.error(f"Failed to execute schedule {schedule.id}: {str(e)}")
        
        logger.info(f"Executed {results['total_schedules']} schedules: {results['successful']} successful, {results['failed']} failed")
        return results
    
    def _validate_schedule_config(self, config: ScheduleConfig) -> None:
        """Validate schedule configuration."""
        if config.schedule_type.value == "cron":
            if not config.cron_expression:
                raise ReportSchedulerError("Cron expression is required for cron schedule type")
            
            # Validate cron expression
            try:
                croniter(config.cron_expression)
            except Exception as e:
                raise ReportSchedulerError(f"Invalid cron expression: {str(e)}")
        
        elif config.schedule_type.value in ["daily", "weekly", "monthly"]:
            if not config.time_of_day:
                raise ReportSchedulerError(f"time_of_day is required for {config.schedule_type.value} schedule")
            
            # Validate time format (HH:MM)
            try:
                time_parts = config.time_of_day.split(":")
                if len(time_parts) != 2:
                    raise ValueError("Invalid time format")
                hour, minute = int(time_parts[0]), int(time_parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError("Invalid time values")
            except ValueError:
                raise ReportSchedulerError("time_of_day must be in HH:MM format (24-hour)")
        
        if config.schedule_type.value == "weekly" and config.day_of_week is not None:
            if not (0 <= config.day_of_week <= 6):
                raise ReportSchedulerError("day_of_week must be between 0 (Monday) and 6 (Sunday)")
        
        if config.schedule_type.value == "monthly" and config.day_of_month is not None:
            if not (1 <= config.day_of_month <= 31):
                raise ReportSchedulerError("day_of_month must be between 1 and 31")
    
    def _validate_recipients(self, recipients: List[str]) -> None:
        """Validate email recipients."""
        if not recipients:
            raise ReportSchedulerError("At least one recipient email is required")
        
        import re
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        for email in recipients:
            if not email_pattern.match(email):
                raise ReportSchedulerError(f"Invalid email address: {email}")
    
    def _calculate_next_run(self, config: ScheduleConfig) -> datetime:
        """Calculate the next run time based on schedule configuration."""
        now = datetime.now(timezone.utc)
        
        if config.schedule_type.value == "cron":
            cron = croniter(config.cron_expression, now)
            return cron.get_next(datetime)
        
        elif config.schedule_type.value == "daily":
            # Parse time
            hour, minute = map(int, config.time_of_day.split(":"))
            
            # Calculate next occurrence
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            return next_run
        
        elif config.schedule_type.value == "weekly":
            # Parse time
            hour, minute = map(int, config.time_of_day.split(":"))
            
            # Calculate next occurrence
            target_weekday = config.day_of_week or 0  # Default to Monday
            days_ahead = target_weekday - now.weekday()
            
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            
            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            return next_run
        
        elif config.schedule_type.value == "monthly":
            # Parse time
            hour, minute = map(int, config.time_of_day.split(":"))
            
            # Calculate next occurrence
            target_day = config.day_of_month or 1
            
            # Try current month first
            try:
                next_run = now.replace(day=target_day, hour=hour, minute=minute, second=0, microsecond=0)
                if next_run > now:
                    return next_run
            except ValueError:
                pass  # Invalid day for current month
            
            # Move to next month
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            
            # Find valid day in next month
            import calendar
            max_day = calendar.monthrange(next_month.year, next_month.month)[1]
            actual_day = min(target_day, max_day)
            
            next_run = next_month.replace(day=actual_day, hour=hour, minute=minute, second=0, microsecond=0)
            return next_run
        
        elif config.schedule_type.value == "yearly":
            # For yearly, run once per year at the same time
            next_run = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return next_run
        
        else:
            raise ReportSchedulerError(f"Unsupported schedule type: {config.schedule_type}")
    
    def _get_scheduled_report_with_access(self, schedule_id: int, user_id: int) -> ScheduledReport:
        """Get scheduled report with access control check."""
        scheduled_report = self.db.query(ScheduledReport).join(ScheduledReport.template).filter(
            and_(
                ScheduledReport.id == schedule_id,
                or_(
                    ReportTemplate.user_id == user_id,
                    ReportTemplate.is_shared == True
                )
            )
        ).first()
        
        if not scheduled_report:
            raise ReportSchedulerError(f"Scheduled report {schedule_id} not found or access denied")
        
        return scheduled_report
    
    def _send_scheduled_report_email(
        self,
        scheduled_report: ScheduledReport,
        template: ReportTemplate,
        report_result: ReportResult
    ) -> None:
        """Send scheduled report via email."""
        try:
            # Get export format and generate report content
            export_format = ExportFormat(
                scheduled_report.schedule_config.get("export_format", "pdf")
            )
            
            # Export the report data to get the content
            report_content = None
            if report_result.data and export_format != ExportFormat.JSON:
                try:
                    report_content = self.report_exporter.export_report(
                        report_result.data, 
                        export_format
                    )
                except Exception as e:
                    logger.error(f"Failed to export report for email: {str(e)}")
                    # Continue without attachment
            
            # Determine file extension based on export format
            file_extension = {
                ExportFormat.PDF: "pdf",
                ExportFormat.CSV: "csv", 
                ExportFormat.EXCEL: "xlsx",
                ExportFormat.JSON: "json"
            }.get(export_format, "pdf")
            
            # Create attachment if we have content
            attachments = []
            if report_content:
                # Handle both bytes and string content
                if isinstance(report_content, str):
                    content_bytes = report_content.encode('utf-8')
                else:
                    content_bytes = report_content
                    
                attachment = EmailAttachment(
                    filename=f"{template.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}",
                    content=content_bytes,
                    content_type=self._get_content_type(file_extension)
                )
                attachments.append(attachment)
            
            # Create email message for each recipient
            for recipient_email in scheduled_report.recipients:
                message = EmailMessage(
                    to_email=recipient_email,
                    to_name=recipient_email.split('@')[0],  # Use email prefix as name
                    subject=f"Scheduled Report: {template.name}",
                    html_body=self._create_scheduled_report_html(template, report_result),
                    text_body=self._create_scheduled_report_text(template, report_result),
                    from_email=self.settings.EMAIL_FROM or "noreply@invoiceapp.com",
                    from_name=self.settings.EMAIL_FROM_NAME or "Invoice Management System",
                    attachments=attachments
                )
                
                success = self.email_service.send_email(message)
                if not success:
                    logger.error(f"Failed to send scheduled report email to {recipient_email}")
                else:
                    logger.info(f"Sent scheduled report email to {recipient_email}")
        
        except Exception as e:
            logger.error(f"Failed to send scheduled report email: {str(e)}")
            raise ReportSchedulerError(f"Failed to send email: {str(e)}")
    
    def _get_content_type(self, file_extension: str) -> str:
        """Get MIME content type for file extension."""
        content_types = {
            "pdf": "application/pdf",
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "json": "application/json"
        }
        return content_types.get(file_extension, "application/octet-stream")
    
    def _create_scheduled_report_html(self, template: ReportTemplate, report_result: ReportResult) -> str:
        """Create HTML email body for scheduled report."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Scheduled Report: {template.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .content {{ background-color: #fff; padding: 20px; border: 1px solid #dee2e6; border-radius: 5px; }}
                .footer {{ margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; font-size: 12px; color: #6c757d; }}
                .success {{ color: #28a745; font-weight: bold; }}
                .error {{ color: #dc3545; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Scheduled Report</h1>
                    <p>Your automated report has been generated and is attached to this email.</p>
                </div>
                
                <div class="content">
                    <h2>Report Details</h2>
                    <p><strong>Report Name:</strong> {template.name}</p>
                    <p><strong>Report Type:</strong> {template.report_type.title()}</p>
                    <p><strong>Generated:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    <p><strong>Status:</strong> <span class="{'success' if report_result.success else 'error'}">
                        {'Success' if report_result.success else 'Failed'}
                    </span></p>
                    
                    {f'<p><strong>Error:</strong> <span class="error">{report_result.error_message}</span></p>' if not report_result.success else ''}
                    
                    <p>Please find the generated report attached to this email.</p>
                </div>
                
                <div class="footer">
                    <p>This is an automated email from your Invoice Management System.</p>
                    <p>If you no longer wish to receive these reports, please contact your administrator.</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_scheduled_report_text(self, template: ReportTemplate, report_result: ReportResult) -> str:
        """Create plain text email body for scheduled report."""
        return f"""
Scheduled Report: {template.name}

Your automated report has been generated and is attached to this email.

Report Details:
- Report Name: {template.name}
- Report Type: {template.report_type.title()}
- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
- Status: {'Success' if report_result.success else 'Failed'}

{f'Error: {report_result.error_message}' if not report_result.success else ''}

Please find the generated report attached to this email.

---
This is an automated email from your Invoice Management System.
If you no longer wish to receive these reports, please contact your administrator.
        """