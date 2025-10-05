"""
Approval Rule Engine Service

This service handles the evaluation of approval rules for expenses and determines
which approvers should be assigned based on configured rules.
"""

import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.models_per_tenant import (
    Expense, ApprovalRule, User, ApprovalDelegate, ExpenseApproval
)
from schemas.approval import ApprovalStatus


class ApprovalRuleEngine:
    """
    Engine for evaluating approval rules and determining expense approval workflows.
    
    This class handles:
    - Rule evaluation based on expense amount and category
    - Multi-level approval workflow determination
    - Approver assignment with delegation support
    - Auto-approval logic for qualifying expenses
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def evaluate_expense(self, expense: Expense) -> List[ApprovalRule]:
        """
        Evaluate an expense against all active approval rules.
        
        Args:
            expense: The expense to evaluate
            
        Returns:
            List of matching approval rules, ordered by priority and approval level
        """
        # Get all active approval rules
        rules = self.db.query(ApprovalRule).filter(
            ApprovalRule.is_active == True
        ).order_by(
            ApprovalRule.priority.desc(),  # Higher priority first
            ApprovalRule.approval_level.asc()  # Lower levels first
        ).all()
        
        matching_rules = []
        
        for rule in rules:
            if self._rule_matches_expense(rule, expense):
                matching_rules.append(rule)
        
        return matching_rules
    
    def _rule_matches_expense(self, rule: ApprovalRule, expense: Expense) -> bool:
        """
        Check if a specific rule matches the given expense.
        
        Args:
            rule: The approval rule to check
            expense: The expense to match against
            
        Returns:
            True if the rule matches the expense, False otherwise
        """
        # Check currency match
        if rule.currency != expense.currency:
            return False
        
        # Check amount thresholds
        if rule.min_amount is not None and expense.amount < rule.min_amount:
            return False
        
        if rule.max_amount is not None and expense.amount > rule.max_amount:
            return False
        
        # Check category filter
        if rule.category_filter:
            try:
                allowed_categories = json.loads(rule.category_filter)
                if isinstance(allowed_categories, list) and expense.category not in allowed_categories:
                    return False
            except (json.JSONDecodeError, TypeError):
                # If category_filter is not valid JSON, treat as single category
                if rule.category_filter != expense.category:
                    return False
        
        return True
    
    def get_required_approval_levels(self, expense: Expense) -> List[int]:
        """
        Determine the approval levels required for an expense.
        
        Args:
            expense: The expense to evaluate
            
        Returns:
            List of approval levels required, in order
        """
        matching_rules = self.evaluate_expense(expense)
        
        if not matching_rules:
            return []
        
        # Get unique approval levels from matching rules
        levels = sorted(set(rule.approval_level for rule in matching_rules))
        return levels
    
    def assign_approvers(self, expense: Expense, rules: Optional[List[ApprovalRule]] = None) -> List[Tuple[int, User, ApprovalRule]]:
        """
        Assign approvers for an expense based on matching rules.
        
        Args:
            expense: The expense to assign approvers for
            rules: Optional pre-evaluated rules (if None, will evaluate)
            
        Returns:
            List of tuples containing (approval_level, approver_user, approval_rule)
        """
        if rules is None:
            rules = self.evaluate_expense(expense)
        
        if not rules:
            return []
        
        approver_assignments = []
        
        # Group rules by approval level
        rules_by_level = {}
        for rule in rules:
            level = rule.approval_level
            if level not in rules_by_level:
                rules_by_level[level] = []
            rules_by_level[level].append(rule)
        
        # For each level, assign the highest priority rule's approver
        for level in sorted(rules_by_level.keys()):
            level_rules = rules_by_level[level]
            # Sort by priority (highest first)
            level_rules.sort(key=lambda r: r.priority, reverse=True)
            
            # Use the highest priority rule for this level
            selected_rule = level_rules[0]
            
            # Get the actual approver (considering delegation)
            approver = self._get_effective_approver(selected_rule.approver_id)
            
            if approver:
                approver_assignments.append((level, approver, selected_rule))
        
        return approver_assignments
    
    def _get_effective_approver(self, approver_id: int) -> Optional[User]:
        """
        Get the effective approver, considering active delegations.
        
        Args:
            approver_id: ID of the original approver
            
        Returns:
            The effective approver (delegate if active delegation exists, otherwise original)
        """
        now = datetime.now(timezone.utc)
        
        # Check for active delegation
        delegation = self.db.query(ApprovalDelegate).filter(
            and_(
                ApprovalDelegate.approver_id == approver_id,
                ApprovalDelegate.is_active == True,
                ApprovalDelegate.start_date <= now,
                ApprovalDelegate.end_date >= now
            )
        ).first()
        
        if delegation:
            # Return the delegate
            return self.db.query(User).filter(User.id == delegation.delegate_id).first()
        else:
            # Return the original approver
            return self.db.query(User).filter(User.id == approver_id).first()
    
    def should_auto_approve(self, expense: Expense) -> bool:
        """
        Determine if an expense should be automatically approved.
        
        Args:
            expense: The expense to check
            
        Returns:
            True if the expense should be auto-approved, False otherwise
        """
        matching_rules = self.evaluate_expense(expense)
        
        for rule in matching_rules:
            if (rule.auto_approve_below is not None and 
                expense.amount <= rule.auto_approve_below):
                return True
        
        return False
    
    def get_next_approval_level(self, expense: Expense) -> Optional[int]:
        """
        Get the next approval level required for an expense.
        
        Args:
            expense: The expense to check
            
        Returns:
            The next approval level needed, or None if no more approvals needed
        """
        # Get all approval levels required
        required_levels = self.get_required_approval_levels(expense)
        
        if not required_levels:
            return None
        
        # Get existing approvals for this expense
        existing_approvals = self.db.query(ExpenseApproval).filter(
            and_(
                ExpenseApproval.expense_id == expense.id,
                ExpenseApproval.status == ApprovalStatus.APPROVED
            )
        ).all()
        
        # Get approved levels
        approved_levels = set(approval.approval_level for approval in existing_approvals)
        
        # Find the next level that hasn't been approved
        for level in required_levels:
            if level not in approved_levels:
                return level
        
        return None
    
    def is_fully_approved(self, expense: Expense) -> bool:
        """
        Check if an expense has received all required approvals.
        
        Args:
            expense: The expense to check
            
        Returns:
            True if all required approvals are complete, False otherwise
        """
        return self.get_next_approval_level(expense) is None
    
    def get_approval_summary(self, expense: Expense) -> Dict[str, Any]:
        """
        Get a comprehensive summary of approval requirements and status for an expense.
        
        Args:
            expense: The expense to analyze
            
        Returns:
            Dictionary containing approval summary information
        """
        matching_rules = self.evaluate_expense(expense)
        required_levels = self.get_required_approval_levels(expense)
        approver_assignments = self.assign_approvers(expense, matching_rules)
        next_level = self.get_next_approval_level(expense)
        auto_approve = self.should_auto_approve(expense)
        fully_approved = self.is_fully_approved(expense)
        
        # Get existing approvals
        existing_approvals = self.db.query(ExpenseApproval).filter(
            ExpenseApproval.expense_id == expense.id
        ).all()
        
        return {
            "expense_id": expense.id,
            "expense_amount": expense.amount,
            "expense_currency": expense.currency,
            "expense_category": expense.category,
            "matching_rules_count": len(matching_rules),
            "required_levels": required_levels,
            "approver_assignments": [
                {
                    "level": level,
                    "approver_id": approver.id,
                    "approver_name": f"{approver.first_name or ''} {approver.last_name or ''}".strip() or approver.email,
                    "approver_email": approver.email,
                    "rule_id": rule.id,
                    "rule_name": rule.name
                }
                for level, approver, rule in approver_assignments
            ],
            "next_approval_level": next_level,
            "should_auto_approve": auto_approve,
            "is_fully_approved": fully_approved,
            "existing_approvals_count": len(existing_approvals),
            "pending_approvals_count": len([a for a in existing_approvals if a.status == ApprovalStatus.PENDING]),
            "approved_count": len([a for a in existing_approvals if a.status == ApprovalStatus.APPROVED]),
            "rejected_count": len([a for a in existing_approvals if a.status == ApprovalStatus.REJECTED])
        }
    
    def validate_approval_rules(self) -> List[Dict[str, Any]]:
        """
        Validate all approval rules for potential conflicts or issues.
        
        Returns:
            List of validation issues found
        """
        issues = []
        
        # Get all active rules
        rules = self.db.query(ApprovalRule).filter(
            ApprovalRule.is_active == True
        ).all()
        
        # Check for overlapping rules with same priority and level
        for i, rule1 in enumerate(rules):
            for rule2 in rules[i+1:]:
                if (rule1.approval_level == rule2.approval_level and 
                    rule1.priority == rule2.priority and
                    rule1.currency == rule2.currency):
                    
                    # Check for amount overlap
                    if self._rules_have_amount_overlap(rule1, rule2):
                        issues.append({
                            "type": "overlapping_rules",
                            "message": f"Rules '{rule1.name}' and '{rule2.name}' have overlapping amount ranges with same priority and level",
                            "rule1_id": rule1.id,
                            "rule2_id": rule2.id,
                            "severity": "warning"
                        })
        
        # Check for rules without valid approvers
        for rule in rules:
            approver = self.db.query(User).filter(User.id == rule.approver_id).first()
            if not approver or not approver.is_active:
                issues.append({
                    "type": "invalid_approver",
                    "message": f"Rule '{rule.name}' has invalid or inactive approver",
                    "rule_id": rule.id,
                    "severity": "error"
                })
        
        # Check for gaps in approval levels
        levels_by_currency = {}
        for rule in rules:
            if rule.currency not in levels_by_currency:
                levels_by_currency[rule.currency] = set()
            levels_by_currency[rule.currency].add(rule.approval_level)
        
        for currency, levels in levels_by_currency.items():
            sorted_levels = sorted(levels)
            for i in range(len(sorted_levels) - 1):
                if sorted_levels[i+1] - sorted_levels[i] > 1:
                    issues.append({
                        "type": "approval_level_gap",
                        "message": f"Gap in approval levels for {currency}: missing level {sorted_levels[i] + 1}",
                        "currency": currency,
                        "severity": "warning"
                    })
        
        return issues
    
    def _rules_have_amount_overlap(self, rule1: ApprovalRule, rule2: ApprovalRule) -> bool:
        """
        Check if two rules have overlapping amount ranges.
        
        Args:
            rule1: First rule to compare
            rule2: Second rule to compare
            
        Returns:
            True if the rules have overlapping amount ranges
        """
        # Get effective ranges (None means no limit)
        r1_min = rule1.min_amount if rule1.min_amount is not None else 0
        r1_max = rule1.max_amount if rule1.max_amount is not None else float('inf')
        r2_min = rule2.min_amount if rule2.min_amount is not None else 0
        r2_max = rule2.max_amount if rule2.max_amount is not None else float('inf')
        
        # Check for overlap
        return not (r1_max < r2_min or r2_max < r1_min)