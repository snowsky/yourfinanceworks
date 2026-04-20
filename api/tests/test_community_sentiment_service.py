from plugins.investments.services.community_sentiment_service import (
    CommunityPost,
    extract_top_signals,
    score_text_sentiment,
    summarize_posts,
)


def test_score_text_sentiment_detects_positive_and_negative_terms():
    score, matched = score_text_sentiment("Bullish breakout after earnings beat but valuation risk remains")

    assert score > 0
    assert "bullish" in matched
    assert "beat" in matched
    assert "risk" in matched


def test_summarize_posts_builds_negative_summary():
    posts = [
        CommunityPost(
            source="reddit",
            text="Bearish after earnings miss and weak demand",
            url="https://example.com/1",
            score=-0.8,
            matched_terms=("bearish", "miss", "weak"),
        ),
        CommunityPost(
            source="stocktwits",
            text="Still bearish, looks overvalued",
            url="https://example.com/2",
            score=-0.7,
            matched_terms=("bearish", "overvalued"),
        ),
    ]

    summary = summarize_posts(posts)

    assert summary["sentiment_label"] == "negative"
    assert summary["mentions"] == 2
    assert summary["bearish_mentions"] == 2
    assert "bearish points" in summary["suggestion"]


def test_extract_top_signals_prioritizes_themes():
    posts = [
        CommunityPost(source="reddit", text="AI demand and earnings momentum", url="", score=0.4, matched_terms=("bullish",)),
        CommunityPost(source="reddit", text="AI valuation still looks expensive", url="", score=-0.2, matched_terms=("expensive",)),
    ]

    signals = extract_top_signals(posts)

    assert "ai" in signals
    assert "valuation" in signals
