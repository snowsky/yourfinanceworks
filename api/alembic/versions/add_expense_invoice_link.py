"""add expense->invoice link

Revision ID: add_expense_invoice_link_001
Revises: 38f8e053a17e
Create Date: 2025-08-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_expense_invoice_link_001'
down_revision: Union[str, Sequence[str], None] = '38f8e053a17e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'expenses' not in tables or 'invoices' not in tables:
        return
    expense_cols = [c['name'] for c in inspector.get_columns('expenses')]
    if 'invoice_id' not in expense_cols:
        op.add_column('expenses', sa.Column('invoice_id', sa.Integer(), nullable=True))
        try:
            op.create_foreign_key('fk_expenses_invoice_id', 'expenses', 'invoices', ['invoice_id'], ['id'], ondelete=None)
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'expenses' not in tables:
        return
    expense_cols = [c['name'] for c in inspector.get_columns('expenses')]
    if 'invoice_id' in expense_cols:
        try:
            op.drop_constraint('fk_expenses_invoice_id', 'expenses', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('expenses', 'invoice_id')


