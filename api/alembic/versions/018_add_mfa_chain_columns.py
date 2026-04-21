"""add mfa chain columns to user tables

Revision ID: 018_add_mfa_chain_columns
Revises: 017_add_bank_name_to_bank_statements
Create Date: 2026-04-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "018_add_mfa_chain_columns"
down_revision = "017_add_bank_name_to_bank_statements"
branch_labels = None
depends_on = None


def _add_columns_if_missing(table_name: str, columns: list[sa.Column]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return

    existing = {col["name"] for col in inspector.get_columns(table_name)}
    for column in columns:
        if column.name in existing:
            continue
        op.add_column(table_name, column)


def _drop_columns_if_present(table_name: str, column_names: list[str]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return

    existing = {col["name"] for col in inspector.get_columns(table_name)}
    for column_name in column_names:
        if column_name not in existing:
            continue
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    user_columns = [
        sa.Column("mfa_chain_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mfa_chain_mode", sa.String(), nullable=False, server_default="fixed"),
        sa.Column("mfa_chain_factors", sa.JSON(), nullable=True),
        sa.Column("mfa_factor_secrets", sa.JSON(), nullable=True),
    ]

    _add_columns_if_missing("master_users", user_columns)
    _add_columns_if_missing("users", user_columns)


def downgrade() -> None:
    column_names = ["mfa_factor_secrets", "mfa_chain_factors", "mfa_chain_mode", "mfa_chain_enabled"]

    _drop_columns_if_present("master_users", column_names)
    _drop_columns_if_present("users", column_names)
