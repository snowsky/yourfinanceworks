"""add bank transaction -> invoice/expense links

Revision ID: add_bank_txn_invoice_link_001
Revises: add_expense_invoice_link_001
Create Date: 2025-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_bank_txn_invoice_link_001'
down_revision: Union[str, Sequence[str], None] = 'add_expense_invoice_link_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'bank_statement_transactions' not in tables:
        return
    cols = [c['name'] for c in inspector.get_columns('bank_statement_transactions')]
    if 'invoice_id' not in cols:
        op.add_column('bank_statement_transactions', sa.Column('invoice_id', sa.Integer(), nullable=True))
        try:
            op.create_foreign_key('fk_bank_statement_transactions_invoice_id', 'bank_statement_transactions', 'invoices', ['invoice_id'], ['id'])
        except Exception:
            # In case FK already exists or cross-db issues; safe to proceed
            pass
    if 'expense_id' not in cols:
        op.add_column('bank_statement_transactions', sa.Column('expense_id', sa.Integer(), nullable=True))
        try:
            op.create_foreign_key('fk_bank_statement_transactions_expense_id', 'bank_statement_transactions', 'expenses', ['expense_id'], ['id'])
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'bank_statement_transactions' not in tables:
        return
    cols = [c['name'] for c in inspector.get_columns('bank_statement_transactions')]
    if 'invoice_id' in cols:
        try:
            op.drop_constraint('fk_bank_statement_transactions_invoice_id', 'bank_statement_transactions', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('bank_statement_transactions', 'invoice_id')
    if 'expense_id' in cols:
        try:
            op.drop_constraint('fk_bank_statement_transactions_expense_id', 'bank_statement_transactions', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('bank_statement_transactions', 'expense_id')


