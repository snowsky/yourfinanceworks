"""add per-user expense digest preferences

Revision ID: 020_expense_digest_user_preferences
Revises: 019_add_tenant_archive_columns
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "020_expense_digest_user_preferences"
down_revision = "019_add_tenant_archive_columns"
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
        "email_notification_settings",
        [
            sa.Column("expense_digest_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("expense_digest_frequency", sa.String(), nullable=False, server_default="weekly"),
            sa.Column("expense_digest_next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expense_digest_last_sent_at", sa.DateTime(timezone=True), nullable=True),
        ],
    )


def downgrade() -> None:
    _drop_columns_if_present(
        "email_notification_settings",
        [
            "expense_digest_last_sent_at",
            "expense_digest_next_run_at",
            "expense_digest_frequency",
            "expense_digest_enabled",
        ],
    )
