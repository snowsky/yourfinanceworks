"""
Cash Flow Forecasting Service

Provides predictive cash flow projections, runway calculations,
and scenario modeling based on invoices, expenses, and historical patterns.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from core.models.models_per_tenant import (
    Invoice,
    Expense,
    Payment,
    Settings,
)
from core.schemas.cashflow import (
    CashFlowEntry,
    CashFlowForecastResponse,
    CashRunwayResponse,
    DailyBalance,
    ScenarioInput,
    ScenarioResult,
    CashFlowThresholdSettings,
    CashFlowAlertResponse,
)

logger = logging.getLogger(__name__)

# Settings key for cash flow thresholds
CASHFLOW_SETTINGS_KEY = "cashflow_thresholds"

# Minimum number of concrete forecast entries before adding historical pattern predictions
MIN_CONCRETE_ENTRIES_FOR_PATTERN = 5

# Interval (in days) between historical pattern-based prediction entries
HISTORICAL_PATTERN_INTERVAL_DAYS = 7


class CashFlowService:
    """Service for cash flow forecasting and analysis."""

    def __init__(self, db: Session):
        self.db = db

    def get_current_balance(self) -> float:
        """
        Calculate current cash position based on:
        - Total payments received (inflows)
        - Total expenses paid (outflows)
        """
        # Total payments received
        total_payments = (
            self.db.query(func.coalesce(func.sum(Payment.amount), 0.0))
            .scalar()
        ) or 0.0

        # Total expenses
        total_expenses = (
            self.db.query(func.coalesce(func.sum(Expense.amount), 0.0))
            .filter(Expense.is_deleted == False)  # noqa: E712
            .filter(Expense.status != "cancelled")
            .scalar()
        ) or 0.0

        return float(total_payments) - float(total_expenses)

    def get_forecast(self, period: str = "30d", current_balance: Optional[float] = None) -> CashFlowForecastResponse:
        """
        Generate cash flow forecast for the specified period.

        Args:
            period: One of '7d', '30d', '90d'
            current_balance: Optional override for current balance
        """
        days_map = {"7d": 7, "30d": 30, "90d": 90}
        num_days = days_map.get(period, 30)

        today = date.today()
        end_date = today + timedelta(days=num_days)

        if current_balance is None:
            current_balance = self.get_current_balance()

        # Get projected inflows
        inflow_entries = self._get_projected_inflows(today, end_date)

        # Get projected outflows
        outflow_entries = self._get_projected_outflows(today, end_date)

        # Calculate daily balances
        daily_balances = self._calculate_daily_balances(
            current_balance, today, end_date, inflow_entries, outflow_entries
        )

        total_inflows = sum(e.amount for e in inflow_entries)
        total_outflows = sum(e.amount for e in outflow_entries)
        net_change = total_inflows - total_outflows
        projected_end_balance = current_balance + net_change

        # Generate alerts
        thresholds = self._get_threshold_settings()
        alerts = self._generate_alerts(daily_balances, thresholds)

        return CashFlowForecastResponse(
            period=period,
            start_date=today,
            end_date=end_date,
            current_balance=current_balance,
            projected_end_balance=projected_end_balance,
            total_projected_inflows=total_inflows,
            total_projected_outflows=total_outflows,
            net_change=net_change,
            daily_balances=daily_balances,
            inflow_entries=inflow_entries,
            outflow_entries=outflow_entries,
            alerts=alerts,
        )

    def get_runway(self, current_balance: Optional[float] = None) -> CashRunwayResponse:
        """
        Calculate cash runway - how long current reserves will last.
        Uses last 90 days of data to calculate averages.
        """
        if current_balance is None:
            current_balance = self.get_current_balance()

        # Calculate averages from last 90 days
        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

        # Average daily income (payments received)
        total_income_90d = (
            self.db.query(func.coalesce(func.sum(Payment.amount), 0.0))
            .filter(Payment.payment_date >= ninety_days_ago)
            .scalar()
        ) or 0.0

        # Average daily expenses
        total_expenses_90d = (
            self.db.query(func.coalesce(func.sum(Expense.amount), 0.0))
            .filter(Expense.is_deleted == False)  # noqa: E712
            .filter(Expense.status != "cancelled")
            .filter(Expense.expense_date >= ninety_days_ago)
            .scalar()
        ) or 0.0

        avg_daily_income = float(total_income_90d) / 90.0
        avg_daily_burn = float(total_expenses_90d) / 90.0
        net_daily_burn = avg_daily_burn - avg_daily_income

        monthly_burn_rate = avg_daily_burn * 30
        monthly_income_rate = avg_daily_income * 30

        is_sustainable = avg_daily_income >= avg_daily_burn
        runway_days = None
        runway_date = None

        if net_daily_burn > 0 and current_balance > 0:
            runway_days = int(current_balance / net_daily_burn)
            runway_date = date.today() + timedelta(days=runway_days)

        return CashRunwayResponse(
            current_balance=current_balance,
            average_daily_burn=avg_daily_burn,
            average_daily_income=avg_daily_income,
            net_daily_burn=net_daily_burn,
            runway_days=runway_days,
            runway_date=runway_date,
            is_sustainable=is_sustainable,
            monthly_burn_rate=monthly_burn_rate,
            monthly_income_rate=monthly_income_rate,
        )

    def run_scenario(
        self, scenario: ScenarioInput, period: str = "30d", current_balance: Optional[float] = None
    ) -> ScenarioResult:
        """
        Run a what-if scenario analysis.
        """
        days_map = {"7d": 7, "30d": 30, "90d": 90}
        num_days = days_map.get(period, 30)

        today = date.today()
        end_date = today + timedelta(days=num_days)

        if current_balance is None:
            current_balance = self.get_current_balance()

        # Get baseline projections
        baseline_inflows = self._get_projected_inflows(today, end_date)
        baseline_outflows = self._get_projected_outflows(today, end_date)

        # Apply scenario modifications
        scenario_inflows = list(baseline_inflows)
        scenario_outflows = list(baseline_outflows)

        # Apply delayed invoices
        if scenario.delayed_invoice_ids:
            delay_days = scenario.delay_days or 30
            scenario_inflows = self._apply_invoice_delays(
                scenario_inflows, scenario.delayed_invoice_ids, delay_days, end_date
            )

        # Apply additional expense
        if scenario.additional_expense and scenario.additional_expense_date:
            scenario_outflows.append(
                CashFlowEntry(
                    date=scenario.additional_expense_date,
                    amount=scenario.additional_expense,
                    type="outflow",
                    category="scenario_expense",
                    description=f"Scenario: {scenario.description}",
                    confidence=1.0,
                )
            )

        # Apply revenue change percent
        if scenario.revenue_change_percent is not None:
            factor = 1 + (scenario.revenue_change_percent / 100.0)
            scenario_inflows = [
                CashFlowEntry(
                    date=e.date,
                    amount=e.amount * factor,
                    type=e.type,
                    category=e.category,
                    description=e.description,
                    reference_id=e.reference_id,
                    confidence=e.confidence,
                )
                for e in scenario_inflows
            ]

        # Apply expense change percent
        if scenario.expense_change_percent is not None:
            factor = 1 + (scenario.expense_change_percent / 100.0)
            scenario_outflows = [
                CashFlowEntry(
                    date=e.date,
                    amount=e.amount * factor,
                    type=e.type,
                    category=e.category,
                    description=e.description,
                    reference_id=e.reference_id,
                    confidence=e.confidence,
                )
                for e in scenario_outflows
            ]

        # Calculate scenario daily balances
        daily_balances = self._calculate_daily_balances(
            current_balance, today, end_date, scenario_inflows, scenario_outflows
        )

        # Calculate baseline end balance
        baseline_total_inflows = sum(e.amount for e in baseline_inflows)
        baseline_total_outflows = sum(e.amount for e in baseline_outflows)
        baseline_end_balance = current_balance + baseline_total_inflows - baseline_total_outflows

        # Calculate scenario end balance
        scenario_total_inflows = sum(e.amount for e in scenario_inflows)
        scenario_total_outflows = sum(e.amount for e in scenario_outflows)
        scenario_end_balance = current_balance + scenario_total_inflows - scenario_total_outflows

        # Find lowest balance
        lowest_balance = min(db.projected_balance for db in daily_balances) if daily_balances else current_balance
        lowest_balance_date = None
        for db_entry in daily_balances:
            if db_entry.projected_balance == lowest_balance:
                lowest_balance_date = db_entry.date
                break

        # Count days below threshold
        thresholds = self._get_threshold_settings()
        days_below = sum(1 for db_entry in daily_balances if db_entry.projected_balance < thresholds.safety_threshold)

        # Generate alerts
        alerts = []
        if lowest_balance < 0:
            alerts.append(f"⚠️ Balance goes negative on {lowest_balance_date}")
        if lowest_balance < thresholds.safety_threshold:
            alerts.append(
                f"⚠️ Balance drops below safety threshold (${thresholds.safety_threshold:,.2f}) "
                f"on {lowest_balance_date}"
            )
        if days_below > 0:
            alerts.append(f"⚠️ Balance is below safety threshold for {days_below} days in this scenario")

        balance_impact = scenario_end_balance - baseline_end_balance

        return ScenarioResult(
            scenario_description=scenario.description,
            baseline_end_balance=baseline_end_balance,
            scenario_end_balance=scenario_end_balance,
            balance_impact=balance_impact,
            lowest_balance=lowest_balance,
            lowest_balance_date=lowest_balance_date,
            days_below_threshold=days_below,
            alerts=alerts,
            daily_balances=daily_balances,
        )

    def get_alerts(self, current_balance: Optional[float] = None) -> CashFlowAlertResponse:
        """Check for cash flow alerts based on threshold settings."""
        if current_balance is None:
            current_balance = self.get_current_balance()

        thresholds = self._get_threshold_settings()
        alerts = []

        # Check current balance against thresholds
        if current_balance < thresholds.safety_threshold:
            alerts.append(
                f"🔴 CRITICAL: Current balance (${current_balance:,.2f}) is below "
                f"safety threshold (${thresholds.safety_threshold:,.2f})"
            )
        elif current_balance < thresholds.warning_threshold:
            alerts.append(
                f"🟡 WARNING: Current balance (${current_balance:,.2f}) is approaching "
                f"safety threshold (${thresholds.safety_threshold:,.2f})"
            )

        # Project forward to find when threshold might be breached
        forecast = self.get_forecast("90d", current_balance)
        days_until_breach = None
        breach_date = None

        for daily in forecast.daily_balances:
            if daily.projected_balance < thresholds.safety_threshold:
                days_until_breach = (daily.date - date.today()).days
                breach_date = daily.date
                alerts.append(
                    f"⚠️ Projected to breach safety threshold in {days_until_breach} days ({breach_date})"
                )
                break

        return CashFlowAlertResponse(
            has_alerts=len(alerts) > 0,
            alerts=alerts,
            current_balance=current_balance,
            safety_threshold=thresholds.safety_threshold,
            warning_threshold=thresholds.warning_threshold,
            days_until_threshold_breach=days_until_breach,
            breach_date=breach_date,
        )

    def get_threshold_settings(self) -> CashFlowThresholdSettings:
        """Get current threshold settings."""
        return self._get_threshold_settings()

    def update_threshold_settings(
        self, safety_threshold: Optional[float] = None,
        warning_threshold: Optional[float] = None,
        currency: Optional[str] = None,
    ) -> CashFlowThresholdSettings:
        """Update cash flow threshold settings."""
        settings_row = (
            self.db.query(Settings)
            .filter(Settings.key == CASHFLOW_SETTINGS_KEY)
            .first()
        )

        current = self._get_threshold_settings()

        new_values = {
            "safety_threshold": safety_threshold if safety_threshold is not None else current.safety_threshold,
            "warning_threshold": warning_threshold if warning_threshold is not None else current.warning_threshold,
            "currency": currency if currency is not None else current.currency,
        }

        if settings_row:
            settings_row.value = new_values
        else:
            settings_row = Settings(
                key=CASHFLOW_SETTINGS_KEY,
                value=new_values,
                description="Cash flow alert threshold settings",
                category="cashflow",
                is_public=True,
            )
            self.db.add(settings_row)

        self.db.commit()

        return CashFlowThresholdSettings(**new_values)

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _get_threshold_settings(self) -> CashFlowThresholdSettings:
        """Load threshold settings from database or return defaults."""
        settings_row = (
            self.db.query(Settings)
            .filter(Settings.key == CASHFLOW_SETTINGS_KEY)
            .first()
        )

        if settings_row and settings_row.value:
            return CashFlowThresholdSettings(**settings_row.value)

        return CashFlowThresholdSettings()

    def _get_projected_inflows(self, start_date: date, end_date: date) -> List[CashFlowEntry]:
        """
        Get projected cash inflows from:
        1. Outstanding invoices (due within period)
        2. Recurring invoice patterns (predicted future invoices)
        """
        entries = []

        # 1. Outstanding invoices due within the forecast period
        outstanding_invoices = (
            self.db.query(Invoice)
            .filter(Invoice.is_deleted == False)  # noqa: E712
            .filter(Invoice.status.in_(["sent", "pending", "overdue", "partially_paid"]))
            .filter(Invoice.due_date >= datetime.combine(start_date, datetime.min.time()))
            .filter(Invoice.due_date <= datetime.combine(end_date, datetime.max.time()))
            .all()
        )

        for inv in outstanding_invoices:
            paid_amount = inv.paid_amount if hasattr(inv, 'paid_amount') else 0.0
            remaining = inv.amount - paid_amount
            if remaining > 0:
                inv_due_date = inv.due_date.date() if isinstance(inv.due_date, datetime) else inv.due_date
                entries.append(
                    CashFlowEntry(
                        date=inv_due_date,
                        amount=remaining,
                        type="inflow",
                        category="invoice",
                        description=f"Invoice {inv.number}",
                        reference_id=inv.id,
                        confidence=0.8,  # Not guaranteed to be paid on time
                    )
                )

        # 2. Recurring invoices - predict future occurrences
        recurring_invoices = (
            self.db.query(Invoice)
            .filter(Invoice.is_deleted == False)  # noqa: E712
            .filter(Invoice.is_recurring == True)  # noqa: E712
            .filter(Invoice.status != "cancelled")
            .all()
        )

        for inv in recurring_invoices:
            predicted_dates = self._predict_recurring_dates(
                inv.recurring_frequency, inv.created_at, start_date, end_date
            )
            for pred_date in predicted_dates:
                entries.append(
                    CashFlowEntry(
                        date=pred_date,
                        amount=inv.amount,
                        type="inflow",
                        category="recurring_invoice",
                        description=f"Recurring: {inv.number}",
                        reference_id=inv.id,
                        confidence=0.7,
                    )
                )

        # 3. Historical pattern-based prediction (average daily income from last 90 days)
        # Only add if we have few concrete entries to fill gaps
        if len(entries) < MIN_CONCRETE_ENTRIES_FOR_PATTERN:
            avg_daily = self._get_historical_average_daily_income()
            if avg_daily > 0:
                current = start_date + timedelta(days=1)
                while current <= end_date:
                    # Only add for days without existing entries
                    if not any(e.date == current for e in entries):
                        entries.append(
                            CashFlowEntry(
                                date=current,
                                amount=avg_daily,
                                type="inflow",
                                category="historical_pattern",
                                description="Based on historical average",
                                confidence=0.4,
                            )
                        )
                    current += timedelta(days=HISTORICAL_PATTERN_INTERVAL_DAYS)

        return sorted(entries, key=lambda e: e.date)

    def _get_projected_outflows(self, start_date: date, end_date: date) -> List[CashFlowEntry]:
        """
        Get projected cash outflows from:
        1. Known upcoming expenses
        2. Recurring expense patterns
        3. Historical average spending
        """
        entries = []

        # 1. Known upcoming expenses (future-dated or pending)
        upcoming_expenses = (
            self.db.query(Expense)
            .filter(Expense.is_deleted == False)  # noqa: E712
            .filter(Expense.status.in_(["pending", "approved", "recorded"]))
            .filter(Expense.expense_date >= datetime.combine(start_date, datetime.min.time()))
            .filter(Expense.expense_date <= datetime.combine(end_date, datetime.max.time()))
            .all()
        )

        for exp in upcoming_expenses:
            exp_date = exp.expense_date.date() if isinstance(exp.expense_date, datetime) else exp.expense_date
            amount = exp.amount or 0.0
            if amount > 0:
                entries.append(
                    CashFlowEntry(
                        date=exp_date,
                        amount=amount,
                        type="outflow",
                        category="expense",
                        description=f"{exp.category}: {exp.vendor or 'Unknown'}",
                        reference_id=exp.id,
                        confidence=0.9,
                    )
                )

        # 2. Historical expense pattern - predict recurring expenses
        avg_daily_expense = self._get_historical_average_daily_expense()
        if avg_daily_expense > 0:
            # Fill in with weekly averages for days without concrete entries
            current = start_date + timedelta(days=1)
            while current <= end_date:
                day_total = sum(e.amount for e in entries if e.date == current)
                if day_total == 0:
                    entries.append(
                        CashFlowEntry(
                            date=current,
                            amount=avg_daily_expense,
                            type="outflow",
                            category="historical_pattern",
                            description="Based on historical average",
                            confidence=0.4,
                        )
                    )
                current += timedelta(days=HISTORICAL_PATTERN_INTERVAL_DAYS)

        return sorted(entries, key=lambda e: e.date)

    def _calculate_daily_balances(
        self,
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

    def _predict_recurring_dates(
        self, frequency: Optional[str], start_from: datetime, period_start: date, period_end: date
    ) -> List[date]:
        """Predict future dates for a recurring item based on its frequency."""
        if not frequency or not start_from:
            return []

        freq_days = {
            "weekly": 7,
            "biweekly": 14,
            "monthly": 30,
            "quarterly": 90,
            "annually": 365,
            "yearly": 365,
        }

        interval = freq_days.get(frequency.lower(), 30)
        dates = []
        ref_date = start_from.date() if isinstance(start_from, datetime) else start_from

        # Project forward from the original start date
        current = ref_date
        while current <= period_end:
            current += timedelta(days=interval)
            if period_start <= current <= period_end:
                dates.append(current)

        return dates

    def _get_historical_average_daily_income(self) -> float:
        """Calculate average daily income from the last 90 days."""
        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

        total = (
            self.db.query(func.coalesce(func.sum(Payment.amount), 0.0))
            .filter(Payment.payment_date >= ninety_days_ago)
            .scalar()
        ) or 0.0

        return float(total) / 90.0

    def _get_historical_average_daily_expense(self) -> float:
        """Calculate average daily expense from the last 90 days."""
        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

        total = (
            self.db.query(func.coalesce(func.sum(Expense.amount), 0.0))
            .filter(Expense.is_deleted == False)  # noqa: E712
            .filter(Expense.status != "cancelled")
            .filter(Expense.expense_date >= ninety_days_ago)
            .scalar()
        ) or 0.0

        return float(total) / 90.0

    def _apply_invoice_delays(
        self, inflows: List[CashFlowEntry], invoice_ids: List[int], delay_days: int, end_date: date
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
                        )
                    )
                # If delayed beyond period, it effectively disappears from forecast
            else:
                result.append(entry)
        return result

    def _generate_alerts(
        self, daily_balances: List[DailyBalance], thresholds: CashFlowThresholdSettings
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
