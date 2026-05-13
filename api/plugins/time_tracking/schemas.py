"""
Time Tracking Plugin — Pydantic Schemas

Covers:
  - Project CRUD schemas
  - ProjectTask CRUD schemas
  - TimeEntry CRUD schemas (with computed `hours` field)
  - Timer request/response schemas
  - Project summary and unbilled items schemas
  - Monthly export filter / row schemas
"""

from __future__ import annotations
from typing import Any, Dict, Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------

class ProjectBase(BaseModel):
    client_id: int
    name: str
    description: Optional[str] = None
    billing_method: str = "hourly"   # 'hourly' | 'fixed_cost'
    hourly_rate: Optional[float] = None
    fixed_amount: Optional[float] = None
    budget_hours: Optional[float] = None
    budget_amount: Optional[float] = None
    status: str = "active"
    currency: str = "USD"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    client_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    billing_method: Optional[str] = None
    hourly_rate: Optional[float] = None
    fixed_amount: Optional[float] = None
    budget_hours: Optional[float] = None
    budget_amount: Optional[float] = None
    status: Optional[str] = None
    currency: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # Enriched fields (joined in the router)
    client_name: Optional[str] = None
    total_hours_logged: Optional[float] = None
    total_amount_logged: Optional[float] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ProjectTask schemas
# ---------------------------------------------------------------------------

class ProjectTaskBase(BaseModel):
    name: str
    description: Optional[str] = None
    estimated_hours: Optional[float] = None
    hourly_rate: Optional[float] = None
    status: str = "active"
    kanban_status: str = "todo"
    kanban_position: int = 0
    priority: Optional[str] = None
    due_date: Optional[date] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class ProjectTaskCreate(ProjectTaskBase):
    project_id: int


class ProjectTaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    estimated_hours: Optional[float] = None
    hourly_rate: Optional[float] = None
    status: Optional[str] = None
    kanban_status: Optional[str] = None
    kanban_position: Optional[int] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    custom_fields: Optional[Dict[str, Any]] = None


