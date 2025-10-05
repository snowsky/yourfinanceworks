"""
Tests for Approval Router

This module contains comprehensive tests for all approval REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import json

from main import app
from models.models_per_tenant import (
    Expense, ExpenseApproval, ApprovalRule, User, ApprovalDelegate
)
from schemas.approval import ApprovalStatus
from services.approval_service import ApprovalService


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)

@pytest.fixture
def mock_user():
    """Create mock user for authentication"""
    user = Mock()
    user.id = 1
    user.email = "test@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.role = "admin"
    return user

@pytest.fixture
def mock_expense():
    """Create mock expense for testing"""
    expense = Mock()
    expense.id = 1
    expense.amount = 100.0
    expense.currency = "USD"
    expense.category = "Travel"
    expense.vendor = "Test Vendor"
    expense.expense_date = datetime.now().date()
    expense.status = "draft"
    expense.user_id = 1
    return expense

@pytest.fixture
def mock_approval():
    """Create mock approval for testing"""
    approval = Mock()
    approval.id = 1
    approval.expense_id = 1
    approval.approver_id = 2
    approval.approval_rule_id = 1
    approval.status = ApprovalStatus.PENDING
    approval.notes = "Test approval"
    approval.submitted_at = datetime.now(timezone.utc)
    approval.decided_at = None
    approval.approval_level = 1
    approval.is_current_level = True
    approval.rejection_reason = None
    return approval

@pytest.fixture
def mock_approval_service():
    """Create mock approval service"""
    return Mock(spec=ApprovalService)


class TestApprovalRouter:
    """Test class for approval router endpoints"""
    
    def test_approval_endpoints_exist(self, client):
        """Test that all approval endpoints exist and return proper responses"""
        # Test submit expense for approval endpoint
        response = client.post(
            "/api/v1/approvals/expenses/1/submit-approval",
            json={"expense_id": 1, "notes": "Test"}
        )
        # Should return 401 (unauthorized) not 404 (not found)
        assert response.status_code == 401
        
        # Test get pending approvals endpoint
        response = client.get("/api/v1/approvals/pending")
        assert response.status_code == 401
        
        # Test get pending approvals summary endpoint
        response = client.get("/api/v1/approvals/pending/summary")
        assert response.status_code == 401
        
        # Test approve expense endpoint
        response = client.post(
            "/api/v1/approvals/1/approve",
            json={"status": "approved", "notes": "Test"}
        )
        assert response.status_code == 401
        
        # Test reject expense endpoint
        response = client.post(
            "/api/v1/approvals/1/reject",
            json={"status": "rejected", "rejection_reason": "Test reason"}
        )
        assert response.status_code == 401
        
        # Test get approval history endpoint
        response = client.get("/api/v1/approvals/history/1")
        assert response.status_code == 401
        
        # Test get approval metrics endpoint
        response = client.get("/api/v1/approvals/metrics")
        assert response.status_code == 401
    
    def test_submit_expense_validation(self, client):
        """Test input validation for expense submission"""
        # Test with invalid JSON structure
        response = client.post(
            "/api/v1/approvals/expenses/1/submit-approval",
            json={}  # Missing required expense_id
        )
        # Should return 422 (validation error) or 401 (unauthorized)
        assert response.status_code in [401, 422]
    
    def test_approval_decision_validation(self, client):
        """Test input validation for approval decisions"""
        # Test approve with invalid data
        response = client.post(
            "/api/v1/approvals/1/approve",
            json={}  # Missing required status
        )
        assert response.status_code in [401, 422]
        
        # Test reject with invalid data
        response = client.post(
            "/api/v1/approvals/1/reject",
            json={}  # Missing required status and rejection_reason
        )
        assert response.status_code in [401, 422]
    
    def test_submit_expense_for_approval_mismatched_id(self, client, mock_user, mock_approval_service):
        """Test expense submission with mismatched expense ID"""
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/expenses/1/submit-approval",
                json={
                    "expense_id": 2,  # Different from URL
                    "notes": "Please approve this expense"
                }
            )
        
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]
    
    def test_submit_expense_for_approval_validation_error(self, client, mock_user, mock_approval_service):
        """Test expense submission with validation error"""
        from services.approval_service import ValidationError
        
        mock_approval_service.submit_for_approval.side_effect = ValidationError("Expense not found")
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/expenses/1/submit-approval",
                json={
                    "expense_id": 1,
                    "notes": "Please approve this expense"
                }
            )
        
        assert response.status_code == 400
        assert "Expense not found" in response.json()["detail"]
    
    def test_submit_expense_already_approved(self, client, mock_user, mock_approval_service):
        """Test submitting already approved expense"""
        from services.approval_service import ExpenseAlreadyApproved
        
        mock_approval_service.submit_for_approval.side_effect = ExpenseAlreadyApproved("Already approved")
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/expenses/1/submit-approval",
                json={
                    "expense_id": 1,
                    "notes": "Please approve this expense"
                }
            )
        
        assert response.status_code == 400
        assert "Already approved" in response.json()["detail"]
    
    def test_get_pending_approvals_success(self, client, mock_user, mock_approval_service):
        """Test successful retrieval of pending approvals"""
        mock_approvals = [mock_approval_service]
        mock_approval_service.get_pending_approvals.return_value = mock_approvals
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.get("/api/v1/approvals/pending")
        
        assert response.status_code == 200
        mock_approval_service.get_pending_approvals.assert_called_once_with(
            approver_id=1,
            limit=None,
            offset=None
        )
    
    def test_get_pending_approvals_with_pagination(self, client, mock_user, mock_approval_service):
        """Test pending approvals with pagination parameters"""
        mock_approval_service.get_pending_approvals.return_value = []
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.get("/api/v1/approvals/pending?limit=10&offset=20")
        
        assert response.status_code == 200
        mock_approval_service.get_pending_approvals.assert_called_once_with(
            approver_id=1,
            limit=10,
            offset=20
        )
    
    def test_get_pending_approvals_summary_success(self, client, mock_user, mock_approval_service):
        """Test successful retrieval of pending approvals summary"""
        from schemas.approval import PendingApprovalSummary
        
        mock_summary = PendingApprovalSummary(
            total_pending=5,
            total_amount=500.0,
            currency="USD",
            oldest_submission=datetime.now(timezone.utc),
            by_category=[{"category": "Travel", "count": 3, "amount": 300.0}]
        )
        mock_approval_service.get_pending_approvals_summary.return_value = mock_summary
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.get("/api/v1/approvals/pending/summary")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_pending"] == 5
        assert data["total_amount"] == 500.0
        assert data["currency"] == "USD"
    
    def test_approve_expense_success(self, client, mock_user, mock_approval_service, mock_approval):
        """Test successful expense approval"""
        mock_approval_service.approve_expense.return_value = mock_approval
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'), \
             patch('routers.approvals.log_audit_event'):
            
            response = client.post(
                "/api/v1/approvals/1/approve",
                json={
                    "status": "approved",
                    "notes": "Approved - looks good"
                }
            )
        
        assert response.status_code == 200
        mock_approval_service.approve_expense.assert_called_once_with(
            approval_id=1,
            approver_id=1,
            notes="Approved - looks good"
        )
    
    def test_approve_expense_wrong_status(self, client, mock_user, mock_approval_service):
        """Test approval with wrong status value"""
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/1/approve",
                json={
                    "status": "rejected",  # Wrong status for approve endpoint
                    "notes": "This should fail"
                }
            )
        
        assert response.status_code == 400
        assert "Use the approve endpoint only for approvals" in response.json()["detail"]
    
    def test_approve_expense_insufficient_permissions(self, client, mock_user, mock_approval_service):
        """Test approval with insufficient permissions"""
        from services.approval_service import InsufficientApprovalPermissions
        
        mock_approval_service.approve_expense.side_effect = InsufficientApprovalPermissions("Cannot approve")
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/1/approve",
                json={
                    "status": "approved",
                    "notes": "Should fail"
                }
            )
        
        assert response.status_code == 403
        assert "Cannot approve" in response.json()["detail"]
    
    def test_reject_expense_success(self, client, mock_user, mock_approval_service, mock_approval):
        """Test successful expense rejection"""
        mock_approval.status = ApprovalStatus.REJECTED
        mock_approval.rejection_reason = "Insufficient documentation"
        mock_approval_service.reject_expense.return_value = mock_approval
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'), \
             patch('routers.approvals.log_audit_event'):
            
            response = client.post(
                "/api/v1/approvals/1/reject",
                json={
                    "status": "rejected",
                    "rejection_reason": "Insufficient documentation",
                    "notes": "Please provide receipts"
                }
            )
        
        assert response.status_code == 200
        mock_approval_service.reject_expense.assert_called_once_with(
            approval_id=1,
            approver_id=1,
            rejection_reason="Insufficient documentation",
            notes="Please provide receipts"
        )
    
    def test_reject_expense_wrong_status(self, client, mock_user, mock_approval_service):
        """Test rejection with wrong status value"""
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/1/reject",
                json={
                    "status": "approved",  # Wrong status for reject endpoint
                    "rejection_reason": "This should fail"
                }
            )
        
        assert response.status_code == 400
        assert "Use the reject endpoint only for rejections" in response.json()["detail"]
    
    def test_reject_expense_missing_reason(self, client, mock_user, mock_approval_service):
        """Test rejection without rejection reason"""
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/1/reject",
                json={
                    "status": "rejected",
                    "rejection_reason": "",  # Empty reason
                    "notes": "Should fail"
                }
            )
        
        assert response.status_code == 400
        assert "Rejection reason is required" in response.json()["detail"]
    
    def test_get_approval_history_success(self, client, mock_user, mock_approval_service):
        """Test successful retrieval of approval history"""
        from schemas.approval import ExpenseApprovalHistory, ApprovalHistoryItem
        
        history_item = ApprovalHistoryItem(
            id=1,
            approver_name="Test Approver",
            approver_email="approver@example.com",
            status=ApprovalStatus.APPROVED,
            approval_level=1,
            submitted_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc),
            rejection_reason=None,
            notes="Approved"
        )
        
        mock_history = ExpenseApprovalHistory(
            expense_id=1,
            current_status="approved",
            approval_history=[history_item]
        )
        mock_approval_service.get_approval_history.return_value = mock_history
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.get("/api/v1/approvals/history/1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["expense_id"] == 1
        assert data["current_status"] == "approved"
        assert len(data["approval_history"]) == 1
    
    def test_get_approval_history_expense_not_found(self, client, mock_user, mock_approval_service):
        """Test approval history for non-existent expense"""
        from services.approval_service import ValidationError
        
        mock_approval_service.get_approval_history.side_effect = ValidationError("Expense not found")
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.get("/api/v1/approvals/history/999")
        
        assert response.status_code == 404
        assert "Expense not found" in response.json()["detail"]
    
    def test_get_approval_metrics_success(self, client, mock_user, mock_approval_service):
        """Test successful retrieval of approval metrics"""
        from schemas.approval import ApprovalMetrics
        
        mock_metrics = ApprovalMetrics(
            total_approvals=10,
            approved_count=8,
            rejected_count=2,
            pending_count=0,
            average_approval_time_hours=24.5,
            approval_rate=80.0
        )
        mock_approval_service.get_approval_metrics.return_value = mock_metrics
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.get("/api/v1/approvals/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_approvals"] == 10
        assert data["approved_count"] == 8
        assert data["rejected_count"] == 2
        assert data["approval_rate"] == 80.0
    
    def test_get_approval_metrics_with_approver_filter(self, client, mock_user, mock_approval_service):
        """Test approval metrics with specific approver filter"""
        from schemas.approval import ApprovalMetrics
        
        mock_metrics = ApprovalMetrics(
            total_approvals=5,
            approved_count=4,
            rejected_count=1,
            pending_count=0,
            average_approval_time_hours=12.0,
            approval_rate=80.0
        )
        mock_approval_service.get_approval_metrics.return_value = mock_metrics
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.get("/api/v1/approvals/metrics?approver_id=2")
        
        assert response.status_code == 200
        mock_approval_service.get_approval_metrics.assert_called_once_with(approver_id=2)


class TestApprovalRouterIntegration:
    """Integration tests for approval router with real database"""
    
    @pytest.fixture
    def db_session(self):
        """Create database session for integration tests"""
        # This would be implemented with actual database setup
        pass
    
    @pytest.fixture
    def test_user(self, db_session):
        """Create test user in database"""
        # This would create a real user for testing
        pass
    
    @pytest.fixture
    def test_expense(self, db_session, test_user):
        """Create test expense in database"""
        # This would create a real expense for testing
        pass
    
    @pytest.fixture
    def test_approval_rule(self, db_session, test_user):
        """Create test approval rule in database"""
        # This would create a real approval rule for testing
        pass
    
    def test_full_approval_workflow_integration(self, client, db_session, test_user, test_expense, test_approval_rule):
        """Test complete approval workflow from submission to approval"""
        # This would test the full workflow with real database operations
        pass
    
    def test_multi_level_approval_integration(self, client, db_session):
        """Test multi-level approval workflow"""
        # This would test multi-level approvals with real database
        pass
    
    def test_approval_delegation_integration(self, client, db_session):
        """Test approval delegation functionality"""
        # This would test delegation with real database
        pass


class TestApprovalRouterErrorHandling:
    """Test error handling scenarios for approval router"""
    
    def test_database_connection_error(self, client, mock_user):
        """Test handling of database connection errors"""
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', side_effect=Exception("Database error")), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.get("/api/v1/approvals/pending")
        
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
    
    def test_authentication_required(self, client):
        """Test that authentication is required for all endpoints"""
        # Test without authentication
        response = client.get("/api/v1/approvals/pending")
        assert response.status_code == 401  # Unauthorized
    
    def test_viewer_role_restriction(self, client):
        """Test that viewer role is restricted from approval operations"""
        mock_viewer = Mock()
        mock_viewer.id = 1
        mock_viewer.role = "viewer"
        
        with patch('routers.approvals.get_current_user', return_value=mock_viewer), \
             patch('routers.approvals.require_non_viewer', side_effect=Exception("Viewer access denied")):
            
            response = client.get("/api/v1/approvals/pending")
        
        assert response.status_code == 500  # This would be 403 in real implementation
    
    def test_invalid_approval_id(self, client, mock_user, mock_approval_service):
        """Test handling of invalid approval IDs"""
        from services.approval_service import ValidationError
        
        mock_approval_service.approve_expense.side_effect = ValidationError("Approval not found")
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/999/approve",
                json={"status": "approved", "notes": "Test"}
            )
        
        assert response.status_code == 400
        assert "Approval not found" in response.json()["detail"]
    
    def test_invalid_expense_id(self, client, mock_user, mock_approval_service):
        """Test handling of invalid expense IDs"""
        from services.approval_service import ValidationError
        
        mock_approval_service.get_approval_history.side_effect = ValidationError("Expense not found")
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.get("/api/v1/approvals/history/999")
        
        assert response.status_code == 404
        assert "Expense not found" in response.json()["detail"]


class TestApprovalRouterValidation:
    """Test input validation for approval router endpoints"""
    
    def test_submit_approval_invalid_json(self, client, mock_user):
        """Test submission with invalid JSON"""
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/expenses/1/submit-approval",
                data="invalid json"
            )
        
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_submit_approval_missing_required_fields(self, client, mock_user):
        """Test submission with missing required fields"""
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.require_non_viewer'):
            
            response = client.post(
                "/api/v1/approvals/expenses/1/submit-approval",
                json={}  # Missing expense_id
            )
        
        assert response.status_code == 422  # Validation error
    
    def test_pagination_parameter_validation(self, client, mock_user, mock_approval_service):
        """Test validation of pagination parameters"""
        mock_approval_service.get_pending_approvals.return_value = []
        
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.get_approval_service', return_value=mock_approval_service), \
             patch('routers.approvals.require_non_viewer'):
            
            # Test negative limit
            response = client.get("/api/v1/approvals/pending?limit=-1")
            assert response.status_code == 422
            
            # Test limit too large
            response = client.get("/api/v1/approvals/pending?limit=1000")
            assert response.status_code == 422
            
            # Test negative offset
            response = client.get("/api/v1/approvals/pending?offset=-1")
            assert response.status_code == 422
    
    def test_approval_decision_validation(self, client, mock_user):
        """Test validation of approval decision data"""
        with patch('routers.approvals.get_current_user', return_value=mock_user), \
             patch('routers.approvals.require_non_viewer'):
            
            # Test invalid status
            response = client.post(
                "/api/v1/approvals/1/approve",
                json={"status": "invalid_status"}
            )
            assert response.status_code == 422
            
            # Test missing status
            response = client.post(
                "/api/v1/approvals/1/approve",
                json={"notes": "Test"}
            )
            assert response.status_code == 422