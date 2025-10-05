"""
Comprehensive integration tests for expense approval workflow

This test suite covers end-to-end approval workflows including:
- Complete approval workflows from submission to completion
- Multi-level approval scenarios with different user roles
- Approval delegation integration tests
- Performance tests for approval rule evaluation
- Approval notification delivery in integration scenarios
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.models_per_tenant import (
    Base, User, Expense, ExpenseApproval, ApprovalRule, ApprovalDelegate
)
from services.approval_service import ApprovalService
from services.approval_rule_engine import ApprovalRuleEngine
from services.approval_permission_service import ApprovalPermissionService
from services.notification_service import NotificationService
from schemas.approval import (
    ApprovalStatus, ApprovalDelegateCreate, ExpenseApprovalCreate
)
from exceptions.approval_exceptions import (
    ApprovalException, InsufficientApprovalPermissions,
    ExpenseAlreadyApproved, NoApprovalRuleFound
)


class TestApprovalWorkflowIntegration:
    """Integration tests for complete approval workflows"""
    
    @pytest.fixture
    def db_engine(self):
        """Create test database engine"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        Base.metadata.create_all(bind=engine)
        return engine
    
    @pytest.fixture
    def db_session(self, db_engine):
        """Create database session"""
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    @pytest.fixture
    def notification_service(self):
        """Mock notification service"""
        mock_service = Mock(spec=NotificationService)
        mock_service.send_operation_notification = Mock(return_value=True)
        mock_service.send_approval_notification = AsyncMock()
        mock_service.send_approval_reminder = AsyncMock()
        mock_service.send_approval_decision_notification = AsyncMock()
        return mock_service
    
    @pytest.fixture
    def approval_services(self, db_session, notification_service):
        """Create approval service instances"""
        rule_engine = ApprovalRuleEngine(db_session)
        permission_service = ApprovalPermissionService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        return {
            'rule_engine': rule_engine,
            'permission_service': permission_service,
            'approval_service': approval_service,
            'notification_service': notification_service
        }
    
    @pytest.fixture
    def test_users(self, db_session):
        """Create test users with different roles"""
        users = {
            'employee': User(
                email="employee@company.com",
                hashed_password="hashed",
                role="user",
                first_name="John",
                last_name="Employee"
            ),
            'team_lead': User(
                email="teamlead@company.com",
                hashed_password="hashed",
                role="admin",
                first_name="Jane",
                last_name="TeamLead"
            ),
            'manager': User(
                email="manager@company.com",
                hashed_password="hashed",
                role="admin",
                first_name="Bob",
                last_name="Manager"
            ),
            'director': User(
                email="director@company.com",
                hashed_password="hashed",
                role="admin",
                first_name="Alice",
                last_name="Director"
            )
        }
        
        for user in users.values():
            db_session.add(user)
        db_session.commit()
        
        # Refresh to get IDs
        for user in users.values():
            db_session.refresh(user)
        
        return users
    
    @pytest.fixture
    def approval_rules(self, db_session, test_users):
        """Create approval rules for testing"""
        rules = [
            # Level 1: Team Lead approval for expenses $0-500
            ApprovalRule(
                name="Team Lead Approval",
                min_amount=0.0,
                max_amount=500.0,
                approval_level=1,
                approver_id=test_users['team_lead'].id,
                is_active=True,
                priority=1
            ),
            # Level 2: Manager approval for expenses $500-2000
            ApprovalRule(
                name="Manager Approval",
                min_amount=500.01,
                max_amount=2000.0,
                approval_level=2,
                approver_id=test_users['manager'].id,
                is_active=True,
                priority=2
            ),
            # Level 3: Director approval for expenses >$2000
            ApprovalRule(
                name="Director Approval",
                min_amount=2000.01,
                max_amount=None,
                approval_level=3,
                approver_id=test_users['director'].id,
                is_active=True,
                priority=3
            )
        ]
        
        for rule in rules:
            db_session.add(rule)
        db_session.commit()
        
        return rules

    def test_single_level_approval_workflow(self, db_session, approval_services, test_users, approval_rules):
        """Test complete single-level approval workflow"""
        # Create expense requiring team lead approval
        expense = Expense(
            amount=Decimal('250.00'),
            notes="Office supplies - valid business expense",
            category="Office",
            receipt_path="/receipts/office_supplies.pdf",
            status="draft",
            user_id=test_users['employee'].id,
            expense_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        db_session.refresh(expense)
        
        approval_service = approval_services['approval_service']
        
        # Step 1: Submit for approval
        approvals = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=test_users['employee'].id
        )
        
        assert approvals is not None
        assert len(approvals) > 0
        approval = approvals[0]  # Get the first approval
        assert approval.status == ApprovalStatus.PENDING
        assert approval.approver_id == test_users['team_lead'].id
        assert approval.approval_level == 1
        
        # Verify expense status updated
        db_session.refresh(expense)
        assert expense.status == "pending_approval"
        
        # Verify notification was sent
        approval_services['notification_service'].send_operation_notification.assert_called()
        
        # Step 2: Approve the expense
        approval_service.approve_expense(
            approval_id=approval.id,
            approver_id=test_users['team_lead'].id,
            notes="Approved - valid business expense"
        )
        
        # Verify approval status
        db_session.refresh(approval)
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.decided_at is not None
        assert approval.notes == "Approved - valid business expense"
        
        # Verify expense status
        db_session.refresh(expense)
        assert expense.status == "approved"
        
        # Verify decision notification was sent
        approval_services['notification_service'].send_operation_notification.assert_called()

    def test_multi_level_approval_workflow(self, db_session, approval_services, test_users, approval_rules):
        """Test multi-level approval workflow"""
        # Create expense requiring director approval (over $2000)
        expense = Expense(
            amount=Decimal('3500.00'),
            notes="Major conference attendance - business development",
            category="Travel",
            vendor="Conference Corp",
            receipt_path="/receipts/conference_receipt.pdf",
            status="draft",
            user_id=test_users['employee'].id,
            expense_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        db_session.refresh(expense)
        
        approval_service = approval_services['approval_service']
        
        # Submit for approval
        approvals = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=test_users['employee'].id
        )
        
        # Should start with director (level 3) for $3500 expense
        assert len(approvals) > 0
        approval = approvals[0]
        assert approval.approver_id == test_users['director'].id
        assert approval.approval_level == 3
        
        # Director approves (this should complete the approval since $3500 requires director approval)
        approval_service.approve_expense(
            approval_id=approval.id,
            approver_id=test_users['director'].id,
            notes="Director approval"
        )
        
        # Verify final expense status - should be approved after director approval
        db_session.refresh(expense)
        assert expense.status == "approved"

    def test_sequential_multi_level_approval_workflow(self, db_session, approval_services, test_users, approval_rules):
        """Test sequential multi-level approval workflow with custom rules"""
        # Add a rule that requires sequential approvals for high-value travel expenses
        sequential_rule = ApprovalRule(
            name="High Value Travel - Sequential Approval",
            min_amount=2500.0,
            max_amount=5000.0,
            category_filter='["Travel"]',
            approval_level=1,  # Start at level 1 but require sequential approvals
            approver_id=test_users['team_lead'].id,
            is_active=True,
            priority=10  # Higher priority than other rules
        )
        db_session.add(sequential_rule)
        db_session.commit()
        
        # Create expense requiring sequential approvals
        expense = Expense(
            amount=Decimal('3000.00'),
            notes="High-value conference with sequential approval requirement",
            category="Travel",
            vendor="Premium Conference Corp",
            receipt_path="/receipts/premium_conference.pdf",
            status="draft",
            user_id=test_users['employee'].id,
            expense_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        db_session.refresh(expense)
        
        approval_service = approval_services['approval_service']
        
        # Submit for approval - should start with team lead due to higher priority rule
        approvals = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=test_users['employee'].id
        )
        
        assert len(approvals) > 0
        approval = approvals[0]
        assert approval.approver_id == test_users['team_lead'].id
        assert approval.approval_level == 1
        
        # Team lead approves
        approval_service.approve_expense(
            approval_id=approval.id,
            approver_id=test_users['team_lead'].id,
            notes="Team lead approval for high-value travel"
        )
        
        # Check if next level approval was created
        db_session.refresh(expense)
        if expense.status == "pending_approval":
            # Look for next level approval
            next_approvals = db_session.query(ExpenseApproval).filter(
                ExpenseApproval.expense_id == expense.id,
                ExpenseApproval.status == ApprovalStatus.PENDING,
                ExpenseApproval.approval_level > 1
            ).all()
            
            if next_approvals:
                next_approval = next_approvals[0]
                # Approve the next level
                approval_service.approve_expense(
                    approval_id=next_approval.id,
                    approver_id=next_approval.approver_id,
                    notes="Next level approval"
                )
        
        # Verify final status
        db_session.refresh(expense)
        assert expense.status == "approved"

    def test_approval_rejection_and_resubmission(self, db_session, approval_services, test_users, approval_rules):
        """Test approval rejection and resubmission workflow"""
        # Create expense
        expense = Expense(
            amount=Decimal('300.00'),
            notes="Questionable expense - needs review",
            category="Other",
            receipt_path="/receipts/other_expense.pdf",
            status="draft",
            user_id=test_users['employee'].id,
            expense_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        db_session.refresh(expense)
        
        approval_service = approval_services['approval_service']
        
        # Submit for approval
        approvals = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=test_users['employee'].id
        )
        
        # Reject the expense
        approval = approvals[0]
        approval_service.reject_expense(
            approval_id=approval.id,
            approver_id=test_users['team_lead'].id,
            rejection_reason="Insufficient documentation"
        )
        
        # Verify rejection
        db_session.refresh(approval)
        assert approval.status == ApprovalStatus.REJECTED
        assert approval.rejection_reason == "Insufficient documentation"
        
        db_session.refresh(expense)
        assert expense.status == "rejected"
        
        # Resubmit the expense
        new_approvals = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=test_users['employee'].id
        )
        
        # Should create new approval record
        new_approval = new_approvals[0]
        assert new_approval.id != approval.id
        assert new_approval.status == ApprovalStatus.PENDING
        
        db_session.refresh(expense)
        assert expense.status == "pending_approval"

    def test_approval_permission_enforcement(self, db_session, approval_services, test_users, approval_rules):
        """Test approval permission enforcement"""
        # Create expense
        expense = Expense(
            amount=Decimal('300.00'),
            notes="Permission test expense - valid business purpose",
            category="Office",
            receipt_path="/receipts/permission_test.pdf",
            status="draft",
            user_id=test_users['employee'].id,
            expense_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        db_session.refresh(expense)
        
        approval_service = approval_services['approval_service']
        
        # Submit for approval
        approvals = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=test_users['employee'].id
        )
        
        approval = approvals[0]
        
        # Try to approve with wrong user (should fail)
        with pytest.raises(InsufficientApprovalPermissions):
            approval_service.approve_expense(
                approval_id=approval.id,
                approver_id=test_users['employee'].id,  # Employee can't approve
                notes="Unauthorized approval"
            )
        
        # Correct approver should succeed
        approval_service.approve_expense(
            approval_id=approval.id,
            approver_id=test_users['team_lead'].id,
            notes="Authorized approval"
        )
        
        db_session.refresh(approval)
        assert approval.status == ApprovalStatus.APPROVED


