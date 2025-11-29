"""
Integration tests for approval workflow edge cases and error scenarios

This test suite covers:
- Complex multi-level approval scenarios
- Edge cases in approval rule matching
- Error handling in approval workflows
- Boundary conditions and validation
- Recovery from failure scenarios
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models.models_per_tenant import (
    Base, User, Expense, ExpenseApproval, ApprovalRule, ApprovalDelegate
)
from commercial.workflows.approvals.services.approval_service import ApprovalService
from commercial.workflows.approvals.services.approval_rule_engine import ApprovalRuleEngine
from core.schemas.approval import ApprovalStatus
from core.exceptions.approval_exceptions import (
    ApprovalException, InsufficientApprovalPermissions,
    ExpenseAlreadyApproved, NoApprovalRuleFound, ApprovalLevelMismatch
)


class TestApprovalWorkflowEdgeCases:
    """Integration tests for approval workflow edge cases"""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session"""
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
    
    @pytest.fixture
    def complex_approval_setup(self, db_session):
        """Set up complex approval scenario with multiple rules and users"""
        # Create users with different roles
        users = {
            'employee1': User(
                email="emp1@company.com", hashed_password="hashed", role="user",
                first_name="John", last_name="Employee1", 
            ),
            'employee2': User(
                email="emp2@company.com", hashed_password="hashed", role="user",
                first_name="Jane", last_name="Employee2", 
            ),
            'team_lead1': User(
                email="tl1@company.com", hashed_password="hashed", role="admin",
                first_name="Bob", last_name="TeamLead1", 
            ),
            'team_lead2': User(
                email="tl2@company.com", hashed_password="hashed", role="admin",
                first_name="Alice", last_name="TeamLead2", 
            ),
            'manager': User(
                email="mgr@company.com", hashed_password="hashed", role="admin",
                first_name="Charlie", last_name="Manager", 
            ),
            'director': User(
                email="dir@company.com", hashed_password="hashed", role="admin",
                first_name="Diana", last_name="Director", 
            ),
            'cfo': User(
                email="cfo@company.com", hashed_password="hashed", role="admin",
                first_name="Frank", last_name="CFO", 
            )
        }
        
        for user in users.values():
            db_session.add(user)
        db_session.commit()
        
        # Refresh to get IDs
        for user in users.values():
            db_session.refresh(user)
        
        # Create complex approval rules
        rules = [
            # Category-specific rules
            ApprovalRule(
                name="Travel Expenses - Team Lead",
                min_amount=0.0, max_amount=1000.0,
                category_filter='["Travel"]',
                approval_level=1,
                approver_id=users['team_lead1'].id,
                is_active=True, priority=1, 
            ),
            ApprovalRule(
                name="Travel Expenses - Manager",
                min_amount=1000.01, max_amount=5000.0,
                category_filter='["Travel"]',
                approval_level=2,
                approver_id=users['manager'].id,
                is_active=True, priority=2, 
            ),
            ApprovalRule(
                name="Travel Expenses - Director",
                min_amount=5000.01, max_amount=None,
                category_filter='["Travel"]',
                approval_level=3,
                approver_id=users['director'].id,
                is_active=True, priority=3, 
            ),
            # Office expenses
            ApprovalRule(
                name="Office Expenses - Team Lead",
                min_amount=0.0, max_amount=500.0,
                category_filter='["Office"]',
                approval_level=1,
                approver_id=users['team_lead2'].id,
                is_active=True, priority=1, 
            ),
            # High-value expenses requiring CFO approval
            ApprovalRule(
                name="CFO Approval Required",
                min_amount=10000.01, max_amount=None,
                approval_level=4,
                approver_id=users['cfo'].id,
                is_active=True, priority=10, 
            ),
            # Overlapping rules for testing priority
            ApprovalRule(
                name="General Manager Approval",
                min_amount=2000.0, max_amount=10000.0,
                approval_level=2,
                approver_id=users['manager'].id,
                is_active=True, priority=5, 
            )
        ]
        
        for rule in rules:
            db_session.add(rule)
        db_session.commit()
        
        return {'users': users, 'rules': rules}

    def test_no_matching_approval_rule(self, db_session, complex_approval_setup):
        """Test handling when no approval rule matches an expense"""
        setup = complex_approval_setup
        
        # Create expense with category that has no rules
        expense = Expense(
            amount=Decimal('100.00'),
            notes="Unmatched category expense",
            category="Entertainment",  # No rules for this category
            status="draft",
            user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
            
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(db_session, mock_notification)
        
        # Should raise NoApprovalRuleFound exception
        with pytest.raises(NoApprovalRuleFound):
            approval_service.submit_for_approval(
                expense_id=expense.id,
                submitter_id=setup['users']['employee1'].id
            )

    def test_overlapping_approval_rules_priority(self, db_session, complex_approval_setup):
        """Test that approval rules are applied based on priority"""
        setup = complex_approval_setup
        
        # Create expense that matches multiple rules
        expense = Expense(
            amount=Decimal('3000.00'),
            notes="Overlapping rules test",
            category="General",  # Matches general rules
            status="draft",
            user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
            
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        
        rule_engine = ApprovalRuleEngine(db_session)
        matching_rules = rule_engine.evaluate_expense(expense)
        
        # Should return rules ordered by priority
        assert len(matching_rules) > 0
        
        # Verify priority ordering
        for i in range(1, len(matching_rules)):
            assert matching_rules[i-1].priority <= matching_rules[i].priority

    def test_four_level_approval_workflow(self, db_session, complex_approval_setup):
        """Test complex four-level approval workflow"""
        setup = complex_approval_setup
        
        # Create very high-value expense requiring CFO approval
        expense = Expense(
            amount=Decimal('15000.00'),
            notes="Major equipment purchase",
            category="Equipment",
            status="draft",
            user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
            
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(db_session, mock_notification)
        
        # Submit for approval
        approval = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=setup['users']['employee1'].id
        )
        
        # Should start with level 1 (general manager approval)
        assert approval.approval_level == 2  # Based on amount, starts at manager level
        assert approval.approver_id == setup['users']['manager'].id
        
        # Manager approves
        approval_service.approve_expense(
            approval_id=approval.id,
            approver_id=setup['users']['manager'].id,
            notes="Manager approval"
        )
        
        # Should escalate to director (level 3)
        level_3_approvals = db_session.query(ExpenseApproval).filter(
            ExpenseApproval.expense_id == expense.id,
            ExpenseApproval.approval_level == 3,
            ExpenseApproval.status == ApprovalStatus.PENDING
        ).all()
        
        assert len(level_3_approvals) == 1
        level_3_approval = level_3_approvals[0]
        
        # Director approves
        approval_service.approve_expense(
            approval_id=level_3_approval.id,
            approver_id=setup['users']['director'].id,
            notes="Director approval"
        )
        
        # Should escalate to CFO (level 4)
        level_4_approvals = db_session.query(ExpenseApproval).filter(
            ExpenseApproval.expense_id == expense.id,
            ExpenseApproval.approval_level == 4,
            ExpenseApproval.status == ApprovalStatus.PENDING
        ).all()
        
        assert len(level_4_approvals) == 1
        level_4_approval = level_4_approvals[0]
        assert level_4_approval.approver_id == setup['users']['cfo'].id
        
        # CFO approves
        approval_service.approve_expense(
            approval_id=level_4_approval.id,
            approver_id=setup['users']['cfo'].id,
            notes="CFO final approval"
        )
        
        # Verify final status
        db_session.refresh(expense)
        assert expense.status == "approved"

    def test_approval_with_expired_delegation(self, db_session, complex_approval_setup):
        """Test approval workflow with expired delegation"""
        setup = complex_approval_setup
        
        # Create expired delegation
        expired_delegation = ApprovalDelegate(
            approver_id=setup['users']['team_lead1'].id,
            delegate_id=setup['users']['team_lead2'].id,
            start_date=(datetime.now(timezone.utc) - timedelta(days=10)).date(),
            end_date=(datetime.now(timezone.utc) - timedelta(days=1)).date(),  # Expired
            is_active=True,
            
        )
        db_session.add(expired_delegation)
        db_session.commit()
        
        # Create expense
        expense = Expense(
            amount=Decimal('800.00'),
            notes="Expired delegation test",
            category="Travel",
            vendor="Travel Corp",
            status="draft",
            user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
            
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(db_session, mock_notification)
        
        # Submit for approval
        approval = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=setup['users']['employee1'].id
        )
        
        # Should be assigned to original approver, not expired delegate
        assert approval.approver_id == setup['users']['team_lead1'].id

    def test_approval_rule_deactivation_during_workflow(self, db_session, complex_approval_setup):
        """Test handling when approval rule is deactivated during workflow"""
        setup = complex_approval_setup
        
        # Create expense
        expense = Expense(
            amount=Decimal('300.00'),
            notes="Rule deactivation test",
            category="Office",
            status="draft",
            user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
            
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(db_session, mock_notification)
        
        # Submit for approval
        approval = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=setup['users']['employee1'].id
        )
        
        # Deactivate the approval rule
        office_rule = db_session.query(ApprovalRule).filter(
            ApprovalRule.category_filter.contains("Office")
        ).first()
        office_rule.is_active = False
        db_session.commit()
        
        # Approval should still proceed with existing assignment
        approval_service.approve_expense(
            approval_id=approval.id,
            approver_id=setup['users']['team_lead2'].id,
            notes="Approval despite rule deactivation"
        )
        
        db_session.refresh(approval)
        assert approval.status == ApprovalStatus.APPROVED

    def test_approver_user_deletion_during_workflow(self, db_session, complex_approval_setup):
        """Test handling when approver user is deleted during workflow"""
        setup = complex_approval_setup
        
        # Create expense
        expense = Expense(
            amount=Decimal('400.00'),
            notes="Approver deletion test",
            category="Office",
            status="draft",
            user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
            
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(db_session, mock_notification)
        
        # Submit for approval
        approval = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=setup['users']['employee1'].id
        )
        
        original_approver_id = approval.approver_id
        
        # Simulate approver deletion (soft delete by setting inactive)
        approver = db_session.query(User).filter(User.id == original_approver_id).first()
        approver.is_active = False
        db_session.commit()
        
        # Attempting to approve should raise permission error
        with pytest.raises(InsufficientApprovalPermissions):
            approval_service.approve_expense(
                approval_id=approval.id,
                approver_id=original_approver_id,
                notes="Approval by inactive user"
            )

    def test_circular_delegation_prevention(self, db_session, complex_approval_setup):
        """Test prevention of circular delegation chains"""
        setup = complex_approval_setup
        
        # Create circular delegation chain: A -> B -> C -> A
        delegations = [
            ApprovalDelegate(
                approver_id=setup['users']['team_lead1'].id,
                delegate_id=setup['users']['team_lead2'].id,
                start_date=datetime.now(timezone.utc).date(),
                end_date=(datetime.now(timezone.utc) + timedelta(days=7)).date(),
                is_active=True, 
            ),
            ApprovalDelegate(
                approver_id=setup['users']['team_lead2'].id,
                delegate_id=setup['users']['manager'].id,
                start_date=datetime.now(timezone.utc).date(),
                end_date=(datetime.now(timezone.utc) + timedelta(days=7)).date(),
                is_active=True, 
            ),
            ApprovalDelegate(
                approver_id=setup['users']['manager'].id,
                delegate_id=setup['users']['team_lead1'].id,  # Circular!
                start_date=datetime.now(timezone.utc).date(),
                end_date=(datetime.now(timezone.utc) + timedelta(days=7)).date(),
                is_active=True, 
            )
        ]
        
        for delegation in delegations:
            db_session.add(delegation)
        db_session.commit()
        
        # Create expense
        expense = Expense(
            amount=Decimal('600.00'),
            notes="Circular delegation test",
            category="Travel",
            vendor="Travel Corp",
            status="draft",
            user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
            
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(db_session, mock_notification)
        
        # Submit for approval - should handle circular delegation gracefully
        approval = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=setup['users']['employee1'].id
        )
        
        # Should assign to someone in the chain (breaking the circle)
        assert approval.approver_id is not None
        assert approval.status == ApprovalStatus.PENDING

    def test_concurrent_multi_level_approvals(self, db_session, complex_approval_setup):
        """Test concurrent multi-level approval scenarios"""
        setup = complex_approval_setup
        
        # Create multiple expenses requiring different approval levels
        expenses = []
        for i, amount in enumerate([800, 1500, 3000, 8000]):
            expense = Expense(
                amount=Decimal(f'{amount}.00'),
                notes=f"Concurrent test expense {i+1}",
                category="Travel",
            vendor="Travel Corp",
                status="draft",
                user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
                
                created_at=datetime.now(timezone.utc)
            )
            expenses.append(expense)
            db_session.add(expense)
        
        db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(db_session, mock_notification)
        
        # Submit all expenses for approval
        approvals = []
        for expense in expenses:
            approval = approval_service.submit_for_approval(
                expense_id=expense.id,
                submitter_id=setup['users']['employee1'].id
            )
            approvals.append(approval)
        
        # Verify different approval levels assigned
        approval_levels = [approval.approval_level for approval in approvals]
        assert len(set(approval_levels)) > 1  # Should have different levels
        
        # Process approvals concurrently
        for approval in approvals:
            if approval.approval_level == 1:
                approval_service.approve_expense(
                    approval_id=approval.id,
                    approver_id=setup['users']['team_lead1'].id,
                    notes="Level 1 approval"
                )
            elif approval.approval_level == 2:
                approval_service.approve_expense(
                    approval_id=approval.id,
                    approver_id=setup['users']['manager'].id,
                    notes="Level 2 approval"
                )
        
        # Verify all processed correctly
        for expense in expenses:
            db_session.refresh(expense)
            # Status should be either approved or pending next level
            assert expense.status in ["approved", "pending_approval"]

    def test_approval_with_zero_amount_expense(self, db_session, complex_approval_setup):
        """Test approval workflow with zero amount expense"""
        setup = complex_approval_setup
        
        # Create zero amount expense
        expense = Expense(
            amount=Decimal('0.00'),
            notes="Zero amount expense",
            category="Office",
            status="draft",
            user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
            
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(db_session, mock_notification)
        
        # Should handle zero amount gracefully
        approval = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=setup['users']['employee1'].id
        )
        
        assert approval is not None
        assert approval.status == ApprovalStatus.PENDING

    def test_approval_with_negative_amount_expense(self, db_session, complex_approval_setup):
        """Test approval workflow with negative amount expense"""
        setup = complex_approval_setup
        
        # Create negative amount expense (refund scenario)
        expense = Expense(
            amount=Decimal('-100.00'),
            notes="Refund expense",
            category="Office",
            status="draft",
            user_id=setup['users']['employee1'].id,
            expense_date=datetime.now(timezone.utc),
            
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(expense)
        db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(db_session, mock_notification)
        
        # Should handle negative amount appropriately
        approval = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=setup['users']['employee1'].id
        )
        
        assert approval is not None
        assert approval.status == ApprovalStatus.PENDING


class TestApprovalWorkflowRecovery:
    """Tests for approval workflow recovery from failure scenarios"""
    
    @pytest.fixture
    def recovery_db_session(self):
        """Create database session for recovery testing"""
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
    
    def test_recovery_from_notification_failure(self, recovery_db_session):
        """Test recovery when notification service fails"""
        # Create test data
        user = User(
            email="test@company.com", hashed_password="hashed", role="admin",
            first_name="Test", last_name="User", 
        )
        recovery_db_session.add(user)
        recovery_db_session.commit()
        
        rule = ApprovalRule(
            name="Test Rule", min_amount=0.0, max_amount=1000.0,
            approval_level=1, approver_id=user.id,
            is_active=True, priority=1, 
        )
        recovery_db_session.add(rule)
        recovery_db_session.commit()
        
        expense = Expense(
            amount=Decimal('500.00'), notes="Recovery test",
            category="Test", status="draft", user_id=user.id,
            expense_date=datetime.now(timezone.utc),
             created_at=datetime.now(timezone.utc)
        )
        recovery_db_session.add(expense)
        recovery_db_session.commit()
        
        # Mock notification service to fail
        mock_notification = Mock()
        mock_notification.send_approval_notification = Mock(side_effect=Exception("Notification failed"))
        
        approval_service = ApprovalService(recovery_db_session, mock_notification)
        
        # Submission should succeed despite notification failure
        approval = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=user.id
        )
        
        # Approval should be created successfully
        assert approval is not None
        assert approval.status == ApprovalStatus.PENDING
        
        # Expense status should be updated
        recovery_db_session.refresh(expense)
        assert expense.status == "pending_approval"

    def test_recovery_from_database_constraint_violation(self, recovery_db_session):
        """Test recovery from database constraint violations"""
        # Create test data
        user = User(
            email="constraint@company.com", hashed_password="hashed", role="admin",
            first_name="Constraint", last_name="Test", 
        )
        recovery_db_session.add(user)
        recovery_db_session.commit()
        
        expense = Expense(
            amount=Decimal('300.00'), notes="Constraint test",
            category="Test", status="draft", user_id=user.id,
            expense_date=datetime.now(timezone.utc),
             created_at=datetime.now(timezone.utc)
        )
        recovery_db_session.add(expense)
        recovery_db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(recovery_db_session, mock_notification)
        
        # Try to submit expense with no matching rules
        with pytest.raises(NoApprovalRuleFound):
            approval_service.submit_for_approval(
                expense_id=expense.id,
                submitter_id=user.id
            )
        
        # Expense status should remain unchanged
        recovery_db_session.refresh(expense)
        assert expense.status == "draft"

    def test_partial_approval_workflow_recovery(self, recovery_db_session):
        """Test recovery from partial approval workflow completion"""
        # Create test data
        users = []
        for i in range(3):
            user = User(
                email=f"user{i}@company.com", hashed_password="hashed", role="admin",
                first_name=f"User{i}", last_name="Test", 
            )
            users.append(user)
            recovery_db_session.add(user)
        recovery_db_session.commit()
        
        # Create multi-level rules
        rules = [
            ApprovalRule(
                name="Level 1", min_amount=0.0, max_amount=1000.0,
                approval_level=1, approver_id=users[0].id,
                is_active=True, priority=1, 
            ),
            ApprovalRule(
                name="Level 2", min_amount=1000.01, max_amount=5000.0,
                approval_level=2, approver_id=users[1].id,
                is_active=True, priority=2, 
            ),
            ApprovalRule(
                name="Level 3", min_amount=5000.01, max_amount=None,
                approval_level=3, approver_id=users[2].id,
                is_active=True, priority=3, 
            )
        ]
        
        for rule in rules:
            recovery_db_session.add(rule)
        recovery_db_session.commit()
        
        # Create high-value expense
        expense = Expense(
            amount=Decimal('6000.00'), notes="Recovery test",
            category="Test", status="draft", user_id=users[0].id,
            expense_date=datetime.now(timezone.utc),
             created_at=datetime.now(timezone.utc)
        )
        recovery_db_session.add(expense)
        recovery_db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(recovery_db_session, mock_notification)
        
        # Submit and partially approve
        approval = approval_service.submit_for_approval(
            expense_id=expense.id,
            submitter_id=users[0].id
        )
        
        # First level approval
        approval_service.approve_expense(
            approval_id=approval.id,
            approver_id=users[0].id,
            notes="Level 1 approved"
        )
        
        # Verify second level was created
        level_2_approvals = recovery_db_session.query(ExpenseApproval).filter(
            ExpenseApproval.expense_id == expense.id,
            ExpenseApproval.approval_level == 2,
            ExpenseApproval.status == ApprovalStatus.PENDING
        ).all()
        
        assert len(level_2_approvals) == 1
        
        # Simulate system restart by creating new service instance
        new_approval_service = ApprovalService(recovery_db_session, mock_notification)
        
        # Continue with second level approval
        level_2_approval = level_2_approvals[0]
        new_approval_service.approve_expense(
            approval_id=level_2_approval.id,
            approver_id=users[1].id,
            notes="Level 2 approved after recovery"
        )
        
        # Should create third level
        level_3_approvals = recovery_db_session.query(ExpenseApproval).filter(
            ExpenseApproval.expense_id == expense.id,
            ExpenseApproval.approval_level == 3,
            ExpenseApproval.status == ApprovalStatus.PENDING
        ).all()
        
        assert len(level_3_approvals) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])