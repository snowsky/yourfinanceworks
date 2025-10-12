"""
Configuration for approval workflow integration tests

This module contains configuration settings, fixtures, and utilities
shared across all approval workflow integration tests.
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Any
from unittest.mock import Mock, AsyncMock

from api.models.models_per_tenant import User, ApprovalRule, ApprovalDelegate
from api.services.notification_service import NotificationService


class ApprovalTestConfig:
    """Configuration class for approval integration tests"""
    
    # Test data constants
    DEFAULT_TENANT_ID = 1
    TEST_EXPENSE_CATEGORIES = ["Travel", "Office", "Equipment", "Software", "Training", "Marketing"]
    
    # Performance test thresholds
    PERFORMANCE_THRESHOLDS = {
        'rule_evaluation_max_time': 1.0,  # seconds
        'bulk_submission_max_time': 10.0,  # seconds
        'concurrent_approval_max_time': 15.0,  # seconds
        'delegation_resolution_max_time': 8.0,  # seconds
        'history_query_max_time': 3.0,  # seconds
        'memory_usage_max_mb': 150,  # MB
        'rule_evaluation_per_expense_max_ms': 50,  # milliseconds
        'bulk_submission_per_expense_max_ms': 50,  # milliseconds
        'history_query_per_expense_max_ms': 30  # milliseconds
    }
    
    # Test user roles and permissions
    USER_ROLES = {
        'employee': {'role': 'user', 'can_approve': False},
        'team_lead': {'role': 'admin', 'can_approve': True, 'max_amount': 1000.0},
        'manager': {'role': 'admin', 'can_approve': True, 'max_amount': 5000.0},
        'director': {'role': 'admin', 'can_approve': True, 'max_amount': 20000.0},
        'cfo': {'role': 'admin', 'can_approve': True, 'max_amount': None}
    }
    
    # Approval rule templates
    APPROVAL_RULE_TEMPLATES = {
        'small_expenses': {
            'name': 'Small Expense Approval',
            'min_amount': 0.0,
            'max_amount': 500.0,
            'approval_level': 1,
            'auto_approve_below': 50.0
        },
        'medium_expenses': {
            'name': 'Medium Expense Approval',
            'min_amount': 500.01,
            'max_amount': 2000.0,
            'approval_level': 2
        },
        'large_expenses': {
            'name': 'Large Expense Approval',
            'min_amount': 2000.01,
            'max_amount': 10000.0,
            'approval_level': 3
        },
        'very_large_expenses': {
            'name': 'Very Large Expense Approval',
            'min_amount': 10000.01,
            'max_amount': None,
            'approval_level': 4
        }
    }
    
    @classmethod
    def get_performance_threshold(cls, metric: str) -> float:
        """Get performance threshold for a specific metric"""
        return cls.PERFORMANCE_THRESHOLDS.get(metric, 0.0)
    
    @classmethod
    def get_user_role_config(cls, role: str) -> Dict[str, Any]:
        """Get configuration for a specific user role"""
        return cls.USER_ROLES.get(role, {})
    
    @classmethod
    def get_approval_rule_template(cls, template: str) -> Dict[str, Any]:
        """Get approval rule template"""
        return cls.APPROVAL_RULE_TEMPLATES.get(template, {})


class ApprovalTestDataFactory:
    """Factory class for creating test data"""
    
    @staticmethod
    def create_test_users(db_session, count: int = 5) -> Dict[str, User]:
        """Create test users with different roles"""
        users = {}
        role_names = list(ApprovalTestConfig.USER_ROLES.keys())
        
        for i in range(count):
            role_name = role_names[i % len(role_names)]
            role_config = ApprovalTestConfig.get_user_role_config(role_name)
            
            user = User(
                email=f"{role_name}{i}@testcompany.com",
                hashed_password="hashed_password",
                role=role_config.get('role', 'user'),
                first_name=role_name.title(),
                last_name=f"User{i}",
                tenant_id=ApprovalTestConfig.DEFAULT_TENANT_ID,
                is_active=True
            )
            
            users[f"{role_name}{i}"] = user
            db_session.add(user)
        
        db_session.commit()
        
        # Refresh to get IDs
        for user in users.values():
            db_session.refresh(user)
        
        return users
    
    @staticmethod
    def create_approval_rules(db_session, users: Dict[str, User]) -> List[ApprovalRule]:
        """Create standard set of approval rules"""
        rules = []
        templates = ApprovalTestConfig.APPROVAL_RULE_TEMPLATES
        
        # Map templates to users
        template_user_mapping = {
            'small_expenses': 'team_lead0',
            'medium_expenses': 'manager0', 
            'large_expenses': 'director0',
            'very_large_expenses': 'cfo0'
        }
        
        for template_name, template_config in templates.items():
            user_key = template_user_mapping.get(template_name)
            if user_key and user_key in users:
                rule = ApprovalRule(
                    name=template_config['name'],
                    min_amount=template_config['min_amount'],
                    max_amount=template_config['max_amount'],
                    approval_level=template_config['approval_level'],
                    approver_id=users[user_key].id,
                    auto_approve_below=template_config.get('auto_approve_below'),
                    is_active=True,
                    priority=template_config['approval_level'],
                    tenant_id=ApprovalTestConfig.DEFAULT_TENANT_ID
                )
                rules.append(rule)
                db_session.add(rule)
        
        db_session.commit()
        return rules
    
    @staticmethod
    def create_test_expenses(db_session, user: User, count: int = 10) -> List:
        """Create test expenses with varying amounts and categories"""
        from api.models.models_per_tenant import Expense
        
        expenses = []
        categories = ApprovalTestConfig.TEST_EXPENSE_CATEGORIES
        
        for i in range(count):
            amount = Decimal(f'{(i + 1) * 100 + 50}.00')  # $150, $250, $350, etc.
            category = categories[i % len(categories)]
            
            expense = Expense(
                amount=amount,
                notes=f"Test expense {i+1} - {category}",
                category=category,
                status="draft",
                user_id=user.id,
                tenant_id=ApprovalTestConfig.DEFAULT_TENANT_ID,
                created_at=datetime.now(timezone.utc) - timedelta(days=i)
            )
            
            expenses.append(expense)
            db_session.add(expense)
        
        db_session.commit()
        
        # Refresh to get IDs
        for expense in expenses:
            db_session.refresh(expense)
        
        return expenses
    
    @staticmethod
    def create_approval_delegations(db_session, users: Dict[str, User]) -> List[ApprovalDelegate]:
        """Create test approval delegations"""
        delegations = []
        
        # Create some sample delegations
        delegation_configs = [
            {
                'approver': 'team_lead0',
                'delegate': 'team_lead1',
                'days_from_now': 0,
                'duration_days': 7
            },
            {
                'approver': 'manager0',
                'delegate': 'manager1',
                'days_from_now': -2,  # Started 2 days ago
                'duration_days': 10
            }
        ]
        
        for config in delegation_configs:
            approver_key = config['approver']
            delegate_key = config['delegate']
            
            if approver_key in users and delegate_key in users:
                start_date = (datetime.now(timezone.utc) + 
                            timedelta(days=config['days_from_now'])).date()
                end_date = (start_date + 
                          timedelta(days=config['duration_days']))
                
                delegation = ApprovalDelegate(
                    approver_id=users[approver_key].id,
                    delegate_id=users[delegate_key].id,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True,
                    tenant_id=ApprovalTestConfig.DEFAULT_TENANT_ID
                )
                
                delegations.append(delegation)
                db_session.add(delegation)
        
        db_session.commit()
        return delegations


class ApprovalTestMocks:
    """Mock objects for approval workflow testing"""
    
    @staticmethod
    def create_notification_service_mock() -> Mock:
        """Create mock notification service"""
        mock_service = Mock(spec=NotificationService)
        
        # Mock async methods
        mock_service.send_approval_notification = AsyncMock()
        mock_service.send_approval_decision_notification = AsyncMock()
        mock_service.send_approval_reminder = AsyncMock()
        mock_service.send_approval_escalation = AsyncMock()
        
        # Mock sync methods
        mock_service.get_notification_preferences = Mock(return_value={
            'email_enabled': True,
            'in_app_enabled': True,
            'reminder_frequency': 'daily'
        })
        
        return mock_service
    
    @staticmethod
    def create_approval_service_mock() -> Mock:
        """Create mock approval service"""
        from api.services.approval_service import ApprovalService
        
        mock_service = Mock(spec=ApprovalService)
        
        # Configure common return values
        mock_service.submit_for_approval = Mock()
        mock_service.approve_expense = Mock()
        mock_service.reject_expense = Mock()
        mock_service.get_pending_approvals = Mock(return_value=[])
        mock_service.delegate_approval = Mock()
        
        return mock_service


class ApprovalTestAssertions:
    """Custom assertions for approval workflow testing"""
    
    @staticmethod
    def assert_approval_workflow_state(approval, expected_status, expected_approver_id=None):
        """Assert approval workflow state"""
        assert approval is not None, "Approval should not be None"
        assert approval.status == expected_status, f"Expected status {expected_status}, got {approval.status}"
        
        if expected_approver_id is not None:
            assert approval.approver_id == expected_approver_id, \
                f"Expected approver_id {expected_approver_id}, got {approval.approver_id}"
    
    @staticmethod
    def assert_expense_status(expense, expected_status):
        """Assert expense status"""
        assert expense is not None, "Expense should not be None"
        assert expense.status == expected_status, \
            f"Expected expense status {expected_status}, got {expense.status}"
    
    @staticmethod
    def assert_performance_threshold(actual_time, threshold_key):
        """Assert performance meets threshold"""
        threshold = ApprovalTestConfig.get_performance_threshold(threshold_key)
        assert actual_time <= threshold, \
            f"Performance threshold exceeded: {actual_time:.4f}s > {threshold}s for {threshold_key}"
    
    @staticmethod
    def assert_notification_called(mock_notification_service, method_name, call_count=1):
        """Assert notification service method was called"""
        method = getattr(mock_notification_service, method_name)
        assert method.call_count == call_count, \
            f"Expected {method_name} to be called {call_count} times, got {method.call_count}"
    
    @staticmethod
    def assert_approval_history_complete(db_session, expense_id, expected_levels):
        """Assert approval history is complete for all levels"""
        from api.models.models_per_tenant import ExpenseApproval
        
        approvals = db_session.query(ExpenseApproval).filter(
            ExpenseApproval.expense_id == expense_id
        ).order_by(ExpenseApproval.approval_level).all()
        
        assert len(approvals) == len(expected_levels), \
            f"Expected {len(expected_levels)} approval levels, got {len(approvals)}"
        
        for i, approval in enumerate(approvals):
            expected_level = expected_levels[i]
            assert approval.approval_level == expected_level, \
                f"Expected approval level {expected_level}, got {approval.approval_level}"


# Pytest fixtures that can be imported by test modules
@pytest.fixture
def approval_test_config():
    """Provide approval test configuration"""
    return ApprovalTestConfig()


@pytest.fixture
def approval_test_factory():
    """Provide approval test data factory"""
    return ApprovalTestDataFactory()


@pytest.fixture
def approval_test_mocks():
    """Provide approval test mocks"""
    return ApprovalTestMocks()


@pytest.fixture
def approval_test_assertions():
    """Provide approval test assertions"""
    return ApprovalTestAssertions()


@pytest.fixture
def standard_approval_setup(db_session, approval_test_factory):
    """Create standard approval test setup"""
    users = approval_test_factory.create_test_users(db_session, count=8)
    rules = approval_test_factory.create_approval_rules(db_session, users)
    delegations = approval_test_factory.create_approval_delegations(db_session, users)
    
    return {
        'users': users,
        'rules': rules,
        'delegations': delegations,
        'db_session': db_session
    }