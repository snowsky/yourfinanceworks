"""add tenant archive columns

Revision ID: 019_add_tenant_archive_columns
Revises: 018_add_mfa_chain_columns
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "019_add_tenant_archive_columns"
down_revision = "018_add_mfa_chain_columns"
branch_labels = None
depends_on = None


def _add_columns_if_missing(table_name: str, columns: list[sa.Column]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return

    existing = {col["name"] for col in inspector.get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def _drop_columns_if_present(table_name: str, column_names: list[str]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return

    existing = {col["name"] for col in inspector.get_columns(table_name)}
    for column_name in column_names:
        if column_name in existing:
            op.drop_column(table_name, column_name)


def upgrade() -> None:
    _add_columns_if_missing(
        "tenants",
        [
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("archived_by_id", sa.Integer(), nullable=True),
            sa.Column("archive_reason", sa.Text(), nullable=True),
        ],
    )


def downgrade() -> None:
    _drop_columns_if_present(
        "tenants",
        ["archive_reason", "archived_by_id", "archived_at"],
    )
