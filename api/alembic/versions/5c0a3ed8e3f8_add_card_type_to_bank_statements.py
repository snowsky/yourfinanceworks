"""add card_type to bank_statements

Revision ID: 5c0a3ed8e3f8
Revises: 88e9df861f9b
Create Date: 2026-03-11 17:53:23.454354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c0a3ed8e3f8'
down_revision: Union[str, Sequence[str], None] = '88e9df861f9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add card_type column to bank_statements table.

    Defaults to 'debit' for backward compatibility with existing records.
    Credit card statements use inverted sign logic (negative = credit, positive = debit).
    Uses IF NOT EXISTS to be idempotent — safe to run even if the column was already
    created by SQLAlchemy's create_all on first startup.
    """
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE bank_statements "
        "ADD COLUMN IF NOT EXISTS card_type VARCHAR(20) DEFAULT 'debit'"
    ))


def downgrade() -> None:
    """Remove card_type column from bank_statements table."""
    op.drop_column('bank_statements', 'card_type')
