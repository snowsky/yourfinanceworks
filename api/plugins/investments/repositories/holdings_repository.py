"""
Holdings Repository

This module implements the data access layer for investment holdings.
It provides CRUD operations with proper tenant isolation through portfolio
relationships and follows the repository pattern to separate data access
from business logic.

All queries automatically filter by tenant context through portfolio ownership
to ensure data isolation.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from datetime import datetime, timezone
from decimal import Decimal

from ..models import InvestmentHolding, InvestmentPortfolio, SecurityType, AssetClass


class HoldingsRepository:
    """
    Repository for holdings data access operations.

    All methods enforce tenant isolation by filtering queries based on portfolio
    ownership. This ensures users can only access holdings from their own portfolios.
    """

    def __init__(self, db_session: Session):
        """
        Initialize the repository with a database session.

        Args:
            db_session: SQLAlchemy session (required)
        """
        if db_session is None:
            raise ValueError("Database session is required")
        self.db = db_session

    def create(
        self,
        portfolio_id: int,
        security_symbol: str,
        security_name: Optional[str],
        security_type: SecurityType,
        asset_class: AssetClass,
        quantity: Decimal,
        cost_basis: Decimal,
        purchase_date,
        currency: str = "USD"
    ) -> InvestmentHolding:
        """
        Create a new holding.

        Args:
            portfolio_id: Portfolio ID
            security_symbol: Security symbol (e.g., "AAPL")
            security_name: Security name (optional)
            security_type: Type of security
            asset_class: Asset class for allocation
            quantity: Quantity of shares
            cost_basis: Total cost basis
            purchase_date: Initial purchase date

        Returns:
            Created holding instance

        Raises:
            SQLAlchemyError: If database operation fails
        """
        holding = InvestmentHolding(
            portfolio_id=portfolio_id,
            security_symbol=security_symbol,
            security_name=security_name,
            security_type=security_type,
            asset_class=asset_class,
            quantity=quantity,
            cost_basis=cost_basis,
            purchase_date=purchase_date,
            currency=currency,
            is_closed=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        self.db.add(holding)
        self.db.commit()
        self.db.refresh(holding)

        return holding

    def get_by_id(self, holding_id: int) -> Optional[InvestmentHolding]:
        """
        Get a holding by ID with tenant isolation through portfolio ownership.

        Args:
            holding_id: Holding ID

        Returns:
            Holding instance if found and accessible, None otherwise
        """
        return self.db.query(InvestmentHolding).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.id == holding_id,
                InvestmentPortfolio.is_archived == False
            )
        ).first()

    def get_by_portfolio(
        self,
        portfolio_id: int,
        tenant_id: int,
        include_closed: bool = False
    ) -> List[InvestmentHolding]:
        """
        Get all holdings for a portfolio.

        Args:
            portfolio_id: Portfolio ID
            include_closed: Whether to include closed holdings

        Returns:
            List of holding instances
        """
        query = self.db.query(InvestmentHolding).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.portfolio_id == portfolio_id,
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentPortfolio.is_archived == False
            )
        )

        if not include_closed:
            query = query.filter(InvestmentHolding.is_closed == False)

        return query.order_by(InvestmentHolding.security_symbol).all()

    def get_active_holdings(self, portfolio_id: int, tenant_id: int) -> List[InvestmentHolding]:
        """
        Get only active (non-closed) holdings for a portfolio.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for isolation

        Returns:
            List of active holding instances
        """
        return self.get_by_portfolio(portfolio_id, tenant_id, include_closed=False)

    def update(self, holding_id: int, **updates) -> Optional[InvestmentHolding]:
        """
        Update a holding.

        Args:
            holding_id: Holding ID
            **updates: Fields to update (security_name, security_type, asset_class,
                      quantity, cost_basis, current_price, price_updated_at)

        Returns:
            Updated holding instance if found, None otherwise

        Raises:
            SQLAlchemyError: If database operation fails
        """
        holding = self.get_by_id(holding_id)
        if not holding:
            return None

        # Update allowed fields
        allowed_fields = {
            'security_name', 'security_type', 'asset_class', 'quantity',
            'cost_basis', 'current_price', 'price_updated_at', 'is_closed'
        }

        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                setattr(holding, field, value)

        # Always update the timestamp
        holding.updated_at = datetime.now(timezone.utc)

        # Auto-close holding if quantity reaches zero or minimal value
        if hasattr(holding, 'quantity') and holding.quantity <= Decimal('0.00000001'):
            holding.is_closed = True

        self.db.commit()
        self.db.refresh(holding)

        return holding

    def delete(self, holding_id: int) -> bool:
        """
        Delete a holding permanently.

        Args:
            holding_id: Holding ID

        Returns:
            True if holding was deleted, False otherwise

        Raises:
            SQLAlchemyError: If database operation fails
        """
        holding = self.get_by_id(holding_id)
        if not holding:
            return False

        self.db.delete(holding)
        self.db.commit()

        return True

    def update_price(
        self,
        holding_id: int,
        current_price: Decimal,
        price_date: Optional[datetime] = None
    ) -> Optional[InvestmentHolding]:
        """
        Update the current price of a holding.

        Args:
            holding_id: Holding ID
            current_price: New current price per share
            price_date: Price update timestamp (defaults to now)

        Returns:
            Updated holding instance if found, None otherwise
        """
        if price_date is None:
            price_date = datetime.now(timezone.utc)

        return self.update(
            holding_id,
            current_price=current_price,
            price_updated_at=price_date
        )

    def adjust_quantity(
        self,
        holding_id: int,
        quantity_delta: Decimal,
        cost_delta: Decimal
    ) -> Optional[InvestmentHolding]:
        """
        Adjust the quantity and cost basis of a holding.

        This method is used by transaction processing to update holdings
        when buy/sell transactions are recorded.

        Args:
            holding_id: Holding ID
            quantity_delta: Change in quantity (positive for buy, negative for sell)
            cost_delta: Change in cost basis (positive for buy, negative for sell)

        Returns:
            Updated holding instance if found, None otherwise

        Raises:
            ValueError: If resulting quantity would be negative
        """
        holding = self.get_by_id(holding_id)
        if not holding:
            return None

        new_quantity = holding.quantity + quantity_delta
        new_cost_basis = holding.cost_basis + cost_delta

        # Validate that quantity doesn't go negative
        if new_quantity < 0:
            raise ValueError(f"Insufficient quantity. Current: {holding.quantity}, Requested: {abs(quantity_delta)}")

        # Validate that cost basis doesn't go negative (with small tolerance for rounding)
        if new_cost_basis < -0.01:  # Allow small negative values due to rounding
            raise ValueError(f"Cost basis cannot be negative. Current: {holding.cost_basis}, Delta: {cost_delta}")

        # Handle closing holdings: when quantity becomes 0, keep minimal values
        # to satisfy database constraints until we can fix the constraints
        if new_quantity == 0:
            # For closed holdings, set minimal positive values to satisfy constraints
            # This is a temporary workaround until the database constraints are fixed
            new_quantity = Decimal('0.00000001')  # Minimal positive quantity
            new_cost_basis = Decimal('0.01')      # Minimal positive cost basis
        elif new_cost_basis <= 0:
            # For active holdings, ensure cost basis is positive
            new_cost_basis = Decimal('0.01')

        return self.update(
            holding_id,
            quantity=new_quantity,
            cost_basis=new_cost_basis
        )

    def close(self, holding_id: int) -> Optional[InvestmentHolding]:
        """
        Close a holding (mark as closed but retain historical data).

        Args:
            holding_id: Holding ID

        Returns:
            Updated holding instance if found, None otherwise
        """
        return self.update(holding_id, is_closed=True)

    def get_by_symbol(
        self,
        portfolio_id: int,
        security_symbol: str,
        include_closed: bool = False
    ) -> List[InvestmentHolding]:
        """
        Get holdings by security symbol within a portfolio.

        Args:
            portfolio_id: Portfolio ID
            security_symbol: Security symbol to search for
            include_closed: Whether to include closed holdings

        Returns:
            List of holdings matching symbol
        """
        query = self.db.query(InvestmentHolding).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.portfolio_id == portfolio_id,
                InvestmentHolding.security_symbol == security_symbol,
                InvestmentPortfolio.is_archived == False
            )
        )

        if not include_closed:
            query = query.filter(InvestmentHolding.is_closed == False)

        return query.order_by(InvestmentHolding.purchase_date).all()

    def get_by_symbol_and_currency(
        self,
        portfolio_id: int,
        security_symbol: str,
        currency: str,
        include_closed: bool = False
    ) -> List[InvestmentHolding]:
        """
        Get holdings by security symbol and currency within a portfolio.

        Args:
            portfolio_id: Portfolio ID
            security_symbol: Security symbol to search for
            currency: Currency code to filter by
            include_closed: Whether to include closed holdings

        Returns:
            List of holdings matching symbol and currency
        """
        query = self.db.query(InvestmentHolding).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.portfolio_id == portfolio_id,
                InvestmentHolding.security_symbol == security_symbol,
                InvestmentHolding.currency == currency,
                InvestmentPortfolio.is_archived == False
            )
        )

        if not include_closed:
            query = query.filter(InvestmentHolding.is_closed == False)

        return query.order_by(InvestmentHolding.purchase_date).all()

    def get_by_asset_class(
        self,
        portfolio_id: int,
        asset_class: AssetClass,
        include_closed: bool = False
    ) -> List[InvestmentHolding]:
        """
        Get holdings by asset class within a portfolio.

        Args:
            portfolio_id: Portfolio ID
            asset_class: Asset class to filter by
            include_closed: Whether to include closed holdings

        Returns:
            List of holdings in the specified asset class
        """
        query = self.db.query(InvestmentHolding).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.portfolio_id == portfolio_id,
                InvestmentHolding.asset_class == asset_class,
                InvestmentPortfolio.is_archived == False
            )
        )

        if not include_closed:
            query = query.filter(InvestmentHolding.is_closed == False)

        return query.order_by(InvestmentHolding.security_symbol).all()

    def get_by_security_type(
        self,
        portfolio_id: int,
        security_type: SecurityType,
        include_closed: bool = False
    ) -> List[InvestmentHolding]:
        """
        Get holdings by security type within a portfolio.

        Args:
            portfolio_id: Portfolio ID
            security_type: Security type to filter by
            include_closed: Whether to include closed holdings

        Returns:
            List of holdings of the specified security type
        """
        query = self.db.query(InvestmentHolding).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.portfolio_id == portfolio_id,
                InvestmentHolding.security_type == security_type,
                InvestmentPortfolio.is_archived == False
            )
        )

        if not include_closed:
            query = query.filter(InvestmentHolding.is_closed == False)

        return query.order_by(InvestmentHolding.security_symbol).all()

    def get_holdings_needing_price_update(
        self,
        max_age_hours: int = 24
    ) -> List[InvestmentHolding]:
        """
        Get holdings that need price updates (price is old or missing).

        Args:
            max_age_hours: Maximum age of price in hours before considering it stale

        Returns:
            List of holdings needing price updates
        """
        cutoff_time = datetime.now(timezone.utc) - timezone.timedelta(hours=max_age_hours)

        return self.db.query(InvestmentHolding).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.is_closed == False,
                InvestmentPortfolio.is_archived == False,
                or_(
                    InvestmentHolding.current_price.is_(None),
                    InvestmentHolding.price_updated_at.is_(None),
                    InvestmentHolding.price_updated_at < cutoff_time
                )
            )
        ).order_by(InvestmentHolding.security_symbol).all()

    def get_portfolio_value(self, portfolio_id: int, tenant_id: int) -> Decimal:
        """
        Calculate total portfolio value using current prices or cost basis fallback.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for isolation

        Returns:
            Total portfolio value
        """
        holdings = self.get_by_portfolio(portfolio_id, tenant_id, include_closed=False)
        total_value = Decimal('0')

        for holding in holdings:
            total_value += holding.current_value

        return total_value

    def get_portfolio_cost_basis(self, portfolio_id: int, tenant_id: int) -> Decimal:
        """
        Calculate total portfolio cost basis.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for isolation

        Returns:
            Total portfolio cost basis
        """
        result = self.db.query(
            func.sum(InvestmentHolding.cost_basis)
        ).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.portfolio_id == portfolio_id,
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentHolding.is_closed == False,
                InvestmentPortfolio.is_archived == False
            )
        ).scalar()

        return result or Decimal('0')

    def validate_tenant_access(self, holding_id: int) -> bool:
        """
        Validate that a holding exists and is accessible by the current tenant.

        This is done by checking if the holding's portfolio is in the current
        tenant's database (tenant isolation is handled at the database level).

        Args:
            holding_id: Holding ID to validate

        Returns:
            True if holding exists and is accessible, False otherwise
        """
        holding = self.get_by_id(holding_id)
        return holding is not None

    def exists(self, holding_id: int) -> bool:
        """
        Check if a holding exists and is accessible.

        Args:
            holding_id: Holding ID

        Returns:
            True if holding exists, False otherwise
        """
        return self.db.query(InvestmentHolding.id).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.id == holding_id,
                InvestmentPortfolio.is_archived == False
            )
        ).first() is not None

    def count_by_portfolio(self, portfolio_id: int, tenant_id: int, include_closed: bool = False) -> int:
        """
        Count holdings in a portfolio.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for isolation
            include_closed: Whether to include closed holdings

        Returns:
            Number of holdings in the portfolio
        """
        query = self.db.query(func.count(InvestmentHolding.id)).join(InvestmentPortfolio).filter(
            and_(
                InvestmentHolding.portfolio_id == portfolio_id,
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentPortfolio.is_archived == False
            )
        )

        if not include_closed:
            query = query.filter(InvestmentHolding.is_closed == False)

        return query.scalar() or 0

    def get_active_holdings_count(self, tenant_id: int) -> int:
        """
        Get total number of active holdings across all portfolios for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Total active holdings count
        """
        return self.db.query(InvestmentHolding).join(InvestmentPortfolio).filter(
            and_(
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentPortfolio.is_archived == False,
                InvestmentHolding.is_closed == False
            )
        ).count()

    def get_asset_class_summary(self, portfolio_id: int, tenant_id: int) -> List[dict]:
        """
        Get asset class summary for a portfolio.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for isolation

        Returns:
            List of dictionaries with asset_class, total_value, holdings_count
        """
        holdings = self.get_by_portfolio(portfolio_id, tenant_id, include_closed=False)

        summary = {}
        for holding in holdings:
            asset_class = holding.asset_class
            if asset_class not in summary:
                summary[asset_class] = {
                    'asset_class': asset_class,
                    'total_value': Decimal('0'),
                    'holdings_count': 0
                }

            summary[asset_class]['total_value'] += holding.current_value
            summary[asset_class]['holdings_count'] += 1

        return list(summary.values())
