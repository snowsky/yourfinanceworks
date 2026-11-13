"""Private cost and invoice provenance tables; never serialize through time APIs."""
from sqlalchemy import (
    CheckConstraint, Column, Date, ForeignKey, Integer, Numeric, String,
    UniqueConstraint, DateTime, JSON,
)
from core.models.models_per_tenant import Base


class ContributorCostRate(Base):
    __tablename__ = "contributor_cost_rates"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    currency = Column(String(3), nullable=False)
    effective_from = Column(Date, nullable=False)
    hourly_cost = Column(Numeric(19, 6), nullable=False)
    contributor_kind = Column(String(32), nullable=False, default="employee", server_default="employee")
    __table_args__ = (
        UniqueConstraint("user_id", "currency", "effective_from", name="uq_contributor_cost_rate_date"),
        CheckConstraint("hourly_cost >= 0", name="ck_contributor_cost_rate_nonnegative"),
        CheckConstraint("contributor_kind IN ('owner', 'employee', 'subcontractor')", name="ck_contributor_cost_rate_kind"),
    )


class TimeEntryCost(Base):
    __tablename__ = "time_entry_costs"
    time_entry_id = Column(Integer, ForeignKey("time_entries.id", ondelete="CASCADE"), primary_key=True)
    method = Column(String(32), nullable=False)
    hourly_cost = Column(Numeric(19, 6), nullable=True)
    currency = Column(String(3), nullable=False)
    source_rate_id = Column(Integer, ForeignKey("contributor_cost_rates.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    __table_args__ = (
        CheckConstraint("(method = 'hourly' AND hourly_cost IS NOT NULL AND hourly_cost >= 0) OR (method = 'supplier_expense' AND hourly_cost IS NULL AND source_rate_id IS NULL)", name="ck_time_entry_cost_method"),
        CheckConstraint("version > 0", name="ck_time_entry_cost_version"),
    )


class TimeEntryCostExpense(Base):
    __tablename__ = "time_entry_cost_expenses"
    time_entry_id = Column(Integer, ForeignKey("time_entries.id", ondelete="CASCADE"), primary_key=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True)


class ProjectInvoiceSource(Base):
    __tablename__ = "project_invoice_sources"
    invoice_item_id = Column(Integer, ForeignKey("invoice_items.id", ondelete="CASCADE"), primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    time_entry_id = Column(Integer, ForeignKey("time_entries.id", ondelete="RESTRICT"), nullable=True, unique=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="RESTRICT"), nullable=True, unique=True)
    snapshot = Column(JSON, nullable=True)
    __table_args__ = (
        CheckConstraint("(time_entry_id IS NOT NULL AND expense_id IS NULL) OR (time_entry_id IS NULL AND expense_id IS NOT NULL)", name="ck_project_invoice_source_exactly_one"),
    )


class TimeEntryCostRevision(Base):
    """Sensitive prior snapshots; accessible only through protected cost routes."""
    __tablename__ = "time_entry_cost_revisions"
    id = Column(Integer, primary_key=True)
    time_entry_id = Column(Integer, ForeignKey("time_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    snapshot = Column(JSON, nullable=False)


class ProjectInvoiceLink(Base):
    """Durable discovery even after every invoice line/source link is removed."""
    __tablename__ = 'project_invoice_links'
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='RESTRICT'), primary_key=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id', ondelete='CASCADE'), primary_key=True)
