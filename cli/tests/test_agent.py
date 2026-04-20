from decimal import Decimal

from cli.finance_agent_cli.agent import PortfolioMonitorAgent
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
