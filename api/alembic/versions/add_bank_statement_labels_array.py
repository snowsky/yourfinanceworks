"""add labels array to bank_statements

Revision ID: add_bank_statement_labels_array_001
Revises: add_bank_statement_label_001
Create Date: 2025-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_bank_statement_labels_array_001'
down_revision: Union[str, Sequence[str], None] = 'add_bank_statement_label_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'bank_statements' not in tables:
        return
    cols = [c['name'] for c in inspector.get_columns('bank_statements')]
    if 'labels' not in cols:
        op.add_column('bank_statements', sa.Column('labels', sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'bank_statements' not in tables:
        return
    cols = [c['name'] for c in inspector.get_columns('bank_statements')]
    if 'labels' in cols:
        op.drop_column('bank_statements', 'labels')


