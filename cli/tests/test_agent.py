from decimal import Decimal

from cli.finance_agent_cli.agent import (
    SEVERITY_BUCKET,
    PortfolioMonitorAgent,
    _severity_bucket_str,
)
from cli.finance_agent_cli.state import AgentState


class StubClient:
    def __init__(self):
        self.calls = []

    def refresh_prices(self):
        self.calls.append("refresh_prices")
        return {"success": 1}

    def get_price_status(self):
        return {"stale_prices": 1, "fresh_prices": 3}

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
                    "holdings_count": 2,
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


def test_severity_bucket_quantizes_to_two_decimal_places():
    assert _severity_bucket_str(Decimal("1.014")) == "1.01"
    assert _severity_bucket_str(Decimal("1.015")) == "1.02"  # ROUND_HALF_EVEN bumps .015 -> .02
    assert _severity_bucket_str(Decimal("1.0")) == "1.00"
    assert SEVERITY_BUCKET == Decimal("0.01")


def test_monitor_dedupes_identical_recommendations():
    client = StubClient()
    agent = PortfolioMonitorAgent(client, AgentState())

    first = agent.run_cycle(drift_threshold=Decimal("1.0"))
    second = agent.run_cycle(drift_threshold=Decimal("1.0"))

    assert len(first.emitted) == 1
    assert len(second.emitted) == 0


def test_monitor_reemits_when_severity_changes():
    client = StubClient()
    agent = PortfolioMonitorAgent(client, AgentState())
    agent.run_cycle(drift_threshold=Decimal("1.0"))

    def changed_rebalance(_portfolio_id):
        return {
            "drifts": {"STOCKS": "8.0", "BONDS": "-8.0"},
            "recommended_actions": [
                {"action_type": "SELL", "asset_class": "STOCKS", "amount": "800", "percentage_drift": "8.0"}
            ],
            "summary": "Reduce equity overweight.",
        }

    client.get_rebalance = changed_rebalance
    updated = agent.run_cycle(drift_threshold=Decimal("1.0"))
    assert len(updated.emitted) == 1


def test_monitor_forever_recovers_after_cycle_failure(monkeypatch):
    monkeypatch.setattr("cli.finance_agent_cli.agent.time.sleep", lambda _: None)

    client = StubClient()
    agent = PortfolioMonitorAgent(client, AgentState())

    attempts = {"count": 0}
    original_run_cycle = agent.run_cycle

    def flaky_run_cycle(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 2:
            raise RuntimeError("simulated transient failure")
        return original_run_cycle(*args, **kwargs)

    agent.run_cycle = flaky_run_cycle

    generator = agent.monitor_forever(drift_threshold=Decimal("1.0"), interval_seconds=1)
    first = next(generator)
    third = next(generator)

    assert first is not None
    assert third is not None
    assert attempts["count"] == 3


def test_monitor_persists_history_and_snapshot(tmp_path):
    client = StubClient()
    agent = PortfolioMonitorAgent(client, AgentState())
    cycle = agent.run_cycle(drift_threshold=Decimal("1.0"))

    state_path = tmp_path / "state.json"
    history_path = tmp_path / "history.jsonl"
    snapshot_dir = tmp_path / "snapshots"

    agent.persist_cycle_artifacts(
        cycle,
        state_path=state_path,
        history_path=history_path,
        snapshot_dir=snapshot_dir,
    )

    assert state_path.exists()
    assert history_path.exists()
    snapshots = list(snapshot_dir.glob("monitor-*.json"))
    assert len(snapshots) == 1
