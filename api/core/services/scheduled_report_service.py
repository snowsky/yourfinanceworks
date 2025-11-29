"""
Scheduled Report Management Service

This service provides CRUD operations for managing scheduled reports,
including creation, updating, deletion, and querying of scheduled reports.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models.models_per_tenant import ScheduledReport, ReportTemplate
from core.schemas.report import (
    ScheduledReportCreate, ScheduledReportUpdate, ScheduledReport as ScheduledReportSchema,
    ScheduledReportListResponse
)
from core.services.report_scheduler import ReportScheduler
from core.services.report_validation_service import ReportValidationService
from core.services.report_retry_service import ReportRetryService, retry_on_failure
from core.exceptions.report_exceptions import (
    ReportScheduleException, ReportValidationException, ReportErrorCode,
    schedule_not_found_error, validation_error
)

logger = logging.getLogger(__name__)


class ScheduledReportService:
    """
    Service for managing scheduled reports with full CRUD operations.
    
    This service acts as a higher-level interface for scheduled report management,
    providing business logic and validation on top of the ReportScheduler.
    """
    
    def __init__(self, db: Session, report_scheduler: ReportScheduler):
        self.db = db
        self.report_scheduler = report_scheduler
        self.validation_service = ReportValidationService(db)
        self.retry_service = ReportRetryService()
    
    def create_scheduled_report(
        self, 
        schedule_data: ScheduledReportCreate, 
        user_id: int
    ) -> ScheduledReportSchema:
        """
        Create a new scheduled report.
        
        Args:
            schedule_data: Schedule configuration data
            user_id: ID of the user creating the schedule
            
        Returns:
            Created ScheduledReport schema
            
        Raises:
            ReportSchedulerError: If creation fails
        """
        try:
            # Use the report scheduler to create the scheduled report
            scheduled_report = self.report_scheduler.create_scheduled_report(
                schedule_data, user_id
            )
            
            # Convert to schema and return
            return self._convert_to_schema(scheduled_report)
            
        except Exception as e:
            logger.error(f"Failed to create scheduled report: {str(e)}")
            raise ReportSchedulerError(f"Failed to create scheduled report: {str(e)}")
    
    def get_scheduled_report(self, schedule_id: int, user_id: int) -> ScheduledReportSchema:
        """
        Get a specific scheduled report by ID.
        
        Args:
            schedule_id: ID of the scheduled report
            user_id: ID of the user requesting the report
            
        Returns:
            ScheduledReport schema
            
        Raises:
            ReportSchedulerError: If report not found or access denied
        """
        try:
            scheduled_report = self.report_scheduler.get_scheduled_report(schedule_id, user_id)
            return self._convert_to_schema(scheduled_report)
            
        except Exception as e:
            logger.error(f"Failed to get scheduled report {schedule_id}: {str(e)}")
            raise ReportSchedulerError(f"Failed to get scheduled report: {str(e)}")
    
    def get_scheduled_reports(
        self, 
        user_id: int, 
        active_only: bool = False,
        template_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> ScheduledReportListResponse:
        """
        Get all scheduled reports for a user with optional filtering.
        
        Args:
            user_id: ID of the user
            active_only: If True, only return active schedules
            template_id: Optional template ID to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip
            
        Returns:
            ScheduledReportListResponse with list of scheduled reports
        """
        try:
            # Build query
            query = self.db.query(ScheduledReport).join(ScheduledReport.template).filter(
                or_(
                    ReportTemplate.user_id == user_id,
                    ReportTemplate.is_shared == True
                )
            )
            
            # Apply filters
            if active_only:
                query = query.filter(ScheduledReport.is_active == True)
            
            if template_id:
                query = query.filter(ScheduledReport.template_id == template_id)
            
            # Get total count before applying limit/offset
            total = query.count()
            
            # Apply pagination
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            # Execute query
            scheduled_reports = query.all()
            
            # Convert to schemas
            report_schemas = [self._convert_to_schema(report) for report in scheduled_reports]
            
            return ScheduledReportListResponse(
                scheduled_reports=report_schemas,
                total=total
            )
            
        except Exception as e:
            logger.error(f"Failed to get scheduled reports for user {user_id}: {str(e)}")
            raise ReportSchedulerError(f"Failed to get scheduled reports: {str(e)}")
    
    def update_scheduled_report(
        self, 
        schedule_id: int, 
        update_data: ScheduledReportUpdate, 
        user_id: int
    ) -> ScheduledReportSchema:
        """
        Update an existing scheduled report.
        
        Args:
            schedule_id: ID of the schedule to update
            update_data: Updated schedule data
            user_id: ID of the user updating the schedule
            
        Returns:
            Updated ScheduledReport schema
            
        Raises:
            ReportSchedulerError: If update fails
        """
        try:
            # Use the report scheduler to update the scheduled report
            scheduled_report = self.report_scheduler.update_scheduled_report(
                schedule_id, update_data, user_id
            )
            
            # Convert to schema and return
            return self._convert_to_schema(scheduled_report)
            
        except Exception as e:
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
            return self.report_scheduler.delete_scheduled_report(schedule_id, user_id)
            
        except Exception as e:
            logger.error(f"Failed to delete scheduled report {schedule_id}: {str(e)}")
            raise ReportSchedulerError(f"Failed to delete scheduled report: {str(e)}")
    
    def toggle_scheduled_report(self, schedule_id: int, user_id: int) -> ScheduledReportSchema:
        """
        Toggle the active status of a scheduled report.
        
        Args:
            schedule_id: ID of the schedule to toggle
            user_id: ID of the user toggling the schedule
            
        Returns:
            Updated ScheduledReport schema
            
        Raises:
            ReportSchedulerError: If toggle fails
        """
        try:
            # Get current scheduled report
            scheduled_report = self.report_scheduler.get_scheduled_report(schedule_id, user_id)
            
            # Toggle active status
            update_data = ScheduledReportUpdate(is_active=not scheduled_report.is_active)
            
            # Update the scheduled report
            updated_report = self.report_scheduler.update_scheduled_report(
                schedule_id, update_data, user_id
            )
            
            return self._convert_to_schema(updated_report)
            
        except Exception as e:
            logger.error(f"Failed to toggle scheduled report {schedule_id}: {str(e)}")
            raise ReportSchedulerError(f"Failed to toggle scheduled report: {str(e)}")
    
    def execute_scheduled_report(self, schedule_id: int, user_id: int) -> Dict[str, Any]:
        """
        Manually execute a scheduled report.
        
        Args:
            schedule_id: ID of the schedule to execute
            user_id: ID of the user executing the schedule
            
        Returns:
            Dictionary with execution result
            
        Raises:
            ReportSchedulerError: If execution fails
        """
        try:
            # Verify user has access to the scheduled report
            self.report_scheduler.get_scheduled_report(schedule_id, user_id)
            
            # Execute the scheduled report
            result = self.report_scheduler.execute_scheduled_report(schedule_id)
            
            return {
                "success": result.success,
                "message": "Report executed successfully" if result.success else result.error_message,
                "executed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to execute scheduled report {schedule_id}: {str(e)}")
            raise ReportSchedulerError(f"Failed to execute scheduled report: {str(e)}")
    
    def get_schedule_execution_history(
        self, 
        schedule_id: int, 
        user_id: int,
        limit: Optional[int] = 10
    ) -> List[Dict[str, Any]]:
        """
        Get execution history for a scheduled report.
        
        Args:
            schedule_id: ID of the scheduled report
            user_id: ID of the user requesting the history
            limit: Maximum number of history entries to return
            
        Returns:
            List of execution history entries
            
        Raises:
            ReportSchedulerError: If retrieval fails
        """
        try:
            # Verify user has access to the scheduled report
            scheduled_report = self.report_scheduler.get_scheduled_report(schedule_id, user_id)
            
            # Query report history for this template
            from ..models.models_per_tenant import ReportHistory
            
            query = self.db.query(ReportHistory).filter(
                ReportHistory.template_id == scheduled_report.template_id
            ).order_by(ReportHistory.generated_at.desc())
            
            if limit:
                query = query.limit(limit)
            
            history_entries = query.all()
            
            # Convert to response format
            history = []
            for entry in history_entries:
                history.append({
                    "id": entry.id,
                    "status": entry.status,
                    "generated_at": entry.generated_at.isoformat(),
                    "error_message": entry.error_message,
                    "parameters": entry.parameters
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get execution history for schedule {schedule_id}: {str(e)}")
            raise ReportSchedulerError(f"Failed to get execution history: {str(e)}")
    
    def get_due_schedules_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get summary of due schedules for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with due schedules summary
        """
        try:
            # Get all user's scheduled reports
            user_schedules = self.report_scheduler.get_scheduled_reports(user_id, active_only=True)
            
            # Get due schedules
            due_schedules = self.report_scheduler.get_due_schedules()
            
            # Filter due schedules to only include user's schedules
            user_due_schedules = [
                schedule for schedule in due_schedules 
                if schedule.id in [s.id for s in user_schedules]
            ]
            
            return {
                "total_active_schedules": len(user_schedules),
                "due_schedules": len(user_due_schedules),
                "next_due": min([s.next_run for s in user_schedules if s.next_run]) if user_schedules else None,
                "due_schedule_ids": [s.id for s in user_due_schedules]
            }
            
        except Exception as e:
            logger.error(f"Failed to get due schedules summary for user {user_id}: {str(e)}")
            return {
                "total_active_schedules": 0,
                "due_schedules": 0,
                "next_due": None,
                "due_schedule_ids": [],
                "error": str(e)
            }
    
    def _convert_to_schema(self, scheduled_report: ScheduledReport) -> ScheduledReportSchema:
        """Convert ScheduledReport model to schema."""
        from ..schemas.report import ScheduleConfig
        
        # Parse schedule config
        schedule_config = ScheduleConfig(**scheduled_report.schedule_config)
        
        return ScheduledReportSchema(
            id=scheduled_report.id,
            template_id=scheduled_report.template_id,
            schedule_config=schedule_config,
            recipients=scheduled_report.recipients,
            export_format=scheduled_report.schedule_config.get("export_format", "pdf"),
            is_active=scheduled_report.is_active,
            last_run=scheduled_report.last_run,
            next_run=scheduled_report.next_run,
            created_at=scheduled_report.created_at,
            updated_at=scheduled_report.updated_at
        )