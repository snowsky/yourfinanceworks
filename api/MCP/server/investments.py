"""Investment Management tool registrations."""
from ._shared import mcp, server_context


@mcp.tool()
async def list_portfolios(skip: int = 0, limit: int = 50) -> dict:
    """
    List all investment portfolios with summary metrics including total value and performance.

    Args:
        skip: Number of portfolios to skip for pagination (default: 0)
        limit: Maximum number of portfolios to return (default: 50)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_portfolios(skip=skip, limit=limit)


@mcp.tool()
async def get_portfolio_summary(portfolio_id: int) -> dict:
    """
    Get a comprehensive summary of a specific portfolio by ID, including its holdings,
    recent performance, asset allocation, and dividend summary.

    Args:
        portfolio_id: ID of the portfolio to retrieve
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_portfolio_summary(portfolio_id=portfolio_id)
