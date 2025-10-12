"""Add expense approval workflow tables

Revision ID: add_expense_approval_workflow_tables
Revises: 
Create Date: 2025-01-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'add_expense_approval_workflow_tables'
down_revision = None  # This will be updated when the migration is run
branch_labels = None
depends_on = None


def upgrade():
    """Create approval workflow tables"""
    
    # Create approval_rules table
    op.create_table('approval_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('min_amount', sa.Float(), nullable=True),
        sa.Column('max_amount', sa.Float(), nullable=True),
        sa.Column('category_filter', sa.String(), nullable=True),
        sa.Column('currency', sa.String(), nullable=False, default='USD'),
        sa.Column('approval_level', sa.Integer(), nullable=False, default=1),
        sa.Column('approver_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('priority', sa.Integer(), nullable=False, default=0),
        sa.Column('auto_approve_below', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_rules_id'), 'approval_rules', ['id'], unique=False)
    
    # Create expense_approvals table
    op.create_table('expense_approvals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('expense_id', sa.Integer(), nullable=False),
        sa.Column('approver_id', sa.Integer(), nullable=False),
        sa.Column('approval_rule_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approval_level', sa.Integer(), nullable=False, default=1),
        sa.Column('is_current_level', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['approval_rule_id'], ['approval_rules.id'], ),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['expense_id'], ['expenses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_expense_approvals_id'), 'expense_approvals', ['id'], unique=False)
    
    # Create approval_delegates table
    op.create_table('approval_delegates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('approver_id', sa.Integer(), nullable=False),
        sa.Column('delegate_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['delegate_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('approver_id', 'delegate_id', 'start_date', name='unique_active_delegation')
    )
    op.create_index(op.f('ix_approval_delegates_id'), 'approval_delegates', ['id'], unique=False)


def downgrade():
    """Drop approval workflow tables"""
    op.drop_index(op.f('ix_approval_delegates_id'), table_name='approval_delegates')
    op.drop_table('approval_delegates')
    
    op.drop_index(op.f('ix_expense_approvals_id'), table_name='expense_approvals')
    op.drop_table('expense_approvals')
    
    op.drop_index(op.f('ix_approval_rules_id'), table_name='approval_rules')
    op.drop_table('approval_rules')