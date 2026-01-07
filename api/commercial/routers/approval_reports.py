"""
Approval Reports Router

FastAPI router for approval analytics and reporting endpoints.
Provides comprehensive reporting capabilities for the expense approval workflow.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from core.models.database import get_db
from commercial.workflows.approvals.services.approval_analytics_service import ApprovalAnalyticsService
from core.schemas.approval_reports import (
    ApprovalReportRequest,
    ApprovalReportResponse,
    ApprovalReportType,
    ApprovalMetricsReport,
    ApprovalPatternAnalysisReport,
    ApprovalComplianceReport,
    ApprovalAnalyticsDashboard,
    ApprovalAnalyticsFilters,
    ApprovalDashboardSummary,
)
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.utils.rbac import require_permission
from core.utils.feature_gate import check_feature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approval-reports", tags=["approval-reports"])


@router.get("/dashboard", response_model=ApprovalAnalyticsDashboard)
async def get_approval_analytics_dashboard(
    filters: ApprovalAnalyticsFilters = Depends(),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive approval analytics dashboard data.

    Requires: approval_view permission
    """
    # Check permissions
    require_permission(current_user, "approval_view")

    # Check feature license
    check_feature("approval_analytics", db)

    try:
        analytics_service = ApprovalAnalyticsService(db)

        # Determine date range
        date_from, date_to = _parse_date_range(filters)

        # Get dashboard summary
        summary_data = await _get_dashboard_summary(
            analytics_service, date_from, date_to, filters
        )

        # Get trend data
        trends = await _get_trend_data(
            analytics_service, date_from, date_to, filters
        )
        
        # Get category performance
        metrics = analytics_service.calculate_approval_metrics(
            date_from=date_from,
            date_to=date_to,
            approver_ids=[filters.approver_id] if filters.approver_id else None,
            categories=[filters.category] if filters.category else None
        )

        # Get recent activity
        recent_activity = await _get_recent_activity(db, current_user)

        # Get pattern analysis for recommendations
        pattern_analysis = analytics_service.analyze_approval_patterns(
            date_from=date_from,
            date_to=date_to
        )

        dashboard = ApprovalAnalyticsDashboard(
            summary=summary_data,
            trends=trends,
            category_performance=metrics.category_breakdown,
            approver_workload=metrics.approver_performance,
            recent_activity=recent_activity,
            recommendations=pattern_analysis.recommendations
        )

        return dashboard

    except Exception as e:
        logger.error(f"Error generating approval analytics dashboard: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate approval analytics dashboard"
        )


