"""add share token access controls

Revision ID: 021_share_token_access_controls
Revises: 020_expense_digest_prefs
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "021_share_token_access_controls"
down_revision = "020_expense_digest_prefs"
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
        "share_tokens",
        [
            sa.Column("access_type", sa.String(length=32), nullable=False, server_default="public"),
            sa.Column("password_hash", sa.String(), nullable=True),
            sa.Column("security_question", sa.String(), nullable=True),
            sa.Column("security_answer_hash", sa.String(), nullable=True),
            sa.Column("max_access_count", sa.Integer(), nullable=True),
            sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        ],
    )


def downgrade() -> None:
    _drop_columns_if_present(
        "share_tokens",
        [
            "access_count",
            "max_access_count",
            "security_answer_hash",
            "security_question",
            "password_hash",
            "access_type",
        ],
    )
