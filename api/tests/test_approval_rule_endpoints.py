"""
Tests for approval rule management endpoints.

This module tests the CRUD operations for approval rules including:
- Creating approval rules (admin only)
- Listing approval rules with filtering
- Updating approval rules (admin only)
- Deleting approval rules (admin only)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from main import app
from core.models.database import get_db
from core.models.models_per_tenant import ApprovalRule, User, ExpenseApproval, Expense
from core.models.models import MasterUser
from core.schemas.approval import ApprovalStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Create database session for testing."""
    # This would typically use a test database
    # For now, we'll mock it in the actual tests
    pass


@pytest.fixture
def admin_user():
    """Create admin user for testing."""
    return MasterUser(
        id=1,
        email="admin@test.com",
        role="admin",
        is_superuser=False,
        tenant_id=1
    )


@pytest.fixture
def regular_user():
    """Create regular user for testing."""
    return MasterUser(
        id=2,
        email="user@test.com",
        role="user",
        is_superuser=False,
        tenant_id=1
    )


@pytest.fixture
def viewer_user():
    """Create viewer user for testing."""
    return MasterUser(
        id=3,
        email="viewer@test.com",
        role="viewer",
        is_superuser=False,
        tenant_id=1
    )


@pytest.fixture
def sample_approval_rule_data():
    """Sample approval rule data for testing."""
    return {
        "name": "Manager Approval for High Value",
        "min_amount": 1000.0,
        "max_amount": 5000.0,
        "category_filter": '["travel", "equipment"]',
        "currency": "USD",
        "approval_level": 1,
        "approver_id": 2,
        "is_active": True,
        "priority": 10,
        "auto_approve_below": 100.0
    }


class TestCreateApprovalRule:
    """Test approval rule creation endpoint."""
    
    def test_create_approval_rule_success(self, client, admin_user, sample_approval_rule_data, mocker):
        """Test successful approval rule creation by admin."""
        # Mock database and dependencies
        mock_db = mocker.Mock(spec=Session)
        mock_user = mocker.Mock(spec=User)
        mock_user.id = 2
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        mock_approval_rule = mocker.Mock()
        mock_approval_rule.id = 1
        mock_approval_rule.name = sample_approval_rule_data["name"]
        mock_approval_rule.created_at = datetime.now(timezone.utc)
        mock_approval_rule.updated_at = datetime.now(timezone.utc)
        
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Mock dependencies
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        mocker.patch("routers.approvals.log_audit_event")
        
        # Mock the ApprovalRule model creation
        mock_approval_rule_class = mocker.patch("routers.approvals.ApprovalRuleModel")
        mock_approval_rule_class.return_value = mock_approval_rule
        
        response = client.post("/approvals/approval-rules", json=sample_approval_rule_data)
        
        assert response.status_code == 200
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_create_approval_rule_non_admin_forbidden(self, client, regular_user, sample_approval_rule_data, mocker):
        """Test that non-admin users cannot create approval rules."""
        mocker.patch("routers.approvals.get_current_user", return_value=regular_user)
        
        response = client.post("/approvals/approval-rules", json=sample_approval_rule_data)
        
        assert response.status_code == 403
    
    def test_create_approval_rule_invalid_approver(self, client, admin_user, sample_approval_rule_data, mocker):
        """Test approval rule creation with invalid approver ID."""
        mock_db = mocker.Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None  # Approver not found
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        
        response = client.post("/approvals/approval-rules", json=sample_approval_rule_data)
        
        assert response.status_code == 422
        assert "not found" in response.json()["detail"]
    
    def test_create_approval_rule_validation_error(self, client, admin_user, mocker):
        """Test approval rule creation with invalid data."""
        invalid_data = {
            "name": "",  # Empty name should fail validation
            "min_amount": -100,  # Negative amount should fail
            "approver_id": 2
        }
        
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        
        response = client.post("/approvals/approval-rules", json=invalid_data)
        
        assert response.status_code == 422


