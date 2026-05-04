"""
Cash flow forecasting tools mixin.
"""
from typing import Any, Dict, List, Optional


SUPPORTED_CASHFLOW_PERIODS = {"7d", "30d", "90d", "365d"}


class CashFlowToolsMixin:
    def _validate_cashflow_period(self, period: str) -> Optional[Dict[str, Any]]:
        if period not in SUPPORTED_CASHFLOW_PERIODS:
            return {
                "success": False,
                "error": "Period must be one of: 7d, 30d, 90d, 365d",
            }
        return None

    async def get_cashflow_forecast(
        self,
        period: str = "30d",
        current_balance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Get projected cash inflows, outflows, balances, and alerts."""
        validation_error = self._validate_cashflow_period(period)
        if validation_error:
            return validation_error

        try:
            result = await self.api_client.get_cashflow_forecast(
                period=period,
                current_balance=current_balance,
            )
            return {
                "success": True,
                "data": result,
                "message": f"Cash flow forecast generated for {period}",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get cash flow forecast: {e}"}

    async def get_cashflow_runway(
        self,
        current_balance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculate cash runway from current balance and recent burn rate."""
        try:
            result = await self.api_client.get_cashflow_runway(
                current_balance=current_balance,
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": f"Failed to get cash flow runway: {e}"}

    async def run_cashflow_scenario(
        self,
        description: str,
        period: str = "30d",
        delayed_invoice_ids: Optional[List[int]] = None,
        delay_days: int = 30,
        additional_expense: Optional[float] = None,
        additional_expense_date: Optional[str] = None,
        revenue_change_percent: Optional[float] = None,
        expense_change_percent: Optional[float] = None,
        current_balance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run a cash flow what-if scenario."""
        validation_error = self._validate_cashflow_period(period)
        if validation_error:
            return validation_error
        if not description or not description.strip():
            return {"success": False, "error": "Scenario description is required"}
        if delay_days < 0:
            return {"success": False, "error": "delay_days must be greater than or equal to 0"}

        scenario: Dict[str, Any] = {
            "description": description,
            "delay_days": delay_days,
        }
        if delayed_invoice_ids:
            scenario["delayed_invoice_ids"] = delayed_invoice_ids
        if additional_expense is not None:
            if additional_expense < 0:
                return {"success": False, "error": "additional_expense must be greater than or equal to 0"}
            scenario["additional_expense"] = additional_expense
        if additional_expense_date:
            scenario["additional_expense_date"] = additional_expense_date
        if revenue_change_percent is not None:
            if revenue_change_percent < -100:
                return {"success": False, "error": "revenue_change_percent must be greater than or equal to -100"}
            scenario["revenue_change_percent"] = revenue_change_percent
        if expense_change_percent is not None:
            if expense_change_percent < -100:
                return {"success": False, "error": "expense_change_percent must be greater than or equal to -100"}
            scenario["expense_change_percent"] = expense_change_percent

        try:
            result = await self.api_client.run_cashflow_scenario(
                scenario=scenario,
                period=period,
                current_balance=current_balance,
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": f"Failed to run cash flow scenario: {e}"}

    async def get_cashflow_alerts(
        self,
        current_balance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Get cash flow threshold alerts."""
        try:
            result = await self.api_client.get_cashflow_alerts(
                current_balance=current_balance,
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": f"Failed to get cash flow alerts: {e}"}

    async def get_cashflow_thresholds(self) -> Dict[str, Any]:
        """Get cash flow threshold settings."""
        try:
            result = await self.api_client.get_cashflow_thresholds()
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": f"Failed to get cash flow thresholds: {e}"}

    async def update_cashflow_thresholds(
        self,
        settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update cash flow threshold settings."""
        if not settings:
            return {"success": False, "error": "At least one cash flow setting is required"}

        try:
            result = await self.api_client.update_cashflow_thresholds(settings=settings)
            return {
                "success": True,
                "data": result,
                "message": "Cash flow threshold settings updated successfully",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update cash flow thresholds: {e}"}
