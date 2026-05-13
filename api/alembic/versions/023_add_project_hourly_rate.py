"""add project hourly rate

Revision ID: 023_project_hourly_rate
Revises: 022_fix_mfa_factor_secrets
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "023_project_hourly_rate"
down_revision = "022_fix_mfa_factor_secrets"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("projects", "hourly_rate"):
        op.add_column("projects", sa.Column("hourly_rate", sa.Float(), nullable=True))


def downgrade() -> None:
    if _has_column("projects", "hourly_rate"):
        op.drop_column("projects", "hourly_rate")
