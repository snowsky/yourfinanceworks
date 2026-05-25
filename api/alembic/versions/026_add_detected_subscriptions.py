"""add detected_subscriptions table

Revision ID: 026_add_detected_subscriptions
Revises: 025_add_rollup_expense_id
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "026_add_detected_subscriptions"
down_revision: Union[str, Sequence[str], None] = "025_add_rollup_expense_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "detected_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("merchant_key", sa.String(length=200), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("last_amount", sa.Float(), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=8),
            nullable=False,
            server_default="USD",
        ),
        sa.Column("cadence_days", sa.Integer(), nullable=False),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("first_seen_date", sa.Date(), nullable=False),
        sa.Column("last_seen_date", sa.Date(), nullable=False),
        sa.Column("next_expected_date", sa.Date(), nullable=True),
        sa.Column(
            "charge_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("source_transaction_ids", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cancel_reminder_at", sa.Date(), nullable=True),
        sa.Column(
            "price_change_acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("dismissed_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "dismissed_at", sa.DateTime(timezone=True), nullable=True
        ),
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
        sa.ForeignKeyConstraint(
            ["dismissed_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "merchant_key", name="uq_detected_subscriptions_merchant_key"
        ),
    )
    op.create_index(
        "ix_detected_subscriptions_id",
        "detected_subscriptions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_detected_subscriptions_merchant_key",
        "detected_subscriptions",
        ["merchant_key"],
        unique=False,
    )
    op.create_index(
        "ix_detected_subscriptions_status",
        "detected_subscriptions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_detected_subscriptions_status_next",
        "detected_subscriptions",
        ["status", "next_expected_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_detected_subscriptions_status_next",
        table_name="detected_subscriptions",
    )
    op.drop_index(
        "ix_detected_subscriptions_status",
        table_name="detected_subscriptions",
    )
    op.drop_index(
        "ix_detected_subscriptions_merchant_key",
        table_name="detected_subscriptions",
    )
    op.drop_index(
        "ix_detected_subscriptions_id",
        table_name="detected_subscriptions",
    )
    op.drop_table("detected_subscriptions")
