"""add file_hash to bank_statements

Revision ID: 014_add_file_hash
Revises: 013_add_is_possible_receipt
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '014_add_file_hash'
down_revision: Union[str, Sequence[str], None] = '013_add_is_possible_receipt'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bank_statements', sa.Column('file_hash', sa.String(64), nullable=True))
    op.create_index('ix_bank_statements_file_hash', 'bank_statements', ['file_hash'])


def downgrade() -> None:
    op.drop_index('ix_bank_statements_file_hash', table_name='bank_statements')
    op.drop_column('bank_statements', 'file_hash')
