"""
Cross-Portfolio Service

This module implements the service layer for cross-portfolio analysis.
It orchestrates the CrossPortfolioAnalyzer calculator with repository
data access, enforcing tenant isolation and input validation.
"""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from ..calculators.cross_portfolio_analyzer import CrossPortfolioAnalyzer
from ..repositories.portfolio_repository import PortfolioRepository
from ..repositories.holdings_repository import HoldingsRepository
from ..repositories.transaction_repository import TransactionRepository
from ..models import InvestmentPortfolio

logger = logging.getLogger(__name__)


class CrossPortfolioService:
    """
    Service for cross-portfolio analysis operations.

    All methods enforce tenant isolation through portfolio ownership
    and accept optional portfolio_ids to scope analysis to a subset.
    """

    def __init__(self, db: Session):
        self.db = db
        self.portfolio_repo = PortfolioRepository(db)
        self.holdings_repo = HoldingsRepository(db)
        self.transaction_repo = TransactionRepository(db)
        self.analyzer = CrossPortfolioAnalyzer()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_portfolios(
        self, tenant_id: int, portfolio_ids: Optional[List[int]] = None
    ) -> List[InvestmentPortfolio]:
        """
        Get portfolios for the tenant, optionally filtered to specific IDs.
        """
        all_portfolios = self.portfolio_repo.get_by_tenant(
            tenant_id=tenant_id, include_archived=False
        )
        if portfolio_ids:
            id_set = set(portfolio_ids)
            return [p for p in all_portfolios if p.id in id_set]
        return all_portfolios

    def _load_portfolios_with_holdings(self, tenant_id: int, portfolio_ids: Optional[List[int]] = None):
        """Load portfolios paired with their active holdings."""
        portfolios = self._get_portfolios(tenant_id, portfolio_ids)
        result = []
        for p in portfolios:
            holdings = self.holdings_repo.get_by_portfolio(
                portfolio_id=p.id, tenant_id=tenant_id, include_closed=False
            )
            result.append((p, holdings))
        return result

    def _load_portfolios_with_holdings_and_transactions(
        self, tenant_id: int, portfolio_ids: Optional[List[int]] = None
    ):
        """Load portfolios paired with holdings and transactions."""
        portfolios = self._get_portfolios(tenant_id, portfolio_ids)
        result = []
        for p in portfolios:
            holdings = self.holdings_repo.get_by_portfolio(
                portfolio_id=p.id, tenant_id=tenant_id, include_closed=False
            )
            transactions = self.transaction_repo.get_by_portfolio(
                portfolio_id=p.id, tenant_id=tenant_id
            )
            result.append((p, holdings, transactions))
        return result

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_consolidated_holdings(
        self, tenant_id: int, portfolio_ids: Optional[List[int]] = None
    ) -> dict:
        """
        Consolidate identical securities across portfolios.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_ids: Optional list of portfolio IDs to scope analysis

        Returns:
            Dict with consolidated holdings and summary stats
        """
        data = self._load_portfolios_with_holdings(tenant_id, portfolio_ids)
        holdings_list = self.analyzer.consolidate_holdings(data)

        return {
            "portfolio_count": len(data),
            "total_unique_securities": len(holdings_list),
            "consolidated_holdings": holdings_list,
        }

    def get_overlap_analysis(
        self, tenant_id: int, portfolio_ids: Optional[List[int]] = None
    ) -> dict:
        """
        Analyse which securities appear in multiple portfolios.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_ids: Optional list of portfolio IDs to scope analysis

        Returns:
            Overlap analysis dict
        """
        data = self._load_portfolios_with_holdings(tenant_id, portfolio_ids)
        return self.analyzer.find_overlapping_securities(data)

    def compare_stock(
        self,
        tenant_id: int,
        symbol: str,
        portfolio_ids: Optional[List[int]] = None,
    ) -> dict:
        """
        Compare a specific stock's metrics across every portfolio that holds it.

        Args:
            tenant_id: Tenant ID for isolation
            symbol: Security symbol (e.g. "AAPL")
            portfolio_ids: Optional list of portfolio IDs to scope analysis

        Returns:
            Per-portfolio comparison dict
        """
        data = self._load_portfolios_with_holdings(tenant_id, portfolio_ids)
        return self.analyzer.compare_stock_across_portfolios(symbol, data)

    def get_exposure_report(
        self, tenant_id: int, portfolio_ids: Optional[List[int]] = None
    ) -> dict:
        """
        Calculate concentration / exposure risk across all holdings.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_ids: Optional list of portfolio IDs to scope analysis

        Returns:
            Exposure report dict with concentration warnings
        """
        data = self._load_portfolios_with_holdings(tenant_id, portfolio_ids)
        return self.analyzer.calculate_total_exposure(data)

    def get_monthly_comparison(
        self,
        tenant_id: int,
        months: int = 6,
        portfolio_ids: Optional[List[int]] = None,
    ) -> dict:
        """
        Compare month-over-month performance across portfolios.

        Args:
            tenant_id: Tenant ID for isolation
            months: Number of months of history (default 6)
            portfolio_ids: Optional list of portfolio IDs to scope analysis

        Returns:
            Monthly comparison dict with per-portfolio and aggregate data
        """
        data = self._load_portfolios_with_holdings_and_transactions(
            tenant_id, portfolio_ids
        )
        return self.analyzer.generate_monthly_comparison(data, months=months)

    def get_cross_portfolio_summary(
        self, tenant_id: int, portfolio_ids: Optional[List[int]] = None
    ) -> dict:
        """
        Unified dashboard summary combining key cross-portfolio insights.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_ids: Optional list of portfolio IDs to scope analysis

        Returns:
            Dict with consolidated overview, overlap highlights, and
            top concentration risks
        """
        data = self._load_portfolios_with_holdings(tenant_id, portfolio_ids)

        if not data:
            return {
                "portfolio_count": 0,
                "total_unique_securities": 0,
                "total_combined_value": 0.0,
                "total_combined_cost": 0.0,
                "total_gain_loss": 0.0,
                "total_gain_loss_pct": 0.0,
                "overlapping_securities_count": 0,
                "top_holdings": [],
                "concentration_warnings": [],
            }

        # Consolidated holdings
        consolidated = self.analyzer.consolidate_holdings(data)

        # Overlap
        overlap = self.analyzer.find_overlapping_securities(data)

        # Exposure
        exposure = self.analyzer.calculate_total_exposure(data)

        total_value = exposure["total_combined_value"]
        total_cost = sum(h["total_cost_basis"] for h in consolidated)
        total_gl = total_value - total_cost
        total_gl_pct = (total_gl / total_cost * 100) if total_cost > 0 else 0.0

        return {
            "portfolio_count": len(data),
            "total_unique_securities": len(consolidated),
            "total_combined_value": total_value,
            "total_combined_cost": total_cost,
            "total_gain_loss": total_gl,
            "total_gain_loss_pct": round(total_gl_pct, 2),
            "overlapping_securities_count": overlap["overlapping_securities_count"],
            "overlap_percentage": overlap["overlap_percentage"],
            "top_holdings": consolidated[:5],  # Top 5 by value
            "concentration_warnings": exposure["concentration_warnings"],
        }
