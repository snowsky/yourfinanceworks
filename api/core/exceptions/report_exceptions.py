"""
Custom exception classes for the reporting module.

This module defines comprehensive error handling for all reporting operations
including validation, generation, export, scheduling, and template management.
"""

from typing import Optional, List, Dict, Any
from enum import Enum


class ReportErrorCode(str, Enum):
    """Enumeration of all report-related error codes"""
    
    # General Report Errors
    REPORT_INVALID_TYPE = "REPORT_001"
    REPORT_INVALID_FILTERS = "REPORT_002"
    REPORT_DATA_TOO_LARGE = "REPORT_003"
    REPORT_GENERATION_FAILED = "REPORT_004"
    REPORT_ACCESS_DENIED = "REPORT_005"
    REPORT_NOT_FOUND = "REPORT_006"
    REPORT_TIMEOUT = "REPORT_007"
    
    # Validation Errors
    VALIDATION_DATE_RANGE_INVALID = "VALIDATION_001"
    VALIDATION_FILTER_MISSING = "VALIDATION_002"
    VALIDATION_FILTER_INVALID = "VALIDATION_003"
    VALIDATION_CLIENT_NOT_FOUND = "VALIDATION_004"
    VALIDATION_AMOUNT_RANGE_INVALID = "VALIDATION_005"
    VALIDATION_CURRENCY_INVALID = "VALIDATION_006"
    VALIDATION_EXPORT_FORMAT_INVALID = "VALIDATION_007"
    
    # Template Errors
    TEMPLATE_NOT_FOUND = "TEMPLATE_001"
    TEMPLATE_INVALID_FORMAT = "TEMPLATE_002"
    TEMPLATE_ACCESS_DENIED = "TEMPLATE_003"
    TEMPLATE_NAME_EXISTS = "TEMPLATE_004"
    TEMPLATE_CREATION_FAILED = "TEMPLATE_005"
    TEMPLATE_UPDATE_FAILED = "TEMPLATE_006"
    TEMPLATE_DELETE_FAILED = "TEMPLATE_007"
    
    # Schedule Errors
    SCHEDULE_INVALID_CRON = "SCHEDULE_001"
    SCHEDULE_EMAIL_FAILED = "SCHEDULE_002"
    SCHEDULE_EXECUTION_FAILED = "SCHEDULE_003"
    SCHEDULE_NOT_FOUND = "SCHEDULE_004"
    SCHEDULE_ACCESS_DENIED = "SCHEDULE_005"
    SCHEDULE_CREATION_FAILED = "SCHEDULE_006"
    SCHEDULE_UPDATE_FAILED = "SCHEDULE_007"
    SCHEDULE_DELETE_FAILED = "SCHEDULE_008"
    
    # Export Errors
    EXPORT_FORMAT_UNSUPPORTED = "EXPORT_001"
    EXPORT_GENERATION_FAILED = "EXPORT_002"
    EXPORT_FILE_TOO_LARGE = "EXPORT_003"
    EXPORT_PERMISSION_DENIED = "EXPORT_004"
    EXPORT_STORAGE_FAILED = "EXPORT_005"
    
    # Data Errors
    DATA_INSUFFICIENT_PERMISSIONS = "DATA_001"
    DATA_TENANT_ISOLATION_VIOLATION = "DATA_002"
    DATA_QUERY_FAILED = "DATA_003"
    DATA_AGGREGATION_FAILED = "DATA_004"
    DATA_CONNECTION_FAILED = "DATA_005"


class BaseReportException(Exception):
    """Base exception class for all reporting module errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ReportErrorCode,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        field: Optional[str] = None,
        retryable: bool = False
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestions = suggestions or []
        self.field = field
        self.retryable = retryable
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions,
            "field": self.field,
            "retryable": self.retryable
        }


class ReportValidationException(BaseReportException):
    """Exception for report validation errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ReportErrorCode,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            field=field,
            details=details,
            suggestions=suggestions,
            retryable=False
        )


class ReportGenerationException(BaseReportException):
    """Exception for report generation errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ReportErrorCode,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        retryable: bool = True
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            suggestions=suggestions,
            retryable=retryable
        )


class ReportTemplateException(BaseReportException):
    """Exception for report template errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ReportErrorCode,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        retryable: bool = False
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            suggestions=suggestions,
            retryable=retryable
        )


