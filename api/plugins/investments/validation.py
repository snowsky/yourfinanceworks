"""
Investment Management Validation Utilities

This module provides validation functions and middleware for the investment management plugin.
It includes input validation, business rule validation, and duplicate detection.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from .models import PortfolioType, SecurityType, AssetClass, TransactionType, DividendType
from .exceptions import (
    ValidationError,
    FutureDateError,
    NegativeValueError,
    InvalidEnumValueError,
    DuplicateTransactionError
)
from .repositories.transaction_repository import TransactionRepository

# Set up logger
logger = logging.getLogger(__name__)


class ValidationUtils:
    """Utility class for common validation operations"""

    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Validate that all required fields are present and not None.

        Args:
            data: Dictionary containing the data to validate
            required_fields: List of required field names

        Raises:
            ValidationError: If any required field is missing or None
        """
        missing_fields = []
        for field in required_fields:
            if field not in data or data[field] is None:
                missing_fields.append(field)

        if missing_fields:
            raise ValidationError(
                f"Missing required fields: {', '.join(missing_fields)}",
                [{"field": field, "message": "This field is required"} for field in missing_fields]
            )

    @staticmethod
    def validate_positive_number(value: Any, field_name: str) -> Decimal:
        """
        Validate that a value is a positive number.

        Args:
            value: The value to validate
            field_name: Name of the field for error messages

        Returns:
            Decimal: The validated value as a Decimal

        Raises:
            ValidationError: If the value is not positive
        """
        try:
            decimal_value = Decimal(str(value))
            if decimal_value <= 0:
                raise NegativeValueError(
                    f"{field_name} must be positive",
                    [{"field": field_name, "message": "Must be a positive number"}]
                )
            return decimal_value
        except (ValueError, TypeError):
            raise ValidationError(
                f"{field_name} must be a valid number",
                [{"field": field_name, "message": "Must be a valid number"}]
            )

    @staticmethod
    def validate_non_negative_number(value: Any, field_name: str) -> Decimal:
        """
        Validate that a value is a non-negative number (>= 0).

        Args:
            value: The value to validate
            field_name: Name of the field for error messages

        Returns:
            Decimal: The validated value as a Decimal

        Raises:
            ValidationError: If the value is negative
        """
        try:
            decimal_value = Decimal(str(value))
            if decimal_value < 0:
                raise NegativeValueError(
                    f"{field_name} cannot be negative",
                    [{"field": field_name, "message": "Cannot be negative"}]
                )
            return decimal_value
        except (ValueError, TypeError):
            raise ValidationError(
                f"{field_name} must be a valid number",
                [{"field": field_name, "message": "Must be a valid number"}]
            )

    @staticmethod
    def validate_date_not_future(date_value: Any, field_name: str) -> date:
        """
        Validate that a date is not in the future.

        Args:
            date_value: The date to validate
            field_name: Name of the field for error messages

        Returns:
            date: The validated date

        Raises:
            FutureDateError: If the date is in the future
        """
        if isinstance(date_value, str):
            try:
                date_value = datetime.fromisoformat(date_value).date()
            except ValueError:
                raise ValidationError(
                    f"{field_name} must be a valid date",
                    [{"field": field_name, "message": "Must be a valid date in YYYY-MM-DD format"}]
                )

        if not isinstance(date_value, date):
            raise ValidationError(
                f"{field_name} must be a valid date",
                [{"field": field_name, "message": "Must be a valid date"}]
            )

        if date_value > date.today():
            raise FutureDateError(
                f"{field_name} cannot be in the future",
                [{"field": field_name, "message": "Cannot be in the future"}]
            )

        return date_value

    @staticmethod
    def validate_enum_value(value: Any, enum_class: type, field_name: str):
        """
        Validate that a value is a valid enum member.

        Args:
            value: The value to validate
            enum_class: The enum class to validate against
            field_name: Name of the field for error messages

        Returns:
            The validated enum value

        Raises:
            InvalidEnumValueError: If the value is not a valid enum member
        """
        if isinstance(value, str):
            try:
                return enum_class(value)
            except ValueError:
                valid_values = [e.value for e in enum_class]
                raise InvalidEnumValueError(
                    f"{field_name} must be one of: {', '.join(valid_values)}",
                    [{"field": field_name, "message": f"Must be one of: {', '.join(valid_values)}"}]
                )

        if not isinstance(value, enum_class):
            valid_values = [e.value for e in enum_class]
            raise InvalidEnumValueError(
                f"{field_name} must be one of: {', '.join(valid_values)}",
                [{"field": field_name, "message": f"Must be one of: {', '.join(valid_values)}"}]
            )

        return value


