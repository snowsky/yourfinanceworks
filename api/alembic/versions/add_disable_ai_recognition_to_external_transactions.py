"""add disable_ai_recognition to external_transactions

Revision ID: add_disable_ai_recognition_001
Revises: add_expense_labels_array_001
Create Date: 2025-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_disable_ai_recognition_001'
down_revision: Union[str, Sequence[str], None] = 'add_expense_labels_array_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'external_transactions' not in tables:
        return

    existing_cols = {c['name'] for c in inspector.get_columns('external_transactions')}
    if 'disable_ai_recognition' not in existing_cols:
        op.add_column('external_transactions', sa.Column('disable_ai_recognition', sa.Boolean(), nullable=False, default=False))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'external_transactions' not in tables:
        return
    existing_cols = {c['name'] for c in inspector.get_columns('external_transactions')}
    if 'disable_ai_recognition' in existing_cols:
        op.drop_column('external_transactions', 'disable_ai_recognition')
