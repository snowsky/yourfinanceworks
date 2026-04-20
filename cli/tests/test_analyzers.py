from decimal import Decimal

from cli.finance_agent_cli.analyzers import build_recommendations
from cli.finance_agent_cli.models import Portfolio, PortfolioAnalysis


def test_build_recommendations_ranks_drift_and_context():
    portfolio = Portfolio(
        id=1,
        name="Growth",
        portfolio_type="TAXABLE",
        currency="USD",
        holdings_count=4,
        total_value=Decimal("100000"),
        total_cost=Decimal("85000"),
    )
    analysis = PortfolioAnalysis(
        portfolio=portfolio,
        performance={},
        allocation={"STOCKS": Decimal("80"), "BONDS": Decimal("20")},
        rebalance={
            "drifts": {"STOCKS": "10.0", "BONDS": "-10.0"},
            "recommended_actions": [
                {"action_type": "SELL", "asset_class": "STOCKS", "amount": "10000", "percentage_drift": "10.0"}
            ],
            "summary": "Rebalancing is recommended.",
        },
        diversification={},
    )

    recommendations = build_recommendations(
        [analysis],
        exposure={"concentration_warnings": ["AAPL > 25%"]},
        overlap={"overlapping_securities_count": 3},
        price_status={"stale_prices": 2},
        drift_threshold=Decimal("1.0"),
    )

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation.portfolio_id == 1
    assert recommendation.severity > Decimal("10")
    assert any("stale prices" in reason for reason in recommendation.reasons)


def test_build_recommendations_skips_balanced_portfolios():
    portfolio = Portfolio(
        id=2,
        name="Income",
        portfolio_type="RETIREMENT",
        currency="USD",
    )
    analysis = PortfolioAnalysis(
        portfolio=portfolio,
        performance={},
        allocation={"BONDS": Decimal("60"), "STOCKS": Decimal("40")},
        rebalance={
            "drifts": {"BONDS": "0.5", "STOCKS": "-0.5"},
            "recommended_actions": [],
            "summary": "Balanced.",
        },
        diversification={},
    )

    assert build_recommendations([analysis], drift_threshold=Decimal("1.0")) == []