class PortfolioValidator:
    """Validator for portfolio-related operations"""

    @staticmethod
    def validate_portfolio_create(data: Dict[str, Any]) -> None:
        """
        Validate portfolio creation data.

        Args:
            data: Portfolio creation data

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        ValidationUtils.validate_required_fields(data, ["name", "portfolio_type"])

        # Validate name
        name = data.get("name", "").strip()
        if not name or len(name) > 100:
            raise ValidationError(
                "Portfolio name must be between 1 and 100 characters",
                [{"field": "name", "message": "Must be between 1 and 100 characters"}]
            )

        # Validate portfolio type
        ValidationUtils.validate_enum_value(data["portfolio_type"], PortfolioType, "portfolio_type")

    @staticmethod
    def validate_portfolio_update(data: Dict[str, Any]) -> None:
        """
        Validate portfolio update data.

        Args:
            data: Portfolio update data

        Raises:
            ValidationError: If validation fails
        """
        # Validate name if provided
        if "name" in data:
            name = data["name"].strip() if data["name"] else ""
            if not name or len(name) > 100:
                raise ValidationError(
                    "Portfolio name must be between 1 and 100 characters",
                    [{"field": "name", "message": "Must be between 1 and 100 characters"}]
                )

        # Validate portfolio type if provided
        if "portfolio_type" in data:
            ValidationUtils.validate_enum_value(data["portfolio_type"], PortfolioType, "portfolio_type")


class HoldingValidator:
    """Validator for holding-related operations"""

    @staticmethod
    def validate_holding_create(data: Dict[str, Any]) -> None:
        """
        Validate holding creation data.

        Args:
            data: Holding creation data

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        ValidationUtils.validate_required_fields(data, [
            "security_symbol", "security_type", "asset_class",
            "quantity", "cost_basis", "purchase_date"
        ])

        # Validate security symbol
        symbol = data.get("security_symbol", "").strip().upper()
        if not symbol or len(symbol) > 20:
            raise ValidationError(
                "Security symbol must be between 1 and 20 characters",
                [{"field": "security_symbol", "message": "Must be between 1 and 20 characters"}]
            )

        # Validate security name if provided
        if "security_name" in data and data["security_name"]:
            if len(data["security_name"]) > 200:
                raise ValidationError(
                    "Security name cannot exceed 200 characters",
                    [{"field": "security_name", "message": "Cannot exceed 200 characters"}]
                )

        # Validate enums
        ValidationUtils.validate_enum_value(data["security_type"], SecurityType, "security_type")
        ValidationUtils.validate_enum_value(data["asset_class"], AssetClass, "asset_class")

        # Validate positive numbers
        ValidationUtils.validate_positive_number(data["quantity"], "quantity")
        ValidationUtils.validate_positive_number(data["cost_basis"], "cost_basis")

        # Validate purchase date
        ValidationUtils.validate_date_not_future(data["purchase_date"], "purchase_date")

    @staticmethod
    def validate_holding_update(data: Dict[str, Any]) -> None:
        """
        Validate holding update data.

        Args:
            data: Holding update data

        Raises:
            ValidationError: If validation fails
        """
        # Validate security name if provided
        if "security_name" in data and data["security_name"]:
            if len(data["security_name"]) > 200:
                raise ValidationError(
                    "Security name cannot exceed 200 characters",
                    [{"field": "security_name", "message": "Cannot exceed 200 characters"}]
                )

        # Validate enums if provided
        if "security_type" in data:
            ValidationUtils.validate_enum_value(data["security_type"], SecurityType, "security_type")

        if "asset_class" in data:
            ValidationUtils.validate_enum_value(data["asset_class"], AssetClass, "asset_class")

        # Validate positive numbers if provided
        if "quantity" in data:
            ValidationUtils.validate_positive_number(data["quantity"], "quantity")

        if "cost_basis" in data:
            ValidationUtils.validate_positive_number(data["cost_basis"], "cost_basis")

    @staticmethod
    def validate_price_update(data: Dict[str, Any]) -> None:
        """
        Validate price update data.

        Args:
            data: Price update data

        Raises:
            ValidationError: If validation fails
        """
        ValidationUtils.validate_required_fields(data, ["current_price"])
        ValidationUtils.validate_positive_number(data["current_price"], "current_price")


