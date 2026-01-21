"""
Tests for the ApprovalRuleEngine service
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
def approval_engine(db_session: Session):
    """Create an ApprovalRuleEngine instance with test database"""
    return ApprovalRuleEngine(db_session)


@pytest.fixture
def test_users(db_session: Session):
    """Create test users for approval scenarios"""
    users = {
        'submitter': User(
            email="submitter@test.com",
            hashed_password="hashed",
            role="user",
            first_name="John",
            last_name="Submitter"
        ),
        'manager': User(
            email="manager@test.com",
            hashed_password="hashed",
            role="admin",
            first_name="Jane",
            last_name="Manager"
        ),
        'director': User(
            email="director@test.com",
            hashed_password="hashed",
            role="admin",
            first_name="Bob",
            last_name="Director"
        ),
        'delegate': User(
            email="delegate@test.com",
            hashed_password="hashed",
            role="admin",
            first_name="Alice",
            last_name="Delegate"
        )
    }
    
    for user in users.values():
        db_session.add(user)
    db_session.commit()
    
    return users


@pytest.fixture
def test_approval_rules(db_session: Session, test_users):
    """Create test approval rules"""
    rules = [
        ApprovalRule(
            name="Low Amount Approval",
            min_amount=0.0,
            max_amount=500.0,
            currency="USD",
            approval_level=1,
            approver_id=test_users['manager'].id,
            is_active=True,
            priority=1,
            auto_approve_below=100.0
        ),
        ApprovalRule(
            name="Medium Amount Approval",
            min_amount=500.01,
            max_amount=2000.0,
            currency="USD",
            approval_level=1,
            approver_id=test_users['manager'].id,
            is_active=True,
            priority=2
        ),
        ApprovalRule(
            name="High Amount Level 1",
            min_amount=2000.01,
            max_amount=None,
            currency="USD",
            approval_level=1,
            approver_id=test_users['manager'].id,
            is_active=True,
            priority=3
        ),
        ApprovalRule(
            name="High Amount Level 2",
            min_amount=2000.01,
            max_amount=None,
            currency="USD",
            approval_level=2,
            approver_id=test_users['director'].id,
            is_active=True,
            priority=3
        ),
        ApprovalRule(
            name="Travel Category Rule",
            min_amount=0.0,
            max_amount=1000.0,
            category_filter='["Travel", "Transportation"]',
            currency="USD",
            approval_level=1,
            approver_id=test_users['manager'].id,
            is_active=True,
            priority=5
        )
    ]
    
    for rule in rules:
        db_session.add(rule)
    db_session.commit()
    
    return rules


class TestApprovalRuleEngine:
    """Test cases for ApprovalRuleEngine"""
    
    def test_evaluate_expense_basic_amount_matching(self, approval_engine, test_users, test_approval_rules, db_session):
        """Test basic expense evaluation based on amount thresholds"""
        # Low amount expense
        low_expense = Expense(
            amount=250.0,
            currency="USD",
            category="Office Supplies",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(low_expense)
        db_session.commit()
        
        matching_rules = approval_engine.evaluate_expense(low_expense)
        assert len(matching_rules) == 1
        assert matching_rules[0].name == "Low Amount Approval"
        
        # Medium amount expense
        medium_expense = Expense(
            amount=1000.0,
            currency="USD",
            category="Equipment",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(medium_expense)
        db_session.commit()
        
        matching_rules = approval_engine.evaluate_expense(medium_expense)
        assert len(matching_rules) == 1
        assert matching_rules[0].name == "Medium Amount Approval"
        
        # High amount expense (should match both levels)
        high_expense = Expense(
            amount=5000.0,
            currency="USD",
            category="Equipment",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(high_expense)
        db_session.commit()
        
        matching_rules = approval_engine.evaluate_expense(high_expense)
        assert len(matching_rules) == 2
        rule_names = [rule.name for rule in matching_rules]
        assert "High Amount Level 1" in rule_names
        assert "High Amount Level 2" in rule_names
    
    def test_evaluate_expense_category_filtering(self, approval_engine, test_users, test_approval_rules, db_session):
        """Test expense evaluation with category filtering"""
        # Travel expense that matches category rule
        travel_expense = Expense(
            amount=500.0,
            currency="USD",
            category="Travel",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(travel_expense)
        db_session.commit()
        
        matching_rules = approval_engine.evaluate_expense(travel_expense)
        # Should match both the travel category rule and the low amount rule
        assert len(matching_rules) >= 1
        rule_names = [rule.name for rule in matching_rules]
        assert "Travel Category Rule" in rule_names
        
        # Non-travel expense
        office_expense = Expense(
            amount=500.0,
            currency="USD",
            category="Office Supplies",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(office_expense)
        db_session.commit()
        
        matching_rules = approval_engine.evaluate_expense(office_expense)
        rule_names = [rule.name for rule in matching_rules]
        assert "Travel Category Rule" not in rule_names
    
    def test_evaluate_expense_currency_matching(self, approval_engine, test_users, db_session):
        """Test that rules only match expenses with the same currency"""
        # Create EUR rule
        eur_rule = ApprovalRule(
            name="EUR Rule",
            min_amount=0.0,
            max_amount=1000.0,
            currency="EUR",
            approval_level=1,
            approver_id=test_users['manager'].id,
            is_active=True,
            priority=1
        )
        db_session.add(eur_rule)
        db_session.commit()
        
        # USD expense should not match EUR rule
        usd_expense = Expense(
            amount=500.0,
            currency="USD",
            category="Office",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(usd_expense)
        db_session.commit()
        
        matching_rules = approval_engine.evaluate_expense(usd_expense)
        rule_names = [rule.name for rule in matching_rules]
        assert "EUR Rule" not in rule_names
        
        # EUR expense should match EUR rule
        eur_expense = Expense(
            amount=500.0,
            currency="EUR",
            category="Office",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(eur_expense)
        db_session.commit()
        
        matching_rules = approval_engine.evaluate_expense(eur_expense)
        rule_names = [rule.name for rule in matching_rules]
        assert "EUR Rule" in rule_names
    
    def test_get_required_approval_levels(self, approval_engine, test_users, test_approval_rules, db_session):
        """Test getting required approval levels for expenses"""
        # Low amount - only level 1
        low_expense = Expense(
            amount=250.0,
            currency="USD",
            category="Office",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(low_expense)
        db_session.commit()
        
        levels = approval_engine.get_required_approval_levels(low_expense)
        assert levels == [1]
        
        # High amount - levels 1 and 2
        high_expense = Expense(
            amount=5000.0,
            currency="USD",
            category="Equipment",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(high_expense)
        db_session.commit()
        
        levels = approval_engine.get_required_approval_levels(high_expense)
        assert levels == [1, 2]
    
    def test_assign_approvers(self, approval_engine, test_users, test_approval_rules, db_session):
        """Test approver assignment based on rules"""
        expense = Expense(
            amount=5000.0,
            currency="USD",
            category="Equipment",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        assignments = approval_engine.assign_approvers(expense)
        assert len(assignments) == 2
        
        # Check level 1 assignment
        level_1_assignment = next((a for a in assignments if a[0] == 1), None)
        assert level_1_assignment is not None
        assert level_1_assignment[1].email == "manager@test.com"
        
        # Check level 2 assignment
        level_2_assignment = next((a for a in assignments if a[0] == 2), None)
        assert level_2_assignment is not None
        assert level_2_assignment[1].email == "director@test.com"
    
    def test_approver_delegation(self, approval_engine, test_users, test_approval_rules, db_session):
        """Test that delegation is properly handled in approver assignment"""
        # Create delegation from manager to delegate
        now = datetime.now(timezone.utc)
        delegation = ApprovalDelegate(
            approver_id=test_users['manager'].id,
            delegate_id=test_users['delegate'].id,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=7),
            is_active=True
        )
        db_session.add(delegation)
        db_session.commit()
        
        expense = Expense(
            amount=250.0,
            currency="USD",
            category="Office",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        assignments = approval_engine.assign_approvers(expense)
        assert len(assignments) == 1
        # Should assign to delegate, not original manager
        assert assignments[0][1].email == "delegate@test.com"
    
    def test_should_auto_approve(self, approval_engine, test_users, test_approval_rules, db_session):
        """Test auto-approval logic"""
        # Expense below auto-approve threshold
        auto_expense = Expense(
            amount=50.0,
            currency="USD",
            category="Office",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(auto_expense)
        db_session.commit()
        
        assert approval_engine.should_auto_approve(auto_expense) == True
        
        # Expense above auto-approve threshold
        manual_expense = Expense(
            amount=200.0,
            currency="USD",
            category="Office",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(manual_expense)
        db_session.commit()
        
        assert approval_engine.should_auto_approve(manual_expense) == False
    
    def test_get_next_approval_level(self, approval_engine, test_users, test_approval_rules, db_session):
        """Test getting the next required approval level"""
        expense = Expense(
            amount=5000.0,
            currency="USD",
            category="Equipment",
            status="pending_approval",
            user_id=test_users['submitter'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        # No approvals yet - should need level 1
        next_level = approval_engine.get_next_approval_level(expense)
        assert next_level == 1
        
        # Add level 1 approval
        approval_1 = ExpenseApproval(
            expense_id=expense.id,
            approver_id=test_users['manager'].id,
            status=ApprovalStatus.APPROVED,
            submitted_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc),
            approval_level=1,
            is_current_level=False
        )
        db_session.add(approval_1)
        db_session.commit()
        
        # Should now need level 2
        next_level = approval_engine.get_next_approval_level(expense)
        assert next_level == 2
        
        # Add level 2 approval
        approval_2 = ExpenseApproval(
            expense_id=expense.id,
            approver_id=test_users['director'].id,
            status=ApprovalStatus.APPROVED,
            submitted_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc),
            approval_level=2,
            is_current_level=True
        )
        db_session.add(approval_2)
        db_session.commit()
        
        # Should be fully approved
        next_level = approval_engine.get_next_approval_level(expense)
        assert next_level is None
    
    def test_is_fully_approved(self, approval_engine, test_users, test_approval_rules, db_session):
        """Test checking if expense is fully approved"""
        expense = Expense(
            amount=5000.0,
            currency="USD",
            category="Equipment",
            status="pending_approval",
            user_id=test_users['submitter'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        # Not approved yet
        assert approval_engine.is_fully_approved(expense) == False
        
        # Add all required approvals
        approval_1 = ExpenseApproval(
            expense_id=expense.id,
            approver_id=test_users['manager'].id,
            status=ApprovalStatus.APPROVED,
            submitted_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc),
            approval_level=1,
            is_current_level=False
        )
        approval_2 = ExpenseApproval(
            expense_id=expense.id,
            approver_id=test_users['director'].id,
            status=ApprovalStatus.APPROVED,
            submitted_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc),
            approval_level=2,
            is_current_level=True
        )
        db_session.add_all([approval_1, approval_2])
        db_session.commit()
        
        # Should be fully approved
        assert approval_engine.is_fully_approved(expense) == True
    
    def test_get_approval_summary(self, approval_engine, test_users, test_approval_rules, db_session):
        """Test getting comprehensive approval summary"""
        expense = Expense(
            amount=1500.0,
            currency="USD",
            category="Equipment",
            status="pending_approval",
            user_id=test_users['submitter'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        summary = approval_engine.get_approval_summary(expense)
        
        assert summary['expense_id'] == expense.id
        assert summary['expense_amount'] == 1500.0
        assert summary['expense_currency'] == "USD"
        assert summary['expense_category'] == "Equipment"
        assert summary['matching_rules_count'] >= 1
        assert summary['required_levels'] == [1]
        assert len(summary['approver_assignments']) >= 1
        assert summary['next_approval_level'] == 1
        assert summary['should_auto_approve'] == False
        assert summary['is_fully_approved'] == False
        assert summary['existing_approvals_count'] == 0
    
    def test_validate_approval_rules(self, approval_engine, test_users, db_session):
        """Test approval rule validation"""
        # Create overlapping rules
        rule1 = ApprovalRule(
            name="Overlapping Rule 1",
            min_amount=100.0,
            max_amount=1000.0,
            currency="USD",
            approval_level=1,
            approver_id=test_users['manager'].id,
            is_active=True,
            priority=1
        )
        rule2 = ApprovalRule(
            name="Overlapping Rule 2",
            min_amount=500.0,
            max_amount=1500.0,
            currency="USD",
            approval_level=1,
            approver_id=test_users['director'].id,
            is_active=True,
            priority=1  # Same priority as rule1
        )
        
        db_session.add_all([rule1, rule2])
        db_session.commit()
        
        issues = approval_engine.validate_approval_rules()
        
        # Should find overlapping rules issue
        overlap_issues = [issue for issue in issues if issue['type'] == 'overlapping_rules']
        assert len(overlap_issues) >= 1
    
    def test_inactive_rules_ignored(self, approval_engine, test_users, db_session):
        """Test that inactive rules are ignored in evaluation"""
        # Create inactive rule
        inactive_rule = ApprovalRule(
            name="Inactive Rule",
            min_amount=0.0,
            max_amount=1000.0,
            currency="USD",
            approval_level=1,
            approver_id=test_users['manager'].id,
            is_active=False,  # Inactive
            priority=1
        )
        db_session.add(inactive_rule)
        db_session.commit()
        
        expense = Expense(
            amount=500.0,
            currency="USD",
            category="Office",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        matching_rules = approval_engine.evaluate_expense(expense)
        rule_names = [rule.name for rule in matching_rules]
        assert "Inactive Rule" not in rule_names
    
    def test_priority_ordering(self, approval_engine, test_users, db_session):
        """Test that rules are ordered by priority correctly"""
        # Create rules with different priorities
        low_priority = ApprovalRule(
            name="Low Priority",
            min_amount=0.0,
            max_amount=1000.0,
            currency="USD",
            approval_level=1,
            approver_id=test_users['manager'].id,
            is_active=True,
            priority=1
        )
        high_priority = ApprovalRule(
            name="High Priority",
            min_amount=0.0,
            max_amount=1000.0,
            currency="USD",
            approval_level=1,
            approver_id=test_users['director'].id,
            is_active=True,
            priority=10
        )
        
        db_session.add_all([low_priority, high_priority])
        db_session.commit()
        
        expense = Expense(
            amount=500.0,
            currency="USD",
            category="Office",
            status="draft",
            user_id=test_users['submitter'].id
        )
        db_session.add(expense)
        db_session.commit()
        
        assignments = approval_engine.assign_approvers(expense)
        # Should use high priority rule (director as approver)
        assert assignments[0][1].email == "director@test.com"
        assert assignments[0][2].name == "High Priority"