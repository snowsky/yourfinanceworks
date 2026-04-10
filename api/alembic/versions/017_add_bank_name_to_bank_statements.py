"""add bank_name to bank_statements

Revision ID: 017_add_bank_name
Revises: 016_add_usage_count
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '017_add_bank_name'
down_revision: Union[str, Sequence[str], None] = '016_add_usage_count'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bank_statements', sa.Column('bank_name', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('bank_statements', 'bank_name')
