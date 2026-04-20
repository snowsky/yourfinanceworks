from decimal import Decimal

from cli.finance_agent_cli.analyzers import build_sentiment_recommendations


def test_build_sentiment_recommendations_emits_positive_and_negative_signals():
    reports = [
        {
            "portfolio_id": 1,
            "portfolio_name": "Growth",
            "holdings": [
                {
                    "symbol": "NVDA",
                    "mentions": 9,
                    "sentiment_score": "0.62",
                    "sentiment_label": "positive",
                    "confidence": "high",
                    "top_signals": ["ai", "earnings"],
                },
                {
                    "symbol": "TSLA",
                    "mentions": 7,
                    "sentiment_score": "-0.57",
                    "sentiment_label": "negative",
                    "confidence": "medium",
                    "top_signals": ["valuation", "demand"],
                },
            ],
        }
    ]

    recommendations = build_sentiment_recommendations(reports)

    assert len(recommendations) == 2
    assert recommendations[0].kind == "sentiment"
    assert recommendations[0].severity >= Decimal("7.0")
    assert any("NVDA" in recommendation.summary for recommendation in recommendations)
    assert any("TSLA" in recommendation.summary for recommendation in recommendations)


def test_build_sentiment_recommendations_skips_weak_or_low_confidence_signals():
    reports = [
        {
            "portfolio_id": 1,
            "portfolio_name": "Growth",
            "holdings": [
                {
                    "symbol": "AAPL",
                    "mentions": 3,
                    "sentiment_score": "0.20",
                    "sentiment_label": "positive",
                    "confidence": "low",
                    "top_signals": [],
                }
            ],
        }
    ]

    assert build_sentiment_recommendations(reports) == []
