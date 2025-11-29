"""
Approval Analytics Service

This service provides comprehensive analytics and reporting capabilities for the expense
approval workflow. It calculates metrics like approval times, bottlenecks, compliance
reporting, and pattern analysis.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, case, extract
import logging
from statistics import mean, median

logger = logging.getLogger(__name__)

from core.models.models_per_tenant import (
    ExpenseApproval, ApprovalRule, ApprovalDelegate, Expense, User
)
from core.schemas.approval import ApprovalStatus


class ApprovalMetrics:
    """Data structure for approval metrics results"""
    
    def __init__(self):
        self.total_approvals: int = 0
        self.pending_approvals: int = 0
        self.approved_count: int = 0
        self.rejected_count: int = 0
        self.average_approval_time: float = 0.0
        self.median_approval_time: float = 0.0
        self.approval_rate: float = 0.0
        self.rejection_rate: float = 0.0
        self.bottlenecks: List[Dict[str, Any]] = []
        self.approver_performance: List[Dict[str, Any]] = []
        self.category_breakdown: Dict[str, Dict[str, Any]] = {}
        self.monthly_trends: Dict[str, Dict[str, Any]] = {}
        self.compliance_issues: List[Dict[str, Any]] = []


class ApprovalPatternAnalysis:
    """Data structure for approval pattern analysis results"""
    
    def __init__(self):
        self.common_rejection_reasons: List[Dict[str, Any]] = []
        self.approval_time_by_amount: Dict[str, float] = {}
        self.approval_time_by_category: Dict[str, float] = {}
        self.peak_submission_times: Dict[str, int] = {}
        self.escalation_patterns: List[Dict[str, Any]] = []
        self.recommendations: List[Dict[str, Any]] = []


class ApprovalComplianceReport:
    """Data structure for approval compliance reporting"""
    
    def __init__(self):
        self.total_expenses: int = 0
        self.expenses_requiring_approval: int = 0
        self.expenses_bypassed_approval: int = 0
        self.compliance_rate: float = 0.0
        self.policy_violations: List[Dict[str, Any]] = []
        self.rule_effectiveness: List[Dict[str, Any]] = []
        self.delegation_usage: Dict[str, Any] = {}


class ApprovalAnalyticsService:
    """
    Core service for approval workflow analytics and reporting.
    Provides comprehensive metrics, pattern analysis, and compliance reporting.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    def calculate_approval_metrics(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        approver_ids: Optional[List[int]] = None,
        categories: Optional[List[str]] = None
    ) -> ApprovalMetrics:
        """
        Calculate comprehensive approval metrics for the specified period and filters.
        
        Args:
            date_from: Start date for analysis
            date_to: End date for analysis
            approver_ids: Optional list of approver IDs to filter by
            categories: Optional list of expense categories to filter by
            
        Returns:
            ApprovalMetrics object with calculated metrics
        """
        metrics = ApprovalMetrics()
        
        # Build base query with joins
        query = self.db.query(ExpenseApproval).options(
            joinedload(ExpenseApproval.expense),
            joinedload(ExpenseApproval.approver),
            joinedload(ExpenseApproval.approval_rule)
        )
        
        # Apply date filtering
        if date_from:
            query = query.filter(ExpenseApproval.submitted_at >= date_from)
        if date_to:
            query = query.filter(ExpenseApproval.submitted_at <= date_to)
        
        # Apply approver filtering
        if approver_ids:
            query = query.filter(ExpenseApproval.approver_id.in_(approver_ids))
        
        # Apply category filtering
        if categories:
            query = query.join(Expense).filter(Expense.category.in_(categories))
        
        approvals = query.all()
        metrics.total_approvals = len(approvals)
        
        if metrics.total_approvals == 0:
            return metrics
        
        # Calculate basic counts
        approved_approvals = [a for a in approvals if a.status == ApprovalStatus.APPROVED]
        rejected_approvals = [a for a in approvals if a.status == ApprovalStatus.REJECTED]
        pending_approvals = [a for a in approvals if a.status == ApprovalStatus.PENDING]
        
        metrics.approved_count = len(approved_approvals)
        metrics.rejected_count = len(rejected_approvals)
        metrics.pending_approvals = len(pending_approvals)
        
        # Calculate rates
        decided_count = metrics.approved_count + metrics.rejected_count
        if decided_count > 0:
            metrics.approval_rate = (metrics.approved_count / decided_count) * 100
            metrics.rejection_rate = (metrics.rejected_count / decided_count) * 100
        
        # Calculate approval times for decided approvals
        decided_approvals = approved_approvals + rejected_approvals
        approval_times = []
        
        for approval in decided_approvals:
            if approval.decided_at and approval.submitted_at:
                time_diff = approval.decided_at - approval.submitted_at
                approval_times.append(time_diff.total_seconds() / 3600)  # Convert to hours
        
        if approval_times:
            metrics.average_approval_time = mean(approval_times)
            metrics.median_approval_time = median(approval_times)
        
        # Calculate bottlenecks (approvers with longest average times)
        metrics.bottlenecks = self._calculate_bottlenecks(decided_approvals)
        
        # Calculate approver performance
        metrics.approver_performance = self._calculate_approver_performance(approvals)
        
        # Calculate category breakdown
        metrics.category_breakdown = self._calculate_category_breakdown(approvals)
        
        # Calculate monthly trends
        metrics.monthly_trends = self._calculate_monthly_trends(approvals)
        
        # Identify compliance issues
        metrics.compliance_issues = self._identify_compliance_issues(approvals)
        
        return metrics
    
    def analyze_approval_patterns(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> ApprovalPatternAnalysis:
        """
        Analyze approval patterns and provide recommendations for process improvement.
        
        Args:
            date_from: Start date for analysis
            date_to: End date for analysis
            
        Returns:
            ApprovalPatternAnalysis object with pattern insights
        """
        analysis = ApprovalPatternAnalysis()
        
        # Build base query
        query = self.db.query(ExpenseApproval).options(
            joinedload(ExpenseApproval.expense),
            joinedload(ExpenseApproval.approver)
        )
        
        # Apply date filtering
        if date_from:
            query = query.filter(ExpenseApproval.submitted_at >= date_from)
        if date_to:
            query = query.filter(ExpenseApproval.submitted_at <= date_to)
        
        approvals = query.all()
        
        if not approvals:
            return analysis
        
        # Analyze common rejection reasons
        analysis.common_rejection_reasons = self._analyze_rejection_reasons(approvals)
        
        # Analyze approval time by expense amount
        analysis.approval_time_by_amount = self._analyze_approval_time_by_amount(approvals)
        
        # Analyze approval time by category
        analysis.approval_time_by_category = self._analyze_approval_time_by_category(approvals)
        
        # Analyze peak submission times
        analysis.peak_submission_times = self._analyze_peak_submission_times(approvals)
        
        # Analyze escalation patterns
        analysis.escalation_patterns = self._analyze_escalation_patterns(approvals)
        
        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis, approvals)
        
        return analysis
    
    def generate_compliance_report(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> ApprovalComplianceReport:
        """
        Generate comprehensive compliance report for audit purposes.
        
        Args:
            date_from: Start date for report
            date_to: End date for report
            
        Returns:
            ApprovalComplianceReport object with compliance metrics
        """
        report = ApprovalComplianceReport()
        
        # Get all expenses in the date range
        expense_query = self.db.query(Expense)
        if date_from:
            expense_query = expense_query.filter(Expense.expense_date >= date_from)
        if date_to:
            expense_query = expense_query.filter(Expense.expense_date <= date_to)
        
        expenses = expense_query.all()
        report.total_expenses = len(expenses)
        
        if report.total_expenses == 0:
            return report
        
        # Identify expenses that should require approval
        approval_rules = self.db.query(ApprovalRule).filter(ApprovalRule.is_active == True).all()
        expenses_requiring_approval = []
        expenses_bypassed = []
        
        for expense in expenses:
            should_require_approval = self._should_expense_require_approval(expense, approval_rules)
            has_approval = self._expense_has_approval_record(expense.id)
            
            if should_require_approval:
                expenses_requiring_approval.append(expense)
                if not has_approval:
                    expenses_bypassed.append(expense)
        
        report.expenses_requiring_approval = len(expenses_requiring_approval)
        report.expenses_bypassed_approval = len(expenses_bypassed)
        
        # Calculate compliance rate
        if report.expenses_requiring_approval > 0:
            compliant_expenses = report.expenses_requiring_approval - report.expenses_bypassed_approval
            report.compliance_rate = (compliant_expenses / report.expenses_requiring_approval) * 100
        
        # Identify policy violations
        report.policy_violations = self._identify_policy_violations(expenses_bypassed)
        
        # Analyze rule effectiveness
        report.rule_effectiveness = self._analyze_rule_effectiveness(approval_rules)
        
        # Analyze delegation usage
        report.delegation_usage = self._analyze_delegation_usage(date_from, date_to)
        
        return report
    
    def _calculate_bottlenecks(self, decided_approvals: List[ExpenseApproval]) -> List[Dict[str, Any]]:
        """Calculate approval bottlenecks by approver"""
        approver_times = {}
        
        for approval in decided_approvals:
            if approval.decided_at and approval.submitted_at:
                approver_id = approval.approver_id
                time_diff = (approval.decided_at - approval.submitted_at).total_seconds() / 3600
                
                if approver_id not in approver_times:
                    approver_times[approver_id] = {
                        'times': [],
                        'approver_name': approval.approver.first_name + ' ' + approval.approver.last_name if approval.approver.first_name else approval.approver.email,
                        'count': 0
                    }
                
                approver_times[approver_id]['times'].append(time_diff)
                approver_times[approver_id]['count'] += 1
        
        # Calculate average times and identify bottlenecks
        bottlenecks = []
        for approver_id, data in approver_times.items():
            if data['times']:
                avg_time = mean(data['times'])
                bottlenecks.append({
                    'approver_id': approver_id,
                    'approver_name': data['approver_name'],
                    'average_time_hours': round(avg_time, 2),
                    'approval_count': data['count'],
                    'is_bottleneck': avg_time > 24  # Consider >24 hours as bottleneck
                })
        
        # Sort by average time descending
        bottlenecks.sort(key=lambda x: x['average_time_hours'], reverse=True)
        
        return bottlenecks[:10]  # Return top 10 bottlenecks
    
    def _calculate_approver_performance(self, approvals: List[ExpenseApproval]) -> List[Dict[str, Any]]:
        """Calculate performance metrics for each approver"""
        approver_stats = {}
        
        for approval in approvals:
            approver_id = approval.approver_id
            
            if approver_id not in approver_stats:
                approver_stats[approver_id] = {
                    'approver_name': approval.approver.first_name + ' ' + approval.approver.last_name if approval.approver.first_name else approval.approver.email,
                    'total_assigned': 0,
                    'approved': 0,
                    'rejected': 0,
                    'pending': 0,
                    'approval_times': []
                }
            
            stats = approver_stats[approver_id]
            stats['total_assigned'] += 1
            
            if approval.status == ApprovalStatus.APPROVED:
                stats['approved'] += 1
            elif approval.status == ApprovalStatus.REJECTED:
                stats['rejected'] += 1
            else:
                stats['pending'] += 1
            
            # Calculate approval time if decided
            if approval.decided_at and approval.submitted_at:
                time_diff = (approval.decided_at - approval.submitted_at).total_seconds() / 3600
                stats['approval_times'].append(time_diff)
        
        # Convert to list with calculated metrics
        performance = []
        for approver_id, stats in approver_stats.items():
            decided_count = stats['approved'] + stats['rejected']
            avg_time = mean(stats['approval_times']) if stats['approval_times'] else 0
            
            performance.append({
                'approver_id': approver_id,
                'approver_name': stats['approver_name'],
                'total_assigned': stats['total_assigned'],
                'approved': stats['approved'],
                'rejected': stats['rejected'],
                'pending': stats['pending'],
                'approval_rate': (stats['approved'] / decided_count * 100) if decided_count > 0 else 0,
                'average_time_hours': round(avg_time, 2),
                'efficiency_score': self._calculate_efficiency_score(stats, avg_time)
            })
        
        # Sort by efficiency score descending
        performance.sort(key=lambda x: x['efficiency_score'], reverse=True)
        
        return performance
    
    def _calculate_category_breakdown(self, approvals: List[ExpenseApproval]) -> Dict[str, Dict[str, Any]]:
        """Calculate approval metrics by expense category"""
        category_stats = {}
        
        for approval in approvals:
            if approval.expense and approval.expense.category:
                category = approval.expense.category
                
                if category not in category_stats:
                    category_stats[category] = {
                        'total': 0,
                        'approved': 0,
                        'rejected': 0,
                        'pending': 0,
                        'approval_times': [],
                        'total_amount': 0.0
                    }
                
                stats = category_stats[category]
                stats['total'] += 1
                stats['total_amount'] += approval.expense.amount or 0
                
                if approval.status == ApprovalStatus.APPROVED:
                    stats['approved'] += 1
                elif approval.status == ApprovalStatus.REJECTED:
                    stats['rejected'] += 1
                else:
                    stats['pending'] += 1
                
                # Calculate approval time if decided
                if approval.decided_at and approval.submitted_at:
                    time_diff = (approval.decided_at - approval.submitted_at).total_seconds() / 3600
                    stats['approval_times'].append(time_diff)
        
        # Calculate derived metrics
        for category, stats in category_stats.items():
            decided_count = stats['approved'] + stats['rejected']
            stats['approval_rate'] = (stats['approved'] / decided_count * 100) if decided_count > 0 else 0
            stats['average_time_hours'] = mean(stats['approval_times']) if stats['approval_times'] else 0
            stats['average_amount'] = stats['total_amount'] / stats['total'] if stats['total'] > 0 else 0
        
        return category_stats
    
    def _calculate_monthly_trends(self, approvals: List[ExpenseApproval]) -> Dict[str, Dict[str, Any]]:
        """Calculate monthly trends for approval metrics"""
        monthly_stats = {}
        
        for approval in approvals:
            month_key = approval.submitted_at.strftime('%Y-%m')
            
            if month_key not in monthly_stats:
                monthly_stats[month_key] = {
                    'total_submitted': 0,
                    'approved': 0,
                    'rejected': 0,
                    'pending': 0,
                    'approval_times': [],
                    'total_amount': 0.0
                }
            
            stats = monthly_stats[month_key]
            stats['total_submitted'] += 1
            
            if approval.expense:
                stats['total_amount'] += approval.expense.amount or 0
            
            if approval.status == ApprovalStatus.APPROVED:
                stats['approved'] += 1
            elif approval.status == ApprovalStatus.REJECTED:
                stats['rejected'] += 1
            else:
                stats['pending'] += 1
            
            # Calculate approval time if decided
            if approval.decided_at and approval.submitted_at:
                time_diff = (approval.decided_at - approval.submitted_at).total_seconds() / 3600
                stats['approval_times'].append(time_diff)
        
        # Calculate derived metrics
        for month, stats in monthly_stats.items():
            decided_count = stats['approved'] + stats['rejected']
            stats['approval_rate'] = (stats['approved'] / decided_count * 100) if decided_count > 0 else 0
            stats['average_time_hours'] = mean(stats['approval_times']) if stats['approval_times'] else 0
        
        return monthly_stats
    
    def _identify_compliance_issues(self, approvals: List[ExpenseApproval]) -> List[Dict[str, Any]]:
        """Identify potential compliance issues in approval workflow"""
        issues = []
        
        # Check for approvals that took too long
        for approval in approvals:
            if approval.decided_at and approval.submitted_at:
                time_diff = (approval.decided_at - approval.submitted_at).total_seconds() / 3600
                
                if time_diff > 168:  # More than 1 week
                    issues.append({
                        'type': 'delayed_approval',
                        'approval_id': approval.id,
                        'expense_id': approval.expense_id,
                        'approver_id': approval.approver_id,
                        'delay_hours': round(time_diff, 2),
                        'description': f'Approval took {round(time_diff/24, 1)} days to complete'
                    })
        
        # Check for approvals without proper documentation
        for approval in approvals:
            if approval.status == ApprovalStatus.REJECTED and not approval.rejection_reason:
                issues.append({
                    'type': 'missing_rejection_reason',
                    'approval_id': approval.id,
                    'expense_id': approval.expense_id,
                    'approver_id': approval.approver_id,
                    'description': 'Expense rejected without providing reason'
                })
        
        return issues
    
    def _analyze_rejection_reasons(self, approvals: List[ExpenseApproval]) -> List[Dict[str, Any]]:
        """Analyze common rejection reasons"""
        rejection_reasons = {}
        
        for approval in approvals:
            if approval.status == ApprovalStatus.REJECTED and approval.rejection_reason:
                reason = approval.rejection_reason.lower().strip()
                
                if reason not in rejection_reasons:
                    rejection_reasons[reason] = {
                        'reason': approval.rejection_reason,
                        'count': 0,
                        'total_amount': 0.0
                    }
                
                rejection_reasons[reason]['count'] += 1
                if approval.expense:
                    rejection_reasons[reason]['total_amount'] += approval.expense.amount or 0
        
        # Convert to sorted list
        reasons_list = list(rejection_reasons.values())
        reasons_list.sort(key=lambda x: x['count'], reverse=True)
        
        return reasons_list[:10]  # Return top 10 reasons
    
    def _analyze_approval_time_by_amount(self, approvals: List[ExpenseApproval]) -> Dict[str, float]:
        """Analyze approval time by expense amount ranges"""
        amount_ranges = {
            '0-100': [],
            '100-500': [],
            '500-1000': [],
            '1000-5000': [],
            '5000+': []
        }
        
        for approval in approvals:
            if approval.decided_at and approval.submitted_at and approval.expense:
                time_diff = (approval.decided_at - approval.submitted_at).total_seconds() / 3600
                amount = approval.expense.amount or 0
                
                if amount <= 100:
                    amount_ranges['0-100'].append(time_diff)
                elif amount <= 500:
                    amount_ranges['100-500'].append(time_diff)
                elif amount <= 1000:
                    amount_ranges['500-1000'].append(time_diff)
                elif amount <= 5000:
                    amount_ranges['1000-5000'].append(time_diff)
                else:
                    amount_ranges['5000+'].append(time_diff)
        
        # Calculate averages
        result = {}
        for range_key, times in amount_ranges.items():
            result[range_key] = mean(times) if times else 0
        
        return result
    
    def _analyze_approval_time_by_category(self, approvals: List[ExpenseApproval]) -> Dict[str, float]:
        """Analyze approval time by expense category"""
        category_times = {}
        
        for approval in approvals:
            if approval.decided_at and approval.submitted_at and approval.expense and approval.expense.category:
                time_diff = (approval.decided_at - approval.submitted_at).total_seconds() / 3600
                category = approval.expense.category
                
                if category not in category_times:
                    category_times[category] = []
                
                category_times[category].append(time_diff)
        
        # Calculate averages
        result = {}
        for category, times in category_times.items():
            result[category] = mean(times) if times else 0
        
        return result
    
    def _analyze_peak_submission_times(self, approvals: List[ExpenseApproval]) -> Dict[str, int]:
        """Analyze peak submission times by hour of day and day of week"""
        hour_counts = {}
        day_counts = {}
        
        for approval in approvals:
            # Hour of day (0-23)
            hour = approval.submitted_at.hour
            hour_counts[str(hour)] = hour_counts.get(str(hour), 0) + 1
            
            # Day of week (0=Monday, 6=Sunday)
            day = approval.submitted_at.weekday()
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_name = day_names[day]
            day_counts[day_name] = day_counts.get(day_name, 0) + 1
        
        return {
            'by_hour': hour_counts,
            'by_day': day_counts
        }
    
    def _analyze_escalation_patterns(self, approvals: List[ExpenseApproval]) -> List[Dict[str, Any]]:
        """Analyze escalation patterns in multi-level approvals"""
        escalations = []
        
        # Group approvals by expense_id to find multi-level approvals
        expense_approvals = {}
        for approval in approvals:
            expense_id = approval.expense_id
            if expense_id not in expense_approvals:
                expense_approvals[expense_id] = []
            expense_approvals[expense_id].append(approval)
        
        # Analyze multi-level approval patterns
        for expense_id, approval_list in expense_approvals.items():
            if len(approval_list) > 1:
                # Sort by approval level
                approval_list.sort(key=lambda x: x.approval_level)
                
                escalation = {
                    'expense_id': expense_id,
                    'levels': len(approval_list),
                    'total_time_hours': 0,
                    'level_times': []
                }
                
                for i, approval in enumerate(approval_list):
                    if approval.decided_at and approval.submitted_at:
                        time_diff = (approval.decided_at - approval.submitted_at).total_seconds() / 3600
                        escalation['level_times'].append({
                            'level': approval.approval_level,
                            'time_hours': round(time_diff, 2),
                            'approver_id': approval.approver_id
                        })
                        escalation['total_time_hours'] += time_diff
                
                if escalation['level_times']:
                    escalations.append(escalation)
        
        # Sort by total time descending
        escalations.sort(key=lambda x: x['total_time_hours'], reverse=True)
        
        return escalations[:20]  # Return top 20 escalations
    
    def _generate_recommendations(self, analysis: ApprovalPatternAnalysis, approvals: List[ExpenseApproval]) -> List[Dict[str, Any]]:
        """Generate recommendations based on pattern analysis"""
        recommendations = []
        
        # Recommendation based on approval times
        if analysis.approval_time_by_amount:
            high_amount_time = analysis.approval_time_by_amount.get('5000+', 0)
            low_amount_time = analysis.approval_time_by_amount.get('0-100', 0)
            
            if high_amount_time > low_amount_time * 3:
                recommendations.append({
                    'type': 'process_optimization',
                    'priority': 'high',
                    'title': 'Optimize High-Value Expense Approvals',
                    'description': 'High-value expenses take significantly longer to approve. Consider dedicated approval tracks for different amount ranges.',
                    'impact': 'Reduce approval time for high-value expenses by up to 50%'
                })
        
        # Recommendation based on rejection patterns
        if analysis.common_rejection_reasons:
            top_reason = analysis.common_rejection_reasons[0]
            if top_reason['count'] > len(approvals) * 0.1:  # More than 10% of approvals
                recommendations.append({
                    'type': 'policy_clarification',
                    'priority': 'medium',
                    'title': 'Address Common Rejection Reason',
                    'description': f'"{top_reason["reason"]}" is the most common rejection reason. Consider policy clarification or training.',
                    'impact': f'Could reduce rejections by up to {top_reason["count"]} cases'
                })
        
        # Recommendation based on peak times
        if analysis.peak_submission_times:
            peak_hour = max(analysis.peak_submission_times.get('by_hour', {}).items(), key=lambda x: x[1], default=(None, 0))
            if peak_hour[0] and peak_hour[1] > len(approvals) * 0.2:  # More than 20% in one hour
                recommendations.append({
                    'type': 'workload_distribution',
                    'priority': 'low',
                    'title': 'Distribute Approval Workload',
                    'description': f'Most approvals are submitted at {peak_hour[0]}:00. Consider encouraging submissions throughout the day.',
                    'impact': 'Improve approver response times and reduce bottlenecks'
                })
        
        return recommendations
    
    def _should_expense_require_approval(self, expense: Expense, approval_rules: List[ApprovalRule]) -> bool:
        """Check if an expense should require approval based on rules"""
        for rule in approval_rules:
            # Check amount thresholds
            if rule.min_amount is not None and expense.amount < rule.min_amount:
                continue
            if rule.max_amount is not None and expense.amount > rule.max_amount:
                continue
            
            # Check category filter
            if rule.category_filter and expense.category:
                import json
                try:
                    categories = json.loads(rule.category_filter)
                    if expense.category not in categories:
                        continue
                except:
                    continue
            
            # Check currency
            if rule.currency != expense.currency:
                continue
            
            # If we reach here, the rule applies
            return True
        
        return False
    
    def _expense_has_approval_record(self, expense_id: int) -> bool:
        """Check if an expense has any approval records"""
        approval = self.db.query(ExpenseApproval).filter(
            ExpenseApproval.expense_id == expense_id
        ).first()
        return approval is not None
    
    def _identify_policy_violations(self, bypassed_expenses: List[Expense]) -> List[Dict[str, Any]]:
        """Identify policy violations from bypassed expenses"""
        violations = []
        
        for expense in bypassed_expenses:
            violations.append({
                'expense_id': expense.id,
                'amount': expense.amount,
                'category': expense.category,
                'expense_date': expense.expense_date,
                'violation_type': 'bypassed_approval',
                'description': f'Expense of {expense.amount} {expense.currency} in {expense.category} category bypassed approval workflow'
            })
        
        return violations
    
    def _analyze_rule_effectiveness(self, approval_rules: List[ApprovalRule]) -> List[Dict[str, Any]]:
        """Analyze the effectiveness of approval rules"""
        rule_stats = []
        
        for rule in approval_rules:
            # Count approvals triggered by this rule
            approval_count = self.db.query(ExpenseApproval).filter(
                ExpenseApproval.approval_rule_id == rule.id
            ).count()
            
            rule_stats.append({
                'rule_id': rule.id,
                'rule_name': rule.name,
                'approval_count': approval_count,
                'is_active': rule.is_active,
                'effectiveness_score': self._calculate_rule_effectiveness_score(rule, approval_count)
            })
        
        # Sort by effectiveness score descending
        rule_stats.sort(key=lambda x: x['effectiveness_score'], reverse=True)
        
        return rule_stats
    
    def _analyze_delegation_usage(self, date_from: Optional[datetime], date_to: Optional[datetime]) -> Dict[str, Any]:
        """Analyze delegation usage patterns"""
        query = self.db.query(ApprovalDelegate)
        
        if date_from:
            query = query.filter(ApprovalDelegate.start_date >= date_from)
        if date_to:
            query = query.filter(ApprovalDelegate.end_date <= date_to)
        
        delegations = query.all()
        
        return {
            'total_delegations': len(delegations),
            'active_delegations': len([d for d in delegations if d.is_active]),
            'average_duration_days': mean([
                (d.end_date - d.start_date).days for d in delegations
            ]) if delegations else 0,
            'most_delegating_approvers': self._get_most_delegating_approvers(delegations)
        }
    
    def _calculate_efficiency_score(self, stats: Dict[str, Any], avg_time: float) -> float:
        """Calculate efficiency score for an approver"""
        decided_count = stats['approved'] + stats['rejected']
        if decided_count == 0:
            return 0
        
        # Base score from approval rate (0-50 points)
        approval_rate_score = (stats['approved'] / decided_count) * 50
        
        # Time efficiency score (0-50 points, inversely related to time)
        # Assume 24 hours is baseline, give full points for <= 8 hours
        time_score = max(0, 50 - (avg_time / 8) * 10)
        
        return min(100, approval_rate_score + time_score)
    
    def _calculate_rule_effectiveness_score(self, rule: ApprovalRule, approval_count: int) -> float:
        """Calculate effectiveness score for an approval rule"""
        # Base score from usage frequency
        usage_score = min(50, approval_count * 2)  # 2 points per approval, max 50
        
        # Configuration completeness score
        config_score = 0
        if rule.min_amount is not None:
            config_score += 10
        if rule.max_amount is not None:
            config_score += 10
        if rule.category_filter:
            config_score += 15
        if rule.auto_approve_below is not None:
            config_score += 15
        
        return usage_score + config_score
    
    def _get_most_delegating_approvers(self, delegations: List[ApprovalDelegate]) -> List[Dict[str, Any]]:
        """Get approvers who delegate most frequently"""
        approver_counts = {}
        
        for delegation in delegations:
            approver_id = delegation.approver_id
            if approver_id not in approver_counts:
                approver_counts[approver_id] = {
                    'approver_id': approver_id,
                    'delegation_count': 0
                }
            approver_counts[approver_id]['delegation_count'] += 1
        
        # Convert to sorted list
        result = list(approver_counts.values())
        result.sort(key=lambda x: x['delegation_count'], reverse=True)
        
        return result[:5]  # Return top 5