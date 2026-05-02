"""
Cash Flow Forecasting Service

Provides predictive cash flow projections, runway calculations,
and scenario modeling based on invoices, expenses, and historical patterns.
"""

import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from core.models.models_per_tenant import (
    Invoice,
    Expense,
    Payment,
    Settings,
    BankStatement,
    BankStatementTransaction,
)
from core.schemas.cashflow import (
    CashFlowEntry,
    CashFlowReference,
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

# Statement statuses whose transactions are usable for cash flow projection.
BANK_STATEMENT_READY_STATUSES = ("processed", "uploaded", "done")

# Labels that are usually scheduled household or operating bills even when the
# lookback window only contains one statement.
LIKELY_MONTHLY_BILL_KEYWORDS = (
    "mortgage",
    "mtge",
    "rent",
    "lease",
    "insurance",
    "ins",
    "hydro",
    "utility",
    "utilities",
    "electric",
    "water",
    "gas",
    "internet",
    "telecom",
    "phone",
)


class CashFlowService:
    """Service for cash flow forecasting and analysis."""

    def __init__(self, db: Session):
        self.db = db

    def get_current_balance(self) -> float:
        """
        Calculate current cash position based on:
        - Payments received as of now (inflows)
        - Expenses dated as of now (outflows)
        """
        now = datetime.now(timezone.utc)

        # Total payments received
        total_payments = (
            self.db.query(func.coalesce(func.sum(Payment.amount), 0.0))
            .filter(Payment.payment_date != None)  # noqa: E711
            .filter(Payment.payment_date <= now)
            .scalar()
        ) or 0.0

        # Total expenses
        total_expenses = (
            self.db.query(func.coalesce(func.sum(Expense.amount), 0.0))
            .filter(Expense.is_deleted == False)  # noqa: E712
            .filter(Expense.status != "cancelled")
            .filter(Expense.expense_date != None)  # noqa: E711
            .filter(Expense.expense_date <= now)
            .scalar()
        ) or 0.0

        return float(total_payments) - float(total_expenses)

    def get_forecast(self, period: str = "30d", current_balance: Optional[float] = None) -> CashFlowForecastResponse:
        """
        Generate cash flow forecast for the specified period.

        Args:
            period: One of '7d', '30d', '90d', '365d'
            current_balance: Optional override for current balance
        """
        days_map = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}
        num_days = days_map.get(period, 30)

        today = date.today()
        end_date = today + timedelta(days=num_days)

        if current_balance is None:
            current_balance = self.get_current_balance()

        settings = self._get_threshold_settings()

        # Get projected inflows
        inflow_entries = self._get_projected_inflows(today, end_date, settings)

        # Get projected outflows
        outflow_entries = self._get_projected_outflows(today, end_date, settings)

        # Calculate daily balances
        daily_balances = self._calculate_daily_balances(
            current_balance, today, end_date, inflow_entries, outflow_entries
        )

        total_inflows = sum(e.amount for e in inflow_entries)
        total_outflows = sum(e.amount for e in outflow_entries)
        net_change = total_inflows - total_outflows
        projected_end_balance = current_balance + net_change

        # Generate alerts
        alerts = self._generate_alerts(daily_balances, settings)

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
        settings = self._get_threshold_settings()

        # Calculate averages from last 90 days
        now = datetime.now(timezone.utc)
        ninety_days_ago = now - timedelta(days=90)

        # Average daily income (payments received)
        total_income_90d = (
            self.db.query(func.coalesce(func.sum(Payment.amount), 0.0))
            .filter(Payment.payment_date != None)  # noqa: E711
            .filter(Payment.payment_date >= ninety_days_ago)
            .filter(Payment.payment_date <= now)
            .scalar()
        ) or 0.0
        if settings.include_bank_statement_patterns:
            total_income_90d += sum(
                abs(float(txn.amount or 0.0))
                for txn in self._get_matching_bank_statement_transactions(
                    "credit",
                    settings,
                    ninety_days_ago.date(),
                    now.date(),
                )
            )

        # Average daily expenses
        total_expenses_90d = (
            self.db.query(func.coalesce(func.sum(Expense.amount), 0.0))
            .filter(Expense.is_deleted == False)  # noqa: E712
            .filter(Expense.status != "cancelled")
            .filter(Expense.expense_date != None)  # noqa: E711
            .filter(Expense.expense_date >= ninety_days_ago)
            .filter(Expense.expense_date <= now)
            .scalar()
        ) or 0.0
        if settings.include_bank_statement_patterns:
            total_expenses_90d += sum(
                abs(float(txn.amount or 0.0))
                for txn in self._get_matching_bank_statement_transactions(
                    "debit",
                    settings,
                    ninety_days_ago.date(),
                    now.date(),
                )
            )

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
        days_map = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}
        num_days = days_map.get(period, 30)

        today = date.today()
        end_date = today + timedelta(days=num_days)

        if current_balance is None:
            current_balance = self.get_current_balance()

        settings = self._get_threshold_settings()

        # Get baseline projections
        baseline_inflows = self._get_projected_inflows(today, end_date, settings)
        baseline_outflows = self._get_projected_outflows(today, end_date, settings)

        # Apply scenario modifications
        scenario_inflows = list(baseline_inflows)
        scenario_outflows = list(baseline_outflows)

        # Apply delayed invoices
        if scenario.delayed_invoice_ids:
            delay_days = scenario.delay_days if scenario.delay_days is not None else 30
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
                    source="scenario",
                    source_label="What-if scenario",
                    source_details="Manually entered one-time scenario expense.",
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
                    source=e.source,
                    source_label=e.source_label,
                    source_details=e.source_details,
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
                    source=e.source,
                    source_label=e.source_label,
                    source_details=e.source_details,
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
        days_below = sum(1 for db_entry in daily_balances if db_entry.projected_balance < settings.safety_threshold)

        # Generate alerts
        alerts = []
        if lowest_balance < 0:
            alerts.append(f"⚠️ Balance goes negative on {lowest_balance_date}")
        if lowest_balance < settings.safety_threshold:
            alerts.append(
                f"⚠️ Balance drops below safety threshold (${settings.safety_threshold:,.2f}) "
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
        include_outstanding_invoices: Optional[bool] = None,
        include_recurring_invoices: Optional[bool] = None,
        include_upcoming_expenses: Optional[bool] = None,
        include_historical_averages: Optional[bool] = None,
        include_bank_statement_patterns: Optional[bool] = None,
        bank_statement_lookback_days: Optional[int] = None,
        bank_statement_min_occurrences: Optional[int] = None,
        bank_statement_intervals: Optional[List[int]] = None,
        bank_statement_inflow_categories: Optional[List[str]] = None,
        bank_statement_outflow_categories: Optional[List[str]] = None,
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
            "include_outstanding_invoices": (
                include_outstanding_invoices if include_outstanding_invoices is not None else current.include_outstanding_invoices
            ),
            "include_recurring_invoices": (
                include_recurring_invoices if include_recurring_invoices is not None else current.include_recurring_invoices
            ),
            "include_upcoming_expenses": (
                include_upcoming_expenses if include_upcoming_expenses is not None else current.include_upcoming_expenses
            ),
            "include_historical_averages": (
                include_historical_averages if include_historical_averages is not None else current.include_historical_averages
            ),
            "include_bank_statement_patterns": (
                include_bank_statement_patterns
                if include_bank_statement_patterns is not None
                else current.include_bank_statement_patterns
            ),
            "bank_statement_lookback_days": (
                bank_statement_lookback_days
                if bank_statement_lookback_days is not None
                else current.bank_statement_lookback_days
            ),
            "bank_statement_min_occurrences": (
                bank_statement_min_occurrences
                if bank_statement_min_occurrences is not None
                else current.bank_statement_min_occurrences
            ),
            "bank_statement_intervals": (
                bank_statement_intervals
                if bank_statement_intervals is not None
                else current.bank_statement_intervals
            ),
            "bank_statement_inflow_categories": (
                bank_statement_inflow_categories
                if bank_statement_inflow_categories is not None
                else current.bank_statement_inflow_categories
            ),
            "bank_statement_outflow_categories": (
                bank_statement_outflow_categories
                if bank_statement_outflow_categories is not None
                else current.bank_statement_outflow_categories
            ),
        }
        validated_settings = CashFlowThresholdSettings(**new_values)
        persisted_values = validated_settings.model_dump()

        if settings_row:
            settings_row.value = persisted_values
        else:
            settings_row = Settings(
                key=CASHFLOW_SETTINGS_KEY,
                value=persisted_values,
                description="Cash flow alert threshold settings",
                category="cashflow",
                is_public=True,
            )
            self.db.add(settings_row)

        self.db.commit()

        return validated_settings

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

    def _get_projected_inflows(
        self,
        start_date: date,
        end_date: date,
        settings: Optional[CashFlowThresholdSettings] = None,
    ) -> List[CashFlowEntry]:
        """
        Get projected cash inflows from:
        1. Outstanding invoices (due within period)
        2. Recurring invoice patterns (predicted future invoices)
        """
        settings = settings or self._get_threshold_settings()
        entries = []

        # 1. Outstanding invoices due within the forecast period
        if settings.include_outstanding_invoices:
            outstanding_invoices = (
                self.db.query(Invoice)
                .filter(Invoice.is_deleted == False)  # noqa: E712
                .filter(Invoice.status.in_(["sent", "pending", "overdue", "partially_paid"]))
                .filter(Invoice.due_date >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc))
                .filter(Invoice.due_date <= datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc))
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
                            source="invoice",
                            source_label="Outstanding invoice",
                            source_details="Open invoice due in the selected forecast window.",
                            references=[self._invoice_reference(inv)],
                        )
                    )

        # 2. Recurring invoices - predict future occurrences
        if settings.include_recurring_invoices:
            recurring_invoices = (
                self.db.query(Invoice)
                .filter(Invoice.is_deleted == False)  # noqa: E712
                .filter(Invoice.is_recurring == True)  # noqa: E712
                .filter(Invoice.status != "cancelled")
                .all()
            )

            for inv in recurring_invoices:
                predicted_dates = self._predict_recurring_dates(
                    inv.recurring_frequency, inv.due_date, start_date, end_date
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
                            source="recurring_invoice",
                            source_label="Recurring invoice",
                            source_details="Predicted from a recurring invoice schedule.",
                            references=[self._invoice_reference(inv)],
                        )
                    )

        if settings.include_bank_statement_patterns:
            entries.extend(self._get_bank_statement_pattern_entries("credit", start_date, end_date, settings))

        # 3. Historical pattern-based prediction (average daily income from last 90 days)
        # Only add if we have few concrete entries to fill gaps
        if settings.include_historical_averages and len(entries) < MIN_CONCRETE_ENTRIES_FOR_PATTERN:
            avg_daily = self._get_historical_average_daily_income(settings)
            if avg_daily > 0:
                references, payment_count, bank_transaction_count = self._get_historical_payment_references(settings)
                current = start_date + timedelta(days=1)
                while current <= end_date:
                    # Only add for days without existing entries
                    if not any(e.date == current for e in entries):
                        interval_days = self._historical_pattern_interval_days(current, end_date)
                        entries.append(
                            CashFlowEntry(
                                date=current,
                                amount=avg_daily * interval_days,
                                type="inflow",
                                category="historical_pattern",
                                description="Based on historical average",
                                confidence=0.4,
                                source="historical_average",
                                source_label="Historical payment average",
                                source_details=(
                                    f"Average income from {payment_count} payments and "
                                    f"{bank_transaction_count} matching bank statement credits over the last 90 days, "
                                    f"grouped into {interval_days}-day forecast blocks."
                                ),
                                references=references,
                            )
                        )
                    current += timedelta(days=HISTORICAL_PATTERN_INTERVAL_DAYS)

        return sorted(entries, key=lambda e: e.date)

    def _get_projected_outflows(
        self,
        start_date: date,
        end_date: date,
        settings: Optional[CashFlowThresholdSettings] = None,
    ) -> List[CashFlowEntry]:
        """
        Get projected cash outflows from:
        1. Known upcoming expenses
        2. Recurring expense patterns
        3. Historical average spending
        """
        settings = settings or self._get_threshold_settings()
        entries = []
        now = datetime.now(timezone.utc)

        # 1. Known upcoming expenses that have not already affected current balance.
        if settings.include_upcoming_expenses:
            upcoming_expenses = (
                self.db.query(Expense)
                .filter(Expense.is_deleted == False)  # noqa: E712
                .filter(Expense.status.in_(["pending", "approved", "recorded"]))
                .filter(Expense.expense_date > now)
                .filter(Expense.expense_date <= datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc))
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
                            source="expense",
                            source_label="Upcoming expense",
                            source_details="Future-dated expense already recorded in the app.",
                            references=[self._expense_reference(exp)],
                        )
                    )

        if settings.include_bank_statement_patterns:
            entries.extend(self._get_bank_statement_pattern_entries("debit", start_date, end_date, settings))

        # 2. Historical expense pattern - predict recurring expenses
        avg_daily_expense = self._get_historical_average_daily_expense(settings)
        if settings.include_historical_averages and avg_daily_expense > 0:
            references, expense_count, bank_transaction_count = self._get_historical_expense_references(settings)
            # Fill in with weekly averages for days without concrete entries
            current = start_date + timedelta(days=1)
            while current <= end_date:
                day_total = sum(e.amount for e in entries if e.date == current)
                if day_total == 0:
                    interval_days = self._historical_pattern_interval_days(current, end_date)
                    entries.append(
                        CashFlowEntry(
                            date=current,
                            amount=avg_daily_expense * interval_days,
                            type="outflow",
                            category="historical_pattern",
                            description="Based on historical average",
                            confidence=0.4,
                            source="historical_average",
                            source_label="Historical expense average",
                            source_details=(
                                f"Average expenses from {expense_count} expenses and "
                                f"{bank_transaction_count} matching bank statement debits over the last 90 days, "
                                f"grouped into {interval_days}-day forecast blocks."
                            ),
                            references=references,
                        )
                    )
                current += timedelta(days=HISTORICAL_PATTERN_INTERVAL_DAYS)

        return sorted(entries, key=lambda e: e.date)

    def _get_bank_statement_pattern_entries(
        self,
        transaction_type: str,
        start_date: date,
        end_date: date,
        settings: CashFlowThresholdSettings,
    ) -> List[CashFlowEntry]:
        """Project recurring cash flow patterns found in bank statement transactions."""
        today = date.today()
        forecast_days = max(0, (end_date - start_date).days)
        lookback_days = max(settings.bank_statement_lookback_days, min(forecast_days, 365))
        lookback_start = today - timedelta(days=lookback_days)

        transactions = self._get_matching_bank_statement_transactions(transaction_type, settings, lookback_start, today)

        grouped: Dict[Tuple[str, str, int], List[BankStatementTransaction]] = defaultdict(list)
        for txn in transactions:
            amount = abs(float(txn.amount or 0.0))
            if amount <= 0:
                continue
            label = self._bank_statement_pattern_label(txn)
            if not self._is_bank_statement_category_enabled(transaction_type, label, settings):
                continue
            grouped[(transaction_type, label.lower(), int(round(amount * 100)))].append(txn)

        entries: List[CashFlowEntry] = []
        for group in grouped.values():
            if len(group) < settings.bank_statement_min_occurrences:
                pattern = self._build_single_observation_bank_statement_pattern(group, settings)
            else:
                pattern = self._build_bank_statement_pattern(group, settings)

            if not pattern:
                continue

            amount, interval_days, label, last_date, sample_count, reference_id, references = pattern
            current = last_date + timedelta(days=interval_days)
            while current <= end_date:
                if current >= start_date:
                    entry_type = "inflow" if transaction_type == "credit" else "outflow"
                    entries.append(
                        CashFlowEntry(
                            date=current,
                            amount=amount,
                            type=entry_type,
                            category="bank_statement_recurring",
                            description=label,
                            reference_id=reference_id,
                            confidence=0.7 if sample_count >= 3 else 0.55,
                            source="bank_statement_pattern",
                            source_label="Bank statement pattern",
                            source_details=(
                                f"Projected from {sample_count} {transaction_type} transactions "
                                f"about every {interval_days} days."
                            ),
                            references=references,
                        )
                    )
                current += timedelta(days=interval_days)

        return sorted(entries, key=lambda e: e.date)

    def _bank_statement_pattern_label(self, txn: BankStatementTransaction) -> str:
        """Choose a stable user-facing label for a statement transaction pattern."""
        category = (txn.category or "").strip()
        if category and category.lower() not in {"other", "uncategorized", "unknown"}:
            return category
        return self._normalize_transaction_description(txn.description)

    def _get_matching_bank_statement_transactions(
        self,
        transaction_type: str,
        settings: CashFlowThresholdSettings,
        start_date: date,
        end_date: date,
    ) -> List[BankStatementTransaction]:
        """Return statement transactions that match cash flow bank statement rules."""
        transactions = (
            self.db.query(BankStatementTransaction)
            .options(joinedload(BankStatementTransaction.statement))
            .join(BankStatement, BankStatement.id == BankStatementTransaction.statement_id)
            .filter(BankStatement.is_deleted == False)  # noqa: E712
            .filter(BankStatement.status.in_(BANK_STATEMENT_READY_STATUSES))
            .filter(BankStatementTransaction.transaction_type == transaction_type)
            .filter(BankStatementTransaction.date >= start_date)
            .filter(BankStatementTransaction.date <= end_date)
            .all()
        )

        return [
            txn
            for txn in transactions
            if abs(float(txn.amount or 0.0)) > 0
            and self._is_bank_statement_category_enabled(
                transaction_type,
                self._bank_statement_pattern_label(txn),
                settings,
            )
        ]

    def _is_bank_statement_category_enabled(
        self,
        transaction_type: str,
        label: str,
        settings: CashFlowThresholdSettings,
    ) -> bool:
        configured = (
            settings.bank_statement_inflow_categories
            if transaction_type == "credit"
            else settings.bank_statement_outflow_categories
        )
        if not configured:
            return True
        label_lower = label.lower()
        return any(
            item_lower in label_lower or label_lower in item_lower
            for item_lower in (item.lower() for item in configured)
        )

    def _normalize_transaction_description(self, description: Optional[str]) -> str:
        """Collapse noisy transaction descriptions into a recurring-pattern key."""
        if not description:
            return "Bank statement transaction"

        normalized = description.lower()
        normalized = re.sub(r"\b\d{2,}\b", " ", normalized)
        normalized = re.sub(r"[^a-z\s]", " ", normalized)
        words = [
            word
            for word in normalized.split()
            if word not in {"pos", "debit", "credit", "payment", "transfer", "online"}
        ]
        if not words:
            return description.strip()[:60] or "Bank statement transaction"

        return " ".join(words[:4]).title()

    def _build_bank_statement_pattern(
        self,
        transactions: List[BankStatementTransaction],
        settings: CashFlowThresholdSettings,
    ) -> Optional[Tuple[float, int, str, date, int, int, List[CashFlowReference]]]:
        """Return amount/interval metadata if transactions look recurring enough."""
        ordered = sorted(transactions, key=lambda txn: txn.date)
        unique_dates = sorted({txn.date for txn in ordered})
        if len(unique_dates) < settings.bank_statement_min_occurrences:
            return None

        intervals = [
            (unique_dates[index] - unique_dates[index - 1]).days
            for index in range(1, len(unique_dates))
            if (unique_dates[index] - unique_dates[index - 1]).days > 0
        ]
        if not intervals:
            return None

        interval_days = self._classify_bank_statement_interval(
            int(round(median(intervals))),
            settings.bank_statement_intervals,
        )
        if interval_days is None:
            return None

        amounts = [abs(float(txn.amount or 0.0)) for txn in ordered]
        avg_amount = sum(amounts) / len(amounts)
        if avg_amount <= 0:
            return None

        label = self._bank_statement_pattern_label(ordered[-1])
        references = [self._bank_statement_transaction_reference(txn) for txn in ordered[-5:]]
        return avg_amount, interval_days, label, unique_dates[-1], len(ordered), ordered[-1].id, references

    def _build_single_observation_bank_statement_pattern(
        self,
        transactions: List[BankStatementTransaction],
        settings: CashFlowThresholdSettings,
    ) -> Optional[Tuple[float, int, str, date, int, int, List[CashFlowReference]]]:
        """Project obvious monthly bills from a single statement observation."""
        if 30 not in set(settings.bank_statement_intervals or []):
            return None

        ordered = sorted(transactions, key=lambda txn: (txn.date, txn.id or 0))
        if not ordered:
            return None

        txn = ordered[-1]
        label = self._bank_statement_pattern_label(txn)
        text = f"{label} {txn.description or ''}".lower()
        if not any(keyword in text for keyword in LIKELY_MONTHLY_BILL_KEYWORDS):
            return None

        amount = abs(float(txn.amount or 0.0))
        if amount <= 0:
            return None

        references = [self._bank_statement_transaction_reference(txn)]
        return amount, 30, label, txn.date, 1, txn.id, references

    def _classify_bank_statement_interval(
        self,
        observed_days: int,
        enabled_intervals: Optional[List[int]] = None,
    ) -> Optional[int]:
        """Map observed transaction spacing to a conservative recurring interval."""
        enabled = set(enabled_intervals or [7, 14, 30, 90])
        if 7 in enabled and 6 <= observed_days <= 8:
            return 7
        if 14 in enabled and 12 <= observed_days <= 16:
            return 14
        if 30 in enabled and 25 <= observed_days <= 35:
            return 30
        if 90 in enabled and 85 <= observed_days <= 95:
            return 90
        return None

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

    def _historical_pattern_interval_days(self, current: date, end_date: date) -> int:
        """Return how many days a weekly historical pattern entry represents."""
        remaining_days = (end_date - current).days + 1
        return max(1, min(HISTORICAL_PATTERN_INTERVAL_DAYS, remaining_days))

    def _invoice_reference(self, invoice: Invoice) -> CashFlowReference:
        return CashFlowReference(
            type="invoice",
            id=invoice.id,
            label=f"Invoice {invoice.number}",
            url=f"/invoices/view/{invoice.id}",
        )

    def _expense_reference(self, expense: Expense) -> CashFlowReference:
        vendor = (expense.vendor or "").strip() or "Unknown vendor"
        category = (expense.category or "").strip() or "Expense"
        return CashFlowReference(
            type="expense",
            id=expense.id,
            label=f"{category}: {vendor}",
            url=f"/expenses/view/{expense.id}",
        )

    def _payment_reference(self, payment: Payment) -> CashFlowReference:
        invoice = getattr(payment, "invoice", None)
        if invoice:
            return CashFlowReference(
                type="invoice",
                id=invoice.id,
                label=f"Payment for invoice {invoice.number}",
                url=f"/invoices/view/{invoice.id}",
            )

        return CashFlowReference(
            type="payment",
            id=payment.id,
            label=f"Payment #{payment.id}",
            url="/payments",
        )

    def _bank_statement_transaction_reference(
        self,
        transaction: BankStatementTransaction,
    ) -> CashFlowReference:
        statement = getattr(transaction, "statement", None)
        date_label = transaction.date.isoformat() if transaction.date else "unknown date"
        description = (transaction.description or "").strip() or "Bank transaction"
        statement_label = (
            getattr(statement, "original_filename", None)
            or f"Statement #{transaction.statement_id}"
        )
        return CashFlowReference(
            type="bank_statement_transaction",
            id=transaction.id,
            label=f"{statement_label} - {date_label} - {description[:60]}",
            url=f"/statements?id={transaction.statement_id}&txn={transaction.id}",
        )

    def _get_historical_payment_references(
        self,
        settings: CashFlowThresholdSettings,
    ) -> Tuple[List[CashFlowReference], int, int]:
        now = datetime.now(timezone.utc)
        ninety_days_ago = now - timedelta(days=90)
        query = (
            self.db.query(Payment)
            .options(joinedload(Payment.invoice))
            .filter(Payment.payment_date != None)  # noqa: E711
            .filter(Payment.payment_date >= ninety_days_ago)
            .filter(Payment.payment_date <= now)
        )
        count = query.count()
        payments = query.order_by(Payment.payment_date.desc()).limit(5).all()
        bank_transactions = (
            self._get_matching_bank_statement_transactions(
                "credit",
                settings,
                ninety_days_ago.date(),
                now.date(),
            )
            if settings.include_bank_statement_patterns
            else []
        )
        references = [self._payment_reference(payment) for payment in payments]
        references.extend(
            self._bank_statement_transaction_reference(txn)
            for txn in sorted(bank_transactions, key=lambda txn: txn.date, reverse=True)[:5]
        )
        return references, count, len(bank_transactions)

    def _get_historical_expense_references(
        self,
        settings: CashFlowThresholdSettings,
    ) -> Tuple[List[CashFlowReference], int, int]:
        now = datetime.now(timezone.utc)
        ninety_days_ago = now - timedelta(days=90)
        query = (
            self.db.query(Expense)
            .filter(Expense.is_deleted == False)  # noqa: E712
            .filter(Expense.status != "cancelled")
            .filter(Expense.expense_date != None)  # noqa: E711
            .filter(Expense.expense_date >= ninety_days_ago)
            .filter(Expense.expense_date <= now)
        )
        count = query.count()
        expenses = query.order_by(Expense.expense_date.desc()).limit(5).all()
        bank_transactions = (
            self._get_matching_bank_statement_transactions(
                "debit",
                settings,
                ninety_days_ago.date(),
                now.date(),
            )
            if settings.include_bank_statement_patterns
            else []
        )
        references = [self._expense_reference(expense) for expense in expenses]
        references.extend(
            self._bank_statement_transaction_reference(txn)
            for txn in sorted(bank_transactions, key=lambda txn: txn.date, reverse=True)[:5]
        )
        return references, count, len(bank_transactions)

    def _get_historical_average_daily_income(
        self,
        settings: Optional[CashFlowThresholdSettings] = None,
    ) -> float:
        """Calculate average daily income from the last 90 days."""
        settings = settings or self._get_threshold_settings()
        now = datetime.now(timezone.utc)
        ninety_days_ago = now - timedelta(days=90)

        total = (
            self.db.query(func.coalesce(func.sum(Payment.amount), 0.0))
            .filter(Payment.payment_date != None)  # noqa: E711
            .filter(Payment.payment_date >= ninety_days_ago)
            .filter(Payment.payment_date <= now)
            .scalar()
        ) or 0.0
        if settings.include_bank_statement_patterns:
            total += sum(
                abs(float(txn.amount or 0.0))
                for txn in self._get_matching_bank_statement_transactions(
                    "credit",
                    settings,
                    ninety_days_ago.date(),
                    now.date(),
                )
            )

        return float(total) / 90.0

    def _get_historical_average_daily_expense(
        self,
        settings: Optional[CashFlowThresholdSettings] = None,
    ) -> float:
        """Calculate average daily expense from the last 90 days."""
        settings = settings or self._get_threshold_settings()
        now = datetime.now(timezone.utc)
        ninety_days_ago = now - timedelta(days=90)

        total = (
            self.db.query(func.coalesce(func.sum(Expense.amount), 0.0))
            .filter(Expense.is_deleted == False)  # noqa: E712
            .filter(Expense.status != "cancelled")
            .filter(Expense.expense_date != None)  # noqa: E711
            .filter(Expense.expense_date >= ninety_days_ago)
            .filter(Expense.expense_date <= now)
            .scalar()
        ) or 0.0
        if settings.include_bank_statement_patterns:
            total += sum(
                abs(float(txn.amount or 0.0))
                for txn in self._get_matching_bank_statement_transactions(
                    "debit",
                    settings,
                    ninety_days_ago.date(),
                    now.date(),
                )
            )

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
