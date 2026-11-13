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
