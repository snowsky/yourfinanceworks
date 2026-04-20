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


@mcp.tool()
async def get_portfolio_rebalance(portfolio_id: int) -> dict:
    """Get rebalance recommendations and drift analysis for a portfolio."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.get_portfolio_rebalance(portfolio_id=portfolio_id)


@mcp.tool()
async def get_portfolio_diversification(portfolio_id: int) -> dict:
    """Get diversification analysis for a portfolio."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.get_portfolio_diversification(portfolio_id=portfolio_id)


@mcp.tool()
async def get_portfolio_community_sentiment(
    portfolio_id: int,
    lookback_days: int = 7,
    max_holdings: int = 8,
    max_items_per_source: int = 5,
) -> dict:
    """Get public community sentiment research for a portfolio."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.get_portfolio_community_sentiment(
        portfolio_id=portfolio_id,
        lookback_days=lookback_days,
        max_holdings=max_holdings,
        max_items_per_source=max_items_per_source,
    )


@mcp.tool()
async def get_portfolio_transactions(portfolio_id: int) -> dict:
    """Get transactions for a portfolio."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.get_portfolio_transactions(portfolio_id=portfolio_id)


@mcp.tool()
async def get_cross_portfolio_summary() -> dict:
    """Get unified cross-portfolio summary with overlap and concentration context."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.get_cross_portfolio_summary()


@mcp.tool()
async def get_cross_portfolio_overlap() -> dict:
    """Get overlap analysis across portfolios."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.get_cross_portfolio_overlap()


@mcp.tool()
async def get_cross_portfolio_exposure() -> dict:
    """Get concentration and exposure analysis across portfolios."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.get_cross_portfolio_exposure()


@mcp.tool()
async def get_investment_price_status() -> dict:
    """Get market price freshness status for holdings."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.get_investment_price_status()


@mcp.tool()
async def refresh_investment_prices() -> dict:
    """Trigger a holdings market price refresh."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.refresh_investment_prices()


@mcp.tool()
async def get_portfolio_optimization_recommendations(drift_threshold: float = 1.0) -> dict:
    """
    Get ranked, read-only optimization recommendations across all portfolios.

    Args:
        drift_threshold: Minimum drift percentage required before a rebalance recommendation is emitted.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    return await server_context.tools.get_portfolio_optimization_recommendations(
        drift_threshold=drift_threshold
    )
