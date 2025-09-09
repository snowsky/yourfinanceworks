"""
Report Security Service

Comprehensive security service for reporting module including:
- Role-based access control
- Data redaction for sensitive information
- Permission validation
- Security policy enforcement
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Set, Union
from fastapi import HTTPException, status
import logging
from datetime import datetime

from models.models import MasterUser
from models.models_per_tenant import User, ReportTemplate, ScheduledReport
from utils.rbac import (
    require_roles, can_user_perform_action, is_admin, is_viewer,
    require_report_access, require_report_management
)
from schemas.report import ReportType, ExportFormat
from exceptions.report_exceptions import ReportAccessDeniedException, ReportErrorCode

logger = logging.getLogger(__name__)


class ReportSecurityService:
    """Service for handling all report security operations."""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Define sensitive fields that may need redaction
        self.sensitive_fields = {
            ReportType.CLIENT: {
                'email', 'phone', 'address', 'tax_id', 'bank_account',
                'credit_card', 'ssn', 'personal_notes'
            },
            ReportType.INVOICE: {
                'client_email', 'client_phone', 'client_address', 
                'bank_details', 'payment_reference'
            },
            ReportType.PAYMENT: {
                'bank_account', 'credit_card', 'payment_reference',
                'routing_number', 'account_number'
            },
            ReportType.EXPENSE: {
                'vendor_tax_id', 'credit_card', 'bank_account',
                'personal_notes', 'receipt_details'
            },
            ReportType.STATEMENT: {
                'account_number', 'routing_number', 'bank_details',
                'transaction_reference', 'merchant_details'
            }
        }
        
        # Define role-based permissions
        self.role_permissions = {
            'admin': {
                'generate_reports': True,
                'view_all_reports': True,
                'manage_templates': True,
                'share_templates': True,
                'schedule_reports': True,
                'access_history': True,
                'download_reports': True,
                'delete_reports': True,
                'view_audit_logs': True,
                'manage_permissions': True
            },
            'user': {
                'generate_reports': True,
                'view_all_reports': False,
                'manage_templates': True,
                'share_templates': True,
                'schedule_reports': True,
                'access_history': True,
                'download_reports': True,
                'delete_reports': True,
                'view_audit_logs': False,
                'manage_permissions': False
            },
            'viewer': {
                'generate_reports': True,
                'view_all_reports': False,
                'manage_templates': False,
                'share_templates': False,
                'schedule_reports': False,
                'access_history': True,
                'download_reports': True,
                'delete_reports': False,
                'view_audit_logs': False,
                'manage_permissions': False
            }
        }
    
    def validate_report_access(
        self,
        user: Union[User, MasterUser],
        action: str,
        resource_type: str = "report"
    ) -> bool:
        """
        Validate if user has permission for a specific report action.
        
        Args:
            user: Current user
            action: Action being attempted
            resource_type: Type of resource being accessed
            
        Returns:
            True if access is granted
            
        Raises:
            ReportAccessDeniedException: If access is denied
        """
        user_role = user.role
        permissions = self.role_permissions.get(user_role, {})
        
        # Map actions to permission keys
        action_permission_map = {
            'generate': 'generate_reports',
            'view': 'generate_reports',
            'download': 'download_reports',
            'create_template': 'manage_templates',
            'update_template': 'manage_templates',
            'delete_template': 'manage_templates',
            'share_template': 'share_templates',
            'create_schedule': 'schedule_reports',
            'update_schedule': 'schedule_reports',
            'delete_schedule': 'schedule_reports',
            'view_history': 'access_history',
            'delete_report': 'delete_reports',
            'view_audit': 'view_audit_logs',
            'manage_permissions': 'manage_permissions'
        }
        
        permission_key = action_permission_map.get(action)
        if not permission_key:
            logger.warning(f"Unknown action: {action}")
            raise ReportAccessDeniedException(
                f"Unknown action: {action}",
                ReportErrorCode.REPORT_ACCESS_DENIED
            )
        
        has_permission = permissions.get(permission_key, False)
        
        if not has_permission:
            logger.warning(f"Access denied for user {user.id} ({user_role}) to {action} on {resource_type}")
            raise ReportAccessDeniedException(
                f"Insufficient permissions to {action} {resource_type}",
                ReportErrorCode.REPORT_ACCESS_DENIED,
                details={
                    "user_role": user_role,
                    "required_permission": permission_key,
                    "action": action,
                    "resource_type": resource_type
                }
            )
        
        return True
    
    def validate_template_access(
        self,
        user: Union[User, MasterUser],
        template_id: int,
        action: str
    ) -> ReportTemplate:
        """
        Validate access to a specific template.
        
        Args:
            user: Current user
            template_id: ID of template to access
            action: Action being attempted
            
        Returns:
            Template if access is granted
            
        Raises:
            ReportAccessDeniedException: If access is denied
        """
        # First validate general permission
        self.validate_report_access(user, action, "template")
        
        # Get the template
        template = self.db.query(ReportTemplate).filter(
            ReportTemplate.id == template_id
        ).first()
        
        if not template:
            raise ReportAccessDeniedException(
                "Template not found",
                ReportErrorCode.TEMPLATE_NOT_FOUND
            )
        
        # Check ownership or sharing permissions
        if template.user_id == user.id:
            # User owns the template
            return template
        
        if template.is_shared and action in ['view', 'generate']:
            # Template is shared and user wants to view/use it
            return template
        
        if is_admin(user):
            # Admins can access all templates
            return template
        
        # Access denied
        raise ReportAccessDeniedException(
            "Access denied to template",
            ReportErrorCode.TEMPLATE_ACCESS_DENIED,
            details={
                "template_id": template_id,
                "template_owner": template.user_id,
                "user_id": user.id,
                "action": action
            }
        )
    
    def validate_schedule_access(
        self,
        user: Union[User, MasterUser],
        schedule_id: int,
        action: str
    ) -> ScheduledReport:
        """
        Validate access to a specific scheduled report.
        
        Args:
            user: Current user
            schedule_id: ID of schedule to access
            action: Action being attempted
            
        Returns:
            Scheduled report if access is granted
            
        Raises:
            ReportAccessDeniedException: If access is denied
        """
        # First validate general permission
        self.validate_report_access(user, action, "schedule")
        
        # Get the scheduled report and its template
        schedule = self.db.query(ScheduledReport).join(ReportTemplate).filter(
            ScheduledReport.id == schedule_id
        ).first()
        
        if not schedule:
            raise ReportAccessDeniedException(
                "Scheduled report not found",
                ReportErrorCode.SCHEDULE_NOT_FOUND
            )
        
        # Check if user owns the template
        if schedule.template.user_id == user.id:
            return schedule
        
        if is_admin(user):
            # Admins can access all schedules
            return schedule
        
        # Access denied
        raise ReportAccessDeniedException(
            "Access denied to scheduled report",
            ReportErrorCode.SCHEDULE_ACCESS_DENIED,
            details={
                "schedule_id": schedule_id,
                "template_owner": schedule.template.user_id,
                "user_id": user.id,
                "action": action
            }
        )
    
    def apply_data_redaction(
        self,
        report_data: Dict[str, Any],
        report_type: ReportType,
        user: Union[User, MasterUser],
        redaction_level: str = "standard"
    ) -> Dict[str, Any]:
        """
        Apply data redaction based on user role and redaction level.
        
        Args:
            report_data: Original report data
            report_type: Type of report
            user: Current user
            redaction_level: Level of redaction (none, standard, strict)
            
        Returns:
            Report data with appropriate redaction applied
        """
        if redaction_level == "none" or is_admin(user):
            # No redaction for admins or when explicitly disabled
            return report_data
        
        sensitive_fields = self.sensitive_fields.get(report_type, set())
        
        if not sensitive_fields:
            # No sensitive fields defined for this report type
            return report_data
        
        redacted_data = report_data.copy()
        redacted_fields = []
        
        # Apply redaction to data rows
        if 'data' in redacted_data and isinstance(redacted_data['data'], list):
            for row in redacted_data['data']:
                if isinstance(row, dict):
                    for field in sensitive_fields:
                        if field in row:
                            if redaction_level == "strict":
                                row[field] = "[REDACTED]"
                            else:  # standard redaction
                                row[field] = self._partial_redact(row[field])
                            redacted_fields.append(field)
        
        # Apply redaction to summary data if present
        if 'summary' in redacted_data and isinstance(redacted_data['summary'], dict):
            for field in sensitive_fields:
                if field in redacted_data['summary']:
                    if redaction_level == "strict":
                        redacted_data['summary'][field] = "[REDACTED]"
                    else:
                        redacted_data['summary'][field] = self._partial_redact(
                            redacted_data['summary'][field]
                        )
                    redacted_fields.append(f"summary.{field}")
        
        # Add redaction metadata
        if redacted_fields:
            redacted_data['_redaction_applied'] = {
                'level': redaction_level,
                'fields': list(set(redacted_fields)),
                'user_role': user.role,
                'applied_at': datetime.utcnow().isoformat()
            }
        
        return redacted_data
    
    def _partial_redact(self, value: Any) -> str:
        """Apply partial redaction to a value."""
        if value is None:
            return None
        
        str_value = str(value)
        
        # Email redaction: show first char and domain
        if '@' in str_value:
            parts = str_value.split('@')
            if len(parts) == 2:
                return f"{parts[0][0]}***@{parts[1]}"
        
        # Phone number redaction: show last 4 digits
        if str_value.replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
            clean_number = ''.join(filter(str.isdigit, str_value))
            if len(clean_number) >= 4:
                return f"***-***-{clean_number[-4:]}"
        
        # General redaction: show first and last character for strings > 4 chars
        if len(str_value) > 4:
            return f"{str_value[0]}***{str_value[-1]}"
        elif len(str_value) > 1:
            return f"{str_value[0]}***"
        else:
            return "***"
    
    def get_user_permissions(self, user: Union[User, MasterUser]) -> Dict[str, bool]:
        """Get all permissions for a user."""
        return self.role_permissions.get(user.role, {})
    
    def can_access_report_type(
        self,
        user: Union[User, MasterUser],
        report_type: ReportType
    ) -> bool:
        """Check if user can access a specific report type."""
        # For now, all users with report access can access all report types
        # This could be extended to have type-specific permissions
        try:
            self.validate_report_access(user, 'generate')
            return True
        except ReportAccessDeniedException:
            return False
    
    def get_allowed_export_formats(
        self,
        user: Union[User, MasterUser]
    ) -> List[ExportFormat]:
        """Get allowed export formats for a user."""
        # Viewers might have restricted export formats
        if is_viewer(user):
            return [ExportFormat.JSON, ExportFormat.CSV]
        
        # All other users can use all formats
        return list(ExportFormat)
    
    def validate_export_format(
        self,
        user: Union[User, MasterUser],
        export_format: ExportFormat
    ) -> bool:
        """Validate if user can use a specific export format."""
        allowed_formats = self.get_allowed_export_formats(user)
        
        if export_format not in allowed_formats:
            raise ReportAccessDeniedException(
                f"Export format {export_format.value} not allowed for role {user.role}",
                ReportErrorCode.EXPORT_FORMAT_UNSUPPORTED,
                details={
                    "user_role": user.role,
                    "requested_format": export_format.value,
                    "allowed_formats": [f.value for f in allowed_formats]
                }
            )
        
        return True
    
    def get_data_access_filters(
        self,
        user: Union[User, MasterUser]
    ) -> Dict[str, Any]:
        """
        Get additional filters to apply based on user permissions.
        
        This can be used to restrict data access based on user role or other criteria.
        """
        filters = {}
        
        # Viewers might have additional restrictions
        if is_viewer(user):
            # Example: Limit to recent data only
            filters['_max_days_back'] = 90
        
        # Non-admin users are automatically filtered by tenant
        # This is handled at the database level
        
        return filters


class ReportRateLimiter:
    """Rate limiting service for report operations."""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Define rate limits per role (requests per hour)
        self.rate_limits = {
            'admin': {
                'report_generation': 100,
                'template_operations': 50,
                'schedule_operations': 20
            },
            'user': {
                'report_generation': 50,
                'template_operations': 25,
                'schedule_operations': 10
            },
            'viewer': {
                'report_generation': 20,
                'template_operations': 0,  # Viewers can't manage templates
                'schedule_operations': 0   # Viewers can't manage schedules
            }
        }
    
    def check_rate_limit(
        self,
        user: Union[User, MasterUser],
        operation_type: str
    ) -> bool:
        """
        Check if user has exceeded rate limit for operation type.
        
        Args:
            user: Current user
            operation_type: Type of operation (report_generation, template_operations, etc.)
            
        Returns:
            True if within rate limit, False if exceeded
        """
        user_limits = self.rate_limits.get(user.role, {})
        limit = user_limits.get(operation_type, 0)
        
        if limit == 0:
            # Operation not allowed for this role
            return False
        
        # Count operations in the last hour
        from sqlalchemy import func
        one_hour_ago = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        # Map operation types to audit log actions
        action_map = {
            'report_generation': ['REPORT_GENERATE'],
            'template_operations': ['TEMPLATE_CREATE', 'TEMPLATE_UPDATE', 'TEMPLATE_DELETE'],
            'schedule_operations': ['SCHEDULE_CREATE', 'SCHEDULE_UPDATE', 'SCHEDULE_DELETE']
        }
        
        actions = action_map.get(operation_type, [])
        if not actions:
            return True  # Unknown operation type, allow it
        
        from models.models_per_tenant import AuditLog
        count = self.db.query(func.count(AuditLog.id)).filter(
            AuditLog.user_id == user.id,
            AuditLog.action.in_(actions),
            AuditLog.created_at >= one_hour_ago,
            AuditLog.status == 'success'
        ).scalar()
        
        return count < limit
    
    def get_rate_limit_info(
        self,
        user: Union[User, MasterUser],
        operation_type: str
    ) -> Dict[str, Any]:
        """Get rate limit information for a user and operation type."""
        user_limits = self.rate_limits.get(user.role, {})
        limit = user_limits.get(operation_type, 0)
        
        # Count current usage
        from sqlalchemy import func
        one_hour_ago = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        action_map = {
            'report_generation': ['REPORT_GENERATE'],
            'template_operations': ['TEMPLATE_CREATE', 'TEMPLATE_UPDATE', 'TEMPLATE_DELETE'],
            'schedule_operations': ['SCHEDULE_CREATE', 'SCHEDULE_UPDATE', 'SCHEDULE_DELETE']
        }
        
        actions = action_map.get(operation_type, [])
        current_usage = 0
        
        if actions:
            from models.models_per_tenant import AuditLog
            current_usage = self.db.query(func.count(AuditLog.id)).filter(
                AuditLog.user_id == user.id,
                AuditLog.action.in_(actions),
                AuditLog.created_at >= one_hour_ago,
                AuditLog.status == 'success'
            ).scalar()
        
        return {
            'limit': limit,
            'current_usage': current_usage,
            'remaining': max(0, limit - current_usage),
            'reset_time': one_hour_ago.replace(hour=one_hour_ago.hour + 1).isoformat(),
            'operation_type': operation_type,
            'user_role': user.role
        }