"""Tests for approval workflow models and schemas"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from api.models.models_per_tenant import (
    User, Expense, ExpenseApproval, ApprovalRule, ApprovalDelegate
)
from api.schemas.approval import (
    ApprovalRuleCreate, ExpenseApprovalCreate, ApprovalDelegateCreate,
    ApprovalStatus
)


def test_approval_rule_model(db_session: Session):
    """Test ApprovalRule model creation and relationships"""
    # Create a user to be the approver
    user = User(
        email="approver@test.com",
        hashed_password="hashed",
        role="admin"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an approval rule
    rule = ApprovalRule(
        name="High Value Approval",
        min_amount=1000.0,
        max_amount=5000.0,
        currency="USD",
        approval_level=1,
        approver_id=user.id,
        is_active=True,
        priority=1
    )
    db_session.add(rule)
    db_session.commit()
    
    # Verify the rule was created
    assert rule.id is not None
    assert rule.name == "High Value Approval"
    assert rule.approver.email == "approver@test.com"


def test_expense_approval_model(db_session: Session):
    """Test ExpenseApproval model creation and relationships"""
    # Create users
    submitter = User(
        email="submitter@test.com",
        hashed_password="hashed",
        role="user"
    )
    approver = User(
        email="approver@test.com",
        hashed_password="hashed",
        role="admin"
    )
    db_session.add_all([submitter, approver])
    db_session.commit()
    
    # Create an expense
    expense = Expense(
        amount=1500.0,
        currency="USD",
        category="Travel",
        status="pending_approval",
        user_id=submitter.id
    )
    db_session.add(expense)
    db_session.commit()
    
    # Create an approval
    approval = ExpenseApproval(
        expense_id=expense.id,
        approver_id=approver.id,
        status="pending",
        submitted_at=datetime.now(timezone.utc),
        approval_level=1,
        is_current_level=True
    )
    db_session.add(approval)
    db_session.commit()
    
    # Verify relationships
    assert approval.expense.amount == 1500.0
    assert approval.approver.email == "approver@test.com"
    assert len(expense.approvals) == 1


def test_approval_delegate_model(db_session: Session):
    """Test ApprovalDelegate model creation and relationships"""
    # Create users
    approver = User(
        email="approver@test.com",
        hashed_password="hashed",
        role="admin"
    )
    delegate = User(
        email="delegate@test.com",
        hashed_password="hashed",
        role="admin"
    )
    db_session.add_all([approver, delegate])
    db_session.commit()
    
    # Create delegation
    delegation = ApprovalDelegate(
        approver_id=approver.id,
        delegate_id=delegate.id,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        is_active=True
    )
    db_session.add(delegation)
    db_session.commit()
    
    # Verify relationships
    assert delegation.approver.email == "approver@test.com"
    assert delegation.delegate.email == "delegate@test.com"


def test_approval_rule_schema_validation():
    """Test ApprovalRule schema validation"""
    # Valid rule
    rule_data = {
        "name": "Test Rule",
        "min_amount": 100.0,
        "max_amount": 1000.0,
        "currency": "USD",
        "approval_level": 1,
        "approver_id": 1,
        "is_active": True,
        "priority": 0
    }
    rule = ApprovalRuleCreate(**rule_data)
    assert rule.name == "Test Rule"
    
    # Invalid rule - max_amount <= min_amount
    with pytest.raises(ValueError):
        ApprovalRuleCreate(
            name="Invalid Rule",
            min_amount=1000.0,
            max_amount=500.0,  # Less than min_amount
            approver_id=1
        )


def test_approval_delegate_schema_validation():
    """Test ApprovalDelegate schema validation"""
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=7)
    
    # Valid delegation
    delegation_data = {
        "approver_id": 1,
        "delegate_id": 2,
        "start_date": start_date,
        "end_date": end_date,
        "is_active": True
    }
    delegation = ApprovalDelegateCreate(**delegation_data)
    assert delegation.approver_id == 1
    assert delegation.delegate_id == 2
    
    # Invalid - same approver and delegate
    with pytest.raises(ValueError):
        ApprovalDelegateCreate(
            approver_id=1,
            delegate_id=1,  # Same as approver
            start_date=start_date,
            end_date=end_date
        )
    
    # Invalid - end_date before start_date
    with pytest.raises(ValueError):
        ApprovalDelegateCreate(
            approver_id=1,
            delegate_id=2,
            start_date=end_date,
            end_date=start_date  # Before start_date
        )


def test_expense_approval_status_enum():
    """Test ApprovalStatus enum values"""
    assert ApprovalStatus.PENDING == "pending"
    assert ApprovalStatus.APPROVED == "approved"
    assert ApprovalStatus.REJECTED == "rejected"
    
    # Test enum in schema
    approval_data = {
        "expense_id": 1,
        "approver_id": 1,
        "status": ApprovalStatus.APPROVED
    }
    # This should not raise an error
    from api.schemas.approval import ExpenseApprovalBase
    approval = ExpenseApprovalBase(**approval_data)