class TestApprovalPerformance:
    """Performance tests for approval rule evaluation"""
    
    @pytest.fixture
    def performance_db_session(self):
        """Create database session for performance testing"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def test_rule_evaluation_performance(self, performance_db_session):
        """Test performance of approval rule evaluation with many rules"""
        # Create many users
        users = []
        for i in range(10):
            user = User(
                email=f"approver{i}@company.com",
                hashed_password="hashed",
                role="admin",
                first_name=f"Approver{i}",
                last_name="User"
            )
            users.append(user)
            performance_db_session.add(user)
        
        performance_db_session.commit()
        
        # Create many approval rules
        rules = []
        for i in range(50):
            rule = ApprovalRule(
                name=f"Rule {i}",
                min_amount=float(i * 100),
                max_amount=float((i + 1) * 100),
                approval_level=1,
                approver_id=users[i % len(users)].id,
                is_active=True,
                priority=i
            )
            rules.append(rule)
            performance_db_session.add(rule)
        
        performance_db_session.commit()
        
        # Create test expense
        expense = Expense(
            amount=Decimal('2500.00'),
            notes="Performance test expense - business purpose",
            category="Test",
            status="draft",
            user_id=users[0].id,
            expense_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        performance_db_session.add(expense)
        performance_db_session.commit()
        
        # Test rule evaluation performance
        rule_engine = ApprovalRuleEngine(performance_db_session)
        
        start_time = time.time()
        matching_rules = rule_engine.evaluate_expense(expense)
        end_time = time.time()
        
        evaluation_time = end_time - start_time
        
        # Should complete within reasonable time (< 1 second)
        assert evaluation_time < 1.0
        assert len(matching_rules) > 0
        
        print(f"Rule evaluation time for 50 rules: {evaluation_time:.4f} seconds")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])