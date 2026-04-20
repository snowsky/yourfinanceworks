"""Command-line interface for the finance agent."""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Sequence

from .agent import PortfolioMonitorAgent
from .analyzers import normalize_allocation
from .api_client import InvestmentAPIClient
from .config import load_profile
from .models import Portfolio, PortfolioAnalysis
from .render import (
    print_json,
    print_portfolio_analysis,
    print_portfolios,
    print_recommendations,
    print_transactions,
)
from .state import AgentState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Investment portfolio monitoring and optimization CLI")
    parser.add_argument("--profile", default=None, help="Profile name from .finance-agent/config.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of formatted output")

    subparsers = parser.add_subparsers(dest="resource", required=True)

    portfolio = subparsers.add_parser("portfolio", help="Portfolio operations")
    portfolio_sub = portfolio.add_subparsers(dest="action", required=True)

    portfolio_sub.add_parser("list", help="List portfolios")

    show = portfolio_sub.add_parser("show", help="Show a portfolio")
    show.add_argument("portfolio_id", type=int)

    analyze = portfolio_sub.add_parser("analyze", help="Analyze a portfolio")
    analyze.add_argument("portfolio_id", type=int)

    rebalance = portfolio_sub.add_parser("rebalance", help="Show rebalance actions for a portfolio")
    rebalance.add_argument("portfolio_id", type=int)

    transactions = portfolio_sub.add_parser("transactions", help="List portfolio transactions")
    transactions.add_argument("portfolio_id", type=int)

    monitor = portfolio_sub.add_parser("monitor", help="Run the optimization monitor")
    monitor.add_argument("--interval", type=int, default=None, help="Polling interval in seconds")
    monitor.add_argument("--drift-threshold", type=float, default=None, help="Minimum drift percentage to alert on")
    monitor.add_argument("--refresh-prices", action="store_true", help="Refresh market prices before each cycle")
    monitor.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    monitor.add_argument("--portfolio-id", type=int, action="append", default=None, help="Limit monitoring to selected portfolio IDs")
    monitor.add_argument("--history-path", default=None, help="Override JSONL history output path")
    monitor.add_argument("--snapshot-dir", default=None, help="Override snapshot output directory")

    portfolio_sub.add_parser("cross-summary", help="Show cross-portfolio summary")
    portfolio_sub.add_parser("exposure", help="Show cross-portfolio exposure analysis")
    portfolio_sub.add_parser("overlap", help="Show cross-portfolio overlap analysis")

    prices = subparsers.add_parser("prices", help="Holding price operations")
    prices_sub = prices.add_subparsers(dest="action", required=True)
    prices_sub.add_parser("status", help="Show price freshness status")
    prices_sub.add_parser("refresh", help="Refresh holding prices")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    profile = load_profile(profile_name=args.profile)

    with InvestmentAPIClient(profile) as client:
        if args.resource == "portfolio":
            return _handle_portfolio(args, client, profile)
        if args.resource == "prices":
            return _handle_prices(args, client)
    return 0


def _handle_portfolio(args, client: InvestmentAPIClient, profile) -> int:
    if args.action == "list":
        payload = client.list_portfolios(limit=200)
        items = [Portfolio.from_api(item) for item in payload.get("items", [])]
        if args.json:
            print_json(payload)
        else:
            print_portfolios(items)
        return 0

    if args.action == "show":
        payload = client.get_portfolio(args.portfolio_id)
        if args.json:
            print_json(payload)
        else:
            print_portfolios([Portfolio.from_api(payload)])
        return 0

    if args.action in {"analyze", "rebalance"}:
        analysis = _load_analysis(client, args.portfolio_id)
        if args.json:
            print_json(
                {
                    "portfolio": analysis.portfolio.__dict__,
                    "performance": analysis.performance,
                    "allocation": {key: float(value) for key, value in analysis.allocation.items()},
                    "rebalance": analysis.rebalance,
                    "diversification": analysis.diversification,
                }
            )
        else:
            print_portfolio_analysis(analysis)
        return 0

    if args.action == "transactions":
        transactions = client.get_transactions(args.portfolio_id)
        if args.json:
            print_json(transactions)
        else:
            print_transactions(transactions)
        return 0

    if args.action == "cross-summary":
        payload = client.get_cross_summary()
        print_json(payload)
        return 0

    if args.action == "exposure":
        payload = client.get_exposure()
        print_json(payload)
        return 0

    if args.action == "overlap":
        payload = client.get_overlap()
        print_json(payload)
        return 0

    if args.action == "monitor":
        state = AgentState.load(profile.state_path)
        agent = PortfolioMonitorAgent(client, state)
        drift_threshold = Decimal(str(args.drift_threshold if args.drift_threshold is not None else profile.drift_threshold))
        interval = args.interval or profile.interval_seconds
        refresh_prices = bool(args.refresh_prices or profile.refresh_prices_on_monitor)
        portfolio_ids = set(args.portfolio_id or [])
        history_path = args.history_path or profile.history_path
        snapshot_dir = args.snapshot_dir or profile.snapshot_dir

        if args.once:
            cycle = agent.run_cycle(
                drift_threshold=drift_threshold,
                refresh_prices=refresh_prices,
                portfolio_ids=portfolio_ids or None,
            )
            if args.json:
                print_json(
                    {
                        "recommendations": [recommendation.__dict__ for recommendation in cycle.recommendations],
                        "emitted": [recommendation.__dict__ for recommendation in cycle.emitted],
                        "cross_summary": cycle.cross_summary,
                        "price_status": cycle.price_status,
                    }
                )
            else:
                print_recommendations(list(cycle.emitted), title="New Recommendations")
            agent.persist_cycle_artifacts(
                cycle,
                state_path=profile.state_path,
                history_path=history_path,
                snapshot_dir=snapshot_dir,
            )
            return 0

        try:
            for cycle in agent.monitor_forever(
                drift_threshold=drift_threshold,
                interval_seconds=interval,
                refresh_prices=refresh_prices,
                portfolio_ids=portfolio_ids or None,
            ):
                if args.json:
                    print_json(
                        {
                            "recommendations": [recommendation.__dict__ for recommendation in cycle.recommendations],
                            "emitted": [recommendation.__dict__ for recommendation in cycle.emitted],
                            "cross_summary": cycle.cross_summary,
                            "price_status": cycle.price_status,
                        }
                    )
                else:
                    print_recommendations(list(cycle.emitted), title="New Recommendations")
                agent.persist_cycle_artifacts(
                    cycle,
                    state_path=profile.state_path,
                    history_path=history_path,
                    snapshot_dir=snapshot_dir,
                )
        except KeyboardInterrupt:
            agent.persist(profile.state_path)
            return 0

    return 0


def _handle_prices(args, client: InvestmentAPIClient) -> int:
    if args.action == "status":
        print_json(client.get_price_status())
        return 0
    if args.action == "refresh":
        print_json(client.refresh_prices())
        return 0
    return 0


def _load_analysis(client: InvestmentAPIClient, portfolio_id: int) -> PortfolioAnalysis:
    portfolio_payload = client.get_portfolio(portfolio_id)
    return PortfolioAnalysis(
        portfolio=Portfolio.from_api(portfolio_payload),
        performance=client.get_performance(portfolio_id),
        allocation=normalize_allocation(client.get_allocation(portfolio_id)),
        rebalance=client.get_rebalance(portfolio_id),
        diversification=client.get_diversification(portfolio_id),
    )
