"""
Transaction Service

This module implements the business logic layer for investment transactions.
It provides high-level operations for recording and processing transactions
with proper validation, tenant isolation, and business rule enforcement.

The service handles all transaction types (buy, sell, dividend, etc.) and
automatically updates holdings when appropriate. It uses simple average cost
basis for realized gain calculations in the MVP.
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session

from ..repositories.transaction_repository import TransactionRepository
from ..repositories.holdings_repository import HoldingsRepository
from ..repositories.portfolio_repository import PortfolioRepository
from ..models import InvestmentTransaction, InvestmentHolding, TransactionType, DividendType
from ..schemas import (
    TransactionResponse, BuyTransactionCreate, SellTransactionCreate,
    DividendTransactionCreate, OtherTransactionCreate
)
from core.exceptions.base import ValidationError, NotFoundError, ConflictError


class TransactionService:
    """
    Service for transaction business logic operations.

    This service provides high-level operations for recording and processing
    investment transactions with proper validation, tenant isolation, and
    automatic holding updates.
    """

    def __init__(self, db: Session):
        """
        Initialize the transaction service.

        Args:
            db: Database session
        """
        self.db = db
        self.transaction_repo = TransactionRepository(db)
        self.holdings_repo = HoldingsRepository(db)
        self.portfolio_repo = PortfolioRepository(db)

    def record_transaction(
        self,
        tenant_id: int,
        portfolio_id: int,
        transaction_data: Dict[str, Any]
    ) -> TransactionResponse:
        """
        Record a transaction (dispatcher method).

        This method dispatches to the appropriate transaction processing method
        based on the transaction type.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            transaction_data: Transaction data dictionary

        Returns:
            Created transaction data

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
            ValidationError: If transaction data is invalid
            ConflictError: If duplicate transaction detected
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Extract transaction type
        transaction_type = transaction_data.get('transaction_type')
        if not transaction_type:
            raise ValidationError("Transaction type is required")

        # Validate required fields
        self._validate_required_fields(transaction_data)

        # Validate amounts and dates
        self._validate_transaction_data(transaction_data)

        # Check for duplicate transactions
        self._check_duplicate_transaction(portfolio_id, transaction_data)

        # Dispatch to appropriate processing method
        if transaction_type == TransactionType.BUY:
            return self.process_buy(tenant_id, portfolio_id, transaction_data)
        elif transaction_type == TransactionType.SELL:
            return self.process_sell(tenant_id, portfolio_id, transaction_data)
        elif transaction_type == TransactionType.DIVIDEND:
            return self.process_dividend(tenant_id, portfolio_id, transaction_data)
        elif transaction_type == TransactionType.INTEREST:
            return self.process_interest(tenant_id, portfolio_id, transaction_data)
        elif transaction_type == TransactionType.FEE:
            return self.process_fee(tenant_id, portfolio_id, transaction_data)
        elif transaction_type == TransactionType.TRANSFER:
            return self.process_transfer(tenant_id, portfolio_id, transaction_data)
        elif transaction_type == TransactionType.CONTRIBUTION:
            return self.process_contribution(tenant_id, portfolio_id, transaction_data)
        else:
            raise ValidationError(f"Unsupported transaction type: {transaction_type}")

    def process_buy(
        self,
        tenant_id: int,
        portfolio_id: int,
        transaction_data: Dict[str, Any]
    ) -> TransactionResponse:
        """
        Process a buy transaction (increase quantity and cost basis).

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            transaction_data: Buy transaction data

        Returns:
            Created transaction data

        Raises:
            NotFoundError: If holding doesn't exist
            ValidationError: If transaction data is invalid
        """
        holding_id = transaction_data.get('holding_id')
        quantity = Decimal(str(transaction_data.get('quantity', 0)))
        price_per_share = Decimal(str(transaction_data.get('price_per_share', 0)))
        total_amount = Decimal(str(transaction_data.get('total_amount', 0)))
        fees = Decimal(str(transaction_data.get('fees', 0)))

        # Validate holding exists and belongs to portfolio
        holding = self.holdings_repo.get_by_id(holding_id, tenant_id)
        if not holding or holding.portfolio_id != portfolio_id:
            raise NotFoundError(f"Holding {holding_id} not found in portfolio {portfolio_id}")

        # Validate buy-specific fields
        if quantity <= 0:
            raise ValidationError("Quantity must be positive for buy transactions")
        if price_per_share <= 0:
            raise ValidationError("Price per share must be positive for buy transactions")

        # Calculate total cost including fees
        total_cost = total_amount + fees

        # Create the transaction
        transaction = self.transaction_repo.create(
            portfolio_id=portfolio_id,
            holding_id=holding_id,
            transaction_type=TransactionType.BUY,
            transaction_date=transaction_data['transaction_date'],
            quantity=quantity,
            price_per_share=price_per_share,
            total_amount=total_amount,
            fees=fees,
            notes=transaction_data.get('notes')
        )

        # Update holding: increase quantity and cost basis
        self.holdings_repo.adjust_quantity(holding_id, tenant_id, quantity, total_cost)

        return TransactionResponse.model_validate(transaction)

    def process_sell(
        self,
        tenant_id: int,
        portfolio_id: int,
        transaction_data: Dict[str, Any]
    ) -> TransactionResponse:
        """
        Process a sell transaction (decrease quantity, calculate realized gains using simple average cost).

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            transaction_data: Sell transaction data

        Returns:
            Created transaction data

        Raises:
            NotFoundError: If holding doesn't exist
            ValidationError: If insufficient quantity or invalid data
        """
        holding_id = transaction_data.get('holding_id')
        quantity = Decimal(str(transaction_data.get('quantity', 0)))
        price_per_share = Decimal(str(transaction_data.get('price_per_share', 0)))
        total_amount = Decimal(str(transaction_data.get('total_amount', 0)))
        fees = Decimal(str(transaction_data.get('fees', 0)))

        # Validate holding exists and belongs to portfolio
        holding = self.holdings_repo.get_by_id(holding_id, tenant_id)
        if not holding or holding.portfolio_id != portfolio_id:
            raise NotFoundError(f"Holding {holding_id} not found in portfolio {portfolio_id}")

        # Validate sell-specific fields
        if quantity <= 0:
            raise ValidationError("Quantity must be positive for sell transactions")
        if price_per_share <= 0:
            raise ValidationError("Price per share must be positive for sell transactions")

        # Check sufficient quantity
        if holding.quantity < quantity:
            raise ValidationError(f"Insufficient quantity. Available: {holding.quantity}, Requested: {quantity}")

        # Calculate realized gain using simple average cost
        realized_gain = self.calculate_realized_gain(holding, quantity, price_per_share, fees)

        # Calculate net proceeds (total amount minus fees)
        net_proceeds = total_amount - fees

        # Create the transaction
        transaction = self.transaction_repo.create(
            portfolio_id=portfolio_id,
            holding_id=holding_id,
            transaction_type=TransactionType.SELL,
            transaction_date=transaction_data['transaction_date'],
            quantity=quantity,
            price_per_share=price_per_share,
            total_amount=total_amount,
            fees=fees,
            realized_gain=realized_gain,
            notes=transaction_data.get('notes')
        )

        # Update holding: decrease quantity and cost basis
        # Cost basis reduction = (quantity sold / total quantity) * total cost basis
        cost_basis_reduction = (quantity / holding.quantity) * holding.cost_basis
        self.holdings_repo.adjust_quantity(holding_id, tenant_id, -quantity, -cost_basis_reduction)

        return TransactionResponse.model_validate(transaction)

    def process_dividend(
        self,
        tenant_id: int,
        portfolio_id: int,
        transaction_data: Dict[str, Any]
    ) -> TransactionResponse:
        """
        Process a dividend transaction (record income, no quantity change).

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            transaction_data: Dividend transaction data

        Returns:
            Created transaction data

        Raises:
            NotFoundError: If holding doesn't exist
            ValidationError: If transaction data is invalid
        """
        holding_id = transaction_data.get('holding_id')
        total_amount = Decimal(str(transaction_data.get('total_amount', 0)))
        dividend_type = transaction_data.get('dividend_type', DividendType.ORDINARY)

        # Validate holding exists and belongs to portfolio
        holding = self.holdings_repo.get_by_id(holding_id, tenant_id)
        if not holding or holding.portfolio_id != portfolio_id:
            raise NotFoundError(f"Holding {holding_id} not found in portfolio {portfolio_id}")

        # Validate dividend amount
        if total_amount <= 0:
            raise ValidationError("Dividend amount must be positive")

        # Create the transaction (no holding update for dividends)
        transaction = self.transaction_repo.create(
            portfolio_id=portfolio_id,
            holding_id=holding_id,
            transaction_type=TransactionType.DIVIDEND,
            transaction_date=transaction_data['transaction_date'],
            total_amount=total_amount,
            fees=Decimal(str(transaction_data.get('fees', 0))),
            dividend_type=dividend_type,
            payment_date=transaction_data.get('payment_date'),
            ex_dividend_date=transaction_data.get('ex_dividend_date'),
            notes=transaction_data.get('notes')
        )

        return TransactionResponse.model_validate(transaction)

    def process_interest(
        self,
        tenant_id: int,
        portfolio_id: int,
        transaction_data: Dict[str, Any]
    ) -> TransactionResponse:
        """
        Process an interest transaction (record only, no holding change).

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            transaction_data: Interest transaction data

        Returns:
            Created transaction data
        """
        total_amount = Decimal(str(transaction_data.get('total_amount', 0)))

        # Validate interest amount
        if total_amount <= 0:
            raise ValidationError("Interest amount must be positive")

        # Create the transaction (no holding update for interest)
        transaction = self.transaction_repo.create(
            portfolio_id=portfolio_id,
            holding_id=transaction_data.get('holding_id'),  # Optional for cash transactions
            transaction_type=TransactionType.INTEREST,
            transaction_date=transaction_data['transaction_date'],
            total_amount=total_amount,
            fees=Decimal(str(transaction_data.get('fees', 0))),
            notes=transaction_data.get('notes')
        )

        return TransactionResponse.model_validate(transaction)

    def process_fee(
        self,
        tenant_id: int,
        portfolio_id: int,
        transaction_data: Dict[str, Any]
    ) -> TransactionResponse:
        """
        Process a fee transaction (record only, no holding change).

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            transaction_data: Fee transaction data

        Returns:
            Created transaction data
        """
        total_amount = Decimal(str(transaction_data.get('total_amount', 0)))

        # Validate fee amount (can be negative for fee refunds)
        if total_amount == 0:
            raise ValidationError("Fee amount cannot be zero")

        # Create the transaction (no holding update for fees)
        transaction = self.transaction_repo.create(
            portfolio_id=portfolio_id,
            holding_id=transaction_data.get('holding_id'),  # Optional for cash transactions
            transaction_type=TransactionType.FEE,
            transaction_date=transaction_data['transaction_date'],
            total_amount=total_amount,
            fees=Decimal(str(transaction_data.get('fees', 0))),
            notes=transaction_data.get('notes')
        )

        return TransactionResponse.model_validate(transaction)

    def process_transfer(
        self,
        tenant_id: int,
        portfolio_id: int,
        transaction_data: Dict[str, Any]
    ) -> TransactionResponse:
        """
        Process a transfer transaction (record only, no holding change).

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            transaction_data: Transfer transaction data

        Returns:
            Created transaction data
        """
        total_amount = Decimal(str(transaction_data.get('total_amount', 0)))

        # Validate transfer amount (can be positive or negative)
        if total_amount == 0:
            raise ValidationError("Transfer amount cannot be zero")

        # Create the transaction (no holding update for transfers)
        transaction = self.transaction_repo.create(
            portfolio_id=portfolio_id,
            holding_id=transaction_data.get('holding_id'),  # Optional for cash transactions
            transaction_type=TransactionType.TRANSFER,
            transaction_date=transaction_data['transaction_date'],
            total_amount=total_amount,
            fees=Decimal(str(transaction_data.get('fees', 0))),
            notes=transaction_data.get('notes')
        )

        return TransactionResponse.model_validate(transaction)

    def process_contribution(
        self,
        tenant_id: int,
        portfolio_id: int,
        transaction_data: Dict[str, Any]
    ) -> TransactionResponse:
        """
        Process a contribution transaction (record only, no holding change).

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            transaction_data: Contribution transaction data

        Returns:
            Created transaction data
        """
        total_amount = Decimal(str(transaction_data.get('total_amount', 0)))

        # Validate contribution amount
        if total_amount <= 0:
            raise ValidationError("Contribution amount must be positive")

        # Create the transaction (no holding update for contributions)
        transaction = self.transaction_repo.create(
            portfolio_id=portfolio_id,
            holding_id=transaction_data.get('holding_id'),  # Optional for cash transactions
            transaction_type=TransactionType.CONTRIBUTION,
            transaction_date=transaction_data['transaction_date'],
            total_amount=total_amount,
            fees=Decimal(str(transaction_data.get('fees', 0))),
            notes=transaction_data.get('notes')
        )

        return TransactionResponse.model_validate(transaction)

    def calculate_realized_gain(
        self,
        holding: InvestmentHolding,
        sell_quantity: Decimal,
        sell_price: Decimal,
        fees: Decimal = Decimal('0')
    ) -> Decimal:
        """
        Calculate realized gain using simple average cost algorithm.

        Args:
            holding: Holding being sold
            sell_quantity: Quantity being sold
            sell_price: Price per share
            fees: Transaction fees

        Returns:
            Realized gain (can be negative for losses)
        """
        # Calculate average cost per share
        if holding.quantity <= 0:
            raise ValidationError("Cannot calculate realized gain for holding with zero quantity")

        average_cost_per_share = holding.cost_basis / holding.quantity

        # Calculate cost basis for shares being sold
        cost_basis_sold = sell_quantity * average_cost_per_share

        # Calculate gross proceeds
        gross_proceeds = sell_quantity * sell_price

        # Calculate net proceeds (after fees)
        net_proceeds = gross_proceeds - fees

        # Calculate realized gain/loss
        realized_gain = net_proceeds - cost_basis_sold

        return realized_gain

    def get_transactions(
        self,
        tenant_id: int,
        portfolio_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_types: Optional[List[TransactionType]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[TransactionResponse]:
        """
        Get transactions for a portfolio with optional filtering.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            start_date: Start date filter (inclusive)
            end_date: End date filter (inclusive)
            transaction_types: List of transaction types to filter by
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of transactions

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get transactions
        transactions = self.transaction_repo.get_by_portfolio(
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            transaction_types=transaction_types,
            limit=limit,
            offset=offset
        )

        return [TransactionResponse.model_validate(transaction) for transaction in transactions]

    def get_transaction(self, tenant_id: int, transaction_id: int) -> TransactionResponse:
        """
        Get a specific transaction by ID.

        Args:
            tenant_id: Tenant ID for isolation
            transaction_id: Transaction ID

        Returns:
            Transaction data

        Raises:
            NotFoundError: If transaction doesn't exist or doesn't belong to tenant
        """
        transaction = self.transaction_repo.get_by_id(transaction_id, tenant_id)
        if not transaction:
            raise NotFoundError(f"Transaction {transaction_id} not found")

        # Validate tenant access through portfolio
        portfolio = self.portfolio_repo.get_by_id(transaction.portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {transaction.portfolio_id} not found")

        return TransactionResponse.model_validate(transaction)

    def _validate_required_fields(self, transaction_data: Dict[str, Any]):
        """
        Validate that required fields are present.

        Args:
            transaction_data: Transaction data to validate

        Raises:
            ValidationError: If required fields are missing
        """
        required_fields = ['transaction_type', 'transaction_date', 'total_amount']

        for field in required_fields:
            if field not in transaction_data or transaction_data[field] is None:
                raise ValidationError(f"Required field '{field}' is missing")

    def _validate_transaction_data(self, transaction_data: Dict[str, Any]):
        """
        Validate transaction data (amounts and dates).

        Args:
            transaction_data: Transaction data to validate

        Raises:
            ValidationError: If data is invalid
        """
        # Validate transaction date is not in the future
        transaction_date = transaction_data.get('transaction_date')
        if isinstance(transaction_date, str):
            transaction_date = date.fromisoformat(transaction_date)

        if transaction_date and transaction_date > date.today():
            raise ValidationError("Transaction date cannot be in the future")

        # Validate total amount
        total_amount = transaction_data.get('total_amount')
        if total_amount is not None:
            try:
                amount_decimal = Decimal(str(total_amount))
                transaction_type = transaction_data.get('transaction_type')

                # Most transaction types require positive amounts
                if transaction_type in [TransactionType.BUY, TransactionType.DIVIDEND,
                                      TransactionType.INTEREST, TransactionType.CONTRIBUTION]:
                    if amount_decimal <= 0:
                        raise ValidationError(f"Amount must be positive for {transaction_type.value} transactions")
                elif transaction_type == TransactionType.SELL:
                    if amount_decimal <= 0:
                        raise ValidationError("Amount must be positive for sell transactions")
                # FEE and TRANSFER can be negative, but not zero
                elif transaction_type in [TransactionType.FEE, TransactionType.TRANSFER]:
                    if amount_decimal == 0:
                        raise ValidationError(f"Amount cannot be zero for {transaction_type.value} transactions")

            except (ValueError, TypeError):
                raise ValidationError("Invalid amount format")

        # Validate fees if present
        fees = transaction_data.get('fees')
        if fees is not None:
            try:
                fees_decimal = Decimal(str(fees))
                if fees_decimal < 0:
                    raise ValidationError("Fees cannot be negative")
            except (ValueError, TypeError):
                raise ValidationError("Invalid fees format")

    def _check_duplicate_transaction(self, portfolio_id: int, transaction_data: Dict[str, Any]):
        """
        Check for duplicate transactions within a time window.

        Args:
            portfolio_id: Portfolio ID
            transaction_data: Transaction data

        Raises:
            ConflictError: If duplicate transaction detected
        """
        transaction_type = transaction_data.get('transaction_type')
        transaction_date = transaction_data.get('transaction_date')
        total_amount = Decimal(str(transaction_data.get('total_amount', 0)))
        quantity = transaction_data.get('quantity')
        holding_id = transaction_data.get('holding_id')

        # Convert string date to date object if needed
        if isinstance(transaction_date, str):
            transaction_date = date.fromisoformat(transaction_date)

        # Convert quantity to Decimal if present
        quantity_decimal = None
        if quantity is not None:
            quantity_decimal = Decimal(str(quantity))

        # Check for duplicate
        is_duplicate = self.transaction_repo.check_duplicate_transaction(
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            transaction_type=transaction_type,
            transaction_date=transaction_date,
            total_amount=total_amount,
            quantity=quantity_decimal,
            holding_id=holding_id,
            time_window_minutes=60
        )

        if is_duplicate:
            raise ConflictError("Duplicate transaction detected within 60-minute window")