"""Persist private project costs and invoice line provenance.

Revision ID: 028_project_profitability
Revises: 027_add_net_worth_tables
"""
from alembic import op
import sqlalchemy as sa

revision = "028_project_profitability"
down_revision = "027_add_net_worth_tables"
branch_labels = None
depends_on = None


def upgrade():
    # Older tenants may already have migration 007's columns. Metadata-created
    # tenants historically omitted them, so reconcile without replacing data.
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("expenses")}
    if "project_id" not in columns:
        op.add_column("expenses", sa.Column("project_id", sa.Integer(), nullable=True))
    if "invoiced" not in columns:
        op.add_column("expenses", sa.Column("invoiced", sa.Boolean(), nullable=True, server_default=sa.false()))
    if "ix_expenses_project_id" not in {index["name"] for index in inspector.get_indexes("expenses")}:
        op.create_index("ix_expenses_project_id", "expenses", ["project_id"])

    op.create_table("contributor_cost_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("hourly_cost", sa.Numeric(19, 6), nullable=False),
        sa.Column("contributor_kind", sa.String(32), nullable=False, server_default="employee"),
        sa.UniqueConstraint("user_id", "currency", "effective_from", name="uq_contributor_cost_rate_date"),
        sa.CheckConstraint("hourly_cost >= 0", name="ck_contributor_cost_rate_nonnegative"),
        sa.CheckConstraint("contributor_kind IN ('owner', 'employee', 'subcontractor')", name="ck_contributor_cost_rate_kind"))
    op.create_index("ix_contributor_cost_rates_user_id", "contributor_cost_rates", ["user_id"])
    op.create_table("time_entry_costs",
        sa.Column("time_entry_id", sa.Integer(), sa.ForeignKey("time_entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("hourly_cost", sa.Numeric(19, 6), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("source_rate_id", sa.Integer(), sa.ForeignKey("contributor_cost_rates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("(method = 'hourly' AND hourly_cost IS NOT NULL AND hourly_cost >= 0) OR (method = 'supplier_expense' AND hourly_cost IS NULL AND source_rate_id IS NULL)", name="ck_time_entry_cost_method"),
        sa.CheckConstraint("version > 0", name="ck_time_entry_cost_version"))
    op.create_table("time_entry_cost_expenses",
        sa.Column("time_entry_id", sa.Integer(), sa.ForeignKey("time_entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("expense_id", sa.Integer(), sa.ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("project_invoice_sources",
        sa.Column("invoice_item_id", sa.Integer(), sa.ForeignKey("invoice_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("time_entry_id", sa.Integer(), sa.ForeignKey("time_entries.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("expense_id", sa.Integer(), sa.ForeignKey("expenses.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.CheckConstraint("(time_entry_id IS NOT NULL AND expense_id IS NULL) OR (time_entry_id IS NULL AND expense_id IS NOT NULL)", name="ck_project_invoice_source_exactly_one"))
    op.create_index("ix_project_invoice_sources_project_id", "project_invoice_sources", ["project_id"])


def downgrade():
    for table in ("project_invoice_sources", "time_entry_cost_expenses", "time_entry_costs", "contributor_cost_rates"):
        op.drop_table(table)
    # Expense mappings predate this migration and must survive downgrade.
