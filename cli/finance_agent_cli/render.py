"""Terminal rendering helpers."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from .models import Portfolio, PortfolioAnalysis, Recommendation


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))


def print_portfolios(portfolios: list[Portfolio]) -> None:
    rows = [
        ["ID", "Name", "Type", "Currency", "Holdings", "Value", "Cost"],
    ]
    for portfolio in portfolios:
        rows.append(
            [
                str(portfolio.id),
                portfolio.name,
                portfolio.portfolio_type,
                portfolio.currency,
                str(portfolio.holdings_count),
                f"{portfolio.total_value:.2f}",
                f"{portfolio.total_cost:.2f}",
            ]
        )
    print(_format_table(rows))


def print_portfolio_analysis(analysis: PortfolioAnalysis) -> None:
    portfolio = analysis.portfolio
    print(f"Portfolio {portfolio.id}: {portfolio.name}")
    print(f"Type: {portfolio.portfolio_type}  Currency: {portfolio.currency}")
    print(f"Value: {portfolio.total_value:.2f}  Cost: {portfolio.total_cost:.2f}  Holdings: {portfolio.holdings_count}")
    print("")
    print("Current Allocation")
    current_rows = [["Asset Class", "Current %", "Target %", "Drift %"]]
    rebalance = analysis.rebalance or {}
    targets = rebalance.get("target_allocations") or portfolio.target_allocations
    drifts = rebalance.get("drifts") or {}
    for asset_class, current in sorted(analysis.allocation.items()):
        current_rows.append(
            [
                asset_class,
                f"{current:.2f}",
                f"{Decimal(str(targets.get(asset_class, 0))):.2f}",
                f"{Decimal(str(drifts.get(asset_class, 0))):.2f}",
            ]
        )
    print(_format_table(current_rows))
    print("")
    if rebalance and rebalance.get("recommended_actions"):
        print("Suggested Actions")
        action_rows = [["Action", "Asset Class", "Amount", "Drift %"]]
        for action in rebalance["recommended_actions"]:
            action_rows.append(
                [
                    str(action.get("action_type")),
                    str(action.get("asset_class")),
                    f"{Decimal(str(action.get('amount', 0))):.2f}",
                    f"{Decimal(str(action.get('percentage_drift', 0))):.2f}",
                ]
            )
        print(_format_table(action_rows))
    else:
        print("No rebalance actions recommended.")


def print_transactions(transactions: list[dict[str, Any]]) -> None:
    rows = [["Date", "Type", "Symbol", "Amount", "Fees", "Notes"]]
    for transaction in transactions:
        rows.append(
            [
                str(transaction.get("transaction_date", "")),
                str(transaction.get("transaction_type", "")),
                str(transaction.get("security_symbol", transaction.get("holding_id", ""))),
                str(transaction.get("total_amount", "")),
                str(transaction.get("fees", "")),
                str(transaction.get("notes", ""))[:40],
            ]
        )
    print(_format_table(rows))


def print_recommendations(recommendations: list[Recommendation], *, title: str = "Recommendations") -> None:
    print(title)
    if not recommendations:
        print("No new optimization recommendations.")
        return
    for recommendation in recommendations:
        print(
            f"- [{recommendation.severity:.2f}] Portfolio {recommendation.portfolio_id} "
            f"({recommendation.portfolio_name}): {recommendation.summary}"
        )
        for reason in recommendation.reasons:
            print(f"  reason: {reason}")
        for action in recommendation.suggested_actions:
            print(f"  action: {action}")


def _format_table(rows: list[list[str]]) -> str:
    widths = [max(len(row[idx]) for row in rows) for idx in range(len(rows[0]))]
    formatted: list[str] = []
    for index, row in enumerate(rows):
        formatted.append("  ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row)))
        if index == 0:
            formatted.append("  ".join("-" * width for width in widths))
    return "\n".join(formatted)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return str(value)
