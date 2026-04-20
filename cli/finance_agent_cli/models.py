"""Typed models used by the finance agent CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


def to_decimal(value: Any, default: str = "0") -> Decimal:
    """Convert JSON values to Decimal consistently."""
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class Portfolio:
    """Normalized portfolio summary used by the CLI."""

    id: int
    name: str
    portfolio_type: str
    currency: str
    holdings_count: int = 0
    total_value: Decimal = field(default_factory=Decimal)
    total_cost: Decimal = field(default_factory=Decimal)
    target_allocations: dict[str, Decimal] = field(default_factory=dict)
    is_archived: bool = False

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Portfolio":
        targets = payload.get("target_allocations") or {}
        return cls(
            id=int(payload["id"]),
            name=str(payload["name"]),
            portfolio_type=str(payload.get("portfolio_type", "UNKNOWN")),
            currency=str(payload.get("currency", "USD")),
            holdings_count=int(payload.get("holdings_count") or 0),
            total_value=to_decimal(payload.get("total_value")),
            total_cost=to_decimal(payload.get("total_cost")),
            target_allocations={str(key): to_decimal(value) for key, value in targets.items()},
            is_archived=bool(payload.get("is_archived", False)),
        )


@dataclass(frozen=True)
class Recommendation:
    """Actionable recommendation emitted by the monitor."""

    portfolio_id: int
    portfolio_name: str
    severity: Decimal
    kind: str
    summary: str
    reasons: tuple[str, ...]
    suggested_actions: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True)
class PortfolioAnalysis:
    """Normalized analysis for a single portfolio."""

    portfolio: Portfolio
    performance: dict[str, Any]
    allocation: dict[str, Decimal]
    rebalance: dict[str, Any] | None
    diversification: dict[str, Any] | None


@dataclass(frozen=True)
class MonitorCycle:
    """Results from one monitor cycle."""

    analyses: tuple[PortfolioAnalysis, ...]
    recommendations: tuple[Recommendation, ...]
    emitted: tuple[Recommendation, ...]
    price_status: dict[str, Any]
    cross_summary: dict[str, Any]
    overlap: dict[str, Any]
    exposure: dict[str, Any]
    sentiment_reports: dict[int, dict[str, Any]] = field(default_factory=dict)
