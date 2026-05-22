"""add rollup_expense_id to bank_statements

Revision ID: 025_add_rollup_expense_id
Revises: 024_add_project_task_kanban
Create Date: 2026-05-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "025_add_rollup_expense_id"
down_revision: Union[str, Sequence[str], None] = "024_add_project_task_kanban"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bank_statements",
        sa.Column("rollup_expense_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "bank_statements_rollup_expense_id_fkey",
        source_table="bank_statements",
        referent_table="expenses",
        local_cols=["rollup_expense_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "bank_statements_rollup_expense_id_fkey",
        "bank_statements",
        type_="foreignkey",
    )
    op.drop_column("bank_statements", "rollup_expense_id")
