from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

# Enums for report types and statuses
class ReportType(str, Enum):
    CLIENT = "client"
    INVOICE = "invoice"
    PAYMENT = "payment"
    EXPENSE = "expense"
    STATEMENT = "statement"

class ReportStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

class ScheduleType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CRON = "cron"

class ExportFormat(str, Enum):
    PDF = "pdf"
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"

# Base filter models for different report types
class BaseReportFilters(BaseModel):
    date_from: Optional[datetime] = Field(None, description="Start date for the report")
    date_to: Optional[datetime] = Field(None, description="End date for the report")
    client_ids: Optional[List[int]] = Field(None, description="List of client IDs to filter by")
    currency: Optional[str] = Field(None, description="Currency code to filter by")

class ClientReportFilters(BaseReportFilters):
    include_inactive: Optional[bool] = Field(False, description="Include inactive clients")
    balance_min: Optional[float] = Field(None, description="Minimum balance filter")
    balance_max: Optional[float] = Field(None, description="Maximum balance filter")

class InvoiceReportFilters(BaseReportFilters):
    status: Optional[List[str]] = Field(None, description="Invoice statuses to filter by")
    amount_min: Optional[float] = Field(None, description="Minimum invoice amount")
    amount_max: Optional[float] = Field(None, description="Maximum invoice amount")
    include_items: Optional[bool] = Field(False, description="Include invoice line items")
    is_recurring: Optional[bool] = Field(None, description="Filter by recurring status")

class PaymentReportFilters(BaseReportFilters):
    payment_methods: Optional[List[str]] = Field(None, description="Payment methods to filter by")
    include_unmatched: Optional[bool] = Field(False, description="Include unmatched payments")
    amount_min: Optional[float] = Field(None, description="Minimum payment amount")
    amount_max: Optional[float] = Field(None, description="Maximum payment amount")

class ExpenseReportFilters(BaseReportFilters):
    categories: Optional[List[str]] = Field(None, description="Expense categories to filter by")
    labels: Optional[List[str]] = Field(None, description="Expense labels to filter by")
    include_attachments: Optional[bool] = Field(False, description="Include attachment information")
    vendor: Optional[str] = Field(None, description="Filter by vendor name")
    status: Optional[List[str]] = Field(None, description="Expense statuses to filter by")

class StatementReportFilters(BaseReportFilters):
    account_ids: Optional[List[int]] = Field(None, description="Bank account IDs to filter by")
    transaction_types: Optional[List[str]] = Field(None, description="Transaction types to filter by")
    include_reconciliation: Optional[bool] = Field(False, description="Include reconciliation status")
    amount_min: Optional[float] = Field(None, description="Minimum transaction amount")
    amount_max: Optional[float] = Field(None, description="Maximum transaction amount")

# Union type for all filter types
ReportFilters = Union[
    ClientReportFilters,
    InvoiceReportFilters,
    PaymentReportFilters,
    ExpenseReportFilters,
    StatementReportFilters
]

# Report generation request models
class ReportGenerateRequest(BaseModel):
    report_type: ReportType = Field(..., description="Type of report to generate")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Report filters")
    columns: Optional[List[str]] = Field(None, description="Columns to include in the report")
    export_format: ExportFormat = Field(ExportFormat.JSON, description="Export format")
    template_id: Optional[int] = Field(None, description="Template ID to use for generation")

class ReportPreviewRequest(BaseModel):
    report_type: ReportType = Field(..., description="Type of report to preview")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Report filters")
    limit: Optional[int] = Field(10, description="Number of records to preview")

# Report template models
class ReportTemplateBase(BaseModel):
    name: str = Field(..., description="Template name")
    report_type: ReportType = Field(..., description="Type of report")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Default filters")
    columns: Optional[List[str]] = Field(None, description="Default columns")
    formatting: Optional[Dict[str, Any]] = Field(None, description="Formatting preferences")
    is_shared: Optional[bool] = Field(False, description="Whether template is shared with other users")

class ReportTemplateCreate(ReportTemplateBase):
    pass

class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Template name")
    filters: Optional[Dict[str, Any]] = Field(None, description="Default filters")
    columns: Optional[List[str]] = Field(None, description="Default columns")
    formatting: Optional[Dict[str, Any]] = Field(None, description="Formatting preferences")
    is_shared: Optional[bool] = Field(None, description="Whether template is shared with other users")

