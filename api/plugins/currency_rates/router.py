"""
Currency Rates Plugin — router.py
====================================

GET /api/v1/currency-rates
    Returns latest exchange rates relative to a base currency.

How the third-party service works
-----------------------------------
1. On the first request (or when the cache has expired) the router fetches
   live rates from https://open.er-api.com/v6/latest/{base} — a free public
   API that requires no API key and supports ~1,500 requests/month.

2. The response is cached in a module-level dict for CACHE_TTL_SECONDS (3600 s
   by default) so repeated calls within the hour cost nothing.

3. If the external request fails for any reason (network error, service down,
   rate-limited) the router logs a warning and returns FALLBACK_RATES instead.
   The response includes a `source` field so the frontend can tell the user
   whether data is live or from the fallback.

Query parameters
-----------------
- base  (str, default "USD")  — The currency to convert FROM.
- currencies (comma-separated list, optional) — Filter the response to only
  these currency codes. If omitted all ~160 currencies are returned.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Cache — module-level so it survives across requests within the same process
# ---------------------------------------------------------------------------
CACHE_TTL_SECONDS = 3600  # refresh live rates at most once per hour

_cache: dict = {}          # { base_currency: {"rates": {...}, "fetched_at": float} }

# ---------------------------------------------------------------------------
# Static fallback rates (approximate, relative to USD)
# Updated manually — used only when the external API is unreachable.
# ---------------------------------------------------------------------------
FALLBACK_RATES: dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 149.50,
    "CAD": 1.36,
    "AUD": 1.53,
    "CHF": 0.90,
    "CNY": 7.24,
    "HKD": 7.82,
    "SGD": 1.34,
    "MXN": 17.15,
    "BRL": 4.97,
    "INR": 83.10,
    "KRW": 1325.0,
    "NOK": 10.55,
    "SEK": 10.43,
    "DKK": 6.89,
    "NZD": 1.63,
    "ZAR": 18.63,
    "PLN": 3.97,
}


def _rebase(rates: dict[str, float], base: str) -> dict[str, float]:
    """Re-express all rates relative to *base* instead of USD."""
    if base == "USD" or base not in rates:
        return rates
    base_rate = rates[base]
    return {code: round(v / base_rate, 6) for code, v in rates.items()}


async def _fetch_live_rates(base: str) -> dict[str, float] | None:
    """
    Fetch rates from open.er-api.com.
    Returns a dict of {currency_code: rate} or None on failure.
    """
    try:
        import httpx
        url = f"https://open.er-api.com/v6/latest/{base}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if data.get("result") == "success":
                return data.get("rates", {})
            logger.warning("currency-rates: unexpected API response: %s", data.get("result"))
    except Exception as exc:
        logger.warning("currency-rates: live fetch failed (%s), using fallback", exc)
    return None


@router.get("/currency-rates")
async def get_currency_rates(
    base: str = Query(default="USD", description="Base currency code (e.g. USD, EUR, GBP)"),
    currencies: Optional[str] = Query(
        default=None,
        description="Comma-separated list of currency codes to return. Omit for all."
    ),
):
    """
    Return exchange rates relative to *base*.

    Response shape
    --------------
    ```json
    {
      "base": "USD",
      "source": "live" | "fallback",
      "fetched_at": 1712345678,
      "rates": { "EUR": 0.92, "GBP": 0.79, ... }
    }
    ```

    - **source** = `"live"` when rates were freshly fetched from open.er-api.com.
    - **source** = `"fallback"` when the API was unreachable and static rates are
      returned. The `fetched_at` timestamp will be 0 in that case.
    """
    base = base.upper()
    now = time.time()

    # --- Check cache ---
    cached = _cache.get(base)
    if cached and (now - cached["fetched_at"]) < CACHE_TTL_SECONDS:
        rates = cached["rates"]
        source = cached["source"]
        fetched_at = cached["fetched_at"]
    else:
        # --- Try live fetch ---
        live = await _fetch_live_rates(base)
        if live:
            rates = live
            source = "live"
            fetched_at = now
        else:
            rates = _rebase(FALLBACK_RATES, base)
            source = "fallback"
            fetched_at = 0

        _cache[base] = {"rates": rates, "source": source, "fetched_at": fetched_at}

    # --- Apply optional filter ---
    if currencies:
        requested = {c.strip().upper() for c in currencies.split(",")}
        rates = {k: v for k, v in rates.items() if k in requested}

    return {
        "base": base,
        "source": source,
        "fetched_at": int(fetched_at),
        "rates": rates,
    }
