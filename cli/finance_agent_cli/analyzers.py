"""Recommendation and ranking logic for portfolio monitoring."""

from __future__ import annotations

from decimal import Decimal
import hashlib
from typing import Any

from .models import Portfolio, PortfolioAnalysis, Recommendation, to_decimal


def normalize_allocation(allocation_payload: dict[str, Any]) -> dict[str, Decimal]:
    """Flatten allocation payload to {asset_class: percentage}."""
    allocations = allocation_payload.get("allocations") or {}
    normalized: dict[str, Decimal] = {}
    for asset_class, detail in allocations.items():
        if isinstance(detail, dict):
            normalized[str(asset_class)] = to_decimal(detail.get("percentage"))
        else:
            normalized[str(asset_class)] = to_decimal(detail)
    return normalized


def build_recommendations(
    analyses: list[PortfolioAnalysis],
    *,
    exposure: dict[str, Any] | None = None,
    overlap: dict[str, Any] | None = None,
    price_status: dict[str, Any] | None = None,
    drift_threshold: Decimal = Decimal("1.0"),
) -> list[Recommendation]:
    """Build and rank optimization recommendations."""
    exposure = exposure or {}
    overlap = overlap or {}
    price_status = price_status or {}
    recommendations: list[Recommendation] = []

    stale_prices = int(price_status.get("stale_prices") or 0)
    concentration_warnings = exposure.get("concentration_warnings") or []
    overlap_count = int(overlap.get("overlapping_securities_count") or 0)

    for analysis in analyses:
        rebalance = analysis.rebalance
        if not rebalance:
            continue

        drifts = rebalance.get("drifts") or {}
        actions = rebalance.get("recommended_actions") or []
        if not actions:
            continue

        max_drift = max((abs(to_decimal(value)) for value in drifts.values()), default=Decimal("0"))
        if max_drift < drift_threshold:
            continue

        total_action_amount = sum((to_decimal(action.get("amount")) for action in actions), Decimal("0"))
        severity = max_drift + min(total_action_amount / Decimal("1000"), Decimal("20"))
        reasons = [f"max drift {max_drift:.2f}% across target allocations"]

        if stale_prices:
            severity += Decimal("2")
            reasons.append(f"{stale_prices} holdings have stale prices")
        if concentration_warnings:
            severity += Decimal(min(len(concentration_warnings), 3))
            reasons.append(f"{len(concentration_warnings)} concentration warnings across portfolios")
        if overlap_count:
            severity += Decimal("1")
            reasons.append(f"{overlap_count} overlapping securities detected")

        suggested_actions = tuple(
            f"{action.get('action_type')} {action.get('asset_class')} ~{to_decimal(action.get('amount')):.2f}"
            for action in actions
        )
        summary = str(rebalance.get("summary") or "Rebalancing is recommended.")
        fingerprint = _fingerprint(analysis.portfolio.id, analysis.portfolio.name, suggested_actions)
        recommendations.append(
            Recommendation(
                portfolio_id=analysis.portfolio.id,
                portfolio_name=analysis.portfolio.name,
                severity=severity.quantize(Decimal("0.01")),
                kind="rebalance",
                summary=summary,
                reasons=tuple(reasons),
                suggested_actions=suggested_actions,
                fingerprint=fingerprint,
            )
        )

    recommendations.sort(key=lambda item: item.severity, reverse=True)
    return recommendations


def _fingerprint(portfolio_id: int, portfolio_name: str, actions: tuple[str, ...]) -> str:
    payload = f"{portfolio_id}|{portfolio_name}|{'|'.join(actions)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