class ProjectTaskResponse(ProjectTaskBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    # Enriched
    actual_hours: Optional[float] = None

    model_config = {"from_attributes": True}


class KanbanColumnBase(BaseModel):
    key: str
    name: str
    position: int = 0
    hidden: bool = False


class KanbanColumnUpdate(BaseModel):
    id: Optional[int] = None
    key: str
    name: str
    position: int = 0
    hidden: bool = False


class KanbanColumnResponse(KanbanColumnBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectCustomFieldBase(BaseModel):
    key: str
    name: str
    field_type: str = "text"
    options: List[str] = Field(default_factory=list)
    required: bool = False
    position: int = 0


class ProjectCustomFieldCreate(ProjectCustomFieldBase):
    pass


class ProjectCustomFieldUpdate(BaseModel):
    key: Optional[str] = None
    name: Optional[str] = None
    field_type: Optional[str] = None
    options: Optional[List[str]] = None
    required: Optional[bool] = None
    position: Optional[int] = None


class ProjectCustomFieldResponse(ProjectCustomFieldBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KanbanTaskMove(BaseModel):
    task_id: int
    kanban_status: str
    kanban_position: int


class KanbanReorderRequest(BaseModel):
    tasks: List[KanbanTaskMove]


class ProjectKanbanResponse(BaseModel):
    project: ProjectResponse
    columns: List[KanbanColumnResponse]
    tasks: List[ProjectTaskResponse]
    custom_fields: List[ProjectCustomFieldResponse]


# ---------------------------------------------------------------------------
# TimeEntry schemas
# ---------------------------------------------------------------------------

class TimeEntryBase(BaseModel):
    project_id: int
    task_id: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    hourly_rate: float
    billable: bool = True


class TimeEntryCreate(TimeEntryBase):
    """
    For manual log: provide started_at + ended_at OR started_at + duration_minutes.
    For timer start: provide only started_at (ended_at is None, status='in_progress').
    """
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class TimeEntryUpdate(BaseModel):
    task_id: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    hourly_rate: Optional[float] = None
    billable: Optional[bool] = None
    status: Optional[str] = None


class TimeEntryResponse(TimeEntryBase):
    id: int
    user_id: int
    client_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    amount: Optional[float] = None
    status: str
    invoiced: bool
    invoice_id: Optional[int] = None
    invoice_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Computed
    hours: float = 0.0

    # Enriched
    project_name: Optional[str] = None
    task_name: Optional[str] = None
    client_name: Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_hours(self) -> "TimeEntryResponse":
        if self.duration_minutes is not None:
            self.hours = round(self.duration_minutes / 60.0, 4)
        return self


# ---------------------------------------------------------------------------
# Timer schemas
# ---------------------------------------------------------------------------

class TimerStartRequest(BaseModel):
    project_id: int
    task_id: Optional[int] = None
    description: Optional[str] = None
    hourly_rate: float
    billable: bool = True
    started_at: Optional[datetime] = None  # defaults to now() if omitted


class TimerStopRequest(BaseModel):
    notes: Optional[str] = None
    ended_at: Optional[datetime] = None  # defaults to now() if omitted


class TimerActiveResponse(BaseModel):
    """Returns the currently running timer, or null if none."""
    active: bool
    entry: Optional[TimeEntryResponse] = None
    elapsed_seconds: Optional[int] = None  # server-computed seconds since started_at


# ---------------------------------------------------------------------------
# Project summary & unbilled
# ---------------------------------------------------------------------------

class ProjectSummaryResponse(BaseModel):
    project_id: int
    project_name: str
    client_id: int
    client_name: Optional[str] = None
    status: str
    billing_method: str
    budget_hours: Optional[float] = None
    budget_amount: Optional[float] = None
    total_hours_logged: float = 0.0
    total_amount_logged: float = 0.0
    total_expenses: float = 0.0
    unbilled_hours: float = 0.0
    unbilled_amount: float = 0.0
    hours_used_pct: Optional[float] = None
    budget_used_pct: Optional[float] = None


class UnbilledTimeEntry(BaseModel):
    id: int
    task_name: Optional[str] = None
    description: Optional[str] = None
    started_at: datetime
    hours: float
    hourly_rate: float
    amount: float
    billable: bool

    model_config = {"from_attributes": True}


class UnbilledExpense(BaseModel):
    id: int
    category: Optional[str] = None
    vendor: Optional[str] = None
    expense_date: str
    amount: float
    currency: Optional[str] = None

    model_config = {"from_attributes": True}


class UnbilledItemsResponse(BaseModel):
    project_id: int
    time_entries: List[UnbilledTimeEntry] = []
    expenses: List[UnbilledExpense] = []
    total_time_amount: float = 0.0
    total_expense_amount: float = 0.0
    grand_total: float = 0.0


class ProjectInvoiceRequest(BaseModel):
    """Request body to generate an invoice from unbilled items."""
    time_entry_ids: List[int] = []
    expense_ids: List[int] = []
    due_date: Optional[str] = None   # ISO date string, e.g. "2026-04-01"
    notes: Optional[str] = None


class ProjectInvoiceResponse(BaseModel):
    invoice_id: int
    invoice_number: str
    amount: float
    currency: str


# ---------------------------------------------------------------------------
# Monthly export
# ---------------------------------------------------------------------------

class TimeExportFilters(BaseModel):
    year: int
    month: int  # 1-12
    project_id: Optional[int] = None
    client_id: Optional[int] = None
    user_id: Optional[int] = None
    billable_only: bool = False


class TimeExportRow(BaseModel):
    """Mirrors one row in the 'Time Log' Excel sheet."""
    date: str                       # YYYY-MM-DD
    client_id: int
    client_name: str
    project_name: str
    task_name: Optional[str]
    description: Optional[str]
    notes: Optional[str]
    hours: float
    hourly_rate: float
    amount: float
    billable: bool
    status: str
    invoiced: bool
    invoice_number: Optional[str]


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

class TimeImportError(BaseModel):
    row: int
    message: str


class TimeImportResponse(BaseModel):
    created_clients: int = 0
    created_projects: int = 0
    reused_projects: int = 0
    created_tasks: int = 0
    created_time_entries: int = 0
    skipped_rows: int = 0
    ai_used: bool = False
    errors: List[TimeImportError] = []
