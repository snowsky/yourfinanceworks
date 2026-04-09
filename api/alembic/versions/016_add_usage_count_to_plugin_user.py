"""add usage_count to plugin_user

Revision ID: 016_add_usage_count
Revises: 015_add_plugin_users
Create Date: 2026-04-09 13:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '016_add_usage_count'
down_revision = '015_add_plugin_users'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('plugin_users', sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('plugin_users', 'usage_count')