class TransactionValidator:
    """Validator for transaction-related operations"""

    @staticmethod
    def validate_transaction_base(data: Dict[str, Any]) -> None:
        """
        Validate base transaction data common to all transaction types.

        Args:
            data: Transaction data

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        ValidationUtils.validate_required_fields(data, [
            "transaction_type", "transaction_date", "total_amount"
        ])

        # Validate transaction type
        ValidationUtils.validate_enum_value(data["transaction_type"], TransactionType, "transaction_type")

        # Validate transaction date
        ValidationUtils.validate_date_not_future(data["transaction_date"], "transaction_date")

        # Validate total amount (can be negative for some transaction types like fees)
        try:
            Decimal(str(data["total_amount"]))
        except (ValueError, TypeError):
            raise ValidationError(
                "Total amount must be a valid number",
                [{"field": "total_amount", "message": "Must be a valid number"}]
            )

        # Validate fees if provided
        if "fees" in data and data["fees"] is not None:
            ValidationUtils.validate_non_negative_number(data["fees"], "fees")

        # Validate notes if provided
        if "notes" in data and data["notes"]:
            if len(data["notes"]) > 500:
                raise ValidationError(
                    "Notes cannot exceed 500 characters",
                    [{"field": "notes", "message": "Cannot exceed 500 characters"}]
                )

    @staticmethod
    def validate_buy_transaction(data: Dict[str, Any]) -> None:
        """
        Validate buy transaction data.

        Args:
            data: Buy transaction data

        Raises:
            ValidationError: If validation fails
        """
        TransactionValidator.validate_transaction_base(data)

        # Validate transaction type is BUY
        if data["transaction_type"] != TransactionType.BUY:
            raise ValidationError(
                "Transaction type must be BUY",
                [{"field": "transaction_type", "message": "Must be BUY"}]
            )

        # Validate required fields for buy transactions
        ValidationUtils.validate_required_fields(data, ["holding_id", "quantity", "price_per_share"])

        # Validate positive numbers
        ValidationUtils.validate_positive_number(data["quantity"], "quantity")
        ValidationUtils.validate_positive_number(data["price_per_share"], "price_per_share")
        ValidationUtils.validate_positive_number(data["total_amount"], "total_amount")

    @staticmethod
    def validate_sell_transaction(data: Dict[str, Any]) -> None:
        """
        Validate sell transaction data.

        Args:
            data: Sell transaction data

        Raises:
            ValidationError: If validation fails
        """
        TransactionValidator.validate_transaction_base(data)

        # Validate transaction type is SELL
        if data["transaction_type"] != TransactionType.SELL:
            raise ValidationError(
                "Transaction type must be SELL",
                [{"field": "transaction_type", "message": "Must be SELL"}]
            )

        # Validate required fields for sell transactions
        ValidationUtils.validate_required_fields(data, ["holding_id", "quantity", "price_per_share"])

        # Validate positive numbers
        ValidationUtils.validate_positive_number(data["quantity"], "quantity")
        ValidationUtils.validate_positive_number(data["price_per_share"], "price_per_share")
        ValidationUtils.validate_positive_number(data["total_amount"], "total_amount")

    @staticmethod
    def validate_dividend_transaction(data: Dict[str, Any]) -> None:
        """
        Validate dividend transaction data.

        Args:
            data: Dividend transaction data

        Raises:
            ValidationError: If validation fails
        """
        TransactionValidator.validate_transaction_base(data)

        # Validate transaction type is DIVIDEND
        if data["transaction_type"] != TransactionType.DIVIDEND:
            raise ValidationError(
                "Transaction type must be DIVIDEND",
                [{"field": "transaction_type", "message": "Must be DIVIDEND"}]
            )

        # Validate required fields for dividend transactions
        ValidationUtils.validate_required_fields(data, ["holding_id"])

        # Validate positive amount for dividends
        ValidationUtils.validate_positive_number(data["total_amount"], "total_amount")

        # Validate dividend type if provided
        if "dividend_type" in data:
            ValidationUtils.validate_enum_value(data["dividend_type"], DividendType, "dividend_type")

        # Validate dates if provided
        if "payment_date" in data and data["payment_date"]:
            ValidationUtils.validate_date_not_future(data["payment_date"], "payment_date")

        if "ex_dividend_date" in data and data["ex_dividend_date"]:
            ValidationUtils.validate_date_not_future(data["ex_dividend_date"], "ex_dividend_date")

    @staticmethod
    def validate_other_transaction(data: Dict[str, Any]) -> None:
        """
        Validate other transaction types (INTEREST, FEE, TRANSFER, CONTRIBUTION).

        Args:
            data: Transaction data

        Raises:
            ValidationError: If validation fails
        """
        TransactionValidator.validate_transaction_base(data)

        # Validate transaction type is one of the allowed other types
        allowed_types = {TransactionType.INTEREST, TransactionType.FEE, TransactionType.TRANSFER, TransactionType.CONTRIBUTION}
        if data["transaction_type"] not in allowed_types:
            valid_values = [t.value for t in allowed_types]
            raise ValidationError(
                f"Transaction type must be one of: {', '.join(valid_values)}",
                [{"field": "transaction_type", "message": f"Must be one of: {', '.join(valid_values)}"}]
            )


class DuplicateTransactionDetector:
    """Detector for duplicate transactions"""

    def __init__(self, db: Session):
        self.db = db
        self.transaction_repo = TransactionRepository(db)

    def check_for_duplicate(self, portfolio_id: int, tenant_id: int, transaction_data: Dict[str, Any]) -> None:
        """
        Check for duplicate transactions within a 60-second window.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for security
            transaction_data: Transaction data to check

        Raises:
            DuplicateTransactionError: If a duplicate is found
        """
        # Define the time window for duplicate detection (60 seconds)
        time_window = timedelta(seconds=60)
        cutoff_time = datetime.utcnow() - time_window

        # Get recent transactions for the portfolio
        recent_transactions = self.transaction_repo.get_recent_transactions(
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            since=cutoff_time
        )

        # Check for duplicates based on key fields
        for transaction in recent_transactions:
            if self._is_duplicate(transaction, transaction_data):
                logger.warning(f"Duplicate transaction detected for portfolio {portfolio_id}")
                raise DuplicateTransactionError()

    def _is_duplicate(self, existing_transaction, new_transaction_data: Dict[str, Any]) -> bool:
        """
        Check if two transactions are duplicates based on key fields.

        Args:
            existing_transaction: Existing transaction from database
            new_transaction_data: New transaction data

        Returns:
            bool: True if transactions are duplicates
        """
        # Compare key fields that would indicate a duplicate
        key_fields = [
            "transaction_type",
            "transaction_date",
            "total_amount",
            "holding_id"
        ]

        for field in key_fields:
            existing_value = getattr(existing_transaction, field, None)
            new_value = new_transaction_data.get(field)

            # Convert values for comparison
            if field == "transaction_date":
                if isinstance(new_value, str):
                    new_value = datetime.fromisoformat(new_value).date()
                existing_value = existing_transaction.transaction_date
            elif field == "total_amount":
                existing_value = existing_transaction.total_amount
                new_value = Decimal(str(new_value))
            elif field == "transaction_type":
                existing_value = existing_transaction.transaction_type
                if isinstance(new_value, str):
                    new_value = TransactionType(new_value)

            # If any key field differs, it's not a duplicate
            if existing_value != new_value:
                return False

        # Also check quantity and price_per_share for buy/sell transactions
        if new_transaction_data.get("transaction_type") in [TransactionType.BUY, TransactionType.SELL]:
            if (existing_transaction.quantity != Decimal(str(new_transaction_data.get("quantity", 0))) or
                existing_transaction.price_per_share != Decimal(str(new_transaction_data.get("price_per_share", 0)))):
                return False

        return True