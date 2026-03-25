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
    # Add notes column to bank_statement_transactions
    op.add_column('bank_statement_transactions', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove notes column from bank_statement_transactions
    op.drop_column('bank_statement_transactions', 'notes')
