"""add project task kanban

Revision ID: 024_project_task_kanban
Revises: 023_project_hourly_rate
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "024_project_task_kanban"
down_revision = "023_project_hourly_rate"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if _has_table("project_tasks"):
        if not _has_column("project_tasks", "kanban_status"):
            op.add_column("project_tasks", sa.Column("kanban_status", sa.String(), nullable=False, server_default="todo"))
            op.create_index("ix_project_tasks_kanban_status", "project_tasks", ["kanban_status"])
        if not _has_column("project_tasks", "kanban_position"):
            op.add_column("project_tasks", sa.Column("kanban_position", sa.Integer(), nullable=False, server_default="0"))
        if not _has_column("project_tasks", "priority"):
            op.add_column("project_tasks", sa.Column("priority", sa.String(), nullable=True))
        if not _has_column("project_tasks", "due_date"):
            op.add_column("project_tasks", sa.Column("due_date", sa.Date(), nullable=True))
        if not _has_column("project_tasks", "custom_fields"):
            op.add_column("project_tasks", sa.Column("custom_fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    if not _has_table("project_kanban_columns"):
        op.create_table(
            "project_kanban_columns",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("hidden", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("project_id", "key", name="uq_project_kanban_columns_project_key"),
        )
        op.create_index("ix_project_kanban_columns_id", "project_kanban_columns", ["id"])
        op.create_index("ix_project_kanban_columns_project_id", "project_kanban_columns", ["project_id"])

    if not _has_table("project_custom_fields"):
        op.create_table(
            "project_custom_fields",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("field_type", sa.String(), nullable=False, server_default="text"),
            sa.Column("options", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("required", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("project_id", "key", name="uq_project_custom_fields_project_key"),
        )
        op.create_index("ix_project_custom_fields_id", "project_custom_fields", ["id"])
        op.create_index("ix_project_custom_fields_project_id", "project_custom_fields", ["project_id"])


def downgrade() -> None:
    if _has_table("project_custom_fields"):
        op.drop_table("project_custom_fields")
    if _has_table("project_kanban_columns"):
        op.drop_table("project_kanban_columns")
    if _has_column("project_tasks", "custom_fields"):
        op.drop_column("project_tasks", "custom_fields")
    if _has_column("project_tasks", "due_date"):
        op.drop_column("project_tasks", "due_date")
    if _has_column("project_tasks", "priority"):
        op.drop_column("project_tasks", "priority")
    if _has_column("project_tasks", "kanban_position"):
        op.drop_column("project_tasks", "kanban_position")
    if _has_column("project_tasks", "kanban_status"):
        op.drop_index("ix_project_tasks_kanban_status", table_name="project_tasks")
        op.drop_column("project_tasks", "kanban_status")