class ReportTemplate(ReportTemplateBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Scheduled report models
class ScheduleConfig(BaseModel):
    schedule_type: ScheduleType = Field(..., description="Type of schedule")
    cron_expression: Optional[str] = Field(None, description="Cron expression for custom schedules")
    time_of_day: Optional[str] = Field(None, description="Time of day for daily/weekly/monthly schedules (HH:MM)")
    day_of_week: Optional[int] = Field(None, description="Day of week for weekly schedules (0=Monday)")
    day_of_month: Optional[int] = Field(None, description="Day of month for monthly schedules")
    timezone: Optional[str] = Field("UTC", description="Timezone for schedule execution")

class ScheduledReportBase(BaseModel):
    template_id: int = Field(..., description="Template ID to use for scheduled reports")
    schedule_config: ScheduleConfig = Field(..., description="Schedule configuration")
    recipients: List[str] = Field(..., description="Email addresses to send reports to")
    export_format: ExportFormat = Field(ExportFormat.PDF, description="Export format for scheduled reports")
    is_active: Optional[bool] = Field(True, description="Whether the schedule is active")

class ScheduledReportCreate(ScheduledReportBase):
    pass

class ScheduledReportUpdate(BaseModel):
    schedule_config: Optional[ScheduleConfig] = Field(None, description="Schedule configuration")
    recipients: Optional[List[str]] = Field(None, description="Email addresses to send reports to")
    export_format: Optional[ExportFormat] = Field(None, description="Export format for scheduled reports")
    is_active: Optional[bool] = Field(None, description="Whether the schedule is active")

class ScheduledReport(ScheduledReportBase):
    id: int
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Report history models
class ReportHistoryBase(BaseModel):
    report_type: ReportType = Field(..., description="Type of report")
    parameters: Dict[str, Any] = Field(..., description="Report generation parameters")
    status: ReportStatus = Field(ReportStatus.PENDING, description="Report generation status")
    error_message: Optional[str] = Field(None, description="Error message if generation failed")

class ReportHistoryCreate(ReportHistoryBase):
    template_id: Optional[int] = Field(None, description="Template ID used for generation")
    generated_by: int = Field(..., description="User ID who generated the report")
    file_path: Optional[str] = Field(None, description="Path to generated report file")
    expires_at: Optional[datetime] = Field(None, description="When the report file expires")

class ReportHistory(ReportHistoryBase):
    id: int
    template_id: Optional[int]
    generated_by: int
    file_path: Optional[str]
    generated_at: datetime
    expires_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

# Report data models
class ReportSummary(BaseModel):
    total_records: int = Field(..., description="Total number of records in the report")
    total_amount: Optional[float] = Field(None, description="Total amount (if applicable)")
    currency: Optional[str] = Field(None, description="Currency for amounts")
    date_range: Optional[Dict[str, datetime]] = Field(None, description="Date range of the report")
    key_metrics: Dict[str, Any] = Field(default_factory=dict, description="Key metrics for the report")

class ReportMetadata(BaseModel):
    generated_at: datetime = Field(..., description="When the report was generated")
    generated_by: int = Field(..., description="User ID who generated the report")
    export_format: ExportFormat = Field(..., description="Export format used")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    generation_time: Optional[float] = Field(None, description="Time taken to generate report in seconds")

class ReportData(BaseModel):
    report_type: ReportType = Field(..., description="Type of report")
    summary: ReportSummary = Field(..., description="Report summary")
    data: List[Dict[str, Any]] = Field(..., description="Report data rows")
    metadata: ReportMetadata = Field(..., description="Report metadata")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filters applied to the report")

class ReportResult(BaseModel):
    success: bool = Field(..., description="Whether report generation was successful")
    report_id: Optional[int] = Field(None, description="Report history ID")
    data: Optional[ReportData] = Field(None, description="Report data (for immediate results)")
    file_path: Optional[str] = Field(None, description="Path to generated file")
    download_url: Optional[str] = Field(None, description="URL to download the report")
    
    # Enhanced error handling fields
    error_message: Optional[str] = Field(None, description="Human-readable error message")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    suggestions: Optional[List[str]] = Field(None, description="Suggestions for resolving the error")
    retryable: Optional[bool] = Field(None, description="Whether the operation can be retried")
    
    # Retry and performance information
    retry_attempts: Optional[int] = Field(None, description="Number of retry attempts made")
    generation_time: Optional[float] = Field(None, description="Time taken to generate the report in seconds")
    circuit_breaker_triggered: Optional[bool] = Field(None, description="Whether circuit breaker was triggered")

# Response models
class ReportTypesResponse(BaseModel):
    report_types: List[Dict[str, Any]] = Field(..., description="Available report types with their configurations")

class ReportTemplateListResponse(BaseModel):
    templates: List[ReportTemplate] = Field(..., description="List of report templates")
    total: int = Field(..., description="Total number of templates")

class ScheduledReportListResponse(BaseModel):
    scheduled_reports: List[ScheduledReport] = Field(..., description="List of scheduled reports")
    total: int = Field(..., description="Total number of scheduled reports")

class ReportHistoryListResponse(BaseModel):
    reports: List[ReportHistory] = Field(..., description="List of report history entries")
    total: int = Field(..., description="Total number of reports")