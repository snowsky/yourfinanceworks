"""
Community sentiment research for investment holdings.

This service aggregates lightweight public-community signals from sources such as
Reddit, Stocktwits, and optional search-provider results that can include X.
It is intentionally read-only and heuristic-driven: the output is research
context for the investment agent, not direct trading advice.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import os
import re
from typing import Any, Iterable, Optional
from urllib.parse import quote_plus

import aiohttp


logger = logging.getLogger(__name__)

POSITIVE_TERMS = {
    "beat",
    "beats",
    "breakout",
    "bull",
    "bullish",
    "cheap",
    "conviction",
    "growth",
    "guide up",
    "momentum",
    "outperform",
    "upgrade",
    "upside",
    "win",
}
NEGATIVE_TERMS = {
    "bear",
    "bearish",
    "bubble",
    "crash",
    "cut",
    "downside",
    "downgrade",
    "expensive",
    "fraud",
    "miss",
    "overvalued",
    "risk",
    "selloff",
    "weak",
}
THEME_KEYWORDS = {
    "ai": {"ai", "inference", "training", "gpu"},
    "earnings": {"earnings", "eps", "revenue", "guidance"},
    "valuation": {"valuation", "multiple", "overvalued", "cheap", "expensive"},
    "regulation": {"regulation", "antitrust", "ban", "probe", "sec"},
    "demand": {"demand", "orders", "bookings", "backlog"},
    "margin": {"margin", "profit", "gross margin"},
    "dilution": {"dilution", "offering", "share issuance"},
    "macro": {"rates", "recession", "inflation", "macro"},
}


@dataclass(frozen=True)
class CommunityPost:
    """Normalized post/snippet from a public community source."""

    source: str
    text: str
    url: str
    published_at: Optional[str] = None
    author: Optional[str] = None
    score: float = 0.0
    matched_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceResult:
    """Fetched items and metadata for one source."""

    source: str
    items: tuple[CommunityPost, ...] = ()
    enabled: bool = True
    warning: Optional[str] = None


class CommunitySource:
    """Base protocol for external community-source providers."""

    source_name = "unknown"

    async def fetch(
        self,
        session: aiohttp.ClientSession,
        *,
        symbol: str,
        security_name: str,
        lookback_days: int,
        limit: int,
    ) -> SourceResult:
        raise NotImplementedError


class RedditCommunitySource(CommunitySource):
    source_name = "reddit"
    _BASE_URL = "https://www.reddit.com/search.json"

    async def fetch(
        self,
        session: aiohttp.ClientSession,
        *,
        symbol: str,
        security_name: str,
        lookback_days: int,
        limit: int,
    ) -> SourceResult:
        query = f'"{symbol}" OR "{security_name}"'
        headers = {"User-Agent": "invoice-app-investment-research/1.0"}
        try:
            async with session.get(
                self._BASE_URL,
                params={"q": query, "sort": "new", "limit": limit, "t": "week"},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    return SourceResult(
                        source=self.source_name,
                        warning=f"reddit returned status {response.status}",
                    )
                payload = await response.json()
        except Exception as exc:
            logger.warning("Reddit community fetch failed for %s: %s", symbol, exc)
            return SourceResult(source=self.source_name, warning=str(exc))

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        posts: list[CommunityPost] = []
        for child in (payload.get("data") or {}).get("children", []):
            data = child.get("data") or {}
            created_utc = data.get("created_utc")
            if created_utc:
                published = datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
                if published < cutoff:
                    continue
                published_at = published.isoformat()
            else:
                published_at = None
            text = f"{data.get('title', '')} {data.get('selftext', '')}".strip()
            if not text:
                continue
            url = data.get("url") or ""
            score, matched_terms = score_text_sentiment(text)
            posts.append(
                CommunityPost(
                    source=self.source_name,
                    text=text[:500],
                    url=url,
                    published_at=published_at,
                    author=data.get("author"),
                    score=score,
                    matched_terms=matched_terms,
                )
            )
        return SourceResult(source=self.source_name, items=tuple(posts))


class StocktwitsCommunitySource(CommunitySource):
    source_name = "stocktwits"
    _BASE_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"

    async def fetch(
        self,
        session: aiohttp.ClientSession,
        *,
        symbol: str,
        security_name: str,
        lookback_days: int,
        limit: int,
    ) -> SourceResult:
        try:
            async with session.get(
                self._BASE_URL.format(symbol=quote_plus(symbol)),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    return SourceResult(
                        source=self.source_name,
                        warning=f"stocktwits returned status {response.status}",
                    )
                payload = await response.json()
        except Exception as exc:
            logger.warning("Stocktwits fetch failed for %s: %s", symbol, exc)
            return SourceResult(source=self.source_name, warning=str(exc))

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        posts: list[CommunityPost] = []
        for message in (payload.get("messages") or [])[:limit]:
            created_at = message.get("created_at")
            published_at = None
            if created_at:
                try:
                    published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    published_at = published.isoformat()
                    if published < cutoff:
                        continue
                except ValueError:
                    published_at = created_at
            text = (message.get("body") or "").strip()
            if not text:
                continue
            entities = message.get("entities") or {}
            sentiment = (entities.get("sentiment") or {}).get("basic")
            score, matched_terms = score_text_sentiment(text)
            if sentiment == "Bullish":
                score = max(score, 0.75)
                matched_terms = tuple(sorted(set(matched_terms + ("bullish",))))
            elif sentiment == "Bearish":
                score = min(score, -0.75)
                matched_terms = tuple(sorted(set(matched_terms + ("bearish",))))
            posts.append(
                CommunityPost(
                    source=self.source_name,
                    text=text[:500],
                    url=message.get("permalink") or "",
                    published_at=published_at,
                    author=(message.get("user") or {}).get("username"),
                    score=score,
                    matched_terms=matched_terms,
                )
            )
        return SourceResult(source=self.source_name, items=tuple(posts))


class SerpApiCommunitySource(CommunitySource):
    """Optional search-backed source that can include X results."""

    source_name = "search"
    _BASE_URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key

    async def fetch(
        self,
        session: aiohttp.ClientSession,
        *,
        symbol: str,
        security_name: str,
        lookback_days: int,
        limit: int,
    ) -> SourceResult:
        if not self.api_key:
            return SourceResult(
                source=self.source_name,
                enabled=False,
                warning="SERPAPI_API_KEY not configured; X/search sentiment disabled",
            )

        query = (
            f'{symbol} stock OR "{security_name}" '
            "site:x.com OR site:reddit.com OR site:stocktwits.com"
        )
        try:
            async with session.get(
                self._BASE_URL,
                params={
                    "engine": "google",
                    "q": query,
                    "api_key": self.api_key,
                    "num": min(limit, 10),
                },
                timeout=aiohttp.ClientTimeout(total=12),
            ) as response:
                if response.status != 200:
                    return SourceResult(
                        source=self.source_name,
                        warning=f"search provider returned status {response.status}",
                    )
                payload = await response.json()
        except Exception as exc:
            logger.warning("Search sentiment fetch failed for %s: %s", symbol, exc)
            return SourceResult(source=self.source_name, warning=str(exc))

        posts: list[CommunityPost] = []
        for item in payload.get("organic_results") or []:
            text = " ".join(filter(None, [item.get("title"), item.get("snippet")])).strip()
            if not text:
                continue
            score, matched_terms = score_text_sentiment(text)
            posts.append(
                CommunityPost(
                    source=self.source_name,
                    text=text[:500],
                    url=item.get("link") or "",
                    score=score,
                    matched_terms=matched_terms,
                )
            )
        return SourceResult(source=self.source_name, items=tuple(posts))


class CommunitySentimentService:
    """Aggregate portfolio holding sentiment from public community sources."""

    def __init__(self) -> None:
        self.providers: tuple[CommunitySource, ...] = (
            RedditCommunitySource(),
            StocktwitsCommunitySource(),
            SerpApiCommunitySource(os.getenv("SERPAPI_API_KEY")),
        )

    async def build_portfolio_report(
        self,
        *,
        portfolio_id: int,
        portfolio_name: str,
        holdings: Iterable[Any],
        lookback_days: int = 7,
        max_holdings: int = 8,
        max_items_per_source: int = 5,
    ) -> dict[str, Any]:
        ranked_holdings = sorted(
            (
                holding
                for holding in holdings
                if not bool(getattr(holding, "is_closed", False))
            ),
            key=lambda holding: _holding_rank_value(holding),
            reverse=True,
        )[:max_holdings]

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            holding_reports = await asyncio.gather(
                *(
                    self._analyze_holding(
                        session,
                        holding=holding,
                        lookback_days=lookback_days,
                        max_items_per_source=max_items_per_source,
                    )
                    for holding in ranked_holdings
                )
            )

        positive = sum(1 for item in holding_reports if item["sentiment_label"] == "positive")
        negative = sum(1 for item in holding_reports if item["sentiment_label"] == "negative")
        mixed = sum(1 for item in holding_reports if item["sentiment_label"] == "mixed")
        unavailable = sum(1 for item in holding_reports if item["sentiment_label"] == "unavailable")

        unique_warnings = []
        seen_warnings: set[str] = set()
        for item in holding_reports:
            for warning in item.get("warnings") or []:
                if warning not in seen_warnings:
                    seen_warnings.add(warning)
                    unique_warnings.append(warning)

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lookback_days": lookback_days,
            "max_holdings": max_holdings,
            "max_items_per_source": max_items_per_source,
            "sources_configured": [provider.source_name for provider in self.providers],
            "portfolio_summary": {
                "positive_holdings": positive,
                "negative_holdings": negative,
                "mixed_holdings": mixed,
                "unavailable_holdings": unavailable,
            },
            "holdings": holding_reports,
            "warnings": unique_warnings,
        }

    async def _analyze_holding(
        self,
        session: aiohttp.ClientSession,
        *,
        holding: Any,
        lookback_days: int,
        max_items_per_source: int,
    ) -> dict[str, Any]:
        symbol = str(getattr(holding, "security_symbol", "")).upper()
        security_name = str(getattr(holding, "security_name", "") or symbol)
        results = await asyncio.gather(
            *(
                provider.fetch(
                    session,
                    symbol=symbol,
                    security_name=security_name,
                    lookback_days=lookback_days,
                    limit=max_items_per_source,
                )
                for provider in self.providers
            ),
            return_exceptions=True,
        )

        source_results: list[SourceResult] = []
        warnings: list[str] = []
        for provider, result in zip(self.providers, results):
            if isinstance(result, Exception):
                warning = f"{provider.source_name} fetch failed: {result}"
                logger.warning("%s for %s", warning, symbol)
                source_results.append(SourceResult(source=provider.source_name, warning=warning))
                warnings.append(warning)
                continue
            source_results.append(result)
            if result.warning:
                warnings.append(result.warning)

        posts = [post for result in source_results for post in result.items]
        summary = summarize_posts(posts)
        source_breakdown = {
            result.source: {
                "enabled": result.enabled,
                "mentions": len(result.items),
            }
            for result in source_results
        }
        return {
            "symbol": symbol,
            "security_name": security_name,
            "current_value": _decimalish(getattr(holding, "current_value", 0)),
            "current_price": _decimalish(getattr(holding, "current_price", 0)),
            "mentions": summary["mentions"],
            "sentiment_score": summary["sentiment_score"],
            "sentiment_label": summary["sentiment_label"],
            "confidence": summary["confidence"],
            "bullish_mentions": summary["bullish_mentions"],
            "bearish_mentions": summary["bearish_mentions"],
            "neutral_mentions": summary["neutral_mentions"],
            "source_breakdown": source_breakdown,
            "top_signals": summary["top_signals"],
            "suggestion": summary["suggestion"],
            "sample_links": summary["sample_links"],
            "warnings": warnings,
        }


def summarize_posts(posts: Iterable[CommunityPost]) -> dict[str, Any]:
    """Convert normalized posts into a compact holding-level summary."""
    posts = list(posts)
    if not posts:
        return {
            "mentions": 0,
            "sentiment_score": 0.0,
            "sentiment_label": "unavailable",
            "confidence": "low",
            "bullish_mentions": 0,
            "bearish_mentions": 0,
            "neutral_mentions": 0,
            "top_signals": [],
            "suggestion": "Insufficient recent public community data from configured sources.",
            "sample_links": [],
        }

    bullish = sum(1 for post in posts if post.score >= 0.35)
    bearish = sum(1 for post in posts if post.score <= -0.35)
    neutral = len(posts) - bullish - bearish
    sentiment_score = round(sum(post.score for post in posts) / max(len(posts), 1), 3)
    distinct_sources = len({post.source for post in posts})

    if sentiment_score >= 0.3:
        label = "positive"
    elif sentiment_score <= -0.3:
        label = "negative"
    elif bullish and bearish:
        label = "mixed"
    else:
        label = "neutral"

    confidence = "low"
    if len(posts) >= 10 and distinct_sources >= 2:
        confidence = "high"
    elif len(posts) >= 5:
        confidence = "medium"

    top_signals = extract_top_signals(posts)
    sample_links = [post.url for post in posts if post.url][:5]

    if label == "positive":
        suggestion = "Community tone is constructive. Validate the thesis and watch for crowded-momentum risk before adding."
    elif label == "negative":
        suggestion = "Community tone is cautious. Review the bearish points before adding or deciding to hold unchanged."
    elif label == "mixed":
        suggestion = "Signals are split. Prefer fundamentals and risk limits over crowd momentum."
    else:
        suggestion = "Signal strength is weak. Treat this as background context, not an action trigger."

    return {
        "mentions": len(posts),
        "sentiment_score": sentiment_score,
        "sentiment_label": label,
        "confidence": confidence,
        "bullish_mentions": bullish,
        "bearish_mentions": bearish,
        "neutral_mentions": neutral,
        "top_signals": top_signals,
        "suggestion": suggestion,
        "sample_links": sample_links,
    }


def score_text_sentiment(text: str) -> tuple[float, tuple[str, ...]]:
    """Apply a small keyword-based sentiment heuristic to a snippet."""
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    positive_hits = {term for term in POSITIVE_TERMS if term in normalized}
    negative_hits = {term for term in NEGATIVE_TERMS if term in normalized}
    raw_score = (len(positive_hits) - len(negative_hits)) / 3.0
    score = max(min(raw_score, 1.0), -1.0)
    matched = tuple(sorted(positive_hits | negative_hits))
    return score, matched


def extract_top_signals(posts: Iterable[CommunityPost]) -> list[str]:
    """Return common thematic signals found across posts."""
    themes = Counter()
    keywords = Counter()
    for post in posts:
        normalized = post.text.lower()
        for theme, terms in THEME_KEYWORDS.items():
            if any(term in normalized for term in terms):
                themes[theme] += 1
        keywords.update(post.matched_terms)

    top_signals: list[str] = []
    for theme, _count in themes.most_common(3):
        top_signals.append(theme)
    for keyword, _count in keywords.most_common(3):
        if keyword not in top_signals:
            top_signals.append(keyword)
        if len(top_signals) >= 4:
            break
    return top_signals


def _holding_rank_value(holding: Any) -> float:
    current_value = getattr(holding, "current_value", None)
    cost_basis = getattr(holding, "cost_basis", 0)
    return float(current_value or cost_basis or 0)


def _decimalish(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
