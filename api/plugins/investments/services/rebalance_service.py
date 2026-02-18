"""
Rebalance Service

This module implements the logic for portfolio rebalancing.
It calculates the drift between current asset allocations and target allocations,
providing actionable trade recommendations.
"""

from typing import List, Dict, Optional, Any
from decimal import Decimal
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..models import AssetClass, InvestmentPortfolio, InvestmentHolding
from ..repositories.portfolio_repository import PortfolioRepository
from ..repositories.holdings_repository import HoldingsRepository
from ..calculators.asset_allocation_analyzer import AssetAllocationAnalyzer
from ..schemas import RebalanceReport, RebalanceAction
from core.models.database import SessionLocal


class RebalanceService:
    """
    Service class for portfolio rebalancing logic.

    Provides methods to calculate drift and generate trade recommendations
    to align a portfolio with its target asset allocation.
    """

    def __init__(self, db_session: Session = None):
        """
        Initialize the service with database session and collaborators.

        Args:
            db_session: SQLAlchemy session. If None, will create a new session.
        """
        self.db = db_session or SessionLocal()
        self.portfolio_repo = PortfolioRepository(self.db)
        self.holdings_repo = HoldingsRepository(self.db)
        self.analyzer = AssetAllocationAnalyzer()

    def generate_rebalance_report(
        self,
        portfolio_id: int,
        tenant_id: int
    ) -> Optional[RebalanceReport]:
        """
        Generate a rebalance report for a specific portfolio.

        Calculates current allocations, compares with targets, and
        suggests buy/sell actions to reach those targets.

        Args:
            portfolio_id: Portfolio ID to analyze
            tenant_id: Tenant ID for isolation

        Returns:
            RebalanceReport if portfolio exists and has targets, None otherwise
        """
        # Fetch portfolio and validate access
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            return None

        # If no targets set, we can't rebalance
        if not portfolio.target_allocations:
            return None

        # Get current holdings and calculate current allocation
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)
        current_allocation = self.analyzer.calculate_asset_allocation(holdings)

        total_value = current_allocation.total_value
        if total_value == 0:
            # Handle empty portfolio - suggest initial buys if we had cash/context
            # For MVP, we return a report with zero value
            return RebalanceReport(
                portfolio_id=portfolio_id,
                total_value=Decimal('0'),
                current_allocations={},
                target_allocations=portfolio.target_allocations,
                drifts={},
                recommended_actions=[],
                is_balanced=True,
                summary="Portfolio is empty. Please add funds or holdings to start rebalancing."
            )

        # Map targets and current percentages
        # target_allocations might have string keys/values due to JSON serialization/encryption
        targets: Dict[AssetClass, Decimal] = {}
        for ac_key, val in portfolio.target_allocations.items():
            try:
                # ac_key could be string or AssetClass
                ac = ac_key if isinstance(ac_key, AssetClass) else AssetClass(ac_key)
                targets[ac] = Decimal(str(val))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid target allocation entry: key={ac_key}, val={val}. Error: {e}")
                continue

        currents: Dict[AssetClass, Decimal] = {
            ac: detail.percentage for ac, detail in current_allocation.allocations.items()
        }

        # Calculate drifts and actions
        drifts: Dict[AssetClass, Decimal] = {}
        actions: List[RebalanceAction] = []

        # Ensure all asset classes in targets or currents are considered
        all_asset_classes = set(targets.keys()) | set(currents.keys())

        for ac in all_asset_classes:
            target_pct = targets.get(ac, Decimal('0'))
            current_pct = currents.get(ac, Decimal('0'))
            drift_pct = current_pct - target_pct
            drifts[ac] = drift_pct

            # If drift is significant (e.g., > 1%), suggest action
            if abs(drift_pct) > Decimal('1.0'):
                # Calculate required amount to reach target
                target_value = (target_pct / Decimal('100')) * total_value
                current_value = (current_pct / Decimal('100')) * total_value
                required_change = target_value - current_value

                actions.append(RebalanceAction(
                    asset_class=ac,
                    action_type="BUY" if required_change > 0 else "SELL",
                    amount=abs(required_change),
                    percentage_drift=drift_pct
                ))

        is_balanced = all(abs(d) <= Decimal('1.0') for d in drifts.values())

        summary = "Portfolio is properly balanced." if is_balanced else "Rebalancing is recommended to align with targets."

        return RebalanceReport(
            portfolio_id=portfolio_id,
            total_value=total_value,
            current_allocations=currents,
            target_allocations=targets,
            drifts=drifts,
            recommended_actions=actions,
            is_balanced=is_balanced,
            summary=summary
        )

    def close(self):
        """Close database connections."""
        if hasattr(self, 'db'):
            self.db.close()
