"""
Investment portfolio-related tools mixin.
"""
from typing import Any, Dict, List, Optional
import logging


class InvestmentToolsMixin:
    # Investment Management Tools
    async def list_portfolios(self, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
        """List all investment portfolios with summary metrics"""
        try:
            response = await self.api_client.list_portfolios(skip=skip, limit=limit)
            portfolios = self._extract_items_from_response(response, ["items", "data", "portfolios"])

            return {
                "success": True,
                "data": portfolios,
                "count": len(portfolios),
                "total": response.get("total", len(portfolios)),
                "pagination": {"skip": skip, "limit": limit}
            }
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to list portfolios: {e}")
            return {"success": False, "error": f"Failed to list portfolios: {e}"}

    async def get_portfolio_summary(self, portfolio_id: int) -> Dict[str, Any]:
        """Get a comprehensive summary of a portfolio including holdings and performance"""
        try:
            # 1. Get Portfolio details (includes summary metrics in the response usually)
            portfolio = await self.api_client.get_portfolio(portfolio_id)

            # 2. Get Holdings
            holdings_resp = await self.api_client.get_portfolio_holdings(portfolio_id)
            holdings = self._extract_items_from_response(holdings_resp, ["items", "data", "holdings"])

            # 3. Get Performance
            performance = await self.api_client.get_portfolio_performance(portfolio_id)

            # 4. Get Allocation
            allocation = await self.api_client.get_portfolio_allocation(portfolio_id)

            return {
                "success": True,
                "data": {
                    "portfolio": portfolio,
                    "holdings_count": len(holdings),
                    "holdings_summary": holdings[:10], # Show first 10 holdings in summary
                    "performance": performance,
                    "allocation": allocation
                }
            }
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get portfolio summary for {portfolio_id}: {e}")
            return {"success": False, "error": f"Failed to get portfolio summary: {e}"}
