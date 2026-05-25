"""add financial_liabilities and net_worth_snapshots tables

Revision ID: 027_add_net_worth_tables
Revises: 026_add_detected_subscriptions
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "027_add_net_worth_tables"
down_revision: Union[str, Sequence[str], None] = "026_add_detected_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_liabilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "kind",
            sa.String(length=32),
            nullable=False,
            server_default="other",
        ),
        sa.Column(
            "balance", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "currency",
            sa.String(length=8),
            nullable=False,
            server_default="USD",
        ),
        sa.Column("interest_rate", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_financial_liabilities_id",
        "financial_liabilities",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_financial_liabilities_kind",
        "financial_liabilities",
        ["kind"],
        unique=False,
    )

    op.create_table(
        "net_worth_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("account_kind", sa.String(length=32), nullable=False),
        sa.Column("account_ref", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column(
            "balance", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "currency",
            sa.String(length=8),
            nullable=False,
            server_default="USD",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_net_worth_snapshots_id",
        "net_worth_snapshots",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_net_worth_snapshots_snapshot_date",
        "net_worth_snapshots",
        ["snapshot_date"],
        unique=False,
    )
    op.create_index(
        "ix_net_worth_snapshots_account_kind",
        "net_worth_snapshots",
        ["account_kind"],
        unique=False,
    )
    op.create_index(
        "ix_net_worth_snapshots_date_kind",
        "net_worth_snapshots",
        ["snapshot_date", "account_kind"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_net_worth_snapshots_date_kind", table_name="net_worth_snapshots"
    )
    op.drop_index(
        "ix_net_worth_snapshots_account_kind", table_name="net_worth_snapshots"
    )
    op.drop_index(
        "ix_net_worth_snapshots_snapshot_date", table_name="net_worth_snapshots"
    )
    op.drop_index(
        "ix_net_worth_snapshots_id", table_name="net_worth_snapshots"
    )
    op.drop_table("net_worth_snapshots")

    op.drop_index(
        "ix_financial_liabilities_kind", table_name="financial_liabilities"
    )
    op.drop_index(
        "ix_financial_liabilities_id", table_name="financial_liabilities"
    )
    op.drop_table("financial_liabilities")
