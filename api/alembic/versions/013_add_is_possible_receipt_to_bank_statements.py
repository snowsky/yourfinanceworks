"""add is_possible_receipt to bank_statements

Revision ID: 013_add_is_possible_receipt
Revises: 012_add_client_id_to_expenses
Create Date: 2026-04-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '013_add_is_possible_receipt'
down_revision: Union[str, Sequence[str], None] = '012_add_client_id_to_expenses'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bank_statements', sa.Column('is_possible_receipt', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('bank_statements', 'is_possible_receipt')
