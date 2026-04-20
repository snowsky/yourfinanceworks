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


def build_sentiment_recommendations(
    sentiment_reports: list[dict[str, Any]],
    *,
    minimum_mentions: int = 4,
    minimum_abs_score: Decimal = Decimal("0.35"),
) -> list[Recommendation]:
    """Create research-oriented recommendations from community sentiment reports."""
    recommendations: list[Recommendation] = []

    for report in sentiment_reports:
        portfolio_id = int(report["portfolio_id"])
        portfolio_name = str(report.get("portfolio_name") or f"Portfolio {portfolio_id}")
        for holding in report.get("holdings") or []:
            mentions = int(holding.get("mentions") or 0)
            score = to_decimal(holding.get("sentiment_score"))
            label = str(holding.get("sentiment_label") or "unavailable")
            confidence = str(holding.get("confidence") or "low")
            if mentions < minimum_mentions or abs(score) < minimum_abs_score or confidence == "low":
                continue
            if label not in {"positive", "negative"}:
                continue

            symbol = str(holding.get("symbol") or "UNKNOWN")
            severity = (
                abs(score) * Decimal("10")
                + min(Decimal(mentions) / Decimal("2"), Decimal("5"))
            ).quantize(Decimal("0.01"))

            reasons = [
                f"{mentions} recent community mentions across public sources",
                f"net sentiment {score:+.2f} with {confidence} confidence",
            ]
            top_signals = holding.get("top_signals") or []
            if top_signals:
                reasons.append(f"recurring themes: {', '.join(str(item) for item in top_signals[:3])}")

            if label == "positive":
                summary = f"{symbol} has positive community momentum; validate the thesis before chasing."
                actions = (
                    f"Review whether {symbol} already reflects the crowd thesis in price",
                    f"Check sizing risk before adding to {symbol}",
                )
            else:
                summary = f"{symbol} has negative community sentiment; review bearish arguments against your thesis."
                actions = (
                    f"Re-check catalysts and downside cases for {symbol}",
                    f"Decide whether the current {symbol} position still matches conviction",
                )

            recommendations.append(
                Recommendation(
                    portfolio_id=portfolio_id,
                    portfolio_name=portfolio_name,
                    severity=severity,
                    kind="sentiment",
                    summary=summary,
                    reasons=tuple(reasons),
                    suggested_actions=actions,
                    fingerprint=_fingerprint(
                        portfolio_id,
                        portfolio_name,
                        (f"sentiment:{symbol}:{label}:{score:.2f}:{mentions}",),
                    ),
                )
            )

    recommendations.sort(key=lambda item: item.severity, reverse=True)
    return recommendations


def _fingerprint(portfolio_id: int, portfolio_name: str, actions: tuple[str, ...]) -> str:
    payload = f"{portfolio_id}|{portfolio_name}|{'|'.join(actions)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
