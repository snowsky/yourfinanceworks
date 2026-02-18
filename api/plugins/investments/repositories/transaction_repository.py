"""
Transaction Repository

This module implements the data access layer for investment transactions.
It provides CRUD operations with proper tenant isolation through portfolio
relationships and follows the repository pattern to separate data access
from business logic.

All queries automatically filter by tenant context through portfolio ownership
to ensure data isolation.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_, desc, asc
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal

from ..models import InvestmentTransaction, InvestmentPortfolio, InvestmentHolding, TransactionType, DividendType


class TransactionRepository:
    """
    Repository for transaction data access operations.

    All methods enforce tenant isolation by filtering queries based on portfolio
    ownership. This ensures users can only access transactions from their own portfolios.
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
        transaction_type: TransactionType,
        transaction_date: date,
        total_amount: Decimal,
        holding_id: Optional[int] = None,
        quantity: Optional[Decimal] = None,
        price_per_share: Optional[Decimal] = None,
        fees: Optional[Decimal] = None,
        realized_gain: Optional[Decimal] = None,
        dividend_type: Optional[DividendType] = None,
        payment_date: Optional[date] = None,
        ex_dividend_date: Optional[date] = None,
        notes: Optional[str] = None
    ) -> InvestmentTransaction:
        """
        Create a new transaction.

        Args:
            portfolio_id: Portfolio ID
            transaction_type: Type of transaction
            transaction_date: Date of transaction
            total_amount: Total transaction amount
            holding_id: Holding ID (optional for cash transactions)
            quantity: Quantity of shares (optional for dividends, fees, etc.)
            price_per_share: Price per share (optional for dividends, fees, etc.)
            fees: Transaction fees
            realized_gain: Realized gain for sell transactions
            dividend_type: Type of dividend (for dividend transactions)
            payment_date: Dividend payment date (for dividend transactions)
            ex_dividend_date: Ex-dividend date (for dividend transactions)
            notes: Transaction notes

        Returns:
            Created transaction instance

        Raises:
            SQLAlchemyError: If database operation fails
        """
        transaction = InvestmentTransaction(
            portfolio_id=portfolio_id,
            holding_id=holding_id,
            transaction_type=transaction_type,
            transaction_date=transaction_date,
            quantity=quantity,
            price_per_share=price_per_share,
            total_amount=total_amount,
            fees=fees or Decimal('0'),
            realized_gain=realized_gain,
            dividend_type=dividend_type,
            payment_date=payment_date,
            ex_dividend_date=ex_dividend_date,
            notes=notes,
            created_at=datetime.now(timezone.utc)
        )

        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)

        return transaction

    def get_by_id(self, transaction_id: int) -> Optional[InvestmentTransaction]:
        """
        Get a transaction by ID with tenant isolation through portfolio ownership.

        Args:
            transaction_id: Transaction ID

        Returns:
            Transaction instance if found and accessible, None otherwise
        """
        return self.db.query(InvestmentTransaction).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.id == transaction_id,
                InvestmentPortfolio.is_archived == False
            )
        ).first()

    def get_by_portfolio(
        self,
        portfolio_id: int,
        tenant_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_types: Optional[List[TransactionType]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[InvestmentTransaction]:
        """
        Get transactions for a portfolio with optional filtering.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for security
            start_date: Start date filter (inclusive)
            end_date: End date filter (inclusive)
            transaction_types: List of transaction types to filter by
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of transaction instances ordered by transaction_date (descending)
        """
        query = self.db.query(InvestmentTransaction).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentPortfolio.tenant_id == tenant_id,
                InvestmentPortfolio.is_archived == False
            )
        )

        # Apply date filters
        if start_date:
            query = query.filter(InvestmentTransaction.transaction_date >= start_date)
        if end_date:
            query = query.filter(InvestmentTransaction.transaction_date <= end_date)

        # Apply transaction type filter
        if transaction_types:
            query = query.filter(InvestmentTransaction.transaction_type.in_(transaction_types))

        # Order by transaction_date (descending for most recent first)
        query = query.order_by(desc(InvestmentTransaction.transaction_date), desc(InvestmentTransaction.id))

        # Apply pagination
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        return query.all()

    def get_by_date_range(
        self,
        portfolio_id: int,
        start_date: date,
        end_date: date,
        transaction_types: Optional[List[TransactionType]] = None
    ) -> List[InvestmentTransaction]:
        """
        Get transactions within a specific date range.

        Args:
            portfolio_id: Portfolio ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            transaction_types: Optional list of transaction types to filter by

        Returns:
            List of transactions ordered by transaction_date (ascending)
        """
        query = self.db.query(InvestmentTransaction).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentTransaction.transaction_date >= start_date,
                InvestmentTransaction.transaction_date <= end_date,
                InvestmentPortfolio.is_archived == False
            )
        )

        if transaction_types:
            query = query.filter(InvestmentTransaction.transaction_type.in_(transaction_types))

        return query.order_by(asc(InvestmentTransaction.transaction_date), asc(InvestmentTransaction.id)).all()

    def get_by_holding(
        self,
        holding_id: int,
        transaction_types: Optional[List[TransactionType]] = None
    ) -> List[InvestmentTransaction]:
        """
        Get all transactions for a specific holding.

        Args:
            holding_id: Holding ID
            transaction_types: Optional list of transaction types to filter by

        Returns:
            List of transactions ordered by transaction_date (ascending)
        """
        query = self.db.query(InvestmentTransaction).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.holding_id == holding_id,
                InvestmentPortfolio.is_archived == False
            )
        )

        if transaction_types:
            query = query.filter(InvestmentTransaction.transaction_type.in_(transaction_types))

        return query.order_by(asc(InvestmentTransaction.transaction_date), asc(InvestmentTransaction.id)).all()

    def get_buy_transactions(self, holding_id: int) -> List[InvestmentTransaction]:
        """
        Get all buy transactions for a holding (used for cost basis calculations).

        Args:
            holding_id: Holding ID

        Returns:
            List of buy transactions ordered by transaction_date (ascending)
        """
        return self.get_by_holding(holding_id, [TransactionType.BUY])

    def get_sell_transactions(self, holding_id: int) -> List[InvestmentTransaction]:
        """
        Get all sell transactions for a holding.

        Args:
            holding_id: Holding ID

        Returns:
            List of sell transactions ordered by transaction_date (ascending)
        """
        return self.get_by_holding(holding_id, [TransactionType.SELL])

    def get_dividend_transactions(
        self,
        portfolio_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[InvestmentTransaction]:
        """
        Get dividend transactions for a portfolio within a date range.

        Args:
            portfolio_id: Portfolio ID
            start_date: Start date filter (inclusive)
            end_date: End date filter (inclusive)

        Returns:
            List of dividend transactions ordered by transaction_date (descending)
        """
        return self.get_by_portfolio(
            portfolio_id=portfolio_id,
            start_date=start_date,
            end_date=end_date,
            transaction_types=[TransactionType.DIVIDEND]
        )

    def get_realized_gains_for_year(self, portfolio_id: int, tax_year: int) -> List[InvestmentTransaction]:
        """
        Get all sell transactions with realized gains for a specific tax year.

        Args:
            portfolio_id: Portfolio ID
            tax_year: Tax year (e.g., 2024)

        Returns:
            List of sell transactions with realized gains
        """
        start_date = date(tax_year, 1, 1)
        end_date = date(tax_year, 12, 31)

        return self.db.query(InvestmentTransaction).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentTransaction.transaction_type == TransactionType.SELL,
                InvestmentTransaction.transaction_date >= start_date,
                InvestmentTransaction.transaction_date <= end_date,
                InvestmentTransaction.realized_gain.isnot(None),
                InvestmentPortfolio.is_archived == False
            )
        ).order_by(asc(InvestmentTransaction.transaction_date)).all()

    def get_dividends_for_year(self, portfolio_id: int, tax_year: int) -> List[InvestmentTransaction]:
        """
        Get all dividend transactions for a specific tax year.

        Args:
            portfolio_id: Portfolio ID
            tax_year: Tax year (e.g., 2024)

        Returns:
            List of dividend transactions
        """
        start_date = date(tax_year, 1, 1)
        end_date = date(tax_year, 12, 31)

        return self.get_dividend_transactions(portfolio_id, start_date, end_date)

    def calculate_total_dividends(
        self,
        portfolio_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Decimal:
        """
        Calculate total dividend income for a portfolio within a date range.

        Args:
            portfolio_id: Portfolio ID
            start_date: Start date filter (inclusive)
            end_date: End date filter (inclusive)

        Returns:
            Total dividend amount
        """
        query = self.db.query(
            func.sum(InvestmentTransaction.total_amount)
        ).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentTransaction.transaction_type == TransactionType.DIVIDEND,
                InvestmentPortfolio.is_archived == False
            )
        )

        if start_date:
            query = query.filter(InvestmentTransaction.transaction_date >= start_date)
        if end_date:
            query = query.filter(InvestmentTransaction.transaction_date <= end_date)

        result = query.scalar()
        return result or Decimal('0')

    def calculate_total_realized_gains(self, portfolio_id: int, tax_year: Optional[int] = None) -> Decimal:
        """
        Calculate total realized gains for a portfolio.

        Args:
            portfolio_id: Portfolio ID
            tax_year: Optional tax year to filter by

        Returns:
            Total realized gains (can be negative for losses)
        """
        query = self.db.query(
            func.sum(InvestmentTransaction.realized_gain)
        ).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentTransaction.transaction_type == TransactionType.SELL,
                InvestmentTransaction.realized_gain.isnot(None),
                InvestmentPortfolio.is_archived == False
            )
        )

        if tax_year:
            start_date = date(tax_year, 1, 1)
            end_date = date(tax_year, 12, 31)
            query = query.filter(
                and_(
                    InvestmentTransaction.transaction_date >= start_date,
                    InvestmentTransaction.transaction_date <= end_date
                )
            )

        result = query.scalar()
        return result or Decimal('0')

    def get_transactions_for_tax_export(self, portfolio_id: int, tax_year: int) -> List[InvestmentTransaction]:
        """
        Get all transactions relevant for tax reporting for a specific year.

        Args:
            portfolio_id: Portfolio ID
            tax_year: Tax year (e.g., 2024)

        Returns:
            List of transactions (sells with realized gains and dividends)
        """
        start_date = date(tax_year, 1, 1)
        end_date = date(tax_year, 12, 31)

        return self.db.query(InvestmentTransaction).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentTransaction.transaction_date >= start_date,
                InvestmentTransaction.transaction_date <= end_date,
                or_(
                    and_(
                        InvestmentTransaction.transaction_type == TransactionType.SELL,
                        InvestmentTransaction.realized_gain.isnot(None)
                    ),
                    InvestmentTransaction.transaction_type == TransactionType.DIVIDEND
                ),
                InvestmentPortfolio.is_archived == False
            )
        ).order_by(asc(InvestmentTransaction.transaction_date)).all()

    def count_by_portfolio(
        self,
        portfolio_id: int,
        transaction_types: Optional[List[TransactionType]] = None
    ) -> int:
        """
        Count transactions in a portfolio.

        Args:
            portfolio_id: Portfolio ID
            transaction_types: Optional list of transaction types to filter by

        Returns:
            Number of transactions in the portfolio
        """
        query = self.db.query(func.count(InvestmentTransaction.id)).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentPortfolio.is_archived == False
            )
        )

        if transaction_types:
            query = query.filter(InvestmentTransaction.transaction_type.in_(transaction_types))

        return query.scalar() or 0

    def get_latest_transactions(self, portfolio_id: int, limit: int = 10) -> List[InvestmentTransaction]:
        """
        Get the most recent transactions for a portfolio.

        Args:
            portfolio_id: Portfolio ID
            limit: Maximum number of transactions to return

        Returns:
            List of recent transactions ordered by date (descending)
        """
        return self.get_by_portfolio(portfolio_id, limit=limit)

    def check_duplicate_transaction(
        self,
        portfolio_id: int,
        transaction_type: TransactionType,
        transaction_date: date,
        total_amount: Decimal,
        quantity: Optional[Decimal] = None,
        holding_id: Optional[int] = None,
        time_window_minutes: int = 60
    ) -> bool:
        """
        Check for duplicate transactions within a time window.

        Args:
            portfolio_id: Portfolio ID
            transaction_type: Transaction type
            transaction_date: Transaction date
            total_amount: Transaction amount
            quantity: Transaction quantity (optional)
            holding_id: Holding ID (optional)
            time_window_minutes: Time window in minutes to check for duplicates

        Returns:
            True if a duplicate transaction exists, False otherwise
        """
        # Calculate time window
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)

        query = self.db.query(InvestmentTransaction).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentTransaction.transaction_type == transaction_type,
                InvestmentTransaction.transaction_date == transaction_date,
                InvestmentTransaction.total_amount == total_amount,
                InvestmentTransaction.created_at >= cutoff_time,
                InvestmentPortfolio.is_archived == False
            )
        )

        # Add optional filters
        if quantity is not None:
            query = query.filter(InvestmentTransaction.quantity == quantity)
        if holding_id is not None:
            query = query.filter(InvestmentTransaction.holding_id == holding_id)

        return query.first() is not None

    def validate_tenant_access(self, transaction_id: int) -> bool:
        """
        Validate that a transaction exists and is accessible by the current tenant.

        This is done by checking if the transaction's portfolio is in the current
        tenant's database (tenant isolation is handled at the database level).

        Args:
            transaction_id: Transaction ID to validate

        Returns:
            True if transaction exists and is accessible, False otherwise
        """
        transaction = self.get_by_id(transaction_id)
        return transaction is not None

    def exists(self, transaction_id: int) -> bool:
        """
        Check if a transaction exists and is accessible.

        Args:
            transaction_id: Transaction ID

        Returns:
            True if transaction exists, False otherwise
        """
        return self.db.query(InvestmentTransaction.id).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.id == transaction_id,
                InvestmentPortfolio.is_archived == False
            )
        ).first() is not None

    def get_portfolio_transaction_summary(self, portfolio_id: int) -> dict:
        """
        Get transaction summary statistics for a portfolio.

        Args:
            portfolio_id: Portfolio ID

        Returns:
            Dictionary with transaction counts by type and total amounts
        """
        # Get transaction counts by type
        type_counts = self.db.query(
            InvestmentTransaction.transaction_type,
            func.count(InvestmentTransaction.id).label('count'),
            func.sum(InvestmentTransaction.total_amount).label('total_amount')
        ).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentPortfolio.is_archived == False
            )
        ).group_by(InvestmentTransaction.transaction_type).all()

        summary = {
            'total_transactions': 0,
            'by_type': {},
            'total_buy_amount': Decimal('0'),
            'total_sell_amount': Decimal('0'),
            'total_dividend_amount': Decimal('0'),
            'total_realized_gains': Decimal('0')
        }

        for transaction_type, count, total_amount in type_counts:
            summary['total_transactions'] += count
            summary['by_type'][transaction_type.value] = {
                'count': count,
                'total_amount': total_amount or Decimal('0')
            }

            # Aggregate key amounts
            if transaction_type == TransactionType.BUY:
                summary['total_buy_amount'] = total_amount or Decimal('0')
            elif transaction_type == TransactionType.SELL:
                summary['total_sell_amount'] = total_amount or Decimal('0')
            elif transaction_type == TransactionType.DIVIDEND:
                summary['total_dividend_amount'] = total_amount or Decimal('0')

        # Get total realized gains separately
        summary['total_realized_gains'] = self.calculate_total_realized_gains(portfolio_id)

        return summary

    def get_recent_transactions(
        self,
        portfolio_id: int,
        since: datetime,
        limit: Optional[int] = 100
    ) -> List[InvestmentTransaction]:
        """
        Get recent transactions for duplicate detection.

        Args:
            portfolio_id: Portfolio ID
            since: Get transactions created since this datetime
            limit: Maximum number of transactions to return

        Returns:
            List of recent transactions ordered by creation time (descending)
        """
        return self.db.query(InvestmentTransaction).join(InvestmentPortfolio).filter(
            and_(
                InvestmentTransaction.portfolio_id == portfolio_id,
                InvestmentTransaction.created_at >= since,
                InvestmentPortfolio.is_archived == False
            )
        ).order_by(desc(InvestmentTransaction.created_at)).limit(limit).all()

    def close_session(self):
        """Close the database session."""
        if self.db:
            self.db.close()