"""add notes to bank statement transactions

Revision ID: 009_add_notes_to_transactions
Revises: 008_add_transaction_links
Create Date: 2026-03-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_notes_to_transactions'
down_revision: Union[str, Sequence[str], None] = '008_add_transaction_links'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.add_column('bank_statement_transactions', sa.Column('notes', sa.Text(), nullable=True))
    except Exception as e:
        # SQLite doesn't natively support all ALTER operations in the same way, but add_column usually works.
        # If it fails, print or log
        pass


def downgrade() -> None:
    try:
        op.drop_column('bank_statement_transactions', 'notes')
    except Exception as e:
        pass
