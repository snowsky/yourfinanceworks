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
from pydantic import ValidationError

from core.services.cashflow_service import CashFlowService
from core.schemas.cashflow import (
    ScenarioInput,
    CashFlowThresholdSettings,
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
        # 10 historical/current expenses of 500 = 5000; future expenses are not current cash.
        assert balance == 10000.0 - 5000.0  # 5000.0

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
        assert not any(
            entry.category == "expense" and entry.description == "operations: Unknown"
            for entry in forecast.outflow_entries
        )

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

    def test_get_forecast_365d(self, service, seed_data):
        """Test 365-day forecast."""
        forecast = service.get_forecast(period="365d")
        assert forecast.period == "365d"
        assert forecast.end_date == date.today() + timedelta(days=365)
        assert len(forecast.daily_balances) == 366

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

    def test_update_threshold_settings_rejects_invalid_order(self, service):
        """Invalid threshold updates should not be persisted."""
        with pytest.raises(ValidationError):
            service.update_threshold_settings(
                safety_threshold=20000.0,
                warning_threshold=10000.0,
            )

        reloaded = service.get_threshold_settings()
        assert reloaded.safety_threshold == 10000.0
        assert reloaded.warning_threshold == 25000.0

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

    def test_current_balance_excludes_future_payments(self, db_session):
        """Future-dated payments should not affect current cash."""
        from core.models.models_per_tenant import Payment

        now = datetime.now(timezone.utc)
        db_session.add(
            Payment(
                amount=5000.0,
                currency="USD",
                payment_date=now + timedelta(days=3),
                payment_method="bank_transfer",
            )
        )
        db_session.commit()

        service = CashFlowService(db_session)
        assert service.get_current_balance() == 0.0

    def test_historical_pattern_entries_are_scaled_by_interval(self, db_session):
        """Weekly historical pattern entries should represent the whole interval."""
        from core.models.models_per_tenant import Payment

        now = datetime.now(timezone.utc)
        db_session.add(
            Payment(
                amount=9000.0,
                currency="USD",
                payment_date=now - timedelta(days=10),
                payment_method="bank_transfer",
            )
        )
        db_session.commit()

        service = CashFlowService(db_session)
        entries = service._get_projected_inflows(date.today(), date.today() + timedelta(days=13))
        pattern_entries = [entry for entry in entries if entry.category == "historical_pattern"]

        assert len(pattern_entries) == 2
        assert pattern_entries[0].amount == pytest.approx(700.0)
        assert pattern_entries[1].amount == pytest.approx(600.0)

    def test_recurring_invoice_projection_uses_due_date_anchor(self, db_session):
        """Recurring invoice cash timing should follow due dates."""
        from core.models.models_per_tenant import Client, Invoice

        now = datetime.now(timezone.utc)
        client = Client(name="Recurring Client", email="recurring@test.com")
        db_session.add(client)
        db_session.commit()
        db_session.refresh(client)

        invoice = Invoice(
            number="INV-RECUR-DUE",
            amount=1200.0,
            currency="USD",
            due_date=now - timedelta(days=15),
            status="paid",
            client_id=client.id,
            subtotal=1200.0,
            is_recurring=True,
            recurring_frequency="monthly",
            created_at=now - timedelta(days=3),
        )
        db_session.add(invoice)
        db_session.commit()

        service = CashFlowService(db_session)
        entries = service._get_projected_inflows(date.today(), date.today() + timedelta(days=30))
        recurring_entries = [entry for entry in entries if entry.category == "recurring_invoice"]

        assert len(recurring_entries) == 1
        assert recurring_entries[0].date == (now - timedelta(days=15)).date() + timedelta(days=30)
        assert recurring_entries[0].source_label == "Recurring invoice"

    def test_bank_statement_recurring_patterns_create_forecast_entries(self, db_session):
        """Recurring bank statement transactions should be projected into cash flow."""
        from core.models.models_per_tenant import BankStatement, BankStatementTransaction

        statement = BankStatement(
            tenant_id=1,
            original_filename="bank.csv",
            stored_filename="bank.csv",
            file_path="/tmp/bank.csv",
            status="processed",
        )
        db_session.add(statement)
        db_session.commit()
        db_session.refresh(statement)

        for days_ago in (60, 30):
            db_session.add(
                BankStatementTransaction(
                    statement_id=statement.id,
                    date=date.today() - timedelta(days=days_ago),
                    description="Mortgage Payment",
                    amount=1800.0,
                    transaction_type="debit",
                    category="Mortgage",
                )
            )

        for days_ago in (60, 30):
            db_session.add(
                BankStatementTransaction(
                    statement_id=statement.id,
                    date=date.today() - timedelta(days=days_ago),
                    description="Salary Deposit",
                    amount=4500.0,
                    transaction_type="credit",
                    category="Salary",
                )
            )
        db_session.commit()

        service = CashFlowService(db_session)
        forecast = service.get_forecast(period="30d", current_balance=0.0)

        bank_outflows = [
            entry for entry in forecast.outflow_entries
            if entry.source == "bank_statement_pattern" and entry.description == "Mortgage"
        ]
        bank_inflows = [
            entry for entry in forecast.inflow_entries
            if entry.source == "bank_statement_pattern" and entry.description == "Salary"
        ]

        assert len(bank_outflows) == 2
        assert bank_outflows[0].amount == pytest.approx(1800.0)
        assert bank_outflows[0].source_label == "Bank statement pattern"
        assert "2 debit transactions" in bank_outflows[0].source_details
        assert bank_outflows[0].references
        assert bank_outflows[0].references[0].type == "bank_statement_transaction"
        assert len(bank_inflows) == 2
        assert bank_inflows[0].amount == pytest.approx(4500.0)
        assert bank_inflows[0].references
        assert bank_inflows[0].references[0].url.startswith("/statements?id=")

    def test_bank_statement_patterns_group_recurring_bills_by_amount(self, db_session):
        """Different payment streams with the same label should not hide each other."""
        from core.models.models_per_tenant import BankStatement, BankStatementTransaction

        statement = BankStatement(
            tenant_id=1,
            original_filename="bank_statement_2.pdf",
            stored_filename="bank_statement_2.pdf",
            file_path="/tmp/bank_statement_2.pdf",
            status="processed",
        )
        db_session.add(statement)
        db_session.commit()
        db_session.refresh(statement)

        for txn_date, amount in (
            (date.today() - timedelta(days=42), 937.58),
            (date.today() - timedelta(days=28), 709.99),
            (date.today() - timedelta(days=14), 937.58),
            (date.today() - timedelta(days=1), 709.99),
        ):
            db_session.add(
                BankStatementTransaction(
                    statement_id=statement.id,
                    date=txn_date,
                    description="Mortgage BNS MTGE DEPT",
                    amount=amount,
                    transaction_type="debit",
                    category="Mortgage",
                )
            )
        db_session.commit()

        service = CashFlowService(db_session)
        forecast = service.get_forecast(period="30d", current_balance=0.0)
        mortgage_outflows = [
            entry
            for entry in forecast.outflow_entries
            if entry.source == "bank_statement_pattern" and entry.description == "Mortgage"
        ]

        projected_amounts = {round(entry.amount, 2) for entry in mortgage_outflows}
        assert 937.58 in projected_amounts
        assert 709.99 in projected_amounts

    def test_bank_statement_single_obvious_monthly_bills_create_sources(self, db_session):
        """One-statement utility and insurance rows should still appear as projected sources."""
        from core.models.models_per_tenant import BankStatement, BankStatementTransaction

        statement = BankStatement(
            tenant_id=1,
            original_filename="bank_statement_2.pdf",
            stored_filename="bank_statement_2.pdf",
            file_path="/tmp/bank_statement_2.pdf",
            status="processed",
        )
        db_session.add(statement)
        db_session.commit()
        db_session.refresh(statement)

        for category, description, amount in (
            ("Insurance", "Insurance CERTAS H&A INS", 331.51),
            ("Hydro", "Misc Payment Hydro Ottawa", 204.53),
            ("Dining", "Coffee Shop", 8.75),
        ):
            db_session.add(
                BankStatementTransaction(
                    statement_id=statement.id,
                    date=date.today() - timedelta(days=15),
                    description=description,
                    amount=amount,
                    transaction_type="debit",
                    category=category,
                )
            )
        db_session.commit()

        service = CashFlowService(db_session)
        forecast = service.get_forecast(period="30d", current_balance=0.0)
        bank_outflows = [entry for entry in forecast.outflow_entries if entry.source == "bank_statement_pattern"]
        descriptions = {entry.description for entry in bank_outflows}

        assert "Insurance" in descriptions
        assert "Hydro" in descriptions
        assert "Dining" not in descriptions

    def test_bank_statement_365d_forecast_uses_year_lookback(self, db_session):
        """A yearly forecast should use up to a year of statement history for sources."""
        from core.models.models_per_tenant import BankStatement, BankStatementTransaction

        statement = BankStatement(
            tenant_id=1,
            original_filename="bank_statement_2.pdf",
            stored_filename="bank_statement_2.pdf",
            file_path="/tmp/bank_statement_2.pdf",
            status="processed",
        )
        db_session.add(statement)
        db_session.commit()
        db_session.refresh(statement)

        db_session.add(
            BankStatementTransaction(
                statement_id=statement.id,
                date=date.today() - timedelta(days=300),
                description="Misc Payment Hydro Ottawa",
                amount=204.53,
                transaction_type="debit",
                category="Hydro",
            )
        )
        db_session.commit()

        service = CashFlowService(db_session)
        forecast = service.get_forecast(period="365d", current_balance=0.0)
        bank_outflows = [entry for entry in forecast.outflow_entries if entry.source == "bank_statement_pattern"]

        assert any(entry.description == "Hydro" for entry in bank_outflows)

    def test_historical_average_references_matching_bank_statement_transactions(self, db_session):
        """Historical averages should show matching bank statement transaction source records."""
        from core.models.models_per_tenant import BankStatement, BankStatementTransaction

        statement = BankStatement(
            tenant_id=1,
            original_filename="payroll.csv",
            stored_filename="payroll.csv",
            file_path="/tmp/payroll.csv",
            status="done",
        )
        db_session.add(statement)
        db_session.commit()
        db_session.refresh(statement)

        db_session.add(
            BankStatementTransaction(
                statement_id=statement.id,
                date=date.today() - timedelta(days=10),
                description="Salary Deposit",
                amount=4500.0,
                transaction_type="credit",
                category="Salary",
            )
        )
        db_session.commit()

        service = CashFlowService(db_session)
        service.update_threshold_settings(bank_statement_inflow_categories=["Salary"])
        forecast = service.get_forecast(period="7d", current_balance=0.0)
        historical_inflows = [entry for entry in forecast.inflow_entries if entry.source == "historical_average"]

        assert historical_inflows
        assert historical_inflows[0].amount > 0
        assert "1 matching bank statement credits" in historical_inflows[0].source_details
        assert any(ref.type == "bank_statement_transaction" for ref in historical_inflows[0].references)

    def test_cashflow_settings_can_disable_bank_statement_patterns(self, db_session):
        """Bank statement patterns should be excluded when disabled in settings."""
        from core.models.models_per_tenant import BankStatement, BankStatementTransaction

        statement = BankStatement(
            tenant_id=1,
            original_filename="bank.csv",
            stored_filename="bank.csv",
            file_path="/tmp/bank.csv",
            status="processed",
        )
        db_session.add(statement)
        db_session.commit()
        db_session.refresh(statement)

        for days_ago in (60, 30):
            db_session.add(
                BankStatementTransaction(
                    statement_id=statement.id,
                    date=date.today() - timedelta(days=days_ago),
                    description="Utility Bill",
                    amount=120.0,
                    transaction_type="debit",
                    category="Utilities",
                )
            )
        db_session.commit()

        service = CashFlowService(db_session)
        service.update_threshold_settings(include_bank_statement_patterns=False)
        forecast = service.get_forecast(period="30d", current_balance=0.0)

        assert not any(entry.source == "bank_statement_pattern" for entry in forecast.outflow_entries)

    def test_cashflow_settings_filter_bank_statement_categories(self, db_session):
        """Configured debit categories should control which statement patterns are counted."""
        from core.models.models_per_tenant import BankStatement, BankStatementTransaction

        statement = BankStatement(
            tenant_id=1,
            original_filename="bank.csv",
            stored_filename="bank.csv",
            file_path="/tmp/bank.csv",
            status="processed",
        )
        db_session.add(statement)
        db_session.commit()
        db_session.refresh(statement)

        for category, amount in (("Mortgage", 1800.0), ("Dining", 75.0)):
            for days_ago in (60, 30):
                db_session.add(
                    BankStatementTransaction(
                        statement_id=statement.id,
                        date=date.today() - timedelta(days=days_ago),
                        description=f"{category} debit",
                        amount=amount,
                        transaction_type="debit",
                        category=category,
                    )
                )
        db_session.commit()

        service = CashFlowService(db_session)
        service.update_threshold_settings(bank_statement_outflow_categories=["Mortgage"])
        forecast = service.get_forecast(period="30d", current_balance=0.0)
        bank_outflows = [entry for entry in forecast.outflow_entries if entry.source == "bank_statement_pattern"]

        assert bank_outflows
        assert all(entry.description == "Mortgage" for entry in bank_outflows)

    def test_cashflow_settings_filter_bank_statement_categories_substring(self, db_session):
        """Configured categories should match via substring so 'Mortgage' matches 'Mortgage Payment'."""
        from core.models.models_per_tenant import BankStatement, BankStatementTransaction

        statement = BankStatement(
            tenant_id=1,
            original_filename="bank.csv",
            stored_filename="bank.csv",
            file_path="/tmp/bank.csv",
            status="processed",
        )
        db_session.add(statement)
        db_session.commit()
        db_session.refresh(statement)

        for category, amount in (("Mortgage Payment", 2000.0), ("Home Insurance Premium", 150.0), ("Coffee Shop", 5.0)):
            for days_ago in (60, 30):
                db_session.add(
                    BankStatementTransaction(
                        statement_id=statement.id,
                        date=date.today() - timedelta(days=days_ago),
                        description=f"{category} debit",
                        amount=amount,
                        transaction_type="debit",
                        category=category,
                    )
                )
        db_session.commit()

        service = CashFlowService(db_session)
        service.update_threshold_settings(bank_statement_outflow_categories=["Mortgage", "Insurance"])
        forecast = service.get_forecast(period="30d", current_balance=0.0)
        bank_outflows = [entry for entry in forecast.outflow_entries if entry.source == "bank_statement_pattern"]

        descriptions = {entry.description for entry in bank_outflows}
        assert "Mortgage Payment" in descriptions
        assert "Home Insurance Premium" in descriptions
        assert "Coffee Shop" not in descriptions
        """Historical average projections should be optional."""
        from core.models.models_per_tenant import Payment

        now = datetime.now(timezone.utc)
        db_session.add(
            Payment(
                amount=9000.0,
                currency="USD",
                payment_date=now - timedelta(days=10),
                payment_method="bank_transfer",
            )
        )
        db_session.commit()

        service = CashFlowService(db_session)
        service.update_threshold_settings(include_historical_averages=False)
        forecast = service.get_forecast(period="30d", current_balance=0.0)

        assert not any(entry.source == "historical_average" for entry in forecast.inflow_entries)

    def test_scenario_input_rejects_invalid_values(self):
        """Scenario values should not create negative cash flow entries."""
        with pytest.raises(ValidationError):
            ScenarioInput(description="Bad expense", additional_expense=-1)

        with pytest.raises(ValidationError):
            ScenarioInput(description="Bad delay", delay_days=-1)

        with pytest.raises(ValidationError):
            ScenarioInput(description="Bad revenue", revenue_change_percent=-101)

    def test_threshold_settings_reject_invalid_order(self):
        """Warning threshold must be at least the safety threshold."""
        with pytest.raises(ValidationError):
            CashFlowThresholdSettings(safety_threshold=10000.0, warning_threshold=5000.0)
