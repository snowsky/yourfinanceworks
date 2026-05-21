"""Pure calculation helpers for the cash flow service.

Date math, balance projection, scenario mutation, and alert generation. None
of these need DB access or service state, so they live here as plain module
functions to keep :mod:`cashflow_service` focused on the request pipeline.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

from dateutil.relativedelta import relativedelta

from core.schemas.cashflow import (
    CashFlowEntry,
    CashFlowThresholdSettings,
    DailyBalance,
)

# Interval (in days) between historical pattern-based prediction entries.
HISTORICAL_PATTERN_INTERVAL_DAYS = 7


def calculate_daily_balances(
    starting_balance: float,
    start_date: date,
    end_date: date,
    inflows: List[CashFlowEntry],
    outflows: List[CashFlowEntry],
) -> List[DailyBalance]:
    """Calculate projected balance for each day in the period."""
    daily_balances = []
    running_balance = starting_balance

    current = start_date
    while current <= end_date:
        day_inflows = sum(e.amount for e in inflows if e.date == current)
        day_outflows = sum(e.amount for e in outflows if e.date == current)
        net = day_inflows - day_outflows
        running_balance += net

        daily_balances.append(
            DailyBalance(
                date=current,
                projected_inflows=day_inflows,
                projected_outflows=day_outflows,
                net_change=net,
                projected_balance=running_balance,
            )
        )
        current += timedelta(days=1)

    return daily_balances


def predict_recurring_dates(
    frequency: Optional[str],
    start_from: datetime,
    period_start: date,
    period_end: date,
) -> List[date]:
    """Predict future dates for a recurring item based on its frequency.

    Uses calendar-aware offsets (relativedelta) for monthly/quarterly/annual
    frequencies so a 28th-of-the-month invoice keeps its anchor day instead
    of drifting backward each iteration.
    """
    if not frequency or not start_from:
        return []

    freq_offsets = {
        "weekly": relativedelta(weeks=1),
        "biweekly": relativedelta(weeks=2),
        "monthly": relativedelta(months=1),
        "quarterly": relativedelta(months=3),
        "annually": relativedelta(years=1),
        "yearly": relativedelta(years=1),
    }

    offset = freq_offsets.get(frequency.lower(), relativedelta(months=1))
    ref_date = start_from.date() if isinstance(start_from, datetime) else start_from

    dates: List[date] = []
    current = ref_date
    while current <= period_end:
        current = current + offset
        if period_start <= current <= period_end:
            dates.append(current)

    return dates


def historical_pattern_interval_days(current: date, end_date: date) -> int:
    """Return how many days a weekly historical pattern entry represents."""
    remaining_days = (end_date - current).days + 1
    return max(1, min(HISTORICAL_PATTERN_INTERVAL_DAYS, remaining_days))


def apply_invoice_delays(
    inflows: List[CashFlowEntry],
    invoice_ids: List[int],
    delay_days: int,
    end_date: date,
) -> List[CashFlowEntry]:
    """Apply delays to specific invoices in the inflow list."""
    result = []
    for entry in inflows:
        if entry.reference_id in invoice_ids and entry.category == "invoice":
            new_date = entry.date + timedelta(days=delay_days)
            if new_date <= end_date:
                result.append(
                    CashFlowEntry(
                        date=new_date,
                        amount=entry.amount,
                        type=entry.type,
                        category=entry.category,
                        description=f"{entry.description} (delayed {delay_days}d)",
                        reference_id=entry.reference_id,
                        confidence=entry.confidence * 0.6,
                        source=entry.source,
                        source_label=entry.source_label,
                        source_details=f"{entry.source_details or 'Projected invoice payment.'} Delayed by scenario.",
                        references=entry.references,
                    )
                )
            # If delayed beyond period, it effectively disappears from forecast
        else:
            result.append(entry)
    return result


def generate_alerts(
    daily_balances: List[DailyBalance],
    thresholds: CashFlowThresholdSettings,
) -> List[str]:
    """Generate alerts based on projected balances and thresholds."""
    alerts = []

    for daily in daily_balances:
        if daily.projected_balance < 0:
            alerts.append(f"🔴 CRITICAL: Projected negative balance on {daily.date}")
            break

    for daily in daily_balances:
        if daily.projected_balance < thresholds.safety_threshold:
            alerts.append(
                f"⚠️ Balance projected to drop below safety threshold "
                f"(${thresholds.safety_threshold:,.2f}) on {daily.date}"
            )
            break

    for daily in daily_balances:
        if daily.projected_balance < thresholds.warning_threshold:
            alerts.append(
                f"🟡 Balance projected to approach warning level "
                f"(${thresholds.warning_threshold:,.2f}) on {daily.date}"
            )
            break

    return alerts
