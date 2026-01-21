"""
Integration tests for ApprovalRuleEngine with complete workflow scenarios
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from commercial.workflows.approvals.services.approval_rule_engine import ApprovalRuleEngine
from core.models.models_per_tenant import (
    User, Expense, ApprovalRule, ApprovalDelegate, ExpenseApproval
)
from core.schemas.approval import ApprovalStatus


@pytest.fixture
def complete_approval_setup(db_session: Session):
    """Set up a complete approval workflow scenario"""
    # Create users
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
        ),
        'backup_manager': User(
            email="backup@company.com",
            hashed_password="hashed",
            role="admin",
            first_name="Charlie",
            last_name="Backup"
        )
    }
    
    for user in users.values():
        db_session.add(user)
    db_session.commit()
    
    # Create comprehensive approval rules
    rules = [
        # Small expenses - team lead approval, auto-approve under $25
        ApprovalRule(
            name="Small Expenses",
            min_amount=0.0,
            max_amount=200.0,
            currency="USD",
            approval_level=1,
            approver_id=users['team_lead'].id,
            is_active=True,
            priority=1,
            auto_approve_below=25.0
        ),
        # Medium expenses - manager approval
        ApprovalRule(
            name="Medium Expenses",
            min_amount=200.01,
            max_amount=1000.0,
            currency="USD",
            approval_level=1,
            approver_id=users['manager'].id,
            is_active=True,
            priority=2
        ),
        # Large expenses - manager + director approval
        ApprovalRule(
            name="Large Expenses Level 1",
            min_amount=1000.01,
            max_amount=None,
            currency="USD",
            approval_level=1,
            approver_id=users['manager'].id,
            is_active=True,
            priority=3
        ),
        ApprovalRule(
            name="Large Expenses Level 2",
            min_amount=1000.01,
            max_amount=None,
            currency="USD",
            approval_level=2,
            approver_id=users['director'].id,
            is_active=True,
            priority=3
        ),
        # Special travel category - different approver
        ApprovalRule(
            name="Travel Expenses",
            min_amount=0.0,
            max_amount=500.0,
            category_filter='["Travel", "Transportation", "Accommodation"]',
            currency="USD",
            approval_level=1,
            approver_id=users['manager'].id,  # Manager handles all travel
            is_active=True,
            priority=10  # Higher priority than amount-based rules
        )
    ]
    
    for rule in rules:
        db_session.add(rule)
    db_session.commit()
    
    return users, rules


class TestApprovalRuleEngineIntegration:
    """Integration tests for complete approval workflows"""
    
    def test_small_expense_auto_approval(self, db_session: Session, complete_approval_setup):
        """Test auto-approval for small expenses"""
        users, rules = complete_approval_setup
        engine = ApprovalRuleEngine(db_session)
        
        # Create small expense under auto-approve threshold
        expense = Expense(
            amount=20.0,
            currency="USD",
            category="Office Supplies",
            status="draft",
            user_id=users['employee'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        # Check if should auto-approve
        assert engine.should_auto_approve(expense) == True
        
        # Get approval summary
        summary = engine.get_approval_summary(expense)
        assert summary['should_auto_approve'] == True
        assert summary['required_levels'] == [1]
        assert len(summary['approver_assignments']) == 1
        assert summary['approver_assignments'][0]['approver_email'] == "teamlead@company.com"
    
    def test_medium_expense_single_approval(self, db_session: Session, complete_approval_setup):
        """Test single-level approval for medium expenses"""
        users, rules = complete_approval_setup
        engine = ApprovalRuleEngine(db_session)
        
        # Create medium expense
        expense = Expense(
            amount=500.0,
            currency="USD",
            category="Equipment",
            status="pending_approval",
            user_id=users['employee'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        # Should not auto-approve
        assert engine.should_auto_approve(expense) == False
        
        # Should require single level approval
        levels = engine.get_required_approval_levels(expense)
        assert levels == [1]
        
        # Should assign to manager
        assignments = engine.assign_approvers(expense)
        assert len(assignments) == 1
        assert assignments[0][1].email == "manager@company.com"
        
        # Check approval summary
        summary = engine.get_approval_summary(expense)
        assert summary['next_approval_level'] == 1
        assert summary['is_fully_approved'] == False
    
    def test_large_expense_multi_level_approval(self, db_session: Session, complete_approval_setup):
        """Test multi-level approval for large expenses"""
        users, rules = complete_approval_setup
        engine = ApprovalRuleEngine(db_session)
        
        # Create large expense
        expense = Expense(
            amount=2500.0,
            currency="USD",
            category="Equipment",
            status="pending_approval",
            user_id=users['employee'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        # Should require two levels
        levels = engine.get_required_approval_levels(expense)
        assert levels == [1, 2]
        
        # Should assign both manager and director
        assignments = engine.assign_approvers(expense)
        assert len(assignments) == 2
        
        level_1_assignment = next((a for a in assignments if a[0] == 1), None)
        level_2_assignment = next((a for a in assignments if a[0] == 2), None)
        
        assert level_1_assignment[1].email == "manager@company.com"
        assert level_2_assignment[1].email == "director@company.com"
        
        # Initially should need level 1
        assert engine.get_next_approval_level(expense) == 1
        assert engine.is_fully_approved(expense) == False
        
        # Add level 1 approval
        approval_1 = ExpenseApproval(
            expense_id=expense.id,
            approver_id=users['manager'].id,
            status=ApprovalStatus.APPROVED,
            submitted_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc),
            approval_level=1,
            is_current_level=False
        )
        db_session.add(approval_1)
        db_session.commit()
        
        # Should now need level 2
        assert engine.get_next_approval_level(expense) == 2
        assert engine.is_fully_approved(expense) == False
        
        # Add level 2 approval
        approval_2 = ExpenseApproval(
            expense_id=expense.id,
            approver_id=users['director'].id,
            status=ApprovalStatus.APPROVED,
            submitted_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc),
            approval_level=2,
            is_current_level=True
        )
        db_session.add(approval_2)
        db_session.commit()
        
        # Should be fully approved
        assert engine.get_next_approval_level(expense) is None
        assert engine.is_fully_approved(expense) == True
    
    def test_travel_expense_category_priority(self, db_session: Session, complete_approval_setup):
        """Test that category-specific rules take priority"""
        users, rules = complete_approval_setup
        engine = ApprovalRuleEngine(db_session)
        
        # Create travel expense that would normally go to team lead (amount-based)
        # but should go to manager due to category rule priority
        expense = Expense(
            amount=150.0,  # Would normally go to team lead
            currency="USD",
            category="Travel",  # But travel goes to manager
            status="pending_approval",
            user_id=users['employee'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        # Should match travel rule due to higher priority
        matching_rules = engine.evaluate_expense(expense)
        travel_rule = next((r for r in matching_rules if r.name == "Travel Expenses"), None)
        assert travel_rule is not None
        
        # Should assign to manager (travel rule) not team lead (amount rule)
        assignments = engine.assign_approvers(expense)
        assert len(assignments) == 1
        assert assignments[0][1].email == "manager@company.com"
        assert assignments[0][2].name == "Travel Expenses"
    
    def test_delegation_workflow(self, db_session: Session, complete_approval_setup):
        """Test approval delegation in a complete workflow"""
        users, rules = complete_approval_setup
        engine = ApprovalRuleEngine(db_session)
        
        # Set up delegation from manager to backup manager
        now = datetime.now(timezone.utc)
        delegation = ApprovalDelegate(
            approver_id=users['manager'].id,
            delegate_id=users['backup_manager'].id,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=7),
            is_active=True
        )
        db_session.add(delegation)
        db_session.commit()
        
        # Create expense that would normally go to manager
        expense = Expense(
            amount=500.0,
            currency="USD",
            category="Equipment",
            status="pending_approval",
            user_id=users['employee'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        # Should assign to backup manager due to delegation
        assignments = engine.assign_approvers(expense)
        assert len(assignments) == 1
        assert assignments[0][1].email == "backup@company.com"
        
        # Approval summary should reflect delegation
        summary = engine.get_approval_summary(expense)
        assert summary['approver_assignments'][0]['approver_email'] == "backup@company.com"
    
    def test_rejected_expense_workflow(self, db_session: Session, complete_approval_setup):
        """Test workflow when expense is rejected"""
        users, rules = complete_approval_setup
        engine = ApprovalRuleEngine(db_session)
        
        # Create expense
        expense = Expense(
            amount=500.0,
            currency="USD",
            category="Equipment",
            status="pending_approval",
            user_id=users['employee'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        # Add rejection
        rejection = ExpenseApproval(
            expense_id=expense.id,
            approver_id=users['manager'].id,
            status=ApprovalStatus.REJECTED,
            rejection_reason="Insufficient justification",
            submitted_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc),
            approval_level=1,
            is_current_level=True
        )
        db_session.add(rejection)
        db_session.commit()
        
        # Should still need level 1 approval (rejection doesn't count as approval)
        assert engine.get_next_approval_level(expense) == 1
        assert engine.is_fully_approved(expense) == False
        
        # Summary should reflect rejection
        summary = engine.get_approval_summary(expense)
        assert summary['rejected_count'] == 1
        assert summary['approved_count'] == 0
    
    def test_rule_validation_comprehensive(self, db_session: Session, complete_approval_setup):
        """Test comprehensive rule validation"""
        users, rules = complete_approval_setup
        engine = ApprovalRuleEngine(db_session)
        
        # Add problematic rule with inactive approver
        inactive_user = User(
            email="inactive@company.com",
            hashed_password="hashed",
            role="admin",
            is_active=False  # Inactive user
        )
        db_session.add(inactive_user)
        db_session.commit()
        
        bad_rule = ApprovalRule(
            name="Bad Rule",
            min_amount=0.0,
            max_amount=100.0,
            currency="USD",
            approval_level=1,
            approver_id=inactive_user.id,  # Inactive approver
            is_active=True,
            priority=1
        )
        db_session.add(bad_rule)
        db_session.commit()
        
        # Validate rules
        issues = engine.validate_approval_rules()
        
        # Should find invalid approver issue
        invalid_approver_issues = [i for i in issues if i['type'] == 'invalid_approver']
        assert len(invalid_approver_issues) >= 1
        
        # Should find the bad rule
        bad_rule_issue = next((i for i in invalid_approver_issues if i['rule_id'] == bad_rule.id), None)
        assert bad_rule_issue is not None
        assert bad_rule_issue['severity'] == 'error'
    
    def test_currency_specific_rules(self, db_session: Session, complete_approval_setup):
        """Test that currency-specific rules work correctly"""
        users, rules = complete_approval_setup
        engine = ApprovalRuleEngine(db_session)
        
        # Add EUR-specific rule
        eur_rule = ApprovalRule(
            name="EUR Expenses",
            min_amount=0.0,
            max_amount=1000.0,
            currency="EUR",
            approval_level=1,
            approver_id=users['director'].id,
            is_active=True,
            priority=1
        )
        db_session.add(eur_rule)
        db_session.commit()
        
        # Create USD expense - should not match EUR rule
        usd_expense = Expense(
            amount=500.0,
            currency="USD",
            category="Equipment",
            status="pending_approval",
            user_id=users['employee'].id
        )
        db_session.add(usd_expense)
        db_session.commit()
        
        usd_assignments = engine.assign_approvers(usd_expense)
        assert usd_assignments[0][1].email == "manager@company.com"  # USD rule
        
        # Create EUR expense - should match EUR rule
        eur_expense = Expense(
            amount=500.0,
            currency="EUR",
            category="Equipment",
            status="pending_approval",
            user_id=users['employee'].id
        )
        db_session.add(eur_expense)
        db_session.commit()
        
        eur_assignments = engine.assign_approvers(eur_expense)
        assert eur_assignments[0][1].email == "director@company.com"  # EUR rule