class TestListApprovalRules:
    """Test approval rule listing endpoint."""
    
    def test_list_approval_rules_success(self, client, regular_user, mocker):
        """Test successful approval rule listing."""
        mock_db = mocker.Mock(spec=Session)
        mock_rules = [
            mocker.Mock(id=1, name="Rule 1", is_active=True, approver_id=2),
            mocker.Mock(id=2, name="Rule 2", is_active=False, approver_id=3)
        ]
        
        mock_query = mock_db.query.return_value
        mock_query.order_by.return_value.all.return_value = mock_rules
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=regular_user)
        
        response = client.get("/approvals/approval-rules")
        
        assert response.status_code == 200
        mock_db.query.assert_called_once()
    
    def test_list_approval_rules_with_filters(self, client, regular_user, mocker):
        """Test approval rule listing with filters."""
        mock_db = mocker.Mock(spec=Session)
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = []
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=regular_user)
        
        response = client.get("/approvals/approval-rules?is_active=true&approver_id=2")
        
        assert response.status_code == 200
        # Verify filters were applied
        assert mock_query.filter.call_count == 2
    
    def test_list_approval_rules_with_pagination(self, client, regular_user, mocker):
        """Test approval rule listing with pagination."""
        mock_db = mocker.Mock(spec=Session)
        mock_query = mock_db.query.return_value
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=regular_user)
        
        response = client.get("/approvals/approval-rules?limit=10&offset=20")
        
        assert response.status_code == 200
        mock_query.offset.assert_called_once_with(20)
        mock_query.limit.assert_called_once_with(10)
    
    def test_list_approval_rules_viewer_forbidden(self, client, viewer_user, mocker):
        """Test that viewer users cannot list approval rules."""
        mocker.patch("routers.approvals.get_current_user", return_value=viewer_user)
        
        response = client.get("/approvals/approval-rules")
        
        assert response.status_code == 403


class TestUpdateApprovalRule:
    """Test approval rule update endpoint."""
    
    def test_update_approval_rule_success(self, client, admin_user, mocker):
        """Test successful approval rule update by admin."""
        mock_db = mocker.Mock(spec=Session)
        
        # Mock existing approval rule
        mock_rule = mocker.Mock()
        mock_rule.id = 1
        mock_rule.name = "Original Rule"
        mock_rule.approver_id = 2
        mock_rule.is_active = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_rule
        
        # Mock approver validation
        mock_user = mocker.Mock(spec=User)
        mock_user.id = 3
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_rule, mock_user]
        
        update_data = {
            "name": "Updated Rule",
            "approver_id": 3,
            "is_active": False
        }
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        mocker.patch("routers.approvals.log_audit_event")
        
        response = client.put("/approvals/approval-rules/1", json=update_data)
        
        assert response.status_code == 200
        mock_db.commit.assert_called_once()
    
    def test_update_approval_rule_not_found(self, client, admin_user, mocker):
        """Test updating non-existent approval rule."""
        mock_db = mocker.Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        
        response = client.put("/approvals/approval-rules/999", json={"name": "Updated"})
        
        assert response.status_code == 404
    
    def test_update_approval_rule_non_admin_forbidden(self, client, regular_user, mocker):
        """Test that non-admin users cannot update approval rules."""
        mocker.patch("routers.approvals.get_current_user", return_value=regular_user)
        
        response = client.put("/approvals/approval-rules/1", json={"name": "Updated"})
        
        assert response.status_code == 403
    
    def test_update_approval_rule_invalid_approver(self, client, admin_user, mocker):
        """Test updating approval rule with invalid approver ID."""
        mock_db = mocker.Mock(spec=Session)
        
        # Mock existing rule
        mock_rule = mocker.Mock()
        mock_rule.id = 1
        
        # Mock approver not found
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_rule, None]
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        
        response = client.put("/approvals/approval-rules/1", json={"approver_id": 999})
        
        assert response.status_code == 422


