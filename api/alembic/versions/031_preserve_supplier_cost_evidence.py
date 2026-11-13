"""Preserve expected supplier expense IDs after recycling and permanent deletion."""
from alembic import op
import sqlalchemy as sa

revision = '031_supplier_cost_evidence'
down_revision = '030_project_invoice_snapshots'
branch_labels = None
depends_on = None


def upgrade():
    # Expense IDs are historical evidence, rather than live references. Existing
    # rows remain intact; same-project validation still applies to all new links.
    convention = {'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s'}
    constraints = sa.inspect(op.get_bind()).get_foreign_keys('time_entry_cost_expenses')
    constraint = next(row for row in constraints if row['constrained_columns'] == ['expense_id'])
    name = constraint['name'] or 'fk_time_entry_cost_expenses_expense_id_expenses'
    with op.batch_alter_table('time_entry_cost_expenses', naming_convention=convention) as batch:
        batch.drop_constraint(name, type_='foreignkey')


def downgrade():
    # Fail rather than silently delete historical evidence if tombstones exist.
    with op.batch_alter_table('time_entry_cost_expenses') as batch:
        batch.create_foreign_key('fk_time_entry_cost_expenses_expense_id_expenses',
                                 'expenses', ['expense_id'], ['id'], ondelete='CASCADE')
