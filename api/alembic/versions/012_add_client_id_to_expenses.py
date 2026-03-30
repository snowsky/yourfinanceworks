"""Add client_id to expenses

Revision ID: 012_add_client_id_to_expenses
Revises: 011_add_client_record_fields
Create Date: 2026-03-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '012_add_client_id_to_expenses'
down_revision: Union[str, Sequence[str], None] = '011_add_client_record_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('expenses', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_expenses_client_id',
        'expenses',
        'clients',
        ['client_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_expenses_client_id', 'expenses', ['client_id'])


def downgrade() -> None:
    op.drop_index('ix_expenses_client_id', table_name='expenses')
    op.drop_constraint('fk_expenses_client_id', 'expenses', type_='foreignkey')
    op.drop_column('expenses', 'client_id')
