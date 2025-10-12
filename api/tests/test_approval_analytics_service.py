"""
Tests for Approval Analytics Service

Tests for approval workflow analytics, metrics calculation, pattern analysis,
and compliance reporting functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from services.approval_analytics_service import (
    ApprovalAnalyticsService, ApprovalMetrics, ApprovalPatternAnalysis,
    ApprovalComplianceReport
)
from models.models_per_tenant import (
    ExpenseApproval, ApprovalRule, ApprovalDelegate, Expense, User
)
from schemas.approval import ApprovalStatus


class TestApprovalAnalyticsService:
    """Test suite for ApprovalAnalyticsService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def analytics_service(self, mock_db):
        """Create analytics service instance"""
        return ApprovalAnalyticsService(mock_db)
    
    @pytest.fixture
    def sample_user(self):
        """Create sample user"""
        user = Mock(spec=User)
        user.id = 1
        user.first_name = "John"
        user.last_name = "Doe"
        user.email = "john.doe@example.com"
        return user
    
    @pytest.fixture
    def sample_expense(self):
        """Create sample expense"""
        expense = Mock(spec=Expense)
        expense.id = 1
        expense.amount = 500.0
        expense.currency = "USD"
        expense.category = "travel"
        expense.expense_date = datetime.now()
        return expense
    
    @pytest.fixture
    def sample_approval_rule(self, sample_user):
        """Create sample approval rule"""
        rule = Mock(spec=ApprovalRule)
        rule.id = 1
        rule.name = "Travel Expenses"
        rule.min_amount = 100.0
        rule.max_amount = 1000.0
        rule.category_filter = '["travel"]'
        rule.currency = "USD"
        rule.approval_level = 1
        rule.approver_id = sample_user.id
        rule.is_active = True
        rule.priority = 1
        rule.auto_approve_below = None
        return rule
    
    @pytest.fixture
    def sample_approval(self, sample_expense, sample_user, sample_approval_rule):
        """Create sample expense approval"""
        approval = Mock(spec=ExpenseApproval)
        approval.id = 1
        approval.expense_id = sample_expense.id
        approval.approver_id = sample_user.id
        approval.approval_rule_id = sample_approval_rule.id
        approval.status = ApprovalStatus.PENDING
        approval.rejection_reason = None
        approval.notes = None
        approval.submitted_at = datetime.now() - timedelta(hours=2)
        approval.decided_at = None
        approval.approval_level = 1
        approval.is_current_level = True
        
        # Set up relationships
        approval.expense = sample_expense
        approval.approver = sample_user
        approval.approval_rule = sample_approval_rule
        
        return approval
    
    def test_calculate_approval_metrics_empty_data(self, analytics_service, mock_db):
        """Test metrics calculation with no data"""
        # Mock empty query result
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        metrics = analytics_service.calculate_approval_metrics()
        
        assert isinstance(metrics, ApprovalMetrics)
        assert metrics.total_approvals == 0
        assert metrics.pending_approvals == 0
        assert metrics.approved_count == 0
        assert metrics.rejected_count == 0
        assert metrics.average_approval_time == 0.0
        assert metrics.approval_rate == 0.0
    
    def test_calculate_approval_metrics_with_data(self, analytics_service, mock_db, sample_approval, sample_user):
        """Test metrics calculation with sample data"""
        # Create approved approval
        approved_approval = Mock(spec=ExpenseApproval)
        approved_approval.id = 2
        approved_approval.status = ApprovalStatus.APPROVED
        approved_approval.submitted_at = datetime.now() - timedelta(hours=24)
        approved_approval.decided_at = datetime.now() - timedelta(hours=20)
        approved_approval.approver_id = sample_user.id
        approved_approval.approver = sample_user
        approved_approval.expense = sample_approval.expense
        approved_approval.approval_rule = sample_approval.approval_rule
        
        # Create rejected approval
        rejected_approval = Mock(spec=ExpenseApproval)
        rejected_approval.id = 3
        rejected_approval.status = ApprovalStatus.REJECTED
        rejected_approval.submitted_at = datetime.now() - timedelta(hours=48)
        rejected_approval.decided_at = datetime.now() - timedelta(hours=46)
        rejected_approval.rejection_reason = "Insufficient documentation"
        rejected_approval.approver_id = sample_user.id
        rejected_approval.approver = sample_user
        rejected_approval.expense = sample_approval.expense
        rejected_approval.approval_rule = sample_approval.approval_rule
        
        approvals = [sample_approval, approved_approval, rejected_approval]
        
        # Mock query chain
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = approvals
        mock_db.query.return_value = mock_query
        
        metrics = analytics_service.calculate_approval_metrics()
        
        assert metrics.total_approvals == 3
        assert metrics.pending_approvals == 1
        assert metrics.approved_count == 1
        assert metrics.rejected_count == 1
        assert metrics.approval_rate == 50.0  # 1 approved out of 2 decided
        assert metrics.rejection_rate == 50.0
        assert metrics.average_approval_time > 0
    
    def test_calculate_approval_metrics_with_filters(self, analytics_service, mock_db, sample_approval):
        """Test metrics calculation with filters applied"""
        date_from = datetime.now() - timedelta(days=30)
        date_to = datetime.now()
        approver_ids = [1, 2]
        categories = ["travel", "meals"]
        
        # Mock query chain
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = [sample_approval]
        mock_db.query.return_value = mock_query
        
        metrics = analytics_service.calculate_approval_metrics(
            date_from=date_from,
            date_to=date_to,
            approver_ids=approver_ids,
            categories=categories
        )
        
        # Verify filters were applied
        assert mock_query.filter.call_count >= 4  # date_from, date_to, approver_ids, categories
        assert metrics.total_approvals == 1
    
    def test_analyze_approval_patterns_empty_data(self, analytics_service, mock_db):
        """Test pattern analysis with no data"""
        # Mock empty query result
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        patterns = analytics_service.analyze_approval_patterns()
        
        assert isinstance(patterns, ApprovalPatternAnalysis)
        assert len(patterns.common_rejection_reasons) == 0
        assert len(patterns.approval_time_by_amount) == 5  # 5 amount ranges
        assert len(patterns.recommendations) == 0
    
    def test_analyze_approval_patterns_with_data(self, analytics_service, mock_db, sample_user, sample_expense):
        """Test pattern analysis with sample data"""
        # Create rejected approval with reason
        rejected_approval = Mock(spec=ExpenseApproval)
        rejected_approval.status = ApprovalStatus.REJECTED
        rejected_approval.rejection_reason = "Missing receipt"
        rejected_approval.submitted_at = datetime.now() - timedelta(hours=10)
        rejected_approval.decided_at = datetime.now() - timedelta(hours=8)
        rejected_approval.approver = sample_user
        rejected_approval.expense = sample_expense
        
        approvals = [rejected_approval]
        
        # Mock query chain
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = approvals
        mock_db.query.return_value = mock_query
        
        patterns = analytics_service.analyze_approval_patterns()
        
        assert len(patterns.common_rejection_reasons) == 1
        assert patterns.common_rejection_reasons[0]['reason'] == "Missing receipt"
        assert patterns.common_rejection_reasons[0]['count'] == 1
    
    def test_generate_compliance_report_empty_data(self, analytics_service, mock_db):
        """Test compliance report generation with no data"""
        # Mock empty query results
        mock_expense_query = Mock()
        mock_expense_query.filter.return_value = mock_expense_query
        mock_expense_query.all.return_value = []
        
        mock_rule_query = Mock()
        mock_rule_query.filter.return_value = mock_rule_query
        mock_rule_query.all.return_value = []
        
        mock_delegation_query = Mock()
        mock_delegation_query.filter.return_value = mock_delegation_query
        mock_delegation_query.all.return_value = []
        
        mock_db.query.side_effect = [mock_expense_query, mock_rule_query, mock_delegation_query]
        
        report = analytics_service.generate_compliance_report()
        
        assert isinstance(report, ApprovalComplianceReport)
        assert report.total_expenses == 0
        assert report.expenses_requiring_approval == 0
        assert report.expenses_bypassed_approval == 0
        assert report.compliance_rate == 0.0
    
    def test_generate_compliance_report_with_violations(self, analytics_service, mock_db, sample_expense, sample_approval_rule):
        """Test compliance report with policy violations"""
        # Mock expenses that should require approval but don't have approval records
        expenses = [sample_expense]
        approval_rules = [sample_approval_rule]
        
        # Mock query chains
        expense_query = Mock()
        expense_query.filter.return_value = expense_query
        expense_query.all.return_value = expenses
        
        rule_query = Mock()
        rule_query.filter.return_value = rule_query
        rule_query.all.return_value = approval_rules
        
        approval_query = Mock()
        approval_query.filter.return_value = approval_query
        approval_query.first.return_value = None  # No approval record found
        
        # Mock the approval count query
        approval_count_query = Mock()
        approval_count_query.filter.return_value = approval_count_query
        approval_count_query.count.return_value = 0
        
        # Mock delegation query
        delegation_query = Mock()
        delegation_query.filter.return_value = delegation_query
        delegation_query.all.return_value = []
        
        mock_db.query.side_effect = [expense_query, rule_query, approval_count_query, delegation_query]
        
        with patch.object(analytics_service, '_should_expense_require_approval', return_value=True):
            with patch.object(analytics_service, '_expense_has_approval_record', return_value=False):
                report = analytics_service.generate_compliance_report()
        
        assert report.total_expenses == 1
        assert report.expenses_requiring_approval == 1
        assert report.expenses_bypassed_approval == 1
        assert report.compliance_rate == 0.0  # 0% compliance
        assert len(report.policy_violations) == 1
    
    def test_should_expense_require_approval_matching_rule(self, analytics_service, sample_expense, sample_approval_rule):
        """Test expense approval requirement with matching rule"""
        # Set up expense that matches the rule
        sample_expense.amount = 500.0  # Within rule range (100-1000)
        sample_expense.category = "travel"  # Matches rule category
        sample_expense.currency = "USD"  # Matches rule currency
        
        approval_rules = [sample_approval_rule]
        
        result = analytics_service._should_expense_require_approval(sample_expense, approval_rules)
        
        assert result is True
    
    def test_should_expense_require_approval_no_matching_rule(self, analytics_service, sample_expense, sample_approval_rule):
        """Test expense approval requirement with no matching rule"""
        # Set up expense that doesn't match the rule
        sample_expense.amount = 50.0  # Below rule minimum
        sample_expense.category = "office"  # Different category
        sample_expense.currency = "EUR"  # Different currency
        
        approval_rules = [sample_approval_rule]
        
        result = analytics_service._should_expense_require_approval(sample_expense, approval_rules)
        
        assert result is False
    
    def test_calculate_bottlenecks(self, analytics_service, sample_user):
        """Test bottleneck calculation"""
        # Create approvals with different timing
        fast_approval = Mock(spec=ExpenseApproval)
        fast_approval.approver_id = 1
        fast_approval.approver = sample_user
        fast_approval.submitted_at = datetime.now() - timedelta(hours=2)
        fast_approval.decided_at = datetime.now() - timedelta(hours=1)
        
        slow_approval = Mock(spec=ExpenseApproval)
        slow_approval.approver_id = 1
        slow_approval.approver = sample_user
        slow_approval.submitted_at = datetime.now() - timedelta(hours=48)
        slow_approval.decided_at = datetime.now() - timedelta(hours=24)
        
        decided_approvals = [fast_approval, slow_approval]
        
        bottlenecks = analytics_service._calculate_bottlenecks(decided_approvals)
        
        assert len(bottlenecks) == 1
        assert bottlenecks[0]['approver_id'] == 1
        assert bottlenecks[0]['average_time_hours'] > 12  # Average of 1h and 24h
        assert bottlenecks[0]['is_bottleneck'] is True  # >24h average (12.5h average should be False, but let's check the actual value)
        # The average should be (1 + 24) / 2 = 12.5 hours, which is < 24, so is_bottleneck should be False
        # Let's fix the assertion
        assert bottlenecks[0]['average_time_hours'] > 12  # Average of 1h and 24h
        # The bottleneck threshold is 24 hours, so 12.5 hours should not be a bottleneck
        assert bottlenecks[0]['is_bottleneck'] is False
    
    def test_analyze_rejection_reasons(self, analytics_service):
        """Test rejection reason analysis"""
        # Create approvals with rejection reasons
        approval1 = Mock(spec=ExpenseApproval)
        approval1.status = ApprovalStatus.REJECTED
        approval1.rejection_reason = "Missing receipt"
        approval1.expense = Mock()
        approval1.expense.amount = 100.0
        
        approval2 = Mock(spec=ExpenseApproval)
        approval2.status = ApprovalStatus.REJECTED
        approval2.rejection_reason = "Missing receipt"
        approval2.expense = Mock()
        approval2.expense.amount = 200.0
        
        approval3 = Mock(spec=ExpenseApproval)
        approval3.status = ApprovalStatus.REJECTED
        approval3.rejection_reason = "Exceeds policy limit"
        approval3.expense = Mock()
        approval3.expense.amount = 500.0
        
        approvals = [approval1, approval2, approval3]
        
        reasons = analytics_service._analyze_rejection_reasons(approvals)
        
        assert len(reasons) == 2
        assert reasons[0]['reason'] == "Missing receipt"
        assert reasons[0]['count'] == 2
        assert reasons[0]['total_amount'] == 300.0
        assert reasons[1]['reason'] == "Exceeds policy limit"
        assert reasons[1]['count'] == 1
    
    def test_analyze_approval_time_by_amount(self, analytics_service, sample_expense):
        """Test approval time analysis by amount ranges"""
        # Create approvals with different amounts and times
        small_approval = Mock(spec=ExpenseApproval)
        small_approval.submitted_at = datetime.now() - timedelta(hours=2)
        small_approval.decided_at = datetime.now() - timedelta(hours=1)
        small_approval.expense = Mock()
        small_approval.expense.amount = 50.0
        
        large_approval = Mock(spec=ExpenseApproval)
        large_approval.submitted_at = datetime.now() - timedelta(hours=24)
        large_approval.decided_at = datetime.now() - timedelta(hours=20)
        large_approval.expense = Mock()
        large_approval.expense.amount = 5000.0
        
        approvals = [small_approval, large_approval]
        
        result = analytics_service._analyze_approval_time_by_amount(approvals)
        
        assert '0-100' in result
        assert '5000+' in result
        assert abs(result['0-100'] - 1.0) < 0.01  # 1 hour (allow for small floating point differences)
        assert result['5000+'] == 4.0  # 4 hours
    
    def test_calculate_efficiency_score(self, analytics_service):
        """Test efficiency score calculation"""
        # High performing approver
        high_perf_stats = {
            'approved': 9,
            'rejected': 1
        }
        high_score = analytics_service._calculate_efficiency_score(high_perf_stats, 4.0)  # 4 hours avg
        
        # Low performing approver
        low_perf_stats = {
            'approved': 5,
            'rejected': 5
        }
        low_score = analytics_service._calculate_efficiency_score(low_perf_stats, 48.0)  # 48 hours avg
        
        assert high_score > low_score
        assert high_score <= 100
        assert low_score >= 0
    
    def test_generate_recommendations(self, analytics_service):
        """Test recommendation generation"""
        # Create pattern analysis with data that should trigger recommendations
        analysis = ApprovalPatternAnalysis()
        analysis.approval_time_by_amount = {
            '0-100': 1.0,
            '5000+': 10.0  # Much longer for high amounts
        }
        analysis.common_rejection_reasons = [
            {'reason': 'Missing receipt', 'count': 50}  # High count
        ]
        analysis.peak_submission_times = {
            'by_hour': {'9': 100},  # High concentration
            'by_day': {}
        }
        
        # Mock approvals list
        approvals = [Mock() for _ in range(100)]
        
        recommendations = analytics_service._generate_recommendations(analysis, approvals)
        
        assert len(recommendations) > 0
        # Should have recommendations for high-value expenses and rejection patterns
        rec_types = [rec['type'] for rec in recommendations]
        assert 'process_optimization' in rec_types or 'policy_clarification' in rec_types
    
    def test_date_filtering_applied(self, analytics_service, mock_db):
        """Test that date filters are properly applied to queries"""
        date_from = datetime.now() - timedelta(days=30)
        date_to = datetime.now()
        
        # Mock query chain
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        analytics_service.calculate_approval_metrics(
            date_from=date_from,
            date_to=date_to
        )
        
        # Verify date filters were applied
        filter_calls = mock_query.filter.call_args_list
        assert len(filter_calls) >= 2  # At least date_from and date_to filters
    
    def test_error_handling_in_metrics_calculation(self, analytics_service, mock_db):
        """Test error handling in metrics calculation"""
        # Mock database error
        mock_db.query.side_effect = Exception("Database error")
        
        with pytest.raises(Exception):
            analytics_service.calculate_approval_metrics()
    
    def test_empty_approval_times_handling(self, analytics_service):
        """Test handling of empty approval times list"""
        # Test with empty list
        bottlenecks = analytics_service._calculate_bottlenecks([])
        assert bottlenecks == []
        
        # Test with approvals that have no decided_at
        pending_approval = Mock(spec=ExpenseApproval)
        pending_approval.decided_at = None
        pending_approval.submitted_at = datetime.now()
        pending_approval.approver_id = 1
        pending_approval.approver = Mock()
        pending_approval.approver.first_name = "Test"
        pending_approval.approver.last_name = "User"
        
        bottlenecks = analytics_service._calculate_bottlenecks([pending_approval])
        assert bottlenecks == []