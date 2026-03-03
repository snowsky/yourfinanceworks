"""Add project fields to expenses

Revision ID: 007_project_expenses
Revises: 006_time_tracking
Create Date: 2026-03-02 21:47:49.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007_project_expenses'
down_revision = '006_time_tracking'
branch_labels = None
depends_on = None


def upgrade():
    """Add project_id and invoiced fields to expenses table"""
    op.add_column('expenses', sa.Column('project_id', sa.Integer(), nullable=True))
    op.add_column('expenses', sa.Column('invoiced', sa.Boolean(), nullable=True, server_default='false'))
    op.create_foreign_key(
        'fk_expenses_project_id',
        'expenses', 'projects',
        ['project_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_expenses_project_id', 'expenses', ['project_id'])


def downgrade():
    """Remove project_id and invoiced fields from expenses table"""
    op.drop_index('ix_expenses_project_id', table_name='expenses')
    op.drop_constraint('fk_expenses_project_id', 'expenses', type_='foreignkey')
    op.drop_column('expenses', 'invoiced')
    op.drop_column('expenses', 'project_id')
