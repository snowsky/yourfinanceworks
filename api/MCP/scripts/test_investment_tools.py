#!/usr/bin/env python3
"""
Lightweight verification for investment MCP tool coverage.

This script validates that:
1. the InvoiceTools mixin exposes the expected investment helpers
2. the InvoiceAPIClient exposes the expected REST wrappers
3. the MCP server module exports the expected investment tool registrations
"""

import inspect
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_investment_tools_class():
    print("1. Checking InvoiceTools investment methods...")
    from MCP.tools import InvoiceTools

    class MockAPIClient:
        pass

    tools = InvoiceTools(MockAPIClient())
    expected_methods = [
        "list_portfolios",
        "get_portfolio_summary",
        "get_portfolio_rebalance",
        "get_portfolio_diversification",
        "get_portfolio_community_sentiment",
        "get_portfolio_transactions",
        "get_cross_portfolio_summary",
        "get_cross_portfolio_overlap",
        "get_cross_portfolio_exposure",
        "get_investment_price_status",
        "refresh_investment_prices",
        "get_portfolio_optimization_recommendations",
    ]
    missing = [method for method in expected_methods if not hasattr(tools, method)]
    if missing:
        print(f"   FAIL missing methods: {missing}")
        return False
    print(f"   OK found {len(expected_methods)} methods")
    return True


def test_investment_api_client():
    print("2. Checking InvoiceAPIClient investment endpoints...")
    from MCP.api_client import InvoiceAPIClient

    client = InvoiceAPIClient(
        base_url="http://localhost:8000/api/v1",
        email="test@example.com",
        password="testpassword",
    )
    expected_methods = [
        "list_portfolios",
        "get_portfolio",
        "get_portfolio_holdings",
        "get_portfolio_performance",
        "get_portfolio_allocation",
        "get_portfolio_dividends",
        "get_portfolio_transactions",
        "get_portfolio_rebalance",
        "get_portfolio_diversification",
        "get_portfolio_community_sentiment",
        "get_cross_portfolio_summary",
        "get_cross_portfolio_overlap",
        "get_cross_portfolio_exposure",
        "get_price_status",
        "update_prices",
    ]
    missing = [method for method in expected_methods if not hasattr(client, method)]
    if missing:
        print(f"   FAIL missing API client methods: {missing}")
        return False
    print(f"   OK found {len(expected_methods)} methods")
    return True


def test_investment_server_exports():
    print("3. Checking MCP server investment tool exports...")
    import MCP.server.investments as server_module

    expected_functions = [
        "list_portfolios",
        "get_portfolio_summary",
        "get_portfolio_rebalance",
        "get_portfolio_diversification",
        "get_portfolio_community_sentiment",
        "get_portfolio_transactions",
        "get_cross_portfolio_summary",
        "get_cross_portfolio_overlap",
        "get_cross_portfolio_exposure",
        "get_investment_price_status",
        "refresh_investment_prices",
        "get_portfolio_optimization_recommendations",
    ]
    missing = [name for name in expected_functions if not hasattr(server_module, name)]
    if missing:
        print(f"   FAIL missing server functions: {missing}")
        return False

    exported = [name for name in expected_functions if hasattr(server_module, name)]
    print(f"   OK found {len(exported)} exported investment functions")
    return True


if __name__ == "__main__":
    checks = [
        test_investment_tools_class,
        test_investment_api_client,
        test_investment_server_exports,
    ]
    passed = 0
    for check in checks:
        if check():
            passed += 1
    print(f"\nResult: {passed}/{len(checks)} checks passed")
    raise SystemExit(0 if passed == len(checks) else 1)
