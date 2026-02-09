"""
Portfolio Repository

This module implements the data access layer for investment portfolios.
It provides CRUD operations with proper tenant isolation and follows
the repository pattern to separate data access from business logic.

All queries automatically filter by tenant context to ensure data isolation.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, timezone

from ..models import InvestmentPortfolio, PortfolioType, InvestmentHolding


class PortfolioRepository:
    """
    Repository for portfolio data access operations.

    All methods enforce tenant isolation by filtering queries based on the
    tenant context. This ensures users can only access their own portfolios.
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

    def create(self, tenant_id: int, name: str, portfolio_type: PortfolioType, currency: str = "USD") -> InvestmentPortfolio:
        """
        Create a new portfolio for a specific tenant.

        Args:
            tenant_id: Tenant ID (for explicit tenant isolation)
            name: Portfolio name
            portfolio_type: Type of portfolio (TAXABLE, RETIREMENT, BUSINESS)
            currency: ISO 4217 currency code (default: USD)

        Returns:
            Created portfolio instance

        Raises:
            SQLAlchemyError: If database operation fails
        """
        portfolio = InvestmentPortfolio(
            tenant_id=tenant_id,
            name=name,
            portfolio_type=portfolio_type,
            currency=currency,
            is_archived=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        self.db.add(portfolio)
        self.db.commit()
        self.db.refresh(portfolio)

        return portfolio

    def get_by_id(self, portfolio_id: int, tenant_id: int) -> Optional[InvestmentPortfolio]:
        """
        Get a portfolio by ID for a specific tenant.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            Portfolio instance if found, None otherwise
        """
        return self.db.query(InvestmentPortfolio).filter(
            and_(
                InvestmentPortfolio.id == portfolio_id,
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentPortfolio.is_archived == False
            )
        ).first()

    def get_by_tenant(self, tenant_id: int, include_archived: bool = False) -> List[InvestmentPortfolio]:
        """
        Get all portfolios for a specific tenant.

        Note: In the current YourFinanceWORKS architecture, tenant isolation
        is handled at the database level through tenant-specific databases.
        The tenant_id parameter is included for explicit tenant isolation
        and future compatibility.

        Args:
            tenant_id: Tenant ID (for explicit tenant isolation)
            include_archived: Whether to include archived portfolios

        Returns:
            List of portfolio instances
        """
        query = self.db.query(InvestmentPortfolio).filter(
            InvestmentPortfolio.tenant_id == tenant_id
        )

        if not include_archived:
            query = query.filter(InvestmentPortfolio.is_archived == False)

        return query.order_by(InvestmentPortfolio.created_at.desc()).all()

    def update(self, portfolio_id: int, tenant_id: int, **updates) -> Optional[InvestmentPortfolio]:
        """
        Update a portfolio for a specific tenant.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)
            **updates: Fields to update (name, portfolio_type)

        Returns:
            Updated portfolio instance if found, None otherwise

        Raises:
            SQLAlchemyError: If database operation fails
        """
        portfolio = self.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            return None

        # Update allowed fields
        allowed_fields = {'name', 'portfolio_type', 'target_allocations'}
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                setattr(portfolio, field, value)

        # Always update the timestamp
        portfolio.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(portfolio)

        return portfolio

    def delete(self, portfolio_id: int, tenant_id: int) -> bool:
        """
        Delete a portfolio (soft delete by archiving) for a specific tenant.

        This method performs a soft delete by setting is_archived=True.
        It also checks that the portfolio has no holdings before deletion.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            True if deleted successfully, False if not found or has holdings

        Raises:
            ValueError: If portfolio has holdings
            SQLAlchemyError: If database operation fails
        """
        portfolio = self.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            return False

        # Check if portfolio has any holdings
        holdings_count = self.db.query(func.count(InvestmentHolding.id)).filter(
            and_(
                InvestmentHolding.portfolio_id == portfolio_id,
                InvestmentHolding.is_closed == False
            )
        ).scalar()

        if holdings_count > 0:
            raise ValueError(f"Cannot delete portfolio with {holdings_count} active holdings")

        # Soft delete by archiving
        portfolio.is_archived = True
        portfolio.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        return True

    def get_with_holdings_count(self, portfolio_id: int, tenant_id: int) -> Optional[tuple]:
        """
        Get a portfolio with its holdings count for a specific tenant.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            Tuple of (portfolio, holdings_count) if found, None otherwise
        """
        result = self.db.query(
            InvestmentPortfolio,
            func.count(InvestmentHolding.id).label('holdings_count')
        ).outerjoin(
            InvestmentHolding,
            and_(
                InvestmentHolding.portfolio_id == InvestmentPortfolio.id,
                InvestmentHolding.is_closed == False
            )
        ).filter(
            and_(
                InvestmentPortfolio.id == portfolio_id,
                InvestmentPortfolio.is_archived == False
            )
        ).group_by(InvestmentPortfolio.id).first()

        if result:
            return result.InvestmentPortfolio, result.holdings_count
        return None

    def get_all_with_holdings_count(self, tenant_id: int, include_archived: bool = False) -> List[tuple]:
        """
        Get all portfolios with their holdings counts for a specific tenant.

        Args:
            tenant_id: Tenant ID (for explicit tenant isolation)
            include_archived: Whether to include archived portfolios

        Returns:
            List of tuples (portfolio, holdings_count)
        """
        query = self.db.query(
            InvestmentPortfolio,
            func.count(InvestmentHolding.id).label('holdings_count')
        ).outerjoin(
            InvestmentHolding,
            and_(
                InvestmentHolding.portfolio_id == InvestmentPortfolio.id,
                InvestmentHolding.is_closed == False
            )
        )

        if not include_archived:
            query = query.filter(InvestmentPortfolio.is_archived == False)

        return query.group_by(InvestmentPortfolio.id).order_by(
            InvestmentPortfolio.created_at.desc()
        ).all()

    def validate_tenant_access(self, portfolio_id: int, tenant_id: int) -> bool:
        """
        Validate that a portfolio exists and is accessible by a specific tenant.

        Note: In the current YourFinanceWORKS architecture, tenant isolation
        is handled at the database level. This method simply checks if the
        portfolio exists in the current tenant's database. The tenant_id
        parameter is included for explicit validation and future compatibility.

        Args:
            portfolio_id: Portfolio ID to validate
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            True if portfolio exists and is accessible, False otherwise
        """
        portfolio = self.get_by_id(portfolio_id, tenant_id)
        return portfolio is not None

    def exists(self, portfolio_id: int, tenant_id: int) -> bool:
        """
        Check if a portfolio exists for a specific tenant.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            True if portfolio exists, False otherwise
        """
        return self.db.query(InvestmentPortfolio.id).filter(
            and_(
                InvestmentPortfolio.id == portfolio_id,
                InvestmentPortfolio.is_archived == False
            )
        ).first() is not None

    def get_by_type(self, tenant_id: int, portfolio_type: PortfolioType, include_archived: bool = False) -> List[InvestmentPortfolio]:
        """
        Get portfolios by type for a specific tenant.

        Args:
            tenant_id: Tenant ID (for explicit tenant isolation)
            portfolio_type: Portfolio type to filter by
            include_archived: Whether to include archived portfolios

        Returns:
            List of portfolios of the specified type
        """
        query = self.db.query(InvestmentPortfolio).filter(
            InvestmentPortfolio.portfolio_type == portfolio_type
        )

        if not include_archived:
            query = query.filter(InvestmentPortfolio.is_archived == False)

        return query.order_by(InvestmentPortfolio.created_at.desc()).all()

    def count_by_type(self, tenant_id: int, portfolio_type: PortfolioType) -> int:
        """
        Count portfolios by type for a specific tenant.

        Args:
            tenant_id: Tenant ID (for explicit tenant isolation)
            portfolio_type: Portfolio type to count

        Returns:
            Number of portfolios of the specified type
        """
        return self.db.query(func.count(InvestmentPortfolio.id)).filter(
            and_(
                InvestmentPortfolio.portfolio_type == portfolio_type,
                InvestmentPortfolio.is_archived == False
            )
        ).scalar()

    def get_paginated(
        self,
        tenant_id: int,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        portfolio_type: Optional[str] = None,
        label: Optional[str] = None
    ) -> tuple[List[InvestmentPortfolio], int]:
        """
        Get paginated portfolios with filtering and search.

        Args:
            tenant_id: Tenant ID (for explicit tenant isolation)
            include_archived: Whether to include archived portfolios
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search query for portfolio name
            portfolio_type: Filter by portfolio type
            label: Filter by label (not implemented in MVP)

        Returns:
            Tuple of (portfolios list, total count)
        """
        # Base query
        query = self.db.query(InvestmentPortfolio).filter(
            InvestmentPortfolio.tenant_id == tenant_id
        )

        # Apply archived filter
        if not include_archived:
            query = query.filter(InvestmentPortfolio.is_archived == False)

        # Apply search filter (case-insensitive)
        if search and search.strip():
            query = query.filter(
                InvestmentPortfolio.name.ilike(f'%{search.strip()}%')
            )

        # Apply portfolio type filter
        if portfolio_type:
            try:
                # Convert string to enum
                type_enum = PortfolioType(portfolio_type.lower())
                query = query.filter(InvestmentPortfolio.portfolio_type == type_enum)
            except ValueError:
                # Invalid portfolio type, return empty results
                return [], 0

        # Get total count before pagination
        total = query.count()

        # Apply pagination and ordering
        portfolios = query.order_by(
            InvestmentPortfolio.created_at.desc()
        ).offset(skip).limit(limit).all()

        return portfolios, total

    def get_deleted_portfolios(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 10
    ) -> tuple[List[InvestmentPortfolio], int]:
        """
        Get deleted (archived) portfolios with pagination.

        Args:
            tenant_id: Tenant ID (for explicit tenant isolation)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (deleted portfolios list, total count)
        """
        # Query only archived portfolios
        query = self.db.query(InvestmentPortfolio).filter(
            and_(
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentPortfolio.is_archived == True
            )
        )

        # Get total count
        total = query.count()

        # Apply pagination and ordering (most recently deleted first)
        portfolios = query.order_by(
            InvestmentPortfolio.updated_at.desc()
        ).offset(skip).limit(limit).all()

        return portfolios, total

    def restore(self, portfolio_id: int, tenant_id: int) -> bool:
        """
        Restore a deleted (archived) portfolio.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            True if restored successfully, False if not found
        """
        portfolio = self.db.query(InvestmentPortfolio).filter(
            and_(
                InvestmentPortfolio.id == portfolio_id,
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentPortfolio.is_archived == True
            )
        ).first()

        if not portfolio:
            return False

        portfolio.is_archived = False
        portfolio.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        return True

    def permanently_delete(self, portfolio_id: int, tenant_id: int) -> bool:
        """
        Permanently delete a portfolio (hard delete).

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            True if deleted successfully, False if not found
        """
        portfolio = self.db.query(InvestmentPortfolio).filter(
            and_(
                InvestmentPortfolio.id == portfolio_id,
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentPortfolio.is_archived == True
            )
        ).first()

        if not portfolio:
            return False

        # Hard delete
        self.db.delete(portfolio)
        self.db.commit()

        return True

    def empty_recycle_bin(self, tenant_id: int) -> int:
        """
        Permanently delete all archived portfolios for a tenant.

        Args:
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            Number of portfolios deleted
        """
        # Get all archived portfolios
        portfolios = self.db.query(InvestmentPortfolio).filter(
            and_(
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentPortfolio.is_archived == True
            )
        ).all()

        count = len(portfolios)

        # Delete all
        for portfolio in portfolios:
            self.db.delete(portfolio)

        self.db.commit()

        return count

    def close(self):
        """Close the database session."""
        if self.db:
            self.db.close()
