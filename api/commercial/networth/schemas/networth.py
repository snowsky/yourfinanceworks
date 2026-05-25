"""Pydantic request/response models for net-worth aggregation."""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


LiabilityKindLiteral = Literal["credit_card", "loan", "mortgage", "other"]
AccountKindLiteral = Literal["bank", "investment", "liability"]


class LiabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: LiabilityKindLiteral
    balance: float
    currency: str
    interest_rate: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LiabilityCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: LiabilityKindLiteral = "other"
    balance: float = Field(ge=0.0)
    currency: str = "USD"
    interest_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    notes: Optional[str] = None


class LiabilityUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    kind: Optional[LiabilityKindLiteral] = None
    balance: Optional[float] = Field(default=None, ge=0.0)
    currency: Optional[str] = None
    interest_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    notes: Optional[str] = None


class AccountBalanceResponse(BaseModel):
    account_kind: AccountKindLiteral
    label: str
    balance: float
    currency: str
    account_ref: Optional[int] = None


class NetWorthSummaryResponse(BaseModel):
    snapshot_date: Optional[date] = None
    total_assets: float
    total_liabilities: float
    net_worth: float
    bank_total: float
    investment_total: float
    liability_total: float
    accounts: List[AccountBalanceResponse] = Field(default_factory=list)


class SnapshotResponse(BaseModel):
    snapshot_date: date
    rows_written: int
    summary: NetWorthSummaryResponse


class HistoryPointResponse(BaseModel):
    snapshot_date: date
    total_assets: float
    total_liabilities: float
    net_worth: float


class HistoryResponse(BaseModel):
    points: List[HistoryPointResponse] = Field(default_factory=list)
