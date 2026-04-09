"""add plugin_users table

Revision ID: 015_add_plugin_users
Revises: 014_add_file_hash_to_bank_statements
Create Date: 2026-04-09 16:53:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '015_add_plugin_users'
down_revision = '014_add_file_hash_to_bank_statements'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create plugin_users table
    op.create_table(
        'plugin_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('plugin_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('google_id', sa.String(), nullable=True),
        sa.Column('azure_ad_id', sa.String(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plugin_users_email'), 'plugin_users', ['email'], unique=False)
    op.create_index(op.f('ix_plugin_users_id'), 'plugin_users', ['id'], unique=False)
    op.create_index(op.f('ix_plugin_users_plugin_id'), 'plugin_users', ['plugin_id'], unique=False)
    op.create_index(op.f('ix_plugin_users_tenant_id'), 'plugin_users', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_plugin_users_tenant_id'), table_name='plugin_users')
    op.drop_index(op.f('ix_plugin_users_plugin_id'), table_name='plugin_users')
    op.drop_index(op.f('ix_plugin_users_id'), table_name='plugin_users')
    op.drop_index(op.f('ix_plugin_users_email'), table_name='plugin_users')
    op.drop_table('plugin_users')
