"""Add is_audited and last_audited_at fields to entities

Revision ID: add_audit_fields
Revises: 
Create Date: 2025-01-10 15:52:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_audit_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add is_audited and last_audited_at to expenses table
    op.add_column('expenses', 'is_audited', sa.Column('is_audited', sa.Boolean(), nullable=False, default=False))
    op.add_column('expenses', 'last_audited_at', sa.Column('last_audited_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add is_audited and last_audited_at to invoices table
    op.add_column('invoices', 'is_audited', sa.Column('is_audited', sa.Boolean(), nullable=False, default=False))
    op.add_column('invoices', 'last_audited_at', sa.Column('last_audited_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add is_audited and last_audited_at to bank_statement_transactions table
    op.add_column('bank_statement_transactions', 'is_audited', sa.Column('is_audited', sa.Boolean(), nullable=False, default=False))
    op.add_column('bank_statement_transactions', 'last_audited_at', sa.Column('last_audited_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Remove is_audited and last_audited_at from expenses table
    op.drop_column('expenses', 'is_audited')
    op.drop_column('expenses', 'last_audited_at')
    
    # Remove is_audited and last_audited_at from invoices table
    op.drop_column('invoices', 'is_audited')
    op.drop_column('invoices', 'last_audited_at')
    
    # Remove is_audited and last_audited_at from bank_statement_transactions table
    op.drop_column('bank_statement_transactions', 'is_audited')
    op.drop_column('bank_statement_transactions', 'last_audited_at')
