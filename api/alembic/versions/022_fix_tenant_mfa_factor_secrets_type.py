"""fix tenant mfa factor secrets column type

Revision ID: 022_fix_tenant_mfa_factor_secrets_type
Revises: 021_share_token_access_controls
Create Date: 2026-05-07
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "022_fix_tenant_mfa_factor_secrets_type"
down_revision = "021_share_token_access_controls"
branch_labels = None
depends_on = None


def _is_tenant_migration() -> bool:
    return os.getenv("ALEMBIC_DB_TYPE", "master") == "tenant" or bool(os.getenv("TENANT_ID"))


def _get_column(table_name: str, column_name: str) -> dict | None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return None

    for column in inspector.get_columns(table_name):
        if column["name"] == column_name:
            return column
    return None


def upgrade() -> None:
    if not _is_tenant_migration():
        return

    if op.get_bind().dialect.name != "postgresql":
        return

    column = _get_column("users", "mfa_factor_secrets")
    if column is None:
        return

    if isinstance(column["type"], (postgresql.JSON, postgresql.JSONB, sa.JSON)):
        op.alter_column(
            "users",
            "mfa_factor_secrets",
            existing_type=column["type"],
            type_=sa.Text(),
            postgresql_using="mfa_factor_secrets::text",
        )


def downgrade() -> None:
    if not _is_tenant_migration():
        return

    if op.get_bind().dialect.name != "postgresql":
        return

    column = _get_column("users", "mfa_factor_secrets")
    if column is None:
        return

    if isinstance(column["type"], sa.Text):
        op.alter_column(
            "users",
            "mfa_factor_secrets",
            existing_type=sa.Text(),
            type_=sa.JSON(),
            postgresql_using="to_json(mfa_factor_secrets)::json",
        )
