"""Preserve private time cost replacement history.

Revision ID: 029_entry_cost_revisions
Revises: 028_project_profitability
"""
from alembic import op
import sqlalchemy as sa

revision = '029_entry_cost_revisions'
down_revision = '028_project_profitability'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('time_entry_cost_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('time_entry_id', sa.Integer(), sa.ForeignKey('time_entries.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False))
    op.create_index('ix_time_entry_cost_revisions_time_entry_id', 'time_entry_cost_revisions', ['time_entry_id'])


def downgrade():
    op.drop_table('time_entry_cost_revisions')
