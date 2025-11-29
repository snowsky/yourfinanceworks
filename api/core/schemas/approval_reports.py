"""
Approval Reporting Schemas

Pydantic schemas for approval analytics and reporting functionality.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ApprovalReportType(str, Enum):
    """Types of approval reports"""
    METRICS = "metrics"
    PATTERNS = "patterns"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"


class ApprovalReportFilters(BaseModel):
    """Filters for approval reports"""
    date_from: Optional[datetime] = Field(None, description="Start date for the report")
    date_to: Optional[datetime] = Field(None, description="End date for the report")
    approver_ids: Optional[List[int]] = Field(None, description="List of approver IDs to filter by")
    categories: Optional[List[str]] = Field(None, description="List of expense categories to filter by")
    status: Optional[List[str]] = Field(None, description="List of approval statuses to filter by")
    amount_min: Optional[float] = Field(None, description="Minimum expense amount")
    amount_max: Optional[float] = Field(None, description="Maximum expense amount")


class BottleneckInfo(BaseModel):
    """Information about approval bottlenecks"""
    approver_id: int
    approver_name: str
    average_time_hours: float
    approval_count: int
    is_bottleneck: bool


class ApproverPerformance(BaseModel):
    """Approver performance metrics"""
    approver_id: int
    approver_name: str
    total_assigned: int
    approved: int
    rejected: int
    pending: int
    approval_rate: float
    average_time_hours: float
    efficiency_score: float


class CategoryBreakdown(BaseModel):
    """Approval metrics by category"""
    total: int
    approved: int
    rejected: int
    pending: int
    approval_rate: float
    average_time_hours: float
    total_amount: float
    average_amount: float


class MonthlyTrend(BaseModel):
    """Monthly trend data"""
    total_submitted: int
    approved: int
    rejected: int
    pending: int
    approval_rate: float
    average_time_hours: float
    total_amount: float


class ComplianceIssue(BaseModel):
    """Compliance issue information"""
    type: str
    approval_id: Optional[int] = None
    expense_id: Optional[int] = None
    approver_id: Optional[int] = None
    delay_hours: Optional[float] = None
    description: str


class ApprovalMetricsReport(BaseModel):
    """Comprehensive approval metrics report"""
    total_approvals: int
    pending_approvals: int
    approved_count: int
    rejected_count: int
    average_approval_time: float
    median_approval_time: float
    approval_rate: float
    rejection_rate: float
    bottlenecks: List[BottleneckInfo]
    approver_performance: List[ApproverPerformance]
    category_breakdown: Dict[str, CategoryBreakdown]
    monthly_trends: Dict[str, MonthlyTrend]
    compliance_issues: List[ComplianceIssue]


class RejectionReason(BaseModel):
    """Common rejection reason analysis"""
    reason: str
    count: int
    total_amount: float


class ApprovalTimeByAmount(BaseModel):
    """Approval time analysis by amount ranges"""
    range_0_100: float = Field(alias="0-100")
    range_100_500: float = Field(alias="100-500")
    range_500_1000: float = Field(alias="500-1000")
    range_1000_5000: float = Field(alias="1000-5000")
    range_5000_plus: float = Field(alias="5000+")

    model_config = ConfigDict(populate_by_name=True)


class PeakSubmissionTimes(BaseModel):
    """Peak submission time analysis"""
    by_hour: Dict[str, int]
    by_day: Dict[str, int]


class EscalationPattern(BaseModel):
    """Escalation pattern information"""
    expense_id: int
    levels: int
    total_time_hours: float
    level_times: List[Dict[str, Any]]


class ProcessRecommendation(BaseModel):
    """Process improvement recommendation"""
    type: str
    priority: str
    title: str
    description: str
    impact: str


class ApprovalPatternAnalysisReport(BaseModel):
    """Approval pattern analysis report"""
    common_rejection_reasons: List[RejectionReason]
    approval_time_by_amount: Dict[str, float]
    approval_time_by_category: Dict[str, float]
    peak_submission_times: PeakSubmissionTimes
    escalation_patterns: List[EscalationPattern]
    recommendations: List[ProcessRecommendation]


class PolicyViolation(BaseModel):
    """Policy violation information"""
    expense_id: int
    amount: float
    category: Optional[str]
    expense_date: datetime
    violation_type: str
    description: str


class RuleEffectiveness(BaseModel):
    """Approval rule effectiveness metrics"""
    rule_id: int
    rule_name: str
    approval_count: int
    is_active: bool
    effectiveness_score: float


class DelegationUsage(BaseModel):
    """Delegation usage analysis"""
    total_delegations: int
    active_delegations: int
    average_duration_days: float
    most_delegating_approvers: List[Dict[str, Any]]


class ApprovalComplianceReport(BaseModel):
    """Approval compliance report"""
    total_expenses: int
    expenses_requiring_approval: int
    expenses_bypassed_approval: int
    compliance_rate: float
    policy_violations: List[PolicyViolation]
    rule_effectiveness: List[RuleEffectiveness]
    delegation_usage: DelegationUsage


class ApprovalReportRequest(BaseModel):
    """Request for generating approval reports"""
    report_type: ApprovalReportType
    filters: ApprovalReportFilters = Field(default_factory=ApprovalReportFilters)
    export_format: Optional[str] = Field("json", description="Export format (json, pdf, csv, excel)")


class ApprovalReportResponse(BaseModel):
    """Response for approval report generation"""
    success: bool
    report_type: ApprovalReportType
    generated_at: datetime
    filters_applied: ApprovalReportFilters
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    export_url: Optional[str] = None


class ApprovalDashboardSummary(BaseModel):
    """Summary data for approval dashboard"""
    pending_approvals_count: int
    overdue_approvals_count: int
    avg_approval_time_hours: float
    approval_rate_last_30_days: float
    top_bottlenecks: List[BottleneckInfo]
    recent_compliance_issues: List[ComplianceIssue]
    quick_stats: Dict[str, Any]


class ApprovalAnalyticsFilters(BaseModel):
    """Filters for approval analytics dashboard"""
    date_range: str = Field("last_30_days", description="Date range preset (last_7_days, last_30_days, last_90_days, custom)")
    custom_date_from: Optional[datetime] = None
    custom_date_to: Optional[datetime] = None
    approver_id: Optional[int] = None
    category: Optional[str] = None
    include_auto_approved: bool = Field(True, description="Include auto-approved expenses in analysis")


class ApprovalTrendData(BaseModel):
    """Trend data for approval analytics"""
    period: str
    submitted_count: int
    approved_count: int
    rejected_count: int
    avg_approval_time: float
    approval_rate: float


class ApprovalAnalyticsDashboard(BaseModel):
    """Complete approval analytics dashboard data"""
    summary: ApprovalDashboardSummary
    trends: List[ApprovalTrendData]
    category_performance: Dict[str, CategoryBreakdown]
    approver_workload: List[ApproverPerformance]
    recent_activity: List[Dict[str, Any]]
    recommendations: List[ProcessRecommendation]