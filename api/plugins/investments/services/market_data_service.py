"""
Market Data Service for Investment Holdings

Provides market price data for securities using various data sources.
Currently supports Yahoo Finance API for free market data.
"""

import logging
import asyncio
from typing import Dict, Optional, List
from datetime import datetime, timezone
from decimal import Decimal
import aiohttp
from sqlalchemy.orm import Session

from ..repositories.holdings_repository import HoldingsRepository
from ..models import InvestmentHolding

logger = logging.getLogger(__name__)


class MarketDataService:
    """Service for fetching and updating market data for investment holdings"""

    def __init__(self, db: Session):
        self.db = db
        self.holdings_repo = HoldingsRepository(db)

    # Browser-like headers to avoid Yahoo Finance rate limiting (429)
    _YAHOO_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://finance.yahoo.com/",
    }

    async def fetch_price_yahoo_finance(self, symbol: str) -> Optional[Decimal]:
        """
        Fetch current market price for a symbol using Yahoo Finance API.
        Retries once with backoff on 429 rate-limit responses.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "GOOGL")

        Returns:
            Current price as Decimal or None if fetch failed
        """
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        max_attempts = 2

        for attempt in range(max_attempts):
            try:
                async with aiohttp.ClientSession(headers=self._YAHOO_HEADERS) as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 429:
                            if attempt < max_attempts - 1:
                                wait = 2 * (attempt + 1)
                                logger.warning(f"Yahoo Finance rate limit (429) for {symbol}, retrying in {wait}s...")
                                await asyncio.sleep(wait)
                                continue
                            logger.warning(f"Yahoo Finance rate limit (429) for {symbol} after {max_attempts} attempts")
                            return None

                        if response.status != 200:
                            logger.warning(f"Yahoo Finance API returned status {response.status} for {symbol}")
                            return None

                        data = await response.json()

                        chart = data.get('chart', {})
                        result = chart.get('result', [])

                        if not result:
                            logger.warning(f"No data returned for {symbol}")
                            return None

                        meta = result[0].get('meta', {})
                        current_price = meta.get('regularMarketPrice')

                        if current_price is None:
                            logger.warning(f"No current price found for {symbol}")
                            return None

                        return Decimal(str(current_price))

            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching price for {symbol} (attempt {attempt + 1})")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1)
                    continue
                return None
            except Exception as e:
                logger.error(f"Error fetching price for {symbol}: {e}")
                return None

        return None

    async def update_holding_price(self, tenant_id: int, holding_id: int, symbol: str) -> bool:
        """
        Update the price for a single holding

        Args:
            tenant_id: Tenant ID for security
            holding_id: ID of the holding to update
            symbol: Symbol to fetch price for

        Returns:
            True if update successful, False otherwise
        """
        try:
            price = await self.fetch_price_yahoo_finance(symbol)

            if price is None:
                logger.warning(f"Failed to fetch price for {symbol}")
                return False

            # Update the holding
            updated_holding = self.holdings_repo.update_price(
                holding_id,
                tenant_id,
                price,
                datetime.now(timezone.utc)
            )

            if updated_holding:
                logger.info(f"Updated price for {symbol}: ${price}")
                return True
            else:
                logger.error(f"Failed to update holding {holding_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating holding {holding_id}: {e}")
            return False

    async def update_all_holdings_prices(self, tenant_id: int) -> Dict[str, int]:
        """
        Update prices for all active holdings in a tenant's portfolios

        Args:
            tenant_id: Tenant ID to update holdings for

        Returns:
            Dictionary with success and failure counts
        """
        try:
            # Get all active holdings that need price updates
            holdings = self.holdings_repo.get_holdings_needing_price_update(tenant_id)

            if not holdings:
                logger.info(f"No holdings need price updates for tenant {tenant_id}")
                return {"success": 0, "failed": 0, "total": 0}

            logger.info(f"Updating prices for {len(holdings)} holdings")

            success_count = 0
            failed_count = 0

            # Group holdings by symbol to avoid duplicate API calls
            symbols_to_holdings = {}
            for holding in holdings:
                symbol = holding.security_symbol.upper()
                if symbol not in symbols_to_holdings:
                    symbols_to_holdings[symbol] = []
                symbols_to_holdings[symbol].append(holding)

            # Fetch price for each unique symbol and update all holdings
            for symbol, holding_list in symbols_to_holdings.items():
                price = await self.fetch_price_yahoo_finance(symbol)

                if price is not None:
                    # Update all holdings with this symbol
                    for holding in holding_list:
                        try:
                            updated = self.holdings_repo.update_price(
                                holding.id,
                                tenant_id,
                                price,
                                datetime.now(timezone.utc)
                            )
                            if updated:
                                success_count += 1
                                logger.info(f"Updated price for {symbol}: ${price} (holding {holding.id})")
                            else:
                                failed_count += 1
                        except Exception as e:
                            logger.error(f"Error updating holding {holding.id}: {e}")
                            failed_count += 1
                else:
                    failed_count += len(holding_list)
                    logger.warning(f"Failed to fetch price for {symbol} ({len(holding_list)} holdings)")

            result = {
                "success": success_count,
                "failed": failed_count,
                "total": len(holdings)
            }

            logger.info(f"Price update completed: {success_count} success, {failed_count} failed, {len(holdings)} total")
            return result

        except Exception as e:
            logger.error(f"Error in bulk price update: {e}")
            return {"success": 0, "failed": 0, "total": 0, "error": str(e)}

    def get_price_update_status(self, tenant_id: int) -> Dict[str, int]:
        """
        Get status of price updates for holdings

        Args:
            tenant_id: Tenant ID to check

        Returns:
            Dictionary with counts of holdings by price update status
        """
        try:
            # Get holdings with various price statuses
            from sqlalchemy import and_, or_
            from datetime import timedelta

            now = datetime.now(timezone.utc)
            one_day_ago = now - timedelta(days=1)

            # All active holdings
            all_active = self.db.query(InvestmentHolding).filter(
                and_(
                    InvestmentHolding.portfolio.has(tenant_id=tenant_id),
                    InvestmentHolding.is_closed == False
                )
            ).count()

            # Holdings with current prices
            with_current_price = self.db.query(InvestmentHolding).filter(
                and_(
                    InvestmentHolding.portfolio.has(tenant_id=tenant_id),
                    InvestmentHolding.is_closed == False,
                    InvestmentHolding.current_price.isnot(None)
                )
            ).count()

            # Holdings with recent price updates (within last day)
            with_recent_updates = self.db.query(InvestmentHolding).filter(
                and_(
                    InvestmentHolding.portfolio.has(tenant_id=tenant_id),
                    InvestmentHolding.is_closed == False,
                    InvestmentHolding.price_updated_at >= one_day_ago
                )
            ).count()

            # Holdings with no price or stale prices
            missing_or_stale = all_active - with_recent_updates

            return {
                "total_active": all_active,
                "with_current_price": with_current_price,
                "with_recent_updates": with_recent_updates,
                "missing_or_stale": missing_or_stale
            }
            
        except Exception as e:
            logger.error(f"Error getting price update status: {e}")
            return {"error": str(e)}
