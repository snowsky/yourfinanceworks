from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class ForecastPeriod(str, Enum):
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"


class CashFlowEntry(BaseModel):
    """A single projected cash flow entry (inflow or outflow)."""
    date: date
    amount: float
    type: str = Field(..., description="'inflow' or 'outflow'")
    category: str = Field(..., description="Source category (e.g., 'invoice', 'recurring_invoice', 'expense', 'recurring_expense')")
    description: Optional[str] = None
    reference_id: Optional[int] = None
    confidence: float = Field(default=1.0, description="Confidence level 0.0-1.0 for predicted entries")


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
    delay_days: Optional[int] = Field(default=30, description="Number of days to delay")
    additional_expense: Optional[float] = Field(default=None, description="Additional one-time expense")
    additional_expense_date: Optional[date] = Field(default=None, description="Date of additional expense")
    revenue_change_percent: Optional[float] = Field(default=None, description="Percentage change in projected revenue (-50 to +100)")
    expense_change_percent: Optional[float] = Field(default=None, description="Percentage change in projected expenses (-50 to +100)")


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
    safety_threshold: float = Field(default=10000.0, description="Alert when balance drops below this amount")
    warning_threshold: float = Field(default=25000.0, description="Warning when balance approaches this amount")
    currency: str = Field(default="USD", description="Currency for thresholds")


class CashFlowThresholdUpdate(BaseModel):
    """Update request for cash flow thresholds."""
    safety_threshold: Optional[float] = None
    warning_threshold: Optional[float] = None
    currency: Optional[str] = None


class CashFlowAlertResponse(BaseModel):
    """Response for cash flow alerts check."""
    has_alerts: bool
    alerts: List[str]
    current_balance: float
    safety_threshold: float
    warning_threshold: float
    days_until_threshold_breach: Optional[int] = None
    breach_date: Optional[date] = None
