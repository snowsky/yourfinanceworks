"""Continuous monitoring agent for investment optimization."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal

from .analyzers import build_recommendations, normalize_allocation
from .api_client import InvestmentAPIClient
from .models import MonitorCycle, Portfolio, PortfolioAnalysis, Recommendation
from .state import AgentState, append_history, write_snapshot


class PortfolioMonitorAgent:
    """Runs monitor cycles and deduplicates recommendations."""

    def __init__(self, api_client: InvestmentAPIClient, state: AgentState):
        self.api_client = api_client
        self.state = state

    def run_cycle(
        self,
        *,
        drift_threshold: Decimal,
        refresh_prices: bool = False,
        portfolio_ids: set[int] | None = None,
    ) -> MonitorCycle:
        if refresh_prices:
            self.api_client.refresh_prices()

        price_status = self.api_client.get_price_status()
        cross_summary = self.api_client.get_cross_summary()
        overlap = self.api_client.get_overlap()
        exposure = self.api_client.get_exposure()

        portfolio_payload = self.api_client.list_portfolios(limit=200)
        portfolio_items = portfolio_payload.get("items", [])
        portfolios = [Portfolio.from_api(item) for item in portfolio_items if not item.get("is_archived", False)]
        if portfolio_ids:
            portfolios = [portfolio for portfolio in portfolios if portfolio.id in portfolio_ids]

        analyses: list[PortfolioAnalysis] = []
        for portfolio in portfolios:
            performance = self.api_client.get_performance(portfolio.id)
            allocation_payload = self.api_client.get_allocation(portfolio.id)
            diversification = self.api_client.get_diversification(portfolio.id)
            rebalance = self.api_client.get_rebalance(portfolio.id)
            analyses.append(
                PortfolioAnalysis(
                    portfolio=portfolio,
                    performance=performance,
                    allocation=normalize_allocation(allocation_payload),
                    rebalance=rebalance,
                    diversification=diversification,
                )
            )

        recommendations = build_recommendations(
            analyses,
            exposure=exposure,
            overlap=overlap,
            price_status=price_status,
            drift_threshold=drift_threshold,
        )
        emitted = self._dedupe(recommendations)
        return MonitorCycle(
            analyses=tuple(analyses),
            recommendations=tuple(recommendations),
            emitted=tuple(emitted),
            price_status=price_status,
            cross_summary=cross_summary,
            overlap=overlap,
            exposure=exposure,
        )

    def persist(self, state_path) -> None:
        self.state.save(state_path)

    def persist_cycle_artifacts(self, cycle: MonitorCycle, *, state_path, history_path, snapshot_dir) -> None:
        """Persist state, history, and snapshot artifacts for a cycle."""
        snapshot_payload = self._serialize_cycle(cycle)
        snapshot_path = write_snapshot(snapshot_dir, snapshot_payload)
        append_history(
            history_path,
            {
                "timestamp": snapshot_payload["timestamp"],
                "snapshot_path": str(snapshot_path),
                "emitted_count": len(cycle.emitted),
                "recommendation_count": len(cycle.recommendations),
                "top_recommendation": cycle.recommendations[0].summary if cycle.recommendations else None,
            },
        )
        self.persist(state_path)

    def monitor_forever(
        self,
        *,
        drift_threshold: Decimal,
        interval_seconds: int,
        refresh_prices: bool = False,
        portfolio_ids: set[int] | None = None,
    ):
        while True:
            cycle = self.run_cycle(
                drift_threshold=drift_threshold,
                refresh_prices=refresh_prices,
                portfolio_ids=portfolio_ids,
            )
            yield cycle
            self.state.last_run_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            time.sleep(interval_seconds)

    def _dedupe(self, recommendations: list[Recommendation]) -> list[Recommendation]:
        emitted: list[Recommendation] = []
        current_fingerprints = {recommendation.fingerprint for recommendation in recommendations}
        self.state.recommendations = {
            fingerprint: severity
            for fingerprint, severity in self.state.recommendations.items()
            if fingerprint in current_fingerprints
        }

        for recommendation in recommendations:
            previous = self.state.recommendations.get(recommendation.fingerprint)
            current = f"{recommendation.severity:.2f}"
            if previous != current:
                emitted.append(recommendation)
            self.state.recommendations[recommendation.fingerprint] = current
        return emitted

    def _serialize_cycle(self, cycle: MonitorCycle) -> dict:
        """Convert a monitor cycle to a JSON-serializable payload."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price_status": cycle.price_status,
            "cross_summary": cycle.cross_summary,
            "overlap": cycle.overlap,
            "exposure": cycle.exposure,
            "recommendations": [
                {
                    "portfolio_id": recommendation.portfolio_id,
                    "portfolio_name": recommendation.portfolio_name,
                    "severity": str(recommendation.severity),
                    "kind": recommendation.kind,
                    "summary": recommendation.summary,
                    "reasons": list(recommendation.reasons),
                    "suggested_actions": list(recommendation.suggested_actions),
                    "fingerprint": recommendation.fingerprint,
                }
                for recommendation in cycle.recommendations
            ],
            "emitted": [recommendation.fingerprint for recommendation in cycle.emitted],
        }
