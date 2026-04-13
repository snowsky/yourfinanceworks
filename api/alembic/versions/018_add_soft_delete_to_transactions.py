"""add soft delete fields to bank_statement_transactions

Revision ID: 018_add_soft_delete_txn
Revises: 017_add_bank_name
Create Date: 2026-04-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '018_add_soft_delete_txn'
down_revision: Union[str, Sequence[str], None] = '017_add_bank_name'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bank_statement_transactions', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('bank_statement_transactions', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bank_statement_transactions', sa.Column('deleted_by', sa.Integer(), nullable=True))
    op.create_index('ix_bank_statement_transactions_is_deleted', 'bank_statement_transactions', ['is_deleted'])


def downgrade() -> None:
    op.drop_index('ix_bank_statement_transactions_is_deleted', 'bank_statement_transactions')
    op.drop_column('bank_statement_transactions', 'deleted_by')
    op.drop_column('bank_statement_transactions', 'deleted_at')
    op.drop_column('bank_statement_transactions', 'is_deleted')
