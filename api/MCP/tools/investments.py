"""
Investment portfolio-related tools mixin.
"""
from typing import Any, Dict, List, Optional
import asyncio
import logging
from decimal import Decimal
import hashlib


class InvestmentToolsMixin:
    def _build_recommendation_fingerprint(self, portfolio_id: int, actions: List[Dict[str, Any]]) -> str:
        payload = f"{portfolio_id}|" + "|".join(
            f"{action.get('action_type')}:{action.get('asset_class')}:{action.get('amount')}"
            for action in actions
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _score_rebalance_recommendation(
        self,
        rebalance: Dict[str, Any],
        *,
        stale_prices: int = 0,
        overlap_count: int = 0,
        concentration_warning_count: int = 0,
        drift_threshold: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        drifts = rebalance.get("drifts") or {}
        actions = rebalance.get("recommended_actions") or []
        if not actions:
            return None

        max_drift = max((abs(Decimal(str(value))) for value in drifts.values()), default=Decimal("0"))
        if max_drift < Decimal(str(drift_threshold)):
            return None

        total_amount = sum((Decimal(str(action.get("amount", 0))) for action in actions), Decimal("0"))
        severity = max_drift + min(total_amount / Decimal("1000"), Decimal("20"))
        reasons = [f"max drift {max_drift:.2f}% across target allocations"]

        if stale_prices:
            severity += Decimal("2")
            reasons.append(f"{stale_prices} holdings have stale prices")
        if concentration_warning_count:
            severity += Decimal(str(min(concentration_warning_count, 3)))
            reasons.append(f"{concentration_warning_count} concentration warnings detected")
        if overlap_count:
            severity += Decimal("1")
            reasons.append(f"{overlap_count} overlapping securities detected")

        return {
            "severity": float(severity.quantize(Decimal("0.01"))),
            "summary": rebalance.get("summary") or "Rebalancing is recommended.",
            "reasons": reasons,
            "suggested_actions": [
                {
                    "action_type": action.get("action_type"),
                    "asset_class": action.get("asset_class"),
                    "amount": action.get("amount"),
                    "percentage_drift": action.get("percentage_drift"),
                }
                for action in actions
            ],
        }

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
            portfolio, holdings_resp, performance, allocation = await asyncio.gather(
                self.api_client.get_portfolio(portfolio_id),
                self.api_client.get_portfolio_holdings(portfolio_id),
                self.api_client.get_portfolio_performance(portfolio_id),
                self.api_client.get_portfolio_allocation(portfolio_id),
            )
            holdings = self._extract_items_from_response(holdings_resp, ["items", "data", "holdings"])

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

    async def get_portfolio_rebalance(self, portfolio_id: int) -> Dict[str, Any]:
        """Get rebalance recommendations and drift analysis for a portfolio."""
        try:
            response = await self.api_client.get_portfolio_rebalance(portfolio_id)
            return {"success": True, "data": response}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get rebalance report for {portfolio_id}: {e}")
            return {"success": False, "error": f"Failed to get rebalance report: {e}"}

    async def get_portfolio_diversification(self, portfolio_id: int) -> Dict[str, Any]:
        """Get diversification analysis for a portfolio."""
        try:
            response = await self.api_client.get_portfolio_diversification(portfolio_id)
            return {"success": True, "data": response}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get diversification analysis for {portfolio_id}: {e}")
            return {"success": False, "error": f"Failed to get diversification analysis: {e}"}

    async def get_portfolio_community_sentiment(
        self,
        portfolio_id: int,
        lookback_days: int = 7,
        max_holdings: int = 8,
        max_items_per_source: int = 5,
    ) -> Dict[str, Any]:
        """Get public community sentiment research for a portfolio."""
        try:
            response = await self.api_client.get_portfolio_community_sentiment(
                portfolio_id,
                lookback_days=lookback_days,
                max_holdings=max_holdings,
                max_items_per_source=max_items_per_source,
            )
            return {"success": True, "data": response}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get community sentiment for {portfolio_id}: {e}")
            return {"success": False, "error": f"Failed to get community sentiment: {e}"}

    async def get_portfolio_transactions(self, portfolio_id: int) -> Dict[str, Any]:
        """Get transactions for a portfolio."""
        try:
            response = await self.api_client.get_portfolio_transactions(portfolio_id)
            transactions = self._extract_items_from_response(response, ["items", "data", "transactions"])
            if transactions == response and isinstance(response, list):
                transactions = response
            return {"success": True, "data": transactions, "count": len(transactions)}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get transactions for {portfolio_id}: {e}")
            return {"success": False, "error": f"Failed to get transactions: {e}"}

    async def get_cross_portfolio_summary(self) -> Dict[str, Any]:
        """Get a unified cross-portfolio summary."""
        try:
            response = await self.api_client.get_cross_portfolio_summary()
            return {"success": True, "data": response}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get cross-portfolio summary: {e}")
            return {"success": False, "error": f"Failed to get cross-portfolio summary: {e}"}

    async def get_cross_portfolio_overlap(self) -> Dict[str, Any]:
        """Get overlap analysis across portfolios."""
        try:
            response = await self.api_client.get_cross_portfolio_overlap()
            return {"success": True, "data": response}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get cross-portfolio overlap: {e}")
            return {"success": False, "error": f"Failed to get cross-portfolio overlap: {e}"}

    async def get_cross_portfolio_exposure(self) -> Dict[str, Any]:
        """Get concentration/exposure analysis across portfolios."""
        try:
            response = await self.api_client.get_cross_portfolio_exposure()
            return {"success": True, "data": response}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get cross-portfolio exposure: {e}")
            return {"success": False, "error": f"Failed to get cross-portfolio exposure: {e}"}

    async def get_investment_price_status(self) -> Dict[str, Any]:
        """Get investment holding price freshness status."""
        try:
            response = await self.api_client.get_price_status()
            return {"success": True, "data": response}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get price status: {e}")
            return {"success": False, "error": f"Failed to get price status: {e}"}

    async def refresh_investment_prices(self) -> Dict[str, Any]:
        """Trigger a holdings price refresh."""
        try:
            response = await self.api_client.update_prices()
            return {"success": True, "data": response}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to refresh prices: {e}")
            return {"success": False, "error": f"Failed to refresh prices: {e}"}

    async def get_portfolio_optimization_recommendations(self, drift_threshold: float = 1.0) -> Dict[str, Any]:
        """
        Get ranked optimization recommendations across all portfolios in one call.

        The result is read-only and combines rebalance drift, stale price context,
        overlap, and concentration warnings into a single recommendation list.
        """
        try:
            portfolios_resp, price_status, overlap, exposure = await asyncio.gather(
                self.api_client.list_portfolios(skip=0, limit=200),
                self.api_client.get_price_status(),
                self.api_client.get_cross_portfolio_overlap(),
                self.api_client.get_cross_portfolio_exposure(),
            )
            portfolios = self._extract_items_from_response(portfolios_resp, ["items", "data", "portfolios"])
            active_portfolios = [portfolio for portfolio in portfolios if not portfolio.get("is_archived", False)]

            stale_prices = int(price_status.get("stale_prices") or 0)
            overlap_count = int(overlap.get("overlapping_securities_count") or 0)
            concentration_warning_count = len(exposure.get("concentration_warnings") or [])

            rebalance_payloads = await asyncio.gather(
                *(self.api_client.get_portfolio_rebalance(int(portfolio["id"])) for portfolio in active_portfolios),
                return_exceptions=True,
            )

            recommendations: List[Dict[str, Any]] = []
            for portfolio, rebalance in zip(active_portfolios, rebalance_payloads):
                if isinstance(rebalance, Exception):
                    logging.getLogger(__name__).warning(
                        "Skipping portfolio %s rebalance due to error: %s",
                        portfolio.get("id"),
                        rebalance,
                    )
                    continue

                scored = self._score_rebalance_recommendation(
                    rebalance,
                    stale_prices=stale_prices,
                    overlap_count=overlap_count,
                    concentration_warning_count=concentration_warning_count,
                    drift_threshold=drift_threshold,
                )
                if not scored:
                    continue

                recommendations.append(
                    {
                        "portfolio_id": portfolio.get("id"),
                        "portfolio_name": portfolio.get("name"),
                        "portfolio_type": portfolio.get("portfolio_type"),
                        "fingerprint": self._build_recommendation_fingerprint(
                            int(portfolio["id"]),
                            scored["suggested_actions"],
                        ),
                        **scored,
                    }
                )

            recommendations.sort(key=lambda item: item["severity"], reverse=True)

            return {
                "success": True,
                "data": {
                    "drift_threshold": drift_threshold,
                    "portfolio_count": len(active_portfolios),
                    "recommendation_count": len(recommendations),
                    "price_status": price_status,
                    "overlap": overlap,
                    "exposure": exposure,
                    "recommendations": recommendations,
                },
            }
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get portfolio optimization recommendations: {e}")
            return {"success": False, "error": f"Failed to get portfolio optimization recommendations: {e}"}
