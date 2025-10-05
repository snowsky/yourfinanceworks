"""Update approval workflow database indexes and constraints

Revision ID: update_approval_workflow_indexes
Revises: add_expense_approval_status_values
Create Date: 2025-01-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'update_approval_workflow_indexes'
down_revision = 'add_expense_approval_status_values'
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes and constraints for approval workflow optimization"""
    
    # Add indexes for ExpenseApproval table for better query performance
    op.create_index('ix_expense_approvals_expense_id', 'expense_approvals', ['expense_id'])
    op.create_index('ix_expense_approvals_approver_id', 'expense_approvals', ['approver_id'])
    op.create_index('ix_expense_approvals_status', 'expense_approvals', ['status'])
    op.create_index('ix_expense_approvals_approval_level', 'expense_approvals', ['approval_level'])
    op.create_index('ix_expense_approvals_is_current_level', 'expense_approvals', ['is_current_level'])
    op.create_index('ix_expense_approvals_submitted_at', 'expense_approvals', ['submitted_at'])
    
    # Composite indexes for common query patterns
    op.create_index('ix_expense_approvals_status_approver', 'expense_approvals', ['status', 'approver_id'])
    op.create_index('ix_expense_approvals_expense_level', 'expense_approvals', ['expense_id', 'approval_level'])
    
    # Add indexes for ApprovalRule table for rule matching performance
    op.create_index('ix_approval_rules_approver_id', 'approval_rules', ['approver_id'])
    op.create_index('ix_approval_rules_is_active', 'approval_rules', ['is_active'])
    op.create_index('ix_approval_rules_priority', 'approval_rules', ['priority'])
    op.create_index('ix_approval_rules_approval_level', 'approval_rules', ['approval_level'])
    op.create_index('ix_approval_rules_currency', 'approval_rules', ['currency'])
    
    # Composite indexes for rule matching
    op.create_index('ix_approval_rules_active_priority', 'approval_rules', ['is_active', 'priority'])
    op.create_index('ix_approval_rules_currency_active', 'approval_rules', ['currency', 'is_active'])
    
    # Add indexes for ApprovalDelegate table for delegation lookups
    op.create_index('ix_approval_delegates_approver_id', 'approval_delegates', ['approver_id'])
    op.create_index('ix_approval_delegates_delegate_id', 'approval_delegates', ['delegate_id'])
    op.create_index('ix_approval_delegates_is_active', 'approval_delegates', ['is_active'])
    op.create_index('ix_approval_delegates_start_date', 'approval_delegates', ['start_date'])
    op.create_index('ix_approval_delegates_end_date', 'approval_delegates', ['end_date'])
    
    # Composite indexes for active delegation queries
    op.create_index('ix_approval_delegates_active_dates', 'approval_delegates', ['is_active', 'start_date', 'end_date'])
    op.create_index('ix_approval_delegates_approver_active', 'approval_delegates', ['approver_id', 'is_active'])
    
    # Add check constraints for data integrity using batch mode for SQLite compatibility
    
    # ExpenseApproval constraints
    with op.batch_alter_table('expense_approvals') as batch_op:
        batch_op.create_check_constraint(
            'ck_expense_approval_status_valid',
            "status IN ('pending', 'approved', 'rejected')"
        )
        batch_op.create_check_constraint(
            'ck_expense_approval_level_positive',
            'approval_level > 0'
        )
    
    # ApprovalRule constraints
    with op.batch_alter_table('approval_rules') as batch_op:
        batch_op.create_check_constraint(
            'ck_approval_rule_priority_non_negative',
            'priority >= 0'
        )
        batch_op.create_check_constraint(
            'ck_approval_rule_level_positive',
            'approval_level > 0'
        )
        batch_op.create_check_constraint(
            'ck_approval_rule_amount_range',
            'min_amount IS NULL OR max_amount IS NULL OR min_amount <= max_amount'
        )
        batch_op.create_check_constraint(
            'ck_approval_rule_auto_approve_positive',
            'auto_approve_below IS NULL OR auto_approve_below > 0'
        )
    
    # ApprovalDelegate constraints
    with op.batch_alter_table('approval_delegates') as batch_op:
        batch_op.create_check_constraint(
            'ck_approval_delegate_date_range',
            'start_date < end_date'
        )
        batch_op.create_check_constraint(
            'ck_approval_delegate_no_self_delegation',
            'approver_id != delegate_id'
        )


def downgrade():
    """Remove indexes and constraints for approval workflow"""
    
    # Drop check constraints using batch mode for SQLite compatibility
    with op.batch_alter_table('approval_delegates') as batch_op:
        batch_op.drop_constraint('ck_approval_delegate_no_self_delegation', type_='check')
        batch_op.drop_constraint('ck_approval_delegate_date_range', type_='check')
    
    with op.batch_alter_table('approval_rules') as batch_op:
        batch_op.drop_constraint('ck_approval_rule_auto_approve_positive', type_='check')
        batch_op.drop_constraint('ck_approval_rule_amount_range', type_='check')
        batch_op.drop_constraint('ck_approval_rule_level_positive', type_='check')
        batch_op.drop_constraint('ck_approval_rule_priority_non_negative', type_='check')
    
    with op.batch_alter_table('expense_approvals') as batch_op:
        batch_op.drop_constraint('ck_expense_approval_level_positive', type_='check')
        batch_op.drop_constraint('ck_expense_approval_status_valid', type_='check')
    
    # Drop ApprovalDelegate indexes
    op.drop_index('ix_approval_delegates_approver_active', table_name='approval_delegates')
    op.drop_index('ix_approval_delegates_active_dates', table_name='approval_delegates')
    op.drop_index('ix_approval_delegates_end_date', table_name='approval_delegates')
    op.drop_index('ix_approval_delegates_start_date', table_name='approval_delegates')
    op.drop_index('ix_approval_delegates_is_active', table_name='approval_delegates')
    op.drop_index('ix_approval_delegates_delegate_id', table_name='approval_delegates')
    op.drop_index('ix_approval_delegates_approver_id', table_name='approval_delegates')
    
    # Drop ApprovalRule indexes
    op.drop_index('ix_approval_rules_currency_active', table_name='approval_rules')
    op.drop_index('ix_approval_rules_active_priority', table_name='approval_rules')
    op.drop_index('ix_approval_rules_currency', table_name='approval_rules')
    op.drop_index('ix_approval_rules_approval_level', table_name='approval_rules')
    op.drop_index('ix_approval_rules_priority', table_name='approval_rules')
    op.drop_index('ix_approval_rules_is_active', table_name='approval_rules')
    op.drop_index('ix_approval_rules_approver_id', table_name='approval_rules')
    
    # Drop ExpenseApproval indexes
    op.drop_index('ix_expense_approvals_expense_level', table_name='expense_approvals')
    op.drop_index('ix_expense_approvals_status_approver', table_name='expense_approvals')
    op.drop_index('ix_expense_approvals_submitted_at', table_name='expense_approvals')
    op.drop_index('ix_expense_approvals_is_current_level', table_name='expense_approvals')
    op.drop_index('ix_expense_approvals_approval_level', table_name='expense_approvals')
    op.drop_index('ix_expense_approvals_status', table_name='expense_approvals')
    op.drop_index('ix_expense_approvals_approver_id', table_name='expense_approvals')
    op.drop_index('ix_expense_approvals_expense_id', table_name='expense_approvals')