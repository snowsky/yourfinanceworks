"""Admin-only cost contracts, deliberately separate from ordinary time schemas."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictCostModel(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)


class CostRateWrite(StrictCostModel):
    user_id: int = Field(gt=0)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    effective_from: date
    hourly_cost: Decimal = Field(ge=0, max_digits=19, decimal_places=6, allow_inf_nan=False)
    contributor_kind: Literal['owner', 'employee', 'subcontractor'] = 'employee'


class CostRateResponse(CostRateWrite):
    id: int


class CostBackfillRequest(StrictCostModel):
    entry_ids: list[int] = Field(min_length=1, max_length=1000)


class CostBackfillEntry(StrictCostModel):
    entry_id: int
    work_date: date
    duration_minutes: int | None
    entry_version: str
    status: str
    user_id: int
    cost_version: int | None
    source_rate_id: int | None
    hourly_cost: Decimal | None
    currency: str
    before_cost: Decimal | None
    after_cost: Decimal | None


class CostBackfillPreview(StrictCostModel):
    project_id: int
    entry_ids: list[int]
    entries: list[CostBackfillEntry]
    before_total: Decimal
    after_total: Decimal
    fingerprint: str


class CostBackfillResult(StrictCostModel):
    applied_entry_ids: list[int]


class EntryCostReplacement(StrictCostModel):
    method: Literal['hourly', 'supplier_expense']
    expense_ids: list[int] = Field(default_factory=list, max_length=1000)


class EntryCostResponse(StrictCostModel):
    time_entry_id: int
    method: Literal['hourly', 'supplier_expense']
    hourly_cost: Decimal | None
    currency: str
    source_rate_id: int | None
    version: int


class ProfitabilityEntry(StrictCostModel):
    id: int
    user_id: int
    task_id: int | None = None
    status: str
    duration_minutes: int | None
    billable: bool
    hourly_rate: Decimal | None
    cost_method: str | None = None
    hourly_cost: Decimal | None = None
    cost_currency: str | None = None
    expense_ids: list[int] = Field(default_factory=list)


class ProfitabilityExpense(StrictCostModel):
    id: int
    project_id: int | None
    amount: Decimal | None
    currency: str
    status: str
    is_deleted: bool = False
    approval_statuses: list[str] = Field(default_factory=list)
    imported_from_attachment: bool = False
    analysis_status: str = 'not_started'
    manual_override: bool = False


class ProjectProfitabilityInput(StrictCostModel):
    project_id: int
    currency: str
    billing_method: str
    decimal_places: int = Field(default=2, ge=0, le=6)
    budget_hours: Decimal | None = None
    budget_amount: Decimal | None = None
    entries: list[ProfitabilityEntry] = Field(default_factory=list)
    expenses: list[ProfitabilityExpense] = Field(default_factory=list)


class ProfitabilityRecord(StrictCostModel):
    record_type: Literal['time_entry', 'expense']
    record_id: int
    reason: str


class ProfitabilityBreakdown(StrictCostModel):
    id: int | None
    completed_hours: Decimal = Decimal(0)
    hourly_cost: Decimal = Decimal(0)
    entry_ids: list[int] = Field(default_factory=list)
    supplier_expense_ids: list[int] = Field(default_factory=list)


class ProjectExpenseBucket(StrictCostModel):
    amount: Decimal = Decimal(0)
    expense_ids: list[int] = Field(default_factory=list)
    cost_basis: Literal['amount'] = 'amount'


class ProjectProfitabilityResponse(StrictCostModel):
    project_id: int
    currency: str
    status: Literal['complete', 'incomplete', 'unsupported_billing_method']
    work_value: Decimal = Decimal(0)
    known_cost: Decimal = Decimal(0)
    contribution: Decimal | None = None
    margin_percent: Decimal | None = None
    completed_hours: Decimal = Decimal(0)
    billable_hours: Decimal = Decimal(0)
    nonbillable_hours: Decimal = Decimal(0)
    missing_hours: Decimal = Decimal(0)
    unresolved_records: list[ProfitabilityRecord] = Field(default_factory=list)
    excluded_records: list[ProfitabilityRecord] = Field(default_factory=list)
    contributors: list[ProfitabilityBreakdown] = Field(default_factory=list)
    tasks: list[ProfitabilityBreakdown] = Field(default_factory=list)
    expense_bucket: ProjectExpenseBucket = Field(default_factory=ProjectExpenseBucket)
    hours_budget_percent: Decimal | None = None
    amount_budget_percent: Decimal | None = None
    budget_warnings: list[str] = Field(default_factory=list)
