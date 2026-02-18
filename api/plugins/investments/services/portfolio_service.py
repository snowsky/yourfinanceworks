"""
Portfolio Service

This module implements the business logic layer for investment portfolios.
It orchestrates data operations through repositories and enforces business
rules while maintaining proper tenant isolation.

The service layer sits between the API endpoints and the data repositories,
providing a clean interface for portfolio management operations.
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from decimal import Decimal
import logging

from ..models import InvestmentPortfolio, PortfolioType
from ..exceptions import PortfolioHasHoldingsError
from ..repositories.portfolio_repository import PortfolioRepository
from ..repositories.holdings_repository import HoldingsRepository
from ..repositories.file_attachment_repository import FileAttachmentRepository
from ..schemas import PortfolioCreate, PortfolioUpdate, PortfolioResponse
from core.models.database import SessionLocal

logger = logging.getLogger(__name__)


class PortfolioService:
    """
    Service class for portfolio business logic operations.

    This service enforces business rules, validates operations, and coordinates
    between repositories to maintain data consistency and tenant isolation.
    """

    def __init__(self, db_session: Session = None):
        """
        Initialize the service with database session and repositories.

        Args:
            db_session: SQLAlchemy session. If None, will create a new session.
        """
        self.db = db_session or SessionLocal()
        self.portfolio_repo = PortfolioRepository(self.db)
        self.holdings_repo = HoldingsRepository(self.db)
        self.file_attachment_repo = FileAttachmentRepository(self.db)

    def create_portfolio(
        self,
        tenant_id: int,
        portfolio_data: PortfolioCreate
    ) -> InvestmentPortfolio:
        """
        Create a new portfolio for a tenant.

        This method validates the portfolio data and creates a new portfolio
        associated with the specified tenant.

        Args:
            tenant_id: Tenant ID for ownership and isolation
            portfolio_data: Portfolio creation data

        Returns:
            Created portfolio instance

        Raises:
            ValueError: If portfolio data is invalid
            SQLAlchemyError: If database operation fails

        Requirements: 1.1, 1.2
        """
        # Validate portfolio type
        if not isinstance(portfolio_data.portfolio_type, PortfolioType):
            raise ValueError(f"Invalid portfolio type: {portfolio_data.portfolio_type}")

        # Validate portfolio name
        if not portfolio_data.name or len(portfolio_data.name.strip()) == 0:
            raise ValueError("Portfolio name cannot be empty")

        if len(portfolio_data.name) > 100:
            raise ValueError("Portfolio name cannot exceed 100 characters")

        # Create the portfolio through repository
        portfolio = self.portfolio_repo.create(
            tenant_id=tenant_id,
            name=portfolio_data.name.strip(),
            portfolio_type=portfolio_data.portfolio_type,
            currency=portfolio_data.currency
        )

        return portfolio

    def get_portfolios(
        self,
        tenant_id: int,
        include_archived: bool = False
    ) -> List[InvestmentPortfolio]:
        """
        Get all portfolios for a tenant.

        This method retrieves all portfolios owned by the specified tenant,
        ensuring proper tenant isolation.

        Args:
            tenant_id: Tenant ID for ownership and isolation
            include_archived: Whether to include archived portfolios

        Returns:
            List of portfolio instances owned by the tenant

        Requirements: 1.4
        """
        return self.portfolio_repo.get_by_tenant(
            tenant_id=tenant_id,
            include_archived=include_archived
        )

    def get_portfolio(
        self,
        portfolio_id: int,
        tenant_id: int
    ) -> Optional[InvestmentPortfolio]:
        """
        Get a specific portfolio for a tenant.

        This method retrieves a portfolio by ID while ensuring the requesting
        tenant has access to it.

        Args:
            portfolio_id: Portfolio ID to retrieve
            tenant_id: Tenant ID for ownership and isolation

        Returns:
            Portfolio instance if found and accessible, None otherwise

        Requirements: 1.4
        """
        # Validate tenant access first
        if not self.validate_tenant_access(portfolio_id, tenant_id):
            return None

        return self.portfolio_repo.get_by_id(portfolio_id, tenant_id)

    def update_portfolio(
        self,
        portfolio_id: int,
        tenant_id: int,
        updates: PortfolioUpdate
    ) -> Optional[InvestmentPortfolio]:
        """
        Update a portfolio for a tenant.

        This method updates portfolio details while ensuring the requesting
        tenant has access to the portfolio and validating the update data.

        Args:
            portfolio_id: Portfolio ID to update
            tenant_id: Tenant ID for ownership and isolation
            updates: Portfolio update data

        Returns:
            Updated portfolio instance if found and accessible, None otherwise

        Raises:
            ValueError: If update data is invalid
            SQLAlchemyError: If database operation fails

        Requirements: 1.5
        """
        # Validate tenant access first
        if not self.validate_tenant_access(portfolio_id, tenant_id):
            return None

        # Prepare update dictionary
        update_dict = {}

        # Validate and add name if provided
        if updates.name is not None:
            name = updates.name.strip()
            if len(name) == 0:
                raise ValueError("Portfolio name cannot be empty")
            if len(name) > 100:
                raise ValueError("Portfolio name cannot exceed 100 characters")
            update_dict['name'] = name

        # Validate and add portfolio type if provided
        if updates.portfolio_type is not None:
            if not isinstance(updates.portfolio_type, PortfolioType):
                raise ValueError(f"Invalid portfolio type: {updates.portfolio_type}")
            update_dict['portfolio_type'] = updates.portfolio_type

        # Add target allocations if provided
        if updates.target_allocations is not None:
            update_dict['target_allocations'] = updates.target_allocations

        # If no updates provided, return current portfolio
        if not update_dict:
            return self.portfolio_repo.get_by_id(portfolio_id, tenant_id)

        # Perform the update
        return self.portfolio_repo.update(portfolio_id, tenant_id, **update_dict)

    def delete_portfolio(
        self,
        portfolio_id: int,
        tenant_id: int
    ) -> bool:
        """
        Delete a portfolio for a tenant.

        This method performs a soft delete (archiving) of a portfolio while
        ensuring the portfolio has no active holdings. The portfolio must
        be owned by the requesting tenant.

        Also handles cascade deletion of associated file attachments.

        Args:
            portfolio_id: Portfolio ID to delete
            tenant_id: Tenant ID for ownership and isolation

        Returns:
            True if deleted successfully, False if not found

        Raises:
            ValueError: If portfolio has active holdings
            SQLAlchemyError: If database operation fails

        Requirements: 1.6, 4.5, 14.1, 14.2, 14.3, 14.4, 14.5
        """
        # Validate tenant access first
        if not self.validate_tenant_access(portfolio_id, tenant_id):
            return False

        # Check holdings count before deletion
        holdings_count = self.holdings_repo.count_by_portfolio(
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            include_closed=False
        )

        if holdings_count > 0:
            raise PortfolioHasHoldingsError(
                f"Cannot delete portfolio with {holdings_count} active holdings. "
                "Please close or transfer all holdings before deleting the portfolio."
            )

        # Delete associated file attachments (cascade delete)
        try:
            deleted_count = self.file_attachment_repo.delete_by_portfolio(portfolio_id, tenant_id)
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} file attachments for portfolio {portfolio_id}")
        except Exception as e:
            logger.error(f"Failed to delete file attachments for portfolio {portfolio_id}: {e}")
            # Continue with portfolio deletion even if file attachment deletion fails
            # The database cascade constraint will handle orphaned attachments

        # Perform the deletion (soft delete by archiving)
        return self.portfolio_repo.delete(portfolio_id, tenant_id)

    def validate_tenant_access(
        self,
        portfolio_id: int,
        tenant_id: int
    ) -> bool:
        """
        Validate that a portfolio exists and is accessible by a tenant.

        This helper method checks if a portfolio exists and is owned by the
        specified tenant, ensuring proper tenant isolation.

        Args:
            portfolio_id: Portfolio ID to validate
            tenant_id: Tenant ID for ownership and isolation

        Returns:
            True if portfolio exists and is accessible, False otherwise

        Requirements: 8.1, 8.4
        """
        return self.portfolio_repo.validate_tenant_access(portfolio_id, tenant_id)

    def get_portfolio_with_summary(
        self,
        portfolio_id: int,
        tenant_id: int
    ) -> Optional[Tuple[InvestmentPortfolio, dict]]:
        """
        Get a portfolio with summary information (holdings count, total value).

        This method retrieves a portfolio along with calculated summary data
        for display purposes.

        Args:
            portfolio_id: Portfolio ID to retrieve
            tenant_id: Tenant ID for ownership and isolation

        Returns:
            Tuple of (portfolio, summary_dict) if found, None otherwise
            Summary dict contains: holdings_count, total_value, total_cost_basis
        """
        # Validate tenant access first
        if not self.validate_tenant_access(portfolio_id, tenant_id):
            return None

        # Get portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            return None

        # Calculate summary information
        holdings_count = self.holdings_repo.count_by_portfolio(
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            include_closed=False
        )

        total_value = self.holdings_repo.get_portfolio_value(portfolio_id, tenant_id)
        total_cost_basis = self.holdings_repo.get_portfolio_cost_basis(portfolio_id)

        summary = {
            'holdings_count': holdings_count,
            'total_value': total_value,
            'total_cost_basis': total_cost_basis,
            'unrealized_gain_loss': total_value - total_cost_basis
        }

        return portfolio, summary

    def get_portfolios_with_summary(
        self,
        tenant_id: int,
        include_archived: bool = False
    ) -> List[Tuple[InvestmentPortfolio, dict]]:
        """
        Get all portfolios with summary information for a tenant.

        This method retrieves all portfolios along with calculated summary data
        for dashboard or listing purposes.

        Args:
            tenant_id: Tenant ID for ownership and isolation
            include_archived: Whether to include archived portfolios

        Returns:
            List of tuples (portfolio, summary_dict)
            Summary dict contains: holdings_count, total_value, total_cost_basis
        """
        portfolios = self.portfolio_repo.get_by_tenant(
            tenant_id=tenant_id,
            include_archived=include_archived
        )

        results = []
        for portfolio in portfolios:
            holdings_count = self.holdings_repo.count_by_portfolio(
                portfolio_id=portfolio.id,
                tenant_id=tenant_id,
                include_closed=False
            )

            total_value = self.holdings_repo.get_portfolio_value(portfolio.id, tenant_id)
            total_cost_basis = self.holdings_repo.get_portfolio_cost_basis(portfolio.id)

            summary = {
                'holdings_count': holdings_count,
                'total_value': total_value,
                'total_cost_basis': total_cost_basis,
                'unrealized_gain_loss': total_value - total_cost_basis
            }

            results.append((portfolio, summary))

        return results

    def get_portfolios_by_type(
        self,
        tenant_id: int,
        portfolio_type: PortfolioType,
        include_archived: bool = False
    ) -> List[InvestmentPortfolio]:
        """
        Get portfolios by type for a tenant.

        This method retrieves portfolios filtered by type while ensuring
        proper tenant isolation.

        Args:
            tenant_id: Tenant ID for ownership and isolation
            portfolio_type: Portfolio type to filter by
            include_archived: Whether to include archived portfolios

        Returns:
            List of portfolios of the specified type
        """
        return self.portfolio_repo.get_by_type(
            tenant_id=tenant_id,
            portfolio_type=portfolio_type,
            include_archived=include_archived
        )

    def count_portfolios_by_type(
        self,
        tenant_id: int,
        portfolio_type: PortfolioType
    ) -> int:
        """
        Count portfolios by type for a tenant.

        Args:
            tenant_id: Tenant ID for ownership and isolation
            portfolio_type: Portfolio type to count

        Returns:
            Number of portfolios of the specified type
        """
        return self.portfolio_repo.count_by_type(tenant_id, portfolio_type)

    def portfolio_exists(
        self,
        portfolio_id: int,
        tenant_id: int
    ) -> bool:
        """
        Check if a portfolio exists and is accessible by a tenant.

        Args:
            portfolio_id: Portfolio ID to check
            tenant_id: Tenant ID for ownership and isolation

        Returns:
            True if portfolio exists and is accessible, False otherwise
        """
        return self.portfolio_repo.exists(portfolio_id, tenant_id)

    def get_portfolios_paginated(
        self,
        tenant_id: int,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        portfolio_type: Optional[str] = None,
        label: Optional[str] = None
    ) -> Tuple[List[InvestmentPortfolio], int]:
        """
        Get paginated portfolios with filtering and search.

        Args:
            tenant_id: Tenant ID for ownership and isolation
            include_archived: Whether to include archived portfolios
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search query for portfolio name
            portfolio_type: Filter by portfolio type
            label: Filter by label

        Returns:
            Tuple of (portfolios list, total count)
        """
        return self.portfolio_repo.get_paginated(
            tenant_id=tenant_id,
            include_archived=include_archived,
            skip=skip,
            limit=limit,
            search=search,
            portfolio_type=portfolio_type,
            label=label
        )

    def get_deleted_portfolios(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 10
    ) -> Tuple[List[InvestmentPortfolio], int]:
        """
        Get deleted (archived) portfolios with pagination.

        Args:
            tenant_id: Tenant ID for ownership and isolation
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (deleted portfolios list, total count)
        """
        return self.portfolio_repo.get_deleted_portfolios(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit
        )

    def restore_portfolio(
        self,
        portfolio_id: int,
        tenant_id: int
    ) -> bool:
        """
        Restore a deleted (archived) portfolio.

        Args:
            portfolio_id: Portfolio ID to restore
            tenant_id: Tenant ID for ownership and isolation

        Returns:
            True if restored successfully, False if not found
        """
        return self.portfolio_repo.restore(portfolio_id, tenant_id)

    def permanently_delete_portfolio(
        self,
        portfolio_id: int,
        tenant_id: int
    ) -> bool:
        """
        Permanently delete a portfolio (hard delete).

        Args:
            portfolio_id: Portfolio ID to delete
            tenant_id: Tenant ID for ownership and isolation

        Returns:
            True if deleted successfully, False if not found
        """
        return self.portfolio_repo.permanently_delete(portfolio_id, tenant_id)

    def empty_recycle_bin(
        self,
        tenant_id: int
    ) -> int:
        """
        Permanently delete all archived portfolios for a tenant.

        Args:
            tenant_id: Tenant ID for ownership and isolation

        Returns:
            Number of portfolios deleted
        """
        return self.portfolio_repo.empty_recycle_bin(tenant_id)

    def close(self):
        """Close database connections and clean up resources."""
        if hasattr(self, 'portfolio_repo'):
            self.portfolio_repo.close()
        if hasattr(self, 'holdings_repo'):
            self.holdings_repo.close_session()
        if hasattr(self, 'db'):
            self.db.close()