class ReportScheduleException(BaseReportException):
    """Exception for report scheduling errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ReportErrorCode,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        retryable: bool = True
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            suggestions=suggestions,
            retryable=retryable
        )


class ReportExportException(BaseReportException):
    """Exception for report export errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ReportErrorCode,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        retryable: bool = True
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            suggestions=suggestions,
            retryable=retryable
        )


class ReportDataException(BaseReportException):
    """Exception for report data access errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ReportErrorCode,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        retryable: bool = True
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            suggestions=suggestions,
            retryable=retryable
        )


# Convenience functions for creating common exceptions
def validation_error(
    message: str,
    field: Optional[str] = None,
    suggestions: Optional[List[str]] = None
) -> ReportValidationException:
    """Create a generic validation error"""
    return ReportValidationException(
        message=message,
        error_code=ReportErrorCode.VALIDATION_FILTER_INVALID,
        field=field,
        suggestions=suggestions
    )


def date_range_error(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> ReportValidationException:
    """Create a date range validation error"""
    details = {}
    if date_from:
        details["date_from"] = date_from
    if date_to:
        details["date_to"] = date_to
    
    return ReportValidationException(
        message="Invalid date range specified",
        error_code=ReportErrorCode.VALIDATION_DATE_RANGE_INVALID,
        field="date_range",
        details=details,
        suggestions=[
            "Ensure date_from is before date_to",
            "Use ISO format (YYYY-MM-DD) for dates",
            "Date range cannot exceed 2 years"
        ]
    )


def client_not_found_error(client_ids: List[int]) -> ReportValidationException:
    """Create a client not found validation error"""
    return ReportValidationException(
        message=f"One or more clients not found: {client_ids}",
        error_code=ReportErrorCode.VALIDATION_CLIENT_NOT_FOUND,
        field="client_ids",
        details={"invalid_client_ids": client_ids},
        suggestions=[
            "Verify client IDs exist in your organization",
            "Check if clients have been deleted",
            "Ensure you have permission to access these clients"
        ]
    )


def amount_range_error(
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None
) -> ReportValidationException:
    """Create an amount range validation error"""
    return ReportValidationException(
        message="Invalid amount range specified",
        error_code=ReportErrorCode.VALIDATION_AMOUNT_RANGE_INVALID,
        field="amount_range",
        details={"amount_min": amount_min, "amount_max": amount_max},
        suggestions=[
            "Ensure amount_min is less than amount_max",
            "Amount values must be positive",
            "Use decimal format for amounts"
        ]
    )


def template_not_found_error(template_id: int) -> ReportTemplateException:
    """Create a template not found error"""
    return ReportTemplateException(
        message=f"Report template not found: {template_id}",
        error_code=ReportErrorCode.TEMPLATE_NOT_FOUND,
        details={"template_id": template_id},
        suggestions=[
            "Verify the template ID is correct",
            "Check if the template has been deleted",
            "Ensure you have permission to access this template"
        ]
    )


def schedule_not_found_error(schedule_id: int) -> ReportScheduleException:
    """Create a schedule not found error"""
    return ReportScheduleException(
        message=f"Scheduled report not found: {schedule_id}",
        error_code=ReportErrorCode.SCHEDULE_NOT_FOUND,
        details={"schedule_id": schedule_id},
        suggestions=[
            "Verify the schedule ID is correct",
            "Check if the schedule has been deleted",
            "Ensure you have permission to access this schedule"
        ]
    )


def export_format_error(format_name: str) -> ReportExportException:
    """Create an export format error"""
    return ReportExportException(
        message=f"Unsupported export format: {format_name}",
        error_code=ReportErrorCode.EXPORT_FORMAT_UNSUPPORTED,
        details={"requested_format": format_name},
        suggestions=[
            "Supported formats: PDF, CSV, Excel, JSON",
            "Check the format parameter spelling",
            "Contact support if you need additional formats"
        ]
    )


# Additional exception classes for backward compatibility
class ReportAccessDeniedException(BaseReportException):
    """Exception for access denied errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ReportErrorCode,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            suggestions=suggestions or [
                "Check your user permissions",
                "Contact your administrator for access",
                "Verify you're accessing the correct resource"
            ],
            retryable=False
        )


class TemplateValidationError(ReportTemplateException):
    """Legacy exception for template validation errors"""
    pass


class TemplateAccessError(ReportTemplateException):
    """Legacy exception for template access errors"""
    pass


class ReportValidationError(ReportValidationException):
    """Legacy exception for report validation errors"""
    pass


class ReportSchedulerError(ReportScheduleException):
    """Legacy exception for scheduler errors"""
    pass