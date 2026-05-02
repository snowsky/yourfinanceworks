from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import date
from enum import Enum


class ForecastPeriod(str, Enum):
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"
    ONE_YEAR = "365d"


class CashFlowReference(BaseModel):
    """Source record used to derive a projected cash flow entry."""
    type: str
    id: int
    label: str
    url: Optional[str] = None


class CashFlowEntry(BaseModel):
    """A single projected cash flow entry (inflow or outflow)."""
    date: date
    amount: float
    type: str = Field(..., description="'inflow' or 'outflow'")
    category: str = Field(..., description="Source category (e.g., 'invoice', 'recurring_invoice', 'expense', 'recurring_expense')")
    description: Optional[str] = None
    reference_id: Optional[int] = None
    confidence: float = Field(default=1.0, description="Confidence level 0.0-1.0 for predicted entries")
    source: str = Field(default="unknown", description="Machine-readable projection source")
    source_label: str = Field(default="Unknown source", description="Human-readable projection source")
    source_details: Optional[str] = Field(default=None, description="Short explanation of how this entry was derived")
    references: List[CashFlowReference] = Field(
        default_factory=list,
        description="Source records that explain or support this projection",
    )


class DailyBalance(BaseModel):
    """Projected balance for a specific day."""
    date: date
    projected_inflows: float
    projected_outflows: float
    net_change: float
    projected_balance: float


class CashFlowForecastResponse(BaseModel):
    """Response for cash flow forecast endpoint."""
    period: str
    start_date: date
    end_date: date
    current_balance: float
    projected_end_balance: float
    total_projected_inflows: float
    total_projected_outflows: float
    net_change: float
    daily_balances: List[DailyBalance]
    inflow_entries: List[CashFlowEntry]
    outflow_entries: List[CashFlowEntry]
    alerts: List[str] = Field(default_factory=list)


class CashRunwayResponse(BaseModel):
    """Response for cash runway calculator."""
    current_balance: float
    average_daily_burn: float
    average_daily_income: float
    net_daily_burn: float
    runway_days: Optional[int] = Field(None, description="Days until cash runs out. None if net positive.")
    runway_date: Optional[date] = Field(None, description="Projected date when cash runs out.")
    is_sustainable: bool = Field(..., description="True if income exceeds expenses")
    monthly_burn_rate: float
    monthly_income_rate: float


class ScenarioInput(BaseModel):
    """Input for what-if scenario modeling."""
    description: str = Field(..., description="Description of the scenario")
    delayed_invoice_ids: Optional[List[int]] = Field(default=None, description="Invoice IDs that would be delayed")
    delay_days: Optional[int] = Field(default=30, ge=0, description="Number of days to delay")
    additional_expense: Optional[float] = Field(default=None, ge=0, description="Additional one-time expense")
    additional_expense_date: Optional[date] = Field(default=None, description="Date of additional expense")
    revenue_change_percent: Optional[float] = Field(default=None, ge=-100, description="Percentage change in projected revenue")
    expense_change_percent: Optional[float] = Field(default=None, ge=-100, description="Percentage change in projected expenses")

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description must not be blank")
        return value


class ScenarioResult(BaseModel):
    """Result of a what-if scenario analysis."""
    scenario_description: str
    baseline_end_balance: float
    scenario_end_balance: float
    balance_impact: float
    lowest_balance: float
    lowest_balance_date: Optional[date] = None
    days_below_threshold: int = 0
    alerts: List[str] = Field(default_factory=list)
    daily_balances: List[DailyBalance]


class CashFlowThresholdSettings(BaseModel):
    """Settings for cash flow alert thresholds."""
    safety_threshold: float = Field(default=10000.0, ge=0, description="Alert when balance drops below this amount")
    warning_threshold: float = Field(default=25000.0, ge=0, description="Warning when balance approaches this amount")
    currency: str = Field(default="USD", description="Currency for thresholds")
    include_outstanding_invoices: bool = True
    include_recurring_invoices: bool = True
    include_upcoming_expenses: bool = True
    include_historical_averages: bool = True
    include_bank_statement_patterns: bool = True
    bank_statement_lookback_days: int = Field(default=120, ge=30, le=365)
    bank_statement_min_occurrences: int = Field(default=2, ge=2, le=12)
    bank_statement_intervals: List[int] = Field(default_factory=lambda: [7, 14, 30, 90])
    bank_statement_inflow_categories: List[str] = Field(default_factory=list)
    bank_statement_outflow_categories: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def warning_must_not_be_below_safety(self) -> "CashFlowThresholdSettings":
        if self.warning_threshold < self.safety_threshold:
            raise ValueError("warning_threshold must be greater than or equal to safety_threshold")
        return self

    @field_validator("bank_statement_intervals")
    @classmethod
    def intervals_must_be_supported(cls, value: List[int]) -> List[int]:
        supported = {7, 14, 30, 90}
        cleaned = sorted(set(value))
        if not cleaned:
            raise ValueError("at least one bank statement interval must be selected")
        if any(interval not in supported for interval in cleaned):
            raise ValueError("bank statement intervals must be one of 7, 14, 30, or 90 days")
        return cleaned

    @field_validator("bank_statement_inflow_categories", "bank_statement_outflow_categories")
    @classmethod
    def normalize_categories(cls, value: List[str]) -> List[str]:
        seen = set()
        normalized = []
        for item in value:
            cleaned = item.strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                normalized.append(cleaned)
        return normalized


class CashFlowThresholdUpdate(BaseModel):
    """Update request for cash flow thresholds."""
    safety_threshold: Optional[float] = Field(default=None, ge=0)
    warning_threshold: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = None
    include_outstanding_invoices: Optional[bool] = None
    include_recurring_invoices: Optional[bool] = None
    include_upcoming_expenses: Optional[bool] = None
    include_historical_averages: Optional[bool] = None
    include_bank_statement_patterns: Optional[bool] = None
    bank_statement_lookback_days: Optional[int] = Field(default=None, ge=30, le=365)
    bank_statement_min_occurrences: Optional[int] = Field(default=None, ge=2, le=12)
    bank_statement_intervals: Optional[List[int]] = None
    bank_statement_inflow_categories: Optional[List[str]] = None
    bank_statement_outflow_categories: Optional[List[str]] = None


class CashFlowAlertResponse(BaseModel):
    """Response for cash flow alerts check."""
    has_alerts: bool
    alerts: List[str]
    current_balance: float
    safety_threshold: float
    warning_threshold: float
    days_until_threshold_breach: Optional[int] = None
    breach_date: Optional[date] = None
