"""
Report Audit Service

Comprehensive audit logging service for all reporting operations.
Tracks report generation, template management, scheduling, and access patterns.
"""

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json
import logging
from fastapi import Request

from utils.audit import log_audit_event, convert_datetimes
from models.models_per_tenant import AuditLog
from models.models import MasterUser
from schemas.report import ReportType, ExportFormat

logger = logging.getLogger(__name__)


class ReportAuditService:
    """Service for auditing all report-related operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_report_generation(
        self,
        user_id: int,
        user_email: str,
        report_type: ReportType,
        export_format: ExportFormat,
        filters: Dict[str, Any],
        template_id: Optional[int] = None,
        report_id: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        record_count: Optional[int] = None,
        file_size_bytes: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Log report generation activity.
        
        Args:
            user_id: ID of the user generating the report
            user_email: Email of the user
            report_type: Type of report being generated
            export_format: Export format requested
            filters: Filters applied to the report
            template_id: ID of template used (if any)
            report_id: Generated report ID
            status: Operation status (success, error, warning)
            error_message: Error message if failed
            execution_time_ms: Time taken to generate report
            record_count: Number of records in report
            file_size_bytes: Size of generated file
            ip_address: User's IP address
            user_agent: User's browser/client info
            
        Returns:
            Created audit log entry
        """
        details = {
            "report_type": report_type.value,
            "export_format": export_format.value,
            "filters": convert_datetimes(filters),
            "template_id": template_id,
            "report_id": report_id,
            "execution_time_ms": execution_time_ms,
            "record_count": record_count,
            "file_size_bytes": file_size_bytes
        }
        
        # Remove None values to keep audit log clean
        details = {k: v for k, v in details.items() if v is not None}
        
        return log_audit_event(
            db=self.db,
            user_id=user_id,
            user_email=user_email,
            action="REPORT_GENERATE",
            resource_type="report",
            resource_id=report_id,
            resource_name=f"{report_type.value}_report",
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message
        )
    
    def log_report_download(
        self,
        user_id: int,
        user_email: str,
        report_id: str,
        report_type: str,
        export_format: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log report download activity."""
        details = {
            "report_type": report_type,
            "export_format": export_format,
            "action_type": "download"
        }
        
        return log_audit_event(
            db=self.db,
            user_id=user_id,
            user_email=user_email,
            action="REPORT_DOWNLOAD",
            resource_type="report",
            resource_id=report_id,
            resource_name=f"{report_type}_report",
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status="success"
        )
    
    def log_template_operation(
        self,
        user_id: int,
        user_email: str,
        action: str,  # CREATE, UPDATE, DELETE, SHARE
        template_id: Optional[int],
        template_name: str,
        report_type: Optional[str] = None,
        shared_with: Optional[List[int]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Log template management operations."""
        details = {
            "template_name": template_name,
            "report_type": report_type,
            "shared_with": shared_with
        }
        
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
        
        return log_audit_event(
            db=self.db,
            user_id=user_id,
            user_email=user_email,
            action=f"TEMPLATE_{action}",
            resource_type="report_template",
            resource_id=str(template_id) if template_id else None,
            resource_name=template_name,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message
        )
    
    def log_schedule_operation(
        self,
        user_id: int,
        user_email: str,
        action: str,  # CREATE, UPDATE, DELETE, PAUSE, RESUME
        schedule_id: Optional[int],
        template_id: int,
        template_name: str,
        schedule_config: Optional[Dict[str, Any]] = None,
        recipients: Optional[List[str]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Log scheduled report operations."""
        details = {
            "template_id": template_id,
            "template_name": template_name,
            "schedule_config": schedule_config,
            "recipients": recipients
        }
        
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
        
        return log_audit_event(
            db=self.db,
            user_id=user_id,
            user_email=user_email,
            action=f"SCHEDULE_{action}",
            resource_type="scheduled_report",
            resource_id=str(schedule_id) if schedule_id else None,
            resource_name=f"schedule_for_{template_name}",
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message
        )
    
    def log_scheduled_execution(
        self,
        schedule_id: int,
        template_id: int,
        template_name: str,
        report_id: Optional[str] = None,
        recipients: Optional[List[str]] = None,
        execution_time_ms: Optional[int] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Log automated scheduled report execution."""
        details = {
            "schedule_id": schedule_id,
            "template_id": template_id,
            "template_name": template_name,
            "report_id": report_id,
            "recipients": recipients,
            "execution_time_ms": execution_time_ms,
            "automated": True
        }
        
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
        
        # Use system user ID for automated executions
        return log_audit_event(
            db=self.db,
            user_id=0,  # System user
            user_email="system@automated",
            action="REPORT_GENERATE_SCHEDULED",
            resource_type="scheduled_report",
            resource_id=str(schedule_id),
            resource_name=f"scheduled_{template_name}",
            details=details,
            status=status,
            error_message=error_message
        )
    
    def log_access_attempt(
        self,
        user_id: int,
        user_email: str,
        resource_type: str,  # report, template, schedule
        resource_id: str,
        action: str,  # VIEW, DOWNLOAD, EDIT, DELETE
        access_granted: bool,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log access attempts for security monitoring."""
        details = {
            "access_granted": access_granted,
            "reason": reason,
            "attempted_action": action
        }
        
        status = "success" if access_granted else "access_denied"
        
        return log_audit_event(
            db=self.db,
            user_id=user_id,
            user_email=user_email,
            action=f"ACCESS_{action}",
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=reason if not access_granted else None
        )
    
    def log_data_redaction(
        self,
        user_id: int,
        user_email: str,
        report_id: str,
        redacted_fields: List[str],
        redaction_reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log data redaction operations for compliance."""
        details = {
            "redacted_fields": redacted_fields,
            "redaction_reason": redaction_reason,
            "redaction_applied": True
        }
        
        return log_audit_event(
            db=self.db,
            user_id=user_id,
            user_email=user_email,
            action="DATA_REDACTION",
            resource_type="report",
            resource_id=report_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status="success"
        )
    
    def get_user_report_activity(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get report activity for a specific user."""
        query = self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.resource_type.in_(['report', 'report_template', 'scheduled_report'])
        )
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    def get_report_access_logs(
        self,
        report_id: str,
        limit: int = 50
    ) -> List[AuditLog]:
        """Get all access logs for a specific report."""
        return self.db.query(AuditLog).filter(
            AuditLog.resource_type == 'report',
            AuditLog.resource_id == report_id
        ).order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    def get_failed_operations(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get failed report operations for monitoring."""
        query = self.db.query(AuditLog).filter(
            AuditLog.resource_type.in_(['report', 'report_template', 'scheduled_report']),
            AuditLog.status.in_(['error', 'access_denied'])
        )
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()


def extract_request_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract IP address and user agent from request."""
    ip_address = None
    user_agent = None
    
    if request:
        # Try to get real IP from headers (for reverse proxy setups)
        ip_address = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
            request.headers.get("X-Real-IP") or
            request.client.host if request.client else None
        )
        user_agent = request.headers.get("User-Agent")
    
    return ip_address, user_agent