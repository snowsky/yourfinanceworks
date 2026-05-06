"""Command-line interface for the finance agent."""

from __future__ import annotations

import argparse
import getpass
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from .agent import PortfolioMonitorAgent
from .analyzers import normalize_allocation
from .api_client import APIError, InvestmentAPIClient
from .chat_agent import CliChatAgent
from .config import load_profile
from .document_classifier import DocumentClassifier
from .document_router import DocumentIngestionAgent
from .models import Portfolio, PortfolioAnalysis
from .render import (
    print_chat_response,
    print_json,
    print_portfolio_analysis,
    print_portfolios,
    print_recommendations,
    print_sentiment_report,
    print_transactions,
)
from .state import AgentState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Investment portfolio monitoring and optimization CLI")
    parser.add_argument("--profile", default=None, help="Profile name from .finance-agent/config.json")
    parser.add_argument("--config", default=None, help="Path to config JSON. Defaults to .finance-agent/config.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of formatted output")

    subparsers = parser.add_subparsers(dest="resource", required=True)

    auth = subparsers.add_parser("auth", help="Authentication commands")
    auth_sub = auth.add_subparsers(dest="action", required=True)
    login = auth_sub.add_parser("login", help="Log in and cache a bearer token")
    login.add_argument("--email", default=None, help="YFW account email")
    login.add_argument("--password", default=None, help="YFW account password. Omit to prompt.")
    browser_login = auth_sub.add_parser("browser-login", help="Log in by approving a browser/device code")
    browser_login.add_argument("--no-open", action="store_true", help="Print the URL instead of opening a browser")
    browser_login.add_argument("--timeout", type=int, default=600, help="Seconds to wait for browser approval")
    device_login = auth_sub.add_parser("device-login", help="Alias for browser-login")
    device_login.add_argument("--no-open", action="store_true", help="Print the URL instead of opening a browser")
    device_login.add_argument("--timeout", type=int, default=600, help="Seconds to wait for browser approval")
    auth_sub.add_parser("status", help="Show cached login status")
    auth_sub.add_parser("logout", help="Remove the cached bearer token")

    portfolio = subparsers.add_parser("portfolio", help="Portfolio operations")
    portfolio_sub = portfolio.add_subparsers(dest="action", required=True)

    portfolio_sub.add_parser("list", help="List portfolios")

    show = portfolio_sub.add_parser("show", help="Show a portfolio")
    show.add_argument("portfolio_id", type=int)

    analyze = portfolio_sub.add_parser("analyze", help="Analyze a portfolio")
    analyze.add_argument("portfolio_id", type=int)

    research = portfolio_sub.add_parser("research", help="Research public community sentiment for a portfolio")
    research.add_argument("portfolio_id", type=int)
    research.add_argument("--lookback-days", type=int, default=7, help="Recent days to include in research")
    research.add_argument("--max-holdings", type=int, default=8, help="Largest holdings to analyze")
    research.add_argument("--max-items-per-source", type=int, default=5, help="Maximum source items per holding")

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
    monitor.add_argument("--with-sentiment", action="store_true", help="Include public community sentiment research")
    monitor.add_argument("--sentiment-lookback-days", type=int, default=7, help="Days of sentiment history to include")
    monitor.add_argument("--history-path", default=None, help="Override JSONL history output path")
    monitor.add_argument("--snapshot-dir", default=None, help="Override snapshot output directory")

    portfolio_sub.add_parser("cross-summary", help="Show cross-portfolio summary")
    portfolio_sub.add_parser("exposure", help="Show cross-portfolio exposure analysis")
    portfolio_sub.add_parser("overlap", help="Show cross-portfolio overlap analysis")

    prices = subparsers.add_parser("prices", help="Holding price operations")
    prices_sub = prices.add_subparsers(dest="action", required=True)
    prices_sub.add_parser("status", help="Show price freshness status")
    prices_sub.add_parser("refresh", help="Refresh holding prices")

    documents = subparsers.add_parser("documents", help="Document scan and YFW ingestion")
    documents_sub = documents.add_subparsers(dest="action", required=True)

    scan = documents_sub.add_parser("scan", help="Scan and classify local PDF/image/CSV files")
    scan.add_argument("folder", help="Folder to scan")
    scan.add_argument("--no-recursive", action="store_true", help="Scan only the top-level folder")
    scan.add_argument("--send", action="store_true", help="Send classified files to YFW")
    scan.add_argument("--portfolio-id", type=int, default=None, help="Portfolio ID for portfolio/holdings files")
    scan.add_argument("--export-destination-id", type=int, default=None, help="Batch export destination ID")
    scan.add_argument("--client-id", type=int, default=None, help="Client ID for invoice files")
    scan.add_argument("--webhook-url", default=None, help="Webhook URL for YFW batch completion")
    scan.add_argument("--card-type", default="auto", choices=["auto", "debit", "credit"], help="Card type for statements")

    agent = subparsers.add_parser("agent", help="Conversational CLI agent")
    agent_sub = agent.add_subparsers(dest="action", required=True)
    chat = agent_sub.add_parser("chat", help="Talk to the CLI agent")
    chat.add_argument("message", nargs="*", help="One-shot message. Omit for interactive chat.")
    chat.add_argument("--config-id", type=int, default=0, help="AI provider config ID. Defaults to backend default.")
    chat.add_argument("--page-context", default=None, help="Optional JSON page context, matching the web AI Assistant payload.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config) if args.config else None
    profile_name = args.profile
    if args.profile and Path(args.profile).suffix == ".json":
        config_path = Path(args.profile)
        profile_name = None
    profile = load_profile(
        config_path=config_path or Path(".finance-agent/config.json"),
        profile_name=profile_name,
    )

    try:
        with InvestmentAPIClient(profile) as client:
            if args.resource == "auth":
                return _handle_auth(args, client, profile)
            if args.resource == "portfolio":
                return _handle_portfolio(args, client, profile)
            if args.resource == "prices":
                return _handle_prices(args, client)
            if args.resource == "documents":
                return _handle_documents(args, client, profile)
            if args.resource == "agent":
                return _handle_agent(args, client, profile)
    except APIError as exc:
        print_json(
            {
                "error": str(exc),
                "status_code": exc.status_code,
                "payload": exc.payload,
            }
        )
        return 1
    return 0


def _handle_auth(args, client: InvestmentAPIClient, profile) -> int:
    if args.action == "status":
        print_json(client.auth_status())
        return 0
    if args.action == "logout":
        print_json(client.logout())
        return 0
    if args.action == "login":
        email = args.email or profile.email
        password = args.password or profile.password
        if not email:
            email = input("Email: ").strip()
        if not password:
            password = getpass.getpass("Password: ")
        login_profile = replace(
            profile,
            auth_type="password",
            email=email,
            password=password,
        )
        with InvestmentAPIClient(login_profile) as login_client:
            print_json(login_client.authenticate())
        return 0
    if args.action in {"browser-login", "device-login"}:
        device = client.start_device_login()
        if args.no_open:
            print(f"Open this URL to approve CLI login: {device['verification_uri_complete']}")
        else:
            import webbrowser
            webbrowser.open(device["verification_uri_complete"])
            print(f"Opened browser for CLI login. If it did not open, visit: {device['verification_uri_complete']}")
        print(f"Device code: {device['user_code']}")
        result = client.poll_device_login(device, timeout_seconds=args.timeout)
        print_json(result)
        return 0
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

    if args.action == "research":
        payload = client.get_community_sentiment(
            args.portfolio_id,
            lookback_days=args.lookback_days,
            max_holdings=args.max_holdings,
            max_items_per_source=args.max_items_per_source,
        )
        if args.json:
            print_json(payload)
        else:
            print_sentiment_report(payload)
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
                include_sentiment=bool(args.with_sentiment),
                sentiment_lookback_days=args.sentiment_lookback_days,
            )
            if args.json:
                print_json(
                    {
                        "recommendations": [recommendation.__dict__ for recommendation in cycle.recommendations],
                        "emitted": [recommendation.__dict__ for recommendation in cycle.emitted],
                        "cross_summary": cycle.cross_summary,
                        "price_status": cycle.price_status,
                        "sentiment_reports": cycle.sentiment_reports,
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
                include_sentiment=bool(args.with_sentiment),
                sentiment_lookback_days=args.sentiment_lookback_days,
            ):
                if args.json:
                    print_json(
                        {
                            "recommendations": [recommendation.__dict__ for recommendation in cycle.recommendations],
                            "emitted": [recommendation.__dict__ for recommendation in cycle.emitted],
                            "cross_summary": cycle.cross_summary,
                            "price_status": cycle.price_status,
                            "sentiment_reports": cycle.sentiment_reports,
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


def _handle_documents(args, client: InvestmentAPIClient, profile) -> int:
    if args.action != "scan":
        return 0
    classifier = DocumentClassifier(profile)
    agent = DocumentIngestionAgent(client, classifier)
    documents = agent.scan_and_classify(Path(args.folder), recursive=not args.no_recursive)
    payload = {
        "documents": [
            {
                "path": document.path,
                "filename": document.filename,
                "document_type": document.document_type,
                "confidence": float(document.confidence),
                "reason": document.reason,
            }
            for document in documents
        ]
    }
    if args.send:
        routed = agent.send_to_yfw(
            documents,
            portfolio_id=args.portfolio_id,
            export_destination_id=args.export_destination_id,
            client_id=args.client_id,
            webhook_url=args.webhook_url,
            card_type=args.card_type,
        )
        payload["sent"] = [
            {
                "filename": item.document.filename,
                "document_type": item.document.document_type,
                "destination": item.destination,
                "response": item.response,
            }
            for item in routed
        ]
    print_json(payload)
    return 0


def _handle_agent(args, client: InvestmentAPIClient, profile) -> int:
    if args.action != "chat":
        return 0
    chat_agent = CliChatAgent(client, profile)
    page_context = _parse_page_context(args.page_context)
    if args.message:
        result = chat_agent.handle(
            " ".join(args.message),
            config_id=args.config_id,
            page_context=page_context,
        )
        if args.json:
            print_json(result)
        else:
            print_chat_response(result)
        return 0
    try:
        while True:
            message = input("finance-agent> ").strip()
            if message.lower() in {"exit", "quit"}:
                return 0
            if message:
                result = chat_agent.handle(
                    message,
                    config_id=args.config_id,
                    page_context=page_context,
                )
                if args.json:
                    print_json(result)
                else:
                    print_chat_response(result)
    except (EOFError, KeyboardInterrupt):
        return 0


def _parse_page_context(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise APIError(f"Invalid --page-context JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise APIError("--page-context must be a JSON object.")
    return parsed


def _load_analysis(client: InvestmentAPIClient, portfolio_id: int) -> PortfolioAnalysis:
    portfolio_payload = client.get_portfolio(portfolio_id)
    return PortfolioAnalysis(
        portfolio=Portfolio.from_api(portfolio_payload),
        performance=client.get_performance(portfolio_id),
        allocation=normalize_allocation(client.get_allocation(portfolio_id)),
        rebalance=client.get_rebalance(portfolio_id),
        diversification=client.get_diversification(portfolio_id),
    )
