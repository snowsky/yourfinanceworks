"""
Tests for Cash Flow Forecasting & Management feature.

Tests cover:
- Cash flow forecast endpoint (7/30/90 day)
- Cash runway calculator
- What-if scenario modeling
- Alert threshold management
"""

import pytest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch, MagicMock

from core.services.cashflow_service import CashFlowService
from core.schemas.cashflow import (
    ScenarioInput,
    CashFlowThresholdSettings,
    ForecastPeriod,
)


class TestCashFlowService:
    """Unit tests for CashFlowService."""

    @pytest.fixture
    def service(self, db_session):
        return CashFlowService(db_session)

    @pytest.fixture
    def seed_data(self, db_session):
        """Seed test data with invoices, payments, and expenses."""
        from core.models.models_per_tenant import Invoice, Payment, Expense, Client

        # Create a client
        client = Client(
            name="Test Client",
            email="client@test.com",
        )
        db_session.add(client)
        db_session.commit()
        db_session.refresh(client)

        # Create invoices (some outstanding, some paid)
        today = datetime.now(timezone.utc)
        invoices = []

        # Outstanding invoice due in 10 days
        inv1 = Invoice(
            number="INV-001",
            amount=5000.0,
            currency="USD",
            due_date=today + timedelta(days=10),
            status="sent",
            client_id=client.id,
            subtotal=5000.0,
            is_recurring=False,
        )
        db_session.add(inv1)

        # Outstanding invoice due in 25 days
        inv2 = Invoice(
            number="INV-002",
            amount=3000.0,
            currency="USD",
            due_date=today + timedelta(days=25),
            status="pending",
            client_id=client.id,
            subtotal=3000.0,
            is_recurring=False,
        )
        db_session.add(inv2)

        # Recurring invoice
        inv3 = Invoice(
            number="INV-RECURRING",
            amount=1000.0,
            currency="USD",
            due_date=today - timedelta(days=30),
            status="paid",
            client_id=client.id,
            subtotal=1000.0,
            is_recurring=True,
            recurring_frequency="monthly",
        )
        db_session.add(inv3)
        db_session.commit()

        # Create payments (historical income)
        for i in range(10):
            payment = Payment(
                invoice_id=inv3.id,
                amount=1000.0,
                currency="USD",
                payment_date=today - timedelta(days=i * 9),
                payment_method="bank_transfer",
            )
            db_session.add(payment)

        # Create expenses (historical and upcoming)
        for i in range(10):
            exp = Expense(
                amount=500.0,
                currency="USD",
                expense_date=today - timedelta(days=i * 9),
                category="operations",
                status="recorded",
            )
            db_session.add(exp)

        # Future expenses
        exp_future = Expense(
            amount=2000.0,
            currency="USD",
            expense_date=today + timedelta(days=15),
            category="rent",
            vendor="Landlord",
            status="approved",
        )
        db_session.add(exp_future)

        db_session.commit()
        db_session.refresh(inv1)
        db_session.refresh(inv2)

        return {
            "client": client,
            "inv1": inv1,
            "inv2": inv2,
            "inv3": inv3,
        }

    def test_get_current_balance(self, service, seed_data):
        """Test current balance calculation from payments minus expenses."""
        balance = service.get_current_balance()
        # 10 payments of 1000 = 10000
        # 10 expenses of 500 + 1 of 2000 = 7000
        assert balance == 10000.0 - 7000.0  # 3000.0

    def test_get_forecast_30d(self, service, seed_data):
        """Test 30-day forecast includes outstanding invoices and expenses."""
        forecast = service.get_forecast(period="30d")

        assert forecast.period == "30d"
        assert forecast.start_date == date.today()
        assert forecast.end_date == date.today() + timedelta(days=30)
        assert forecast.current_balance > 0
        assert len(forecast.daily_balances) == 31  # Including today
        assert forecast.total_projected_inflows > 0
        assert forecast.total_projected_outflows > 0

    def test_get_forecast_7d(self, service, seed_data):
        """Test 7-day forecast."""
        forecast = service.get_forecast(period="7d")
        assert forecast.period == "7d"
        assert len(forecast.daily_balances) == 8

    def test_get_forecast_90d(self, service, seed_data):
        """Test 90-day forecast."""
        forecast = service.get_forecast(period="90d")
        assert forecast.period == "90d"
        assert len(forecast.daily_balances) == 91

    def test_get_forecast_with_custom_balance(self, service, seed_data):
        """Test forecast with overridden starting balance."""
        forecast = service.get_forecast(period="30d", current_balance=50000.0)
        assert forecast.current_balance == 50000.0
        assert forecast.projected_end_balance != 50000.0  # Should change due to flows

    def test_get_runway(self, service, seed_data):
        """Test runway calculation."""
        runway = service.get_runway()

        assert runway.current_balance > 0
        assert runway.average_daily_burn >= 0
        assert runway.average_daily_income >= 0
        assert runway.monthly_burn_rate >= 0
        assert runway.monthly_income_rate >= 0
        assert isinstance(runway.is_sustainable, bool)

    def test_get_runway_with_custom_balance(self, service, seed_data):
        """Test runway with custom balance."""
        runway = service.get_runway(current_balance=100000.0)
        assert runway.current_balance == 100000.0

    def test_run_scenario_delayed_invoices(self, service, seed_data):
        """Test scenario with delayed invoice payments."""
        inv1_id = seed_data["inv1"].id
        scenario = ScenarioInput(
            description="Client X pays 30 days late",
            delayed_invoice_ids=[inv1_id],
            delay_days=30,
        )
        result = service.run_scenario(scenario, period="30d")

        assert result.scenario_description == "Client X pays 30 days late"
        assert result.balance_impact <= 0  # Delayed payment should reduce balance
        assert len(result.daily_balances) > 0

    def test_run_scenario_additional_expense(self, service, seed_data):
        """Test scenario with additional unexpected expense."""
        scenario = ScenarioInput(
            description="Emergency equipment repair",
            additional_expense=10000.0,
            additional_expense_date=date.today() + timedelta(days=5),
        )
        result = service.run_scenario(scenario, period="30d")

        assert result.balance_impact < 0  # Additional expense should reduce balance
        assert result.scenario_end_balance < result.baseline_end_balance

    def test_run_scenario_revenue_change(self, service, seed_data):
        """Test scenario with revenue percentage change."""
        scenario = ScenarioInput(
            description="Revenue drops 50%",
            revenue_change_percent=-50.0,
        )
        result = service.run_scenario(scenario, period="30d")

        assert result.balance_impact <= 0  # Less revenue = lower balance

    def test_run_scenario_expense_increase(self, service, seed_data):
        """Test scenario with expense increase."""
        scenario = ScenarioInput(
            description="Expenses increase 25%",
            expense_change_percent=25.0,
        )
        result = service.run_scenario(scenario, period="30d")

        assert result.balance_impact <= 0  # More expenses = lower balance

    def test_get_alerts_healthy(self, service, seed_data):
        """Test alerts when balance is healthy."""
        # Use a high balance to ensure no alerts
        alerts = service.get_alerts(current_balance=1000000.0)
        assert not alerts.has_alerts or len(alerts.alerts) == 0

    def test_get_alerts_critical(self, service, seed_data):
        """Test alerts when balance is below safety threshold."""
        alerts = service.get_alerts(current_balance=100.0)
        assert alerts.has_alerts
        assert any("CRITICAL" in a for a in alerts.alerts)

    def test_get_alerts_warning(self, service, seed_data):
        """Test alerts when balance is at warning level."""
        alerts = service.get_alerts(current_balance=15000.0)
        # Default warning threshold is 25000, safety is 10000
        # 15000 is between them, so should trigger warning
        assert alerts.has_alerts
        assert any("WARNING" in a for a in alerts.alerts)

    def test_threshold_settings_default(self, service):
        """Test default threshold settings."""
        settings = service.get_threshold_settings()
        assert settings.safety_threshold == 10000.0
        assert settings.warning_threshold == 25000.0
        assert settings.currency == "USD"

    def test_update_threshold_settings(self, service):
        """Test updating threshold settings."""
        updated = service.update_threshold_settings(
            safety_threshold=5000.0,
            warning_threshold=15000.0,
        )
        assert updated.safety_threshold == 5000.0
        assert updated.warning_threshold == 15000.0

        # Verify persistence
        reloaded = service.get_threshold_settings()
        assert reloaded.safety_threshold == 5000.0
        assert reloaded.warning_threshold == 15000.0

    def test_forecast_daily_balances_continuity(self, service, seed_data):
        """Test that daily balances are continuous (no gaps)."""
        forecast = service.get_forecast(period="30d")
        dates = [db.date for db in forecast.daily_balances]

        # Check consecutive dates
        for i in range(1, len(dates)):
            assert dates[i] - dates[i - 1] == timedelta(days=1)

    def test_forecast_inflow_entries_sorted(self, service, seed_data):
        """Test that inflow entries are sorted by date."""
        forecast = service.get_forecast(period="30d")
        if len(forecast.inflow_entries) > 1:
            for i in range(1, len(forecast.inflow_entries)):
                assert forecast.inflow_entries[i].date >= forecast.inflow_entries[i - 1].date

    def test_empty_database_forecast(self, db_session):
        """Test forecast with empty database returns valid structure."""
        service = CashFlowService(db_session)
        forecast = service.get_forecast(period="7d", current_balance=0.0)

        assert forecast.current_balance == 0.0
        assert len(forecast.daily_balances) == 8
        assert forecast.period == "7d"
