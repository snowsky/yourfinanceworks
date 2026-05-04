import pytest

from MCP.tools import InvoiceTools


class FakeCashFlowAPIClient:
    def __init__(self):
        self.last_scenario = None
        self.last_thresholds = None

    async def get_cashflow_forecast(self, period="30d", current_balance=None):
        return {
            "period": period,
            "current_balance": current_balance,
            "projected_end_balance": 1234.0,
        }

    async def get_cashflow_runway(self, current_balance=None):
        return {
            "current_balance": current_balance or 5000.0,
            "runway_days": 42,
            "is_sustainable": False,
        }

    async def run_cashflow_scenario(self, scenario, period="30d", current_balance=None):
        self.last_scenario = {
            "scenario": scenario,
            "period": period,
            "current_balance": current_balance,
        }
        return {
            "scenario_description": scenario["description"],
            "balance_impact": -100.0,
        }

    async def get_cashflow_alerts(self, current_balance=None):
        return {
            "has_alerts": False,
            "alerts": [],
            "current_balance": current_balance or 5000.0,
        }

    async def get_cashflow_thresholds(self):
        return {
            "safety_threshold": 10000.0,
            "warning_threshold": 25000.0,
            "currency": "USD",
        }

    async def update_cashflow_thresholds(self, settings):
        self.last_thresholds = settings
        return settings


@pytest.mark.asyncio
async def test_cashflow_forecast_tool_validates_period():
    tools = InvoiceTools(FakeCashFlowAPIClient())

    result = await tools.get_cashflow_forecast(period="14d")

    assert result["success"] is False
    assert "Period must be one of" in result["error"]


@pytest.mark.asyncio
async def test_cashflow_scenario_tool_builds_payload():
    api_client = FakeCashFlowAPIClient()
    tools = InvoiceTools(api_client)

    result = await tools.run_cashflow_scenario(
        description="Late payment and higher expenses",
        period="90d",
        delayed_invoice_ids=[1, 2],
        delay_days=15,
        additional_expense=250.0,
        additional_expense_date="2026-05-15",
        expense_change_percent=10.0,
        current_balance=3000.0,
    )

    assert result["success"] is True
    assert api_client.last_scenario == {
        "scenario": {
            "description": "Late payment and higher expenses",
            "delay_days": 15,
            "delayed_invoice_ids": [1, 2],
            "additional_expense": 250.0,
            "additional_expense_date": "2026-05-15",
            "expense_change_percent": 10.0,
        },
        "period": "90d",
        "current_balance": 3000.0,
    }


@pytest.mark.asyncio
async def test_update_cashflow_thresholds_requires_settings():
    tools = InvoiceTools(FakeCashFlowAPIClient())

    result = await tools.update_cashflow_thresholds({})

    assert result["success"] is False
    assert result["error"] == "At least one cash flow setting is required"