@router.get("/summary", response_model=ApprovalDashboardSummary)
async def get_approval_dashboard_summary(
    date_from: Optional[datetime] = Query(None, description="Start date for analysis"),
    date_to: Optional[datetime] = Query(None, description="End date for analysis"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get approval dashboard summary data.

    Requires: approval_view permission
    """
    # Check permissions
    require_permission(current_user, "approval_view")

    # Check feature license
    check_feature("approval_analytics", db)

    try:
        analytics_service = ApprovalAnalyticsService(db)

        # Default to last 30 days if no dates provided
        if not date_from:
            date_from = datetime.now() - timedelta(days=30)
        if not date_to:
            date_to = datetime.now()

        # Calculate metrics
        metrics = analytics_service.calculate_approval_metrics(
            date_from=date_from,
            date_to=date_to
        )

        # Count overdue approvals (pending for more than 3 days)
        overdue_threshold = datetime.now() - timedelta(days=3)
        overdue_count = len(
            [
                issue
                for issue in metrics.compliance_issues
                if issue.get("type") == "delayed_approval"
            ]
        )

        summary = ApprovalDashboardSummary(
            pending_approvals_count=metrics.pending_approvals,
            overdue_approvals_count=overdue_count,
            avg_approval_time_hours=metrics.average_approval_time,
            approval_rate_last_30_days=metrics.approval_rate,
            top_bottlenecks=metrics.bottlenecks[:3],  # Top 3 bottlenecks
            recent_compliance_issues=metrics.compliance_issues[:5],  # Recent 5 issues
            quick_stats={
                "total_approvals": metrics.total_approvals,
                "approved_count": metrics.approved_count,
                "rejected_count": metrics.rejected_count,
                "median_approval_time": metrics.median_approval_time
            }
        )

        return summary

    except Exception as e:
        logger.error(f"Error generating approval dashboard summary: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate approval dashboard summary"
        )


@router.post("/generate", response_model=ApprovalReportResponse)
async def generate_approval_report(
    request: ApprovalReportRequest,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive approval reports.

    Requires: approval_view permission for basic reports, approval_admin for compliance reports
    """
    # Check permissions
    if request.report_type == ApprovalReportType.COMPLIANCE:
        require_permission(current_user, "approval_admin")
    else:
        require_permission(current_user, "approval_view")

    # Check feature license
    check_feature("approval_analytics", db)

    try:
        analytics_service = ApprovalAnalyticsService(db)

        # Generate report based on type
        if request.report_type == ApprovalReportType.METRICS:
            report_data = analytics_service.calculate_approval_metrics(
                date_from=request.filters.date_from,
                date_to=request.filters.date_to,
                approver_ids=request.filters.approver_ids,
                categories=request.filters.categories
            )

        elif request.report_type == ApprovalReportType.PATTERNS:
            report_data = analytics_service.analyze_approval_patterns(
                date_from=request.filters.date_from,
                date_to=request.filters.date_to
            )

        elif request.report_type == ApprovalReportType.COMPLIANCE:
            report_data = analytics_service.generate_compliance_report(
                date_from=request.filters.date_from,
                date_to=request.filters.date_to
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported report type: {request.report_type}"
            )

        # Convert to dictionary for response
        report_dict = _convert_report_to_dict(report_data)

        response = ApprovalReportResponse(
            success=True,
            report_type=request.report_type,
            generated_at=datetime.now(),
            filters_applied=request.filters,
            data=report_dict
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating approval report: {e}")
        return ApprovalReportResponse(
            success=False,
            report_type=request.report_type,
            generated_at=datetime.now(),
            filters_applied=request.filters,
            error_message=str(e)
        )


@router.get("/metrics", response_model=ApprovalMetricsReport)
async def get_approval_metrics(
    date_from: Optional[datetime] = Query(None, description="Start date for analysis"),
    date_to: Optional[datetime] = Query(None, description="End date for analysis"),
    approver_ids: Optional[List[int]] = Query(None, description="List of approver IDs"),
    categories: Optional[List[str]] = Query(None, description="List of expense categories"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed approval metrics.

    Requires: approval_view permission
    """
    # Check permissions
    require_permission(current_user, "approval_view")

    # Check feature license
    check_feature("approval_analytics", db)

    try:
        analytics_service = ApprovalAnalyticsService(db)

        metrics = analytics_service.calculate_approval_metrics(
            date_from=date_from,
            date_to=date_to,
            approver_ids=approver_ids,
            categories=categories
        )

        # Convert to Pydantic model
        return _convert_metrics_to_response(metrics)

    except Exception as e:
        logger.error(f"Error calculating approval metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to calculate approval metrics"
        )


@router.get("/patterns", response_model=ApprovalPatternAnalysisReport)
async def get_approval_patterns(
    date_from: Optional[datetime] = Query(None, description="Start date for analysis"),
    date_to: Optional[datetime] = Query(None, description="End date for analysis"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get approval pattern analysis.

    Requires: approval_view permission
    """
    # Check permissions
    require_permission(current_user, "approval_view")

    # Check feature license
    check_feature("approval_analytics", db)

    try:
        analytics_service = ApprovalAnalyticsService(db)

        patterns = analytics_service.analyze_approval_patterns(
            date_from=date_from,
            date_to=date_to
        )

        # Convert to Pydantic model
        return _convert_patterns_to_response(patterns)

    except Exception as e:
        logger.error(f"Error analyzing approval patterns: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to analyze approval patterns"
        )


@router.get("/compliance", response_model=ApprovalComplianceReport)
async def get_approval_compliance(
    date_from: Optional[datetime] = Query(None, description="Start date for analysis"),
    date_to: Optional[datetime] = Query(None, description="End date for analysis"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get approval compliance report.

    Requires: approval_admin permission
    """
    # Check permissions
    require_permission(current_user, "approval_admin")

    # Check feature license
    check_feature("approval_analytics", db)

    try:
        analytics_service = ApprovalAnalyticsService(db)

        compliance = analytics_service.generate_compliance_report(
            date_from=date_from,
            date_to=date_to
        )

        # Convert to Pydantic model
        return _convert_compliance_to_response(compliance)

    except Exception as e:
        logger.error(f"Error generating compliance report: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate compliance report"
        )


# Helper functions


def _parse_date_range(filters: ApprovalAnalyticsFilters) -> tuple[datetime, datetime]:
    """Parse date range from filters"""
    if filters.date_range == "custom":
        if not filters.custom_date_from or not filters.custom_date_to:
            raise HTTPException(
                status_code=400,
                detail="Custom date range requires both custom_date_from and custom_date_to"
            )
        return filters.custom_date_from, filters.custom_date_to

    now = datetime.now()
    if filters.date_range == "last_7_days":
        return now - timedelta(days=7), now
    elif filters.date_range == "last_30_days":
        return now - timedelta(days=30), now
    elif filters.date_range == "last_90_days":
        return now - timedelta(days=90), now
    else:
        # Default to last 30 days
        return now - timedelta(days=30), now


async def _get_dashboard_summary(
    analytics_service: ApprovalAnalyticsService,
    date_from: datetime,
    date_to: datetime,
    filters: ApprovalAnalyticsFilters
) -> ApprovalDashboardSummary:
    """Get dashboard summary data"""
    metrics = analytics_service.calculate_approval_metrics(
        date_from=date_from,
        date_to=date_to,
        approver_ids=[filters.approver_id] if filters.approver_id else None,
        categories=[filters.category] if filters.category else None
    )

    # Count overdue approvals
    overdue_count = len(
        [
            issue
            for issue in metrics.compliance_issues
            if issue.get("type") == "delayed_approval"
        ]
    )

    return ApprovalDashboardSummary(
        pending_approvals_count=metrics.pending_approvals,
        overdue_approvals_count=overdue_count,
        avg_approval_time_hours=metrics.average_approval_time,
        approval_rate_last_30_days=metrics.approval_rate,
        top_bottlenecks=metrics.bottlenecks[:3],
        recent_compliance_issues=metrics.compliance_issues[:5],
        quick_stats={
            "total_approvals": metrics.total_approvals,
            "approved_count": metrics.approved_count,
            "rejected_count": metrics.rejected_count,
            "median_approval_time": metrics.median_approval_time
        }
    )


async def _get_trend_data(
    analytics_service: ApprovalAnalyticsService,
    date_from: datetime,
    date_to: datetime,
    filters: ApprovalAnalyticsFilters
) -> List[dict]:
    """Get trend data for the dashboard"""
    # For now, return monthly trends from the metrics
    metrics = analytics_service.calculate_approval_metrics(
        date_from=date_from,
        date_to=date_to,
        approver_ids=[filters.approver_id] if filters.approver_id else None,
        categories=[filters.category] if filters.category else None
    )

    trends = []
    for period, data in metrics.monthly_trends.items():
        trends.append({
            "period": period,
            "submitted_count": data.get('total_submitted', 0),
            "approved_count": data.get('approved', 0),
            "rejected_count": data.get('rejected', 0),
            "avg_approval_time": data.get('average_time_hours', 0),
            "approval_rate": data.get('approval_rate', 0)
        })
    
    return sorted(trends, key=lambda x: x['period'])


async def _get_recent_activity(db: Session, current_user: MasterUser) -> List[dict]:
    """Get recent approval activity"""
    from core.models.models_per_tenant import ExpenseApproval

    # Get recent approvals (last 10)
    recent_approvals = (
        db.query(ExpenseApproval)
        .options(
            joinedload(ExpenseApproval.expense), joinedload(ExpenseApproval.approver)
        )
        .order_by(ExpenseApproval.submitted_at.desc())
        .limit(10)
        .all()
    )

    activity = []
    for approval in recent_approvals:
        activity.append(
            {
                "id": approval.id,
                "expense_id": approval.expense_id,
                "expense_amount": approval.expense.amount if approval.expense else 0,
                "status": approval.status,
                "approver_name": (
                    approval.approver.first_name + " " + approval.approver.last_name
                    if approval.approver.first_name
                    else approval.approver.email
                ),
                "submitted_at": approval.submitted_at,
                "decided_at": approval.decided_at,
            }
        )

    return activity


def _convert_report_to_dict(report_data) -> dict:
    """Convert report data object to dictionary"""
    if hasattr(report_data, "__dict__"):
        return {k: v for k, v in report_data.__dict__.items() if not k.startswith("_")}
    return {}


def _convert_metrics_to_response(metrics) -> ApprovalMetricsReport:
    """Convert metrics object to Pydantic response model"""
    from core.schemas.approval_reports import (
        BottleneckInfo, ApproverPerformance, CategoryBreakdown,
        MonthlyTrend, ComplianceIssue
    )

    return ApprovalMetricsReport(
        total_approvals=metrics.total_approvals,
        pending_approvals=metrics.pending_approvals,
        approved_count=metrics.approved_count,
        rejected_count=metrics.rejected_count,
        average_approval_time=metrics.average_approval_time,
        median_approval_time=metrics.median_approval_time,
        approval_rate=metrics.approval_rate,
        rejection_rate=metrics.rejection_rate,
        bottlenecks=[BottleneckInfo(**b) for b in metrics.bottlenecks],
        approver_performance=[ApproverPerformance(**p) for p in metrics.approver_performance],
        category_breakdown={k: CategoryBreakdown(**v) for k, v in metrics.category_breakdown.items()},
        monthly_trends={k: MonthlyTrend(**v) for k, v in metrics.monthly_trends.items()},
        compliance_issues=[ComplianceIssue(**i) for i in metrics.compliance_issues]
    )


def _convert_patterns_to_response(patterns) -> ApprovalPatternAnalysisReport:
    """Convert patterns object to Pydantic response model"""
    from core.schemas.approval_reports import (
        RejectionReason, PeakSubmissionTimes, EscalationPattern, ProcessRecommendation
    )

    return ApprovalPatternAnalysisReport(
        common_rejection_reasons=[RejectionReason(**r) for r in patterns.common_rejection_reasons],
        approval_time_by_amount=patterns.approval_time_by_amount,
        approval_time_by_category=patterns.approval_time_by_category,
        peak_submission_times=PeakSubmissionTimes(**patterns.peak_submission_times),
        escalation_patterns=[EscalationPattern(**e) for e in patterns.escalation_patterns],
        recommendations=[ProcessRecommendation(**r) for r in patterns.recommendations]
    )


def _convert_compliance_to_response(compliance) -> ApprovalComplianceReport:
    """Convert compliance object to Pydantic response model"""
    from core.schemas.approval_reports import (
        PolicyViolation, RuleEffectiveness, DelegationUsage
    )

    return ApprovalComplianceReport(
        total_expenses=compliance.total_expenses,
        expenses_requiring_approval=compliance.expenses_requiring_approval,
        expenses_bypassed_approval=compliance.expenses_bypassed_approval,
        compliance_rate=compliance.compliance_rate,
        policy_violations=[PolicyViolation(**v) for v in compliance.policy_violations],
        rule_effectiveness=[RuleEffectiveness(**r) for r in compliance.rule_effectiveness],
        delegation_usage=DelegationUsage(**compliance.delegation_usage)
    )
