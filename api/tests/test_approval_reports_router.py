"""
Tests for Approval Reports Router

Tests for approval analytics and reporting API endpoints.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from main import app
from core.models.models_per_tenant import User
from commercial.workflows.approvals.services.approval_analytics_service import (
    ApprovalMetrics, ApprovalPatternAnalysis, ApprovalComplianceReport
)


class TestApprovalReportsRouter:
    """Test suite for approval reports router"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.role = "admin"
        return user
    
    @pytest.fixture
    def mock_metrics(self):
        """Mock approval metrics"""
        metrics = ApprovalMetrics()
        metrics.total_approvals = 100
        metrics.pending_approvals = 10
        metrics.approved_count = 80
        metrics.rejected_count = 10
        metrics.average_approval_time = 24.5
        metrics.median_approval_time = 18.0
        metrics.approval_rate = 88.9
        metrics.rejection_rate = 11.1
        metrics.bottlenecks = [
            {
                'approver_id': 1,
                'approver_name': 'John Doe',
                'average_time_hours': 48.0,
                'approval_count': 20,
                'is_bottleneck': True
            }
        ]
        metrics.approver_performance = [
            {
                'approver_id': 1,
                'approver_name': 'John Doe',
                'total_assigned': 25,
                'approved': 20,
                'rejected': 3,
                'pending': 2,
                'approval_rate': 87.0,
                'average_time_hours': 36.0,
                'efficiency_score': 75.5
            }
        ]
        metrics.category_breakdown = {
            'travel': {
                'total': 50,
                'approved': 45,
                'rejected': 3,
                'pending': 2,
                'approval_rate': 93.8,
                'average_time_hours': 20.0,
                'total_amount': 25000.0,
                'average_amount': 500.0
            }
        }
        metrics.monthly_trends = {
            '2024-01': {
                'total_submitted': 30,
                'approved': 25,
                'rejected': 3,
                'pending': 2,
                'approval_rate': 89.3,
                'average_time_hours': 22.0,
                'total_amount': 15000.0
            }
        }
        metrics.compliance_issues = [
            {
                'type': 'delayed_approval',
                'approval_id': 123,
                'expense_id': 456,
                'approver_id': 1,
                'delay_hours': 168.0,
                'description': 'Approval took 7.0 days to complete'
            }
        ]
        return metrics
    
    @pytest.fixture
    def mock_patterns(self):
        """Mock approval pattern analysis"""
        patterns = ApprovalPatternAnalysis()
        patterns.common_rejection_reasons = [
            {
                'reason': 'Missing receipt',
                'count': 15,
                'total_amount': 7500.0
            }
        ]
        patterns.approval_time_by_amount = {
            '0-100': 2.0,
            '100-500': 8.0,
            '500-1000': 16.0,
            '1000-5000': 24.0,
            '5000+': 48.0
        }
        patterns.approval_time_by_category = {
            'travel': 18.0,
            'meals': 12.0,
            'office': 6.0
        }
        patterns.peak_submission_times = {
            'by_hour': {'9': 25, '10': 30, '14': 20},
            'by_day': {'Monday': 40, 'Tuesday': 35, 'Wednesday': 25}
        }
        patterns.escalation_patterns = [
            {
                'expense_id': 789,
                'levels': 2,
                'total_time_hours': 72.0,
                'level_times': [
                    {'level': 1, 'time_hours': 24.0, 'approver_id': 1},
                    {'level': 2, 'time_hours': 48.0, 'approver_id': 2}
                ]
            }
        ]
        patterns.recommendations = [
            {
                'type': 'process_optimization',
                'priority': 'high',
                'title': 'Optimize High-Value Expense Approvals',
                'description': 'High-value expenses take significantly longer to approve.',
                'impact': 'Reduce approval time for high-value expenses by up to 50%'
            }
        ]
        return patterns
    
    @pytest.fixture
    def mock_compliance(self):
        """Mock compliance report"""
        compliance = ApprovalComplianceReport()
        compliance.total_expenses = 500
        compliance.expenses_requiring_approval = 300
        compliance.expenses_bypassed_approval = 15
        compliance.compliance_rate = 95.0
        compliance.policy_violations = [
            {
                'expense_id': 101,
                'amount': 750.0,
                'category': 'travel',
                'expense_date': datetime.now().isoformat(),
                'violation_type': 'bypassed_approval',
                'description': 'Expense bypassed approval workflow'
            }
        ]
        compliance.rule_effectiveness = [
            {
                'rule_id': 1,
                'rule_name': 'Travel Expenses',
                'approval_count': 150,
                'is_active': True,
                'effectiveness_score': 85.0
            }
        ]
        compliance.delegation_usage = {
            'total_delegations': 25,
            'active_delegations': 5,
            'average_duration_days': 7.5,
            'most_delegating_approvers': [
                {'approver_id': 1, 'delegation_count': 8}
            ]
        }
        return compliance
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_get_approval_metrics_success(self, mock_service_class, mock_require_permission, 
                                        mock_get_user, client, mock_user, mock_metrics):
        """Test successful approval metrics retrieval"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.calculate_approval_metrics.return_value = mock_metrics
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get("/approval-reports/metrics")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['total_approvals'] == 100
        assert data['approval_rate'] == 88.9
        assert len(data['bottlenecks']) == 1
        assert len(data['approver_performance']) == 1
        
        # Verify service was called correctly
        mock_service.calculate_approval_metrics.assert_called_once()
        mock_require_permission.assert_called_once_with(mock_user, "approval_view")
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_get_approval_metrics_with_filters(self, mock_service_class, mock_require_permission,
                                             mock_get_user, client, mock_user, mock_metrics):
        """Test approval metrics with query filters"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.calculate_approval_metrics.return_value = mock_metrics
        mock_service_class.return_value = mock_service
        
        # Make request with filters
        date_from = (datetime.now() - timedelta(days=30)).isoformat()
        date_to = datetime.now().isoformat()
        
        response = client.get(
            f"/approval-reports/metrics?date_from={date_from}&date_to={date_to}&approver_ids=1&categories=travel"
        )
        
        # Verify response
        assert response.status_code == 200
        
        # Verify service was called with filters
        call_args = mock_service.calculate_approval_metrics.call_args
        assert call_args.kwargs['approver_ids'] == [1]
        assert call_args.kwargs['categories'] == ['travel']
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_get_approval_patterns_success(self, mock_service_class, mock_require_permission,
                                         mock_get_user, client, mock_user, mock_patterns):
        """Test successful approval patterns retrieval"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.analyze_approval_patterns.return_value = mock_patterns
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get("/approval-reports/patterns")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data['common_rejection_reasons']) == 1
        assert data['common_rejection_reasons'][0]['reason'] == 'Missing receipt'
        assert len(data['recommendations']) == 1
        assert data['recommendations'][0]['priority'] == 'high'
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_get_approval_compliance_success(self, mock_service_class, mock_require_permission,
                                           mock_get_user, client, mock_user, mock_compliance):
        """Test successful compliance report retrieval"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.generate_compliance_report.return_value = mock_compliance
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get("/approval-reports/compliance")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['total_expenses'] == 500
        assert data['compliance_rate'] == 95.0
        assert len(data['policy_violations']) == 1
        assert len(data['rule_effectiveness']) == 1
        
        # Verify admin permission was required
        mock_require_permission.assert_called_once_with(mock_user, "approval_admin")
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    def test_get_approval_compliance_permission_denied(self, mock_require_permission,
                                                     mock_get_user, client, mock_user):
        """Test compliance report access denied for non-admin users"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.side_effect = HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Make request
        response = client.get("/approval-reports/compliance")
        
        # Verify permission denied
        assert response.status_code == 403
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_generate_approval_report_metrics(self, mock_service_class, mock_require_permission,
                                            mock_get_user, client, mock_user, mock_metrics):
        """Test approval report generation for metrics"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.calculate_approval_metrics.return_value = mock_metrics
        mock_service_class.return_value = mock_service
        
        # Make request
        request_data = {
            "report_type": "metrics",
            "filters": {
                "date_from": (datetime.now() - timedelta(days=30)).isoformat(),
                "date_to": datetime.now().isoformat()
            },
            "export_format": "json"
        }
        
        response = client.post("/approval-reports/generate", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['report_type'] == 'metrics'
        assert 'data' in data
        assert 'generated_at' in data
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_generate_approval_report_patterns(self, mock_service_class, mock_require_permission,
                                             mock_get_user, client, mock_user, mock_patterns):
        """Test approval report generation for patterns"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.analyze_approval_patterns.return_value = mock_patterns
        mock_service_class.return_value = mock_service
        
        # Make request
        request_data = {
            "report_type": "patterns",
            "filters": {},
            "export_format": "json"
        }
        
        response = client.post("/approval-reports/generate", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['report_type'] == 'patterns'
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_generate_approval_report_compliance(self, mock_service_class, mock_require_permission,
                                               mock_get_user, client, mock_user, mock_compliance):
        """Test approval report generation for compliance"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.generate_compliance_report.return_value = mock_compliance
        mock_service_class.return_value = mock_service
        
        # Make request
        request_data = {
            "report_type": "compliance",
            "filters": {},
            "export_format": "json"
        }
        
        response = client.post("/approval-reports/generate", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['report_type'] == 'compliance'
        
        # Verify admin permission was required
        mock_require_permission.assert_called_once_with(mock_user, "approval_admin")
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    def test_generate_approval_report_invalid_type(self, mock_require_permission,
                                                  mock_get_user, client, mock_user):
        """Test approval report generation with invalid report type"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        # Make request with invalid report type
        request_data = {
            "report_type": "invalid_type",
            "filters": {},
            "export_format": "json"
        }
        
        response = client.post("/approval-reports/generate", json=request_data)
        
        # Verify error response
        assert response.status_code == 400
        assert "Unsupported report type" in response.json()['detail']
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_generate_approval_report_service_error(self, mock_service_class, mock_require_permission,
                                                   mock_get_user, client, mock_user):
        """Test approval report generation with service error"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.calculate_approval_metrics.side_effect = Exception("Service error")
        mock_service_class.return_value = mock_service
        
        # Make request
        request_data = {
            "report_type": "metrics",
            "filters": {},
            "export_format": "json"
        }
        
        response = client.post("/approval-reports/generate", json=request_data)
        
        # Verify error response
        assert response.status_code == 200  # Returns success=False instead of HTTP error
        data = response.json()
        assert data['success'] is False
        assert 'error_message' in data
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_get_approval_dashboard_summary(self, mock_service_class, mock_require_permission,
                                          mock_get_user, client, mock_user, mock_metrics):
        """Test approval dashboard summary retrieval"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.calculate_approval_metrics.return_value = mock_metrics
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get("/approval-reports/summary")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert 'pending_approvals_count' in data
        assert 'overdue_approvals_count' in data
        assert 'avg_approval_time_hours' in data
        assert 'approval_rate_last_30_days' in data
        assert 'top_bottlenecks' in data
        assert 'quick_stats' in data
    
    @patch('routers.approval_reports.get_current_user')
    @patch('routers.approval_reports.require_permission')
    @patch('routers.approval_reports.ApprovalAnalyticsService')
    def test_service_error_handling(self, mock_service_class, mock_require_permission,
                                   mock_get_user, client, mock_user):
        """Test error handling when service throws exception"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_require_permission.return_value = None
        
        mock_service = Mock()
        mock_service.calculate_approval_metrics.side_effect = Exception("Database connection failed")
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get("/approval-reports/metrics")
        
        # Verify error response
        assert response.status_code == 500
        assert "Failed to calculate approval metrics" in response.json()['detail']
    
    @patch('routers.approval_reports.get_current_user')
    def test_authentication_required(self, mock_get_user, client):
        """Test that authentication is required for all endpoints"""
        # Mock authentication failure
        mock_get_user.side_effect = HTTPException(status_code=401, detail="Not authenticated")
        
        # Test various endpoints
        endpoints = [
            "/approval-reports/metrics",
            "/approval-reports/patterns",
            "/approval-reports/compliance",
            "/approval-reports/summary"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401
    
    def test_date_range_parsing(self):
        """Test date range parsing helper function"""
        from core.routers.approval_reports import _parse_date_range
        from core.schemas.approval_reports import ApprovalAnalyticsFilters
        
        # Test last_30_days
        filters = ApprovalAnalyticsFilters(date_range="last_30_days")
        date_from, date_to = _parse_date_range(filters)
        
        assert date_from < date_to
        assert (date_to - date_from).days == 30
        
        # Test custom range
        custom_from = datetime.now() - timedelta(days=60)
        custom_to = datetime.now() - timedelta(days=30)
        
        filters = ApprovalAnalyticsFilters(
            date_range="custom",
            custom_date_from=custom_from,
            custom_date_to=custom_to
        )
        date_from, date_to = _parse_date_range(filters)
        
        assert date_from == custom_from
        assert date_to == custom_to
    
    def test_date_range_parsing_custom_missing_dates(self):
        """Test date range parsing with missing custom dates"""
        from core.routers.approval_reports import _parse_date_range
        from core.schemas.approval_reports import ApprovalAnalyticsFilters
        
        # Test custom range without dates
        filters = ApprovalAnalyticsFilters(date_range="custom")
        
        with pytest.raises(HTTPException) as exc_info:
            _parse_date_range(filters)
        
        assert exc_info.value.status_code == 400
        assert "Custom date range requires" in str(exc_info.value.detail)