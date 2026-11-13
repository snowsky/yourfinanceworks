"""Store immutable generated-invoice provenance; legacy rows remain unresolved."""
from alembic import op
import sqlalchemy as sa

revision = '030_project_invoice_snapshots'
down_revision = '029_entry_cost_revisions'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('project_invoice_links',
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoices.id', ondelete='CASCADE'), primary_key=True))
    op.add_column('project_invoice_sources', sa.Column('snapshot', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('project_invoice_sources', 'snapshot')
    op.drop_table('project_invoice_links')
