"""
Cash Flow Forecasting Router

Provides endpoints for:
- Cash flow projections (7/30/90 day views)
- Cash runway calculator
- What-if scenario modeling
- Cash flow alerts and threshold management
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.utils.feature_gate import require_feature
from core.schemas.cashflow import (
    CashFlowForecastResponse,
    CashRunwayResponse,
    CashFlowThresholdSettings,
    CashFlowThresholdUpdate,
    CashFlowAlertResponse,
    ScenarioInput,
    ScenarioResult,
    ForecastPeriod,
)
from core.services.cashflow_service import CashFlowService

router = APIRouter(
    prefix="/cashflow",
    tags=["cashflow"],
)


@router.get("/forecast", response_model=CashFlowForecastResponse)
@require_feature("cash_flow")
async def get_cash_flow_forecast(
    period: ForecastPeriod = ForecastPeriod.THIRTY_DAYS,
    current_balance: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Get cash flow forecast for the specified period.

    - **period**: Forecast period - '7d', '30d', '90d', or '365d'
    - **current_balance**: Optional override for starting balance
    """
    service = CashFlowService(db)
    return service.get_forecast(period=period.value, current_balance=current_balance)


@router.get("/runway", response_model=CashRunwayResponse)
@require_feature("cash_flow")
async def get_cash_runway(
    current_balance: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Calculate cash runway - how long current reserves will last.

    Uses last 90 days of historical data to project burn rate.
    """
    service = CashFlowService(db)
    return service.get_runway(current_balance=current_balance)


@router.post("/scenario", response_model=ScenarioResult)
@require_feature("cash_flow")
async def run_scenario(
    scenario: ScenarioInput,
    period: ForecastPeriod = ForecastPeriod.THIRTY_DAYS,
    current_balance: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Run a what-if scenario analysis.

    Model scenarios like:
    - What if specific invoices are paid late?
    - What if we have an unexpected expense?
    - What if revenue changes by X%?
    """
    service = CashFlowService(db)
    return service.run_scenario(
        scenario=scenario, period=period.value, current_balance=current_balance
    )


@router.get("/alerts", response_model=CashFlowAlertResponse)
@require_feature("cash_flow")
async def get_cash_flow_alerts(
    current_balance: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Check for cash flow alerts based on configured thresholds.

    Returns alerts if current or projected balance drops below
    safety or warning thresholds.
    """
    service = CashFlowService(db)
    return service.get_alerts(current_balance=current_balance)


@router.get("/settings/thresholds", response_model=CashFlowThresholdSettings)
@require_feature("cash_flow")
async def get_threshold_settings(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get current cash flow alert threshold settings."""
    service = CashFlowService(db)
    return service.get_threshold_settings()


@router.put("/settings/thresholds", response_model=CashFlowThresholdSettings)
@require_feature("cash_flow")
async def update_threshold_settings(
    update: CashFlowThresholdUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Update cash flow alert threshold settings.

    - **safety_threshold**: Critical alert level
    - **warning_threshold**: Warning alert level
    """
    service = CashFlowService(db)
    return service.update_threshold_settings(
        safety_threshold=update.safety_threshold,
        warning_threshold=update.warning_threshold,
        currency=update.currency,
        include_outstanding_invoices=update.include_outstanding_invoices,
        include_recurring_invoices=update.include_recurring_invoices,
        include_upcoming_expenses=update.include_upcoming_expenses,
        include_historical_averages=update.include_historical_averages,
        include_bank_statement_patterns=update.include_bank_statement_patterns,
        bank_statement_lookback_days=update.bank_statement_lookback_days,
        bank_statement_min_occurrences=update.bank_statement_min_occurrences,
        bank_statement_intervals=update.bank_statement_intervals,
        bank_statement_inflow_categories=update.bank_statement_inflow_categories,
        bank_statement_outflow_categories=update.bank_statement_outflow_categories,
    )
