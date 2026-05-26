"""Terminal rendering helpers."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import Portfolio, PortfolioAnalysis, Recommendation


def _money(value: Any) -> str:
    try:
        return f"{Decimal(str(value if value is not None else 0)):,.2f}"
    except (InvalidOperation, ValueError, TypeError):
        return str(value)


def _pct(value: Any) -> str:
    try:
        return f"{Decimal(str(value if value is not None else 0)):.2f}%"
    except (InvalidOperation, ValueError, TypeError):
        return str(value)


def _qty(value: Any) -> str:
    try:
        return f"{Decimal(str(value if value is not None else 0)):,.4f}"
    except (InvalidOperation, ValueError, TypeError):
        return str(value)


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=_json_default))


def print_chat_response(payload: dict[str, Any]) -> None:
    data = payload.get("data") if isinstance(payload, dict) else None
    response = data.get("response") if isinstance(data, dict) else None
    if isinstance(response, str):
        print(response)
        return
    print_json(payload)


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


def print_sentiment_report(payload: dict[str, Any]) -> None:
    print(f"Community Sentiment: {payload.get('portfolio_name')} ({payload.get('portfolio_id')})")
    print(f"Generated: {payload.get('generated_at')}")
    summary = payload.get("portfolio_summary") or {}
    print(
        "Summary: "
        f"{summary.get('positive_holdings', 0)} positive, "
        f"{summary.get('negative_holdings', 0)} negative, "
        f"{summary.get('mixed_holdings', 0)} mixed, "
        f"{summary.get('unavailable_holdings', 0)} unavailable"
    )
    print("")
    rows = [["Symbol", "Label", "Score", "Mentions", "Confidence", "Signals"]]
    for holding in payload.get("holdings") or []:
        rows.append(
            [
                str(holding.get("symbol", "")),
                str(holding.get("sentiment_label", "")),
                f"{Decimal(str(holding.get('sentiment_score', 0))):.2f}",
                str(holding.get("mentions", 0)),
                str(holding.get("confidence", "")),
                ", ".join(str(item) for item in (holding.get("top_signals") or [])[:3]),
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


def print_cross_summary(payload: dict[str, Any]) -> None:
    print("Cross-Portfolio Summary")
    print(
        f"Portfolios: {payload.get('portfolio_count', 0)}  "
        f"Unique Securities: {payload.get('total_unique_securities', 0)}"
    )
    print(
        f"Combined Value: {_money(payload.get('total_combined_value'))}  "
        f"Cost: {_money(payload.get('total_combined_cost'))}  "
        f"Gain/Loss: {_money(payload.get('total_gain_loss'))} "
        f"({_pct(payload.get('total_gain_loss_pct'))})"
    )
    print(
        f"Overlapping Securities: {payload.get('overlapping_securities_count', 0)} "
        f"({_pct(payload.get('overlap_percentage'))})"
    )

    top_holdings = payload.get("top_holdings") or []
    if top_holdings:
        print("")
        print("Top Holdings")
        rows = [["Symbol", "Qty", "Value", "Gain/Loss %", "Portfolios"]]
        for holding in top_holdings:
            rows.append(
                [
                    str(holding.get("security_symbol", "")),
                    _qty(holding.get("total_quantity")),
                    _money(holding.get("total_current_value")),
                    _pct(holding.get("gain_loss_pct")),
                    str(holding.get("portfolio_count", 0)),
                ]
            )
        print(_format_table(rows))

    warnings = payload.get("concentration_warnings") or []
    if warnings:
        print("")
        print("Concentration Warnings")
        print(_format_table(_exposure_rows(warnings)))


def print_overlap_analysis(payload: dict[str, Any]) -> None:
    print("Cross-Portfolio Overlap Analysis")
    print(
        f"Portfolios: {payload.get('portfolio_count', 0)}  "
        f"Unique Securities: {payload.get('total_unique_securities', 0)}"
    )
    print(
        f"Overlapping: {payload.get('overlapping_securities_count', 0)} "
        f"({_pct(payload.get('overlap_percentage'))})"
    )

    details = payload.get("overlap_details") or []
    if not details:
        print("")
        print("No overlap between portfolios.")
        return

    print("")
    print("Overlap Details")
    rows = [["Symbol", "Qty", "Value", "Portfolios"]]
    for detail in details:
        names = ", ".join(detail.get("portfolio_names") or [])
        rows.append(
            [
                str(detail.get("security_symbol", "")),
                _qty(detail.get("total_quantity")),
                _money(detail.get("total_value")),
                names[:50],
            ]
        )
    print(_format_table(rows))


def print_exposure_report(payload: dict[str, Any]) -> None:
    print("Cross-Portfolio Exposure Report")
    print(f"Total Combined Value: {_money(payload.get('total_combined_value'))}")
    print(
        f"Securities: {payload.get('securities_count', 0)}  "
        f"Concentration Warnings: {payload.get('concentration_warnings_count', 0)}"
    )

    warnings = payload.get("concentration_warnings") or []
    if warnings:
        print("")
        print("Concentration Warnings")
        print(_format_table(_exposure_rows(warnings)))

    exposures = payload.get("exposures") or []
    if exposures:
        print("")
        print("Top Exposures")
        print(_format_table(_exposure_rows(exposures[:20])))


def print_document_scan(payload: dict[str, Any]) -> None:
    documents = payload.get("documents") or []
    print(f"Scanned {len(documents)} document(s)")
    if documents:
        rows = [["Filename", "Type", "Confidence", "Reason"]]
        for document in documents:
            rows.append(
                [
                    str(document.get("filename", ""))[:40],
                    str(document.get("document_type", "")),
                    f"{Decimal(str(document.get('confidence', 0))):.2f}",
                    str(document.get("reason", ""))[:30],
                ]
            )
        print(_format_table(rows))

    sent = payload.get("sent") or []
    if sent:
        print("")
        print(f"Sent {len(sent)} document(s) to YFW")
        rows = [["Filename", "Type", "Destination"]]
        for item in sent:
            rows.append(
                [
                    str(item.get("filename", ""))[:40],
                    str(item.get("document_type", "")),
                    str(item.get("destination", "")),
                ]
            )
        print(_format_table(rows))


def _exposure_rows(items: list[dict[str, Any]]) -> list[list[str]]:
    rows = [["Symbol", "Value", "% of Total", "Portfolios"]]
    for item in items:
        rows.append(
            [
                str(item.get("security_symbol", "")),
                _money(item.get("total_value")),
                _pct(item.get("pct_of_total")),
                str(item.get("portfolio_count", 0)),
            ]
        )
    return rows


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