class TestDeleteApprovalRule:
    """Test approval rule deletion endpoint."""
    
    def test_delete_approval_rule_success(self, client, admin_user, mocker):
        """Test successful approval rule deletion by admin."""
        mock_db = mocker.Mock(spec=Session)
        
        # Mock existing approval rule
        mock_rule = mocker.Mock()
        mock_rule.id = 1
        mock_rule.name = "Test Rule"
        mock_rule.approver_id = 2
        mock_rule.approval_level = 1
        
        # Mock no active approvals using this rule
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_rule, None]
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        mocker.patch("routers.approvals.log_audit_event")
        
        response = client.delete("/approvals/approval-rules/1")
        
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]
        mock_db.delete.assert_called_once_with(mock_rule)
        mock_db.commit.assert_called_once()
    
    def test_delete_approval_rule_not_found(self, client, admin_user, mocker):
        """Test deleting non-existent approval rule."""
        mock_db = mocker.Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        
        response = client.delete("/approvals/approval-rules/999")
        
        assert response.status_code == 404
    
    def test_delete_approval_rule_with_active_approvals(self, client, admin_user, mocker):
        """Test deleting approval rule that has active approvals."""
        mock_db = mocker.Mock(spec=Session)
        
        # Mock existing rule
        mock_rule = mocker.Mock()
        mock_rule.id = 1
        
        # Mock active approval using this rule
        mock_active_approval = mocker.Mock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_rule, mock_active_approval]
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        
        response = client.delete("/approvals/approval-rules/1")
        
        assert response.status_code == 400
        assert "currently being used" in response.json()["detail"]
    
    def test_delete_approval_rule_non_admin_forbidden(self, client, regular_user, mocker):
        """Test that non-admin users cannot delete approval rules."""
        mocker.patch("routers.approvals.get_current_user", return_value=regular_user)
        
        response = client.delete("/approvals/approval-rules/1")
        
        assert response.status_code == 403


class TestApprovalRuleIntegration:
    """Integration tests for approval rule endpoints."""
    
    def test_full_approval_rule_lifecycle(self, client, admin_user, regular_user, sample_approval_rule_data, mocker):
        """Test complete CRUD lifecycle for approval rules."""
        mock_db = mocker.Mock(spec=Session)
        
        # Mock user lookup for creation
        mock_user = mocker.Mock(spec=User)
        mock_user.id = 2
        
        # Mock approval rule creation
        mock_rule = mocker.Mock()
        mock_rule.id = 1
        mock_rule.name = sample_approval_rule_data["name"]
        mock_rule.created_at = datetime.now(timezone.utc)
        mock_rule.updated_at = datetime.now(timezone.utc)
        
        # Setup mocks for different operations
        def mock_query_side_effect(*args):
            query_mock = mocker.Mock()
            if args[0] == User:
                query_mock.filter.return_value.first.return_value = mock_user
            else:  # ApprovalRule
                query_mock.filter.return_value.first.return_value = mock_rule
                query_mock.order_by.return_value.all.return_value = [mock_rule]
            return query_mock
        
        mock_db.query.side_effect = mock_query_side_effect
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.log_audit_event")
        mock_approval_rule_class = mocker.patch("routers.approvals.ApprovalRuleModel")
        mock_approval_rule_class.return_value = mock_rule
        
        # Test creation
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        create_response = client.post("/approvals/approval-rules", json=sample_approval_rule_data)
        assert create_response.status_code == 200
        
        # Test listing
        mocker.patch("routers.approvals.get_current_user", return_value=regular_user)
        list_response = client.get("/approvals/approval-rules")
        assert list_response.status_code == 200
        
        # Test update
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        update_response = client.put("/approvals/approval-rules/1", json={"name": "Updated Rule"})
        assert update_response.status_code == 200
        
        # Test deletion (mock no active approvals)
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_rule, None]
        delete_response = client.delete("/approvals/approval-rules/1")
        assert delete_response.status_code == 200
    
    def test_approval_rule_validation_edge_cases(self, client, admin_user, mocker):
        """Test edge cases in approval rule validation."""
        mock_db = mocker.Mock(spec=Session)
        mock_user = mocker.Mock(spec=User)
        mock_user.id = 2
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        mocker.patch("routers.approvals.get_db", return_value=mock_db)
        mocker.patch("routers.approvals.get_current_user", return_value=admin_user)
        
        # Test with max_amount less than min_amount
        invalid_data = {
            "name": "Invalid Rule",
            "min_amount": 1000.0,
            "max_amount": 500.0,  # Less than min_amount
            "approver_id": 2
        }
        
        response = client.post("/approvals/approval-rules", json=invalid_data)
        assert response.status_code == 422