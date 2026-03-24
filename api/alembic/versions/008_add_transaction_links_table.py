"""add transaction_links table

Revision ID: 008_add_transaction_links
Revises: 5c0a3ed8e3f8
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_transaction_links'
down_revision: Union[str, Sequence[str], None] = '5c0a3ed8e3f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create transaction_links table for cross-statement transaction associations.

    Uses IF NOT EXISTS to be idempotent — safe to run even if the table was already
    created by SQLAlchemy's create_all on first startup.
    """
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS transaction_links (
            id SERIAL PRIMARY KEY,
            transaction_a_id INTEGER NOT NULL REFERENCES bank_statement_transactions(id) ON DELETE CASCADE,
            transaction_b_id INTEGER NOT NULL REFERENCES bank_statement_transactions(id) ON DELETE CASCADE,
            link_type VARCHAR NOT NULL DEFAULT 'transfer',
            notes TEXT,
            created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_transaction_links_transaction_a_id
        ON transaction_links (transaction_a_id)
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_transaction_links_transaction_b_id
        ON transaction_links (transaction_b_id)
    """))
    conn.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS unique_transaction_link_pair
        ON transaction_links (transaction_a_id, transaction_b_id)
    """))


def downgrade() -> None:
    """Remove transaction_links table."""
    op.drop_table('transaction_links')
