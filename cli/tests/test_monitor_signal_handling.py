"""SIGTERM/clean-stop semantics for PortfolioMonitorAgent.monitor_forever."""

from __future__ import annotations

import signal
from decimal import Decimal

from cli.finance_agent_cli.agent import PortfolioMonitorAgent
from cli.finance_agent_cli.state import AgentState


class StubClient:
    """Minimal API client surface used by run_cycle. Each cycle returns one drifting portfolio."""

    def refresh_prices(self):
        return {"success": 1}

    def get_price_status(self):
        return {"stale_prices": 0, "fresh_prices": 1}

    def get_cross_summary(self):
        return {"portfolio_count": 1}

    def get_overlap(self):
        return {"overlapping_securities_count": 0}

    def get_exposure(self):
        return {"concentration_warnings": []}

    def list_portfolios(self, limit=200):
        return {
            "items": [
                {
                    "id": 1,
                    "name": "Growth",
                    "portfolio_type": "TAXABLE",
                    "currency": "USD",
                    "holdings_count": 1,
                    "total_value": "10000",
                    "total_cost": "9000",
                }
            ]
        }

    def get_performance(self, portfolio_id):
        return {"total_return_percentage": "11.1"}

    def get_allocation(self, portfolio_id):
        return {"allocations": {"STOCKS": {"percentage": "70"}, "BONDS": {"percentage": "30"}}}

    def get_diversification(self, portfolio_id):
        return {"score": 70}

    def get_rebalance(self, portfolio_id):
        return {
            "drifts": {"STOCKS": "5.0", "BONDS": "-5.0"},
            "recommended_actions": [
                {"action_type": "SELL", "asset_class": "STOCKS", "amount": "500", "percentage_drift": "5.0"}
            ],
            "summary": "Reduce equity overweight.",
        }


def test_request_stop_exits_loop_after_current_cycle(monkeypatch):
    monkeypatch.setattr("cli.finance_agent_cli.agent.time.sleep", lambda _: None)

    agent = PortfolioMonitorAgent(StubClient(), AgentState())

    cycles_emitted = 0
    for _ in agent.monitor_forever(drift_threshold=Decimal("1.0"), interval_seconds=1):
        cycles_emitted += 1
        agent.request_stop()

    assert cycles_emitted == 1


def test_sigterm_handler_sets_stop_flag(monkeypatch):
    monkeypatch.setattr("cli.finance_agent_cli.agent.time.sleep", lambda _: None)

    agent = PortfolioMonitorAgent(StubClient(), AgentState())
    previous = agent._install_signal_handlers()
    try:
        assert agent._stop_requested is False
        # Invoke the registered handler directly (cross-platform; avoids actually killing the process)
        installed = signal.getsignal(signal.SIGTERM)
        assert callable(installed)
        installed(signal.SIGTERM, None)
        assert agent._stop_requested is True
    finally:
        agent._restore_signal_handlers(previous)


def test_monitor_forever_restores_previous_sigterm_handler(monkeypatch):
    monkeypatch.setattr("cli.finance_agent_cli.agent.time.sleep", lambda _: None)

    sentinel_called = []

    def sentinel_handler(_signum, _frame):
        sentinel_called.append(True)

    original = signal.signal(signal.SIGTERM, sentinel_handler)
    try:
        agent = PortfolioMonitorAgent(StubClient(), AgentState())

        for _ in agent.monitor_forever(drift_threshold=Decimal("1.0"), interval_seconds=1):
            agent.request_stop()

        # After monitor_forever exits, the sentinel must be back in place.
        assert signal.getsignal(signal.SIGTERM) is sentinel_handler
    finally:
        signal.signal(signal.SIGTERM, original)


def test_monitor_forever_logs_clean_stop(monkeypatch, caplog):
    import logging

    monkeypatch.setattr("cli.finance_agent_cli.agent.time.sleep", lambda _: None)

    agent = PortfolioMonitorAgent(StubClient(), AgentState())

    with caplog.at_level(logging.INFO, logger="finance_agent_cli.monitor"):
        for _ in agent.monitor_forever(drift_threshold=Decimal("1.0"), interval_seconds=1):
            agent.request_stop()

    assert any("Monitor stopped cleanly" in record.message for record in caplog.records)
