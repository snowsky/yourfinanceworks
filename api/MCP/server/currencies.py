"""Currency Management tool registrations."""
from typing import Optional

from ._shared import mcp, server_context


@mcp.tool()
async def list_currencies(active_only: bool = True) -> dict:
    """
    List supported currencies with optional filtering for active currencies only.

    Args:
        active_only: Return only active currencies (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_currencies(active_only=active_only)


@mcp.tool()
async def create_currency(
    code: str,
    name: str,
    symbol: str,
    decimal_places: int = 2,
    is_active: bool = True,
) -> dict:
    """
    Create a custom currency for the tenant.

    Args:
        code: Currency code (e.g., USD, EUR)
        name: Currency name
        symbol: Currency symbol
        decimal_places: Number of decimal places (default: 2)
        is_active: Whether the currency is active (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_currency(
        code=code, name=name, symbol=symbol, decimal_places=decimal_places, is_active=is_active
    )


@mcp.tool()
async def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    conversion_date: Optional[str] = None,
) -> dict:
    """
    Convert amount from one currency to another using current or historical exchange rates.

    Args:
        amount: Amount to convert
        from_currency: Source currency code
        to_currency: Target currency code
        conversion_date: Date for conversion rate in YYYY-MM-DD format (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.convert_currency(
        amount=amount,
        from_currency=from_currency,
        to_currency=to_currency,
        conversion_date=conversion_date,
    )
