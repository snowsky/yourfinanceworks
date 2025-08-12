"""
add must_reset_password to master_users

Revision ID: 2b1a_must_reset_password_master
Revises: 951a7ee5381c
Create Date: 2025-08-12
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2b1a_must_reset_password_master'
down_revision = '951a7ee5381c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'master_users' not in tables:
        return
    existing_cols = {c['name'] for c in inspector.get_columns('master_users')}
    if 'must_reset_password' not in existing_cols:
        op.add_column('master_users', sa.Column('must_reset_password', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
        op.execute("ALTER TABLE master_users ALTER COLUMN must_reset_password DROP DEFAULT")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'master_users' not in tables:
        return
    existing_cols = {c['name'] for c in inspector.get_columns('master_users')}
    if 'must_reset_password' in existing_cols:
        op.drop_column('master_users', 'must_reset_password')


