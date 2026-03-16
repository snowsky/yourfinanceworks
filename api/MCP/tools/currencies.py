"""
Currency-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ListCurrenciesArgs(BaseModel):
    active_only: bool = Field(default=True, description="Return only active currencies")


class CreateCurrencyArgs(BaseModel):
    code: str = Field(description="Currency code (e.g., USD, EUR)")
    name: str = Field(description="Currency name")
    symbol: str = Field(description="Currency symbol")
    decimal_places: int = Field(default=2, description="Number of decimal places")
    is_active: bool = Field(default=True, description="Whether the currency is active")


class ConvertCurrencyArgs(BaseModel):
    amount: float = Field(description="Amount to convert")
    from_currency: str = Field(description="Source currency code")
    to_currency: str = Field(description="Target currency code")
    conversion_date: Optional[str] = Field(default=None, description="Date for conversion rate (YYYY-MM-DD)")


class CurrencyToolsMixin:
    # Currency Management
    async def list_currencies(self, active_only: bool = True) -> Dict[str, Any]:
        """List supported currencies"""
        try:
            response = await self.api_client.list_currencies(active_only=active_only)

            # Extract items from paginated response
            currencies = self._extract_items_from_response(response, ["items", "data", "currencies"])

            return {
                "success": True,
                "data": currencies,
                "count": len(currencies),
                "active_only": active_only
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to list currencies: {e}"}

    async def create_currency(self, code: str, name: str, symbol: str, decimal_places: int = 2, is_active: bool = True) -> Dict[str, Any]:
        """Create a custom currency"""
        try:
            currency_data = {
                "code": code.upper(),
                "name": name,
                "symbol": symbol,
                "decimal_places": decimal_places,
                "is_active": is_active
            }

            currency = await self.api_client.create_currency(currency_data)

            return {
                "success": True,
                "data": currency,
                "message": "Currency created successfully"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to create currency: {e}"}

    async def convert_currency(self, amount: float, from_currency: str, to_currency: str, conversion_date: Optional[str] = None) -> Dict[str, Any]:
        """Convert amount from one currency to another"""
        try:
            conversion = await self.api_client.convert_currency(
                amount=amount,
                from_currency=from_currency,
                to_currency=to_currency,
                conversion_date=conversion_date
            )

            return {
                "success": True,
                "data": conversion
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to convert currency: {e}"}
