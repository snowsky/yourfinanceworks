"""
Holdings Service

This module implements the business logic layer for investment holdings.
It provides high-level operations for managing holdings with proper validation,
tenant isolation, and business rule enforcement.

The service acts as an intermediary between the API layer and the repository layer,
ensuring that all business rules are enforced consistently.
"""

from typing import List, Optional
from decimal import Decimal
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session

from ..repositories.holdings_repository import HoldingsRepository
from ..repositories.portfolio_repository import PortfolioRepository
from ..models import InvestmentHolding, SecurityType, AssetClass
from ..schemas import HoldingCreate, HoldingUpdate, HoldingResponse
from core.exceptions.base import ValidationError, NotFoundError, ForbiddenError


class HoldingsService:
    """
    Service for holdings business logic operations.

    This service provides high-level operations for managing investment holdings
    with proper validation, tenant isolation, and business rule enforcement.
    """

    def __init__(self, db: Session):
        """
        Initialize the holdings service.

        Args:
            db: Database session
        """
        self.db = db
        self.holdings_repo = HoldingsRepository(db)
        self.portfolio_repo = PortfolioRepository(db)

    def create_holding(
        self,
        tenant_id: int,
        portfolio_id: int,
        holding_data: HoldingCreate
    ) -> HoldingResponse:
        """
        Create a new holding in a portfolio.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            holding_data: Holding creation data

        Returns:
            Created holding data

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
            ValidationError: If holding data is invalid
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Validate holding data
        self._validate_holding_data(holding_data)

        # Check for duplicate holdings (same symbol and currency in same portfolio)
        existing_holding = self.holdings_repo.get_by_symbol_and_currency(portfolio_id, holding_data.security_symbol, holding_data.currency)
        if existing_holding and not existing_holding.is_closed:
            raise ValidationError(f"Active holding for {holding_data.security_symbol} ({holding_data.currency}) already exists in this portfolio")

        # Create the holding
        holding = self.holdings_repo.create(
            portfolio_id=portfolio_id,
            security_symbol=holding_data.security_symbol,
            security_name=holding_data.security_name,
            security_type=holding_data.security_type,
            asset_class=holding_data.asset_class,
            quantity=holding_data.quantity,
            cost_basis=holding_data.cost_basis,
            purchase_date=holding_data.purchase_date,
            currency=holding_data.currency
        )

        return HoldingResponse.from_orm(holding)

    def get_holdings(self, tenant_id: int, portfolio_id: int, include_closed: bool = False) -> List[HoldingResponse]:
        """
        Get all holdings for a portfolio.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            include_closed: Whether to include closed holdings

        Returns:
            List of holdings

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get holdings
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id, include_closed=include_closed)

        return [HoldingResponse.from_orm(holding) for holding in holdings]

    def get_holding(self, tenant_id: int, holding_id: int) -> HoldingResponse:
        """
        Get a specific holding by ID.

        Args:
            tenant_id: Tenant ID for isolation
            holding_id: Holding ID

        Returns:
            Holding data

        Raises:
            NotFoundError: If holding doesn't exist or doesn't belong to tenant
        """
        holding = self.holdings_repo.get_by_id(holding_id)
        if not holding:
            raise NotFoundError(f"Holding {holding_id} not found")

        # Validate tenant access through portfolio
        portfolio = self.portfolio_repo.get_by_id(holding.portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {holding.portfolio_id} not found")

        return HoldingResponse.from_orm(holding)

    def update_holding(
        self,
        tenant_id: int,
        holding_id: int,
        holding_data: HoldingUpdate
    ) -> HoldingResponse:
        """
        Update a holding.

        Args:
            tenant_id: Tenant ID for isolation
            holding_id: Holding ID
            holding_data: Updated holding data

        Returns:
            Updated holding data

        Raises:
            NotFoundError: If holding doesn't exist or doesn't belong to tenant
            ValidationError: If update data is invalid
        """
        # Get and validate holding
        holding = self.holdings_repo.get_by_id(holding_id)
        if not holding:
            raise NotFoundError(f"Holding {holding_id} not found")

        # Validate tenant access through portfolio
        portfolio = self.portfolio_repo.get_by_id(holding.portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {holding.portfolio_id} not found")

        # Validate update data
        if holding_data.quantity is not None:
            self._validate_quantity(holding_data.quantity)

        if holding_data.cost_basis is not None:
            self._validate_cost_basis(holding_data.cost_basis)

        # Update the holding
        update_dict = holding_data.dict(exclude_unset=True)
        updated_holding = self.holdings_repo.update(holding_id, **update_dict)

        return HoldingResponse.from_orm(updated_holding)

    def update_price(
        self,
        tenant_id: int,
        holding_id: int,
        price: Decimal,
        price_date: Optional[datetime] = None
    ) -> HoldingResponse:
        """
        Update the current price of a holding.

        Args:
            tenant_id: Tenant ID for isolation
            holding_id: Holding ID
            price: New price per share
            price_date: Price update timestamp (defaults to now)

        Returns:
            Updated holding data

        Raises:
            NotFoundError: If holding doesn't exist or doesn't belong to tenant
            ValidationError: If price is invalid
        """
        # Get and validate holding
        holding = self.holdings_repo.get_by_id(holding_id)
        if not holding:
            raise NotFoundError(f"Holding {holding_id} not found")

        # Validate tenant access through portfolio
        portfolio = self.portfolio_repo.get_by_id(holding.portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {holding.portfolio_id} not found")

        # Validate price
        if price <= 0:
            raise ValidationError("Price must be positive")

        # Set default price date if not provided
        if price_date is None:
            price_date = datetime.now(timezone.utc)

        # Update the price
        updated_holding = self.holdings_repo.update_price(holding_id, price, price_date)

        return HoldingResponse.from_orm(updated_holding)

    def adjust_quantity(
        self,
        tenant_id: int,
        holding_id: int,
        quantity_change: Decimal,
        cost_basis_change: Decimal
    ) -> HoldingResponse:
        """
        Adjust the quantity and cost basis of a holding.

        This method is typically called by the transaction service when
        processing buy/sell transactions.

        Args:
            tenant_id: Tenant ID for isolation
            holding_id: Holding ID
            quantity_change: Change in quantity (positive for buy, negative for sell)
            cost_basis_change: Change in cost basis

        Returns:
            Updated holding data

        Raises:
            NotFoundError: If holding doesn't exist or doesn't belong to tenant
            ValidationError: If adjustment would result in negative quantity
        """
        # Get and validate holding
        holding = self.holdings_repo.get_by_id(holding_id)
        if not holding:
            raise NotFoundError(f"Holding {holding_id} not found")

        # Validate tenant access through portfolio
        portfolio = self.portfolio_repo.get_by_id(holding.portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {holding.portfolio_id} not found")

        # Calculate new values
        new_quantity = holding.quantity + quantity_change
        new_cost_basis = holding.cost_basis + cost_basis_change

        # Validate new quantity
        if new_quantity < 0:
            raise ValidationError(f"Insufficient quantity. Current: {holding.quantity}, Requested change: {quantity_change}")

        # Validate new cost basis
        if new_cost_basis < 0:
            raise ValidationError(f"Cost basis cannot be negative. Current: {holding.cost_basis}, Requested change: {cost_basis_change}")

        # Update the holding
        updated_holding = self.holdings_repo.adjust_quantity(holding_id, quantity_change, cost_basis_change)

        # Close holding if quantity reaches zero
        if updated_holding.quantity == 0:
            updated_holding = self.holdings_repo.close(holding_id)

        return HoldingResponse.from_orm(updated_holding)

    def close_holding(self, tenant_id: int, holding_id: int) -> HoldingResponse:
        """
        Close a holding (mark as closed).

        Args:
            tenant_id: Tenant ID for isolation
            holding_id: Holding ID

        Returns:
            Closed holding data

        Raises:
            NotFoundError: If holding doesn't exist or doesn't belong to tenant
            ValidationError: If holding still has quantity
        """
        # Get and validate holding
        holding = self.holdings_repo.get_by_id(holding_id)
        if not holding:
            raise NotFoundError(f"Holding {holding_id} not found")

        # Validate tenant access through portfolio
        portfolio = self.portfolio_repo.get_by_id(holding.portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {holding.portfolio_id} not found")

        # Validate holding can be closed
        if holding.quantity > 0:
            raise ValidationError(f"Cannot close holding with remaining quantity: {holding.quantity}")

        if holding.is_closed:
            raise ValidationError("Holding is already closed")

        # Close the holding
        closed_holding = self.holdings_repo.close(holding_id)

        return HoldingResponse.from_orm(closed_holding)

    def delete_holding(self, tenant_id: int, holding_id: int) -> bool:
        """
        Delete a holding permanently.

        Args:
            tenant_id: Tenant ID for isolation
            holding_id: Holding ID

        Returns:
            True if holding was deleted, False otherwise

        Raises:
            NotFoundError: If holding doesn't exist or doesn't belong to tenant
        """
        # Get and validate holding
        holding = self.holdings_repo.get_by_id(holding_id)
        if not holding:
            raise NotFoundError(f"Holding {holding_id} not found")

        # Validate tenant access through portfolio
        portfolio = self.portfolio_repo.get_by_id(holding.portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {holding.portfolio_id} not found")

        # Delete the holding
        return self.holdings_repo.delete(holding_id)

    def get_active_holdings(self, tenant_id: int, portfolio_id: int) -> List[HoldingResponse]:
        """
        Get only active (non-closed) holdings for a portfolio.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            List of active holdings

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get active holdings
        holdings = self.holdings_repo.get_active_holdings(portfolio_id)

        return [HoldingResponse.from_orm(holding) for holding in holdings]

    def get_holdings_by_asset_class(
        self,
        tenant_id: int,
        portfolio_id: int,
        asset_class: AssetClass
    ) -> List[HoldingResponse]:
        """
        Get holdings filtered by asset class.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            asset_class: Asset class to filter by

        Returns:
            List of holdings in the specified asset class

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get holdings by asset class
        holdings = self.holdings_repo.get_by_asset_class(portfolio_id, asset_class)

        return [HoldingResponse.from_orm(holding) for holding in holdings]

    def _validate_tenant_access(self, portfolio, tenant_id: int):
        """
        Validate that the portfolio belongs to the tenant.

        Args:
            portfolio: Portfolio object
            tenant_id: Tenant ID

        Raises:
            ForbiddenError: If portfolio doesn't belong to tenant
        """
        if portfolio.tenant_id != tenant_id:
            raise ForbiddenError("Access denied to portfolio")

    def _validate_holding_data(self, holding_data: HoldingCreate):
        """
        Validate holding creation data.

        Args:
            holding_data: Holding data to validate

        Raises:
            ValidationError: If data is invalid
        """
        self._validate_quantity(holding_data.quantity)
        self._validate_cost_basis(holding_data.cost_basis)

        if holding_data.purchase_date > date.today():
            raise ValidationError("Purchase date cannot be in the future")

    def _validate_quantity(self, quantity: Decimal):
        """
        Validate quantity value.

        Args:
            quantity: Quantity to validate

        Raises:
            ValidationError: If quantity is invalid
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")

    def _validate_cost_basis(self, cost_basis: Decimal):
        """
        Validate cost basis value.

        Args:
            cost_basis: Cost basis to validate

        Raises:
            ValidationError: If cost basis is invalid
        """
        if cost_basis <= 0:
            raise ValidationError("Cost basis must be positive")
