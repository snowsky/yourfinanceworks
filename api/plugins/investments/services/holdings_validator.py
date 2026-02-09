"""
Holdings Validator Service

This module implements validation and duplicate handling for investment holdings.
It provides methods for validating extracted holdings data and detecting/handling
duplicate holdings in portfolios.

The validator ensures data integrity before holdings are created and provides
configurable duplicate handling strategies (merge vs create-separate).

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 12.1, 12.2, 12.3, 12.4, 12.5
"""

import logging
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
from datetime import date

from ..models import SecurityType, AssetClass, InvestmentHolding
from ..repositories.holdings_repository import HoldingsRepository
from core.exceptions.base import ValidationError

logger = logging.getLogger(__name__)


class DuplicateHandlingMode:
    """Configuration for duplicate holding handling"""
    MERGE = "merge"  # Combine quantities and recalculate average cost basis
    CREATE_SEPARATE = "create_separate"  # Create new holding with same symbol


class HoldingsValidator:
    """
    Validator service for investment holdings.

    Provides validation of extracted holdings data and duplicate detection/handling.
    Ensures data integrity before holdings are created in portfolios.

    Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 12.1, 12.2, 12.3, 12.4, 12.5
    """

    def __init__(self, holdings_repo: HoldingsRepository, duplicate_mode: str = DuplicateHandlingMode.MERGE):
        """
        Initialize the holdings validator.

        Args:
            holdings_repo: HoldingsRepository instance for duplicate detection
            duplicate_mode: How to handle duplicates (merge or create_separate)
        """
        self.holdings_repo = holdings_repo
        self.duplicate_mode = duplicate_mode

    def validate_holding(self, holding_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate extracted holding data.

        Checks that all required fields are present and have valid values.
        Validates that quantities and costs are positive numbers.

        Args:
            holding_data: Extracted holding dictionary

        Returns:
            Tuple of (is_valid, error_message)

        Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
        """
        logger.debug(f"Validating holding: {holding_data.get('security_symbol')}")

        # Check required fields
        required_fields = ["security_symbol", "quantity", "cost_basis", "security_type", "asset_class"]
        missing_fields = [f for f in required_fields if f not in holding_data or holding_data[f] is None]

        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg

        # Validate security symbol
        symbol = holding_data.get("security_symbol", "").strip()
        if not symbol:
            error_msg = "Security symbol cannot be empty"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg

        if len(symbol) > 20:
            error_msg = f"Security symbol must be 20 characters or less (got {len(symbol)})"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg

        # Validate quantity is positive
        try:
            quantity = Decimal(str(holding_data.get("quantity")))
            if quantity <= 0:
                error_msg = f"Quantity must be positive (got {quantity})"
                logger.warning(f"Validation failed: {error_msg}")
                return False, error_msg
        except (ValueError, TypeError, Exception) as e:
            error_msg = f"Quantity must be a valid number (got {holding_data.get('quantity')})"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg

        # Validate cost basis is positive
        try:
            cost_basis = Decimal(str(holding_data.get("cost_basis")))
            if cost_basis <= 0:
                error_msg = f"Cost basis must be positive (got {cost_basis})"
                logger.warning(f"Validation failed: {error_msg}")
                return False, error_msg
        except (ValueError, TypeError, Exception) as e:
            error_msg = f"Cost basis must be a valid number (got {holding_data.get('cost_basis')})"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg

        # Validate security type
        security_type_str = str(holding_data.get("security_type", "")).lower()
        try:
            SecurityType(security_type_str)
        except (ValueError, KeyError):
            error_msg = f"Invalid security type: {holding_data.get('security_type')}"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg

        # Validate asset class
        asset_class_str = str(holding_data.get("asset_class", "")).lower()
        try:
            AssetClass(asset_class_str)
        except (ValueError, KeyError):
            error_msg = f"Invalid asset class: {holding_data.get('asset_class')}"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg

        # Validate purchase date if provided
        if "purchase_date" in holding_data and holding_data["purchase_date"] is not None:
            try:
                purchase_date = holding_data["purchase_date"]
                if isinstance(purchase_date, str):
                    purchase_date = date.fromisoformat(purchase_date)

                if purchase_date > date.today():
                    error_msg = f"Purchase date cannot be in the future (got {purchase_date})"
                    logger.warning(f"Validation failed: {error_msg}")
                    return False, error_msg
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid purchase date format: {holding_data.get('purchase_date')}"
                logger.warning(f"Validation failed: {error_msg}")
                return False, error_msg

        logger.debug(f"Holding validation passed: {holding_data.get('security_symbol')}")
        return True, None

    def detect_duplicate(
        self,
        portfolio_id: int,
        security_symbol: str
    ) -> Optional[InvestmentHolding]:
        """
        Detect if a holding with the same security symbol already exists.

        Checks for existing active holdings with the same symbol in the portfolio.
        Returns the existing holding if found, None otherwise.

        Args:
            portfolio_id: Portfolio ID
            security_symbol: Security symbol to check

        Returns:
            Existing InvestmentHolding if found, None otherwise

        Requirements: 12.1, 12.2
        """
        logger.debug(f"Detecting duplicate for {security_symbol} in portfolio {portfolio_id}")

        # Query for existing holdings with same symbol (returns list)
        existing_holdings = self.holdings_repo.get_by_symbol(portfolio_id, security_symbol)

        # Return the first active holding if any exist
        if existing_holdings:
            for holding in existing_holdings:
                if not holding.is_closed:
                    logger.info(f"Duplicate detected: {security_symbol} already exists in portfolio")
                    return holding

        logger.debug(f"No duplicate found for {security_symbol}")
        return None

    def merge_holdings(
        self,
        existing_holding: InvestmentHolding,
        new_quantity: Decimal,
        new_cost_basis: Decimal
    ) -> Dict[str, Any]:
        """
        Merge a new holding with an existing holding.

        Combines quantities and recalculates average cost basis.
        Returns the merged holding data.

        Args:
            existing_holding: Existing InvestmentHolding
            new_quantity: Quantity from new holding
            new_cost_basis: Cost basis from new holding

        Returns:
            Dictionary with merged holding data (quantity, cost_basis)

        Requirements: 12.3
        """
        logger.info(f"Merging holdings for {existing_holding.security_symbol}")

        # Calculate merged quantity
        merged_quantity = Decimal(str(existing_holding.quantity)) + new_quantity

        # Calculate merged cost basis
        merged_cost_basis = Decimal(str(existing_holding.cost_basis)) + new_cost_basis

        # Calculate new average cost per share
        if merged_quantity > 0:
            new_average_cost = merged_cost_basis / merged_quantity
        else:
            new_average_cost = Decimal('0')

        logger.info(
            f"Merged {existing_holding.security_symbol}: "
            f"quantity {existing_holding.quantity} + {new_quantity} = {merged_quantity}, "
            f"cost_basis {existing_holding.cost_basis} + {new_cost_basis} = {merged_cost_basis}, "
            f"avg_cost {new_average_cost}"
        )

        return {
            "quantity": merged_quantity,
            "cost_basis": merged_cost_basis,
            "average_cost_per_share": new_average_cost
        }

    def create_separate_holding(
        self,
        existing_holding: InvestmentHolding,
        new_quantity: Decimal,
        new_cost_basis: Decimal
    ) -> Dict[str, Any]:
        """
        Create a separate holding with the same symbol.

        Returns the new holding data without modifying the existing holding.
        This allows multiple holdings of the same security in a portfolio.

        Args:
            existing_holding: Existing InvestmentHolding (for reference)
            new_quantity: Quantity for new holding
            new_cost_basis: Cost basis for new holding

        Returns:
            Dictionary with new holding data (quantity, cost_basis)

        Requirements: 12.4
        """
        logger.info(
            f"Creating separate holding for {existing_holding.security_symbol}: "
            f"quantity {new_quantity}, cost_basis {new_cost_basis}"
        )

        # Calculate average cost per share for new holding
        if new_quantity > 0:
            average_cost = new_cost_basis / new_quantity
        else:
            average_cost = Decimal('0')

        return {
            "quantity": new_quantity,
            "cost_basis": new_cost_basis,
            "average_cost_per_share": average_cost
        }

    def handle_duplicate(
        self,
        portfolio_id: int,
        security_symbol: str,
        new_quantity: Decimal,
        new_cost_basis: Decimal
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Handle duplicate holding detection and resolution.

        Detects duplicates and applies the configured handling strategy
        (merge or create-separate). Returns the action to take.

        Args:
            portfolio_id: Portfolio ID
            security_symbol: Security symbol
            new_quantity: Quantity from new holding
            new_cost_basis: Cost basis from new holding

        Returns:
            Tuple of (is_duplicate, action_data)
            - is_duplicate: True if duplicate was found and handled
            - action_data: Dictionary with handling result
              - For merge: {quantity, cost_basis, average_cost_per_share}
              - For create_separate: {quantity, cost_basis, average_cost_per_share}
              - For no duplicate: {}

        Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
        """
        logger.debug(f"Handling duplicate for {security_symbol} in portfolio {portfolio_id}")

        # Detect duplicate
        existing_holding = self.detect_duplicate(portfolio_id, security_symbol)

        if not existing_holding:
            logger.debug(f"No duplicate found for {security_symbol}")
            return False, {}

        # Apply handling strategy
        if self.duplicate_mode == DuplicateHandlingMode.MERGE:
            logger.info(f"Applying MERGE strategy for {security_symbol}")
            action_data = self.merge_holdings(existing_holding, new_quantity, new_cost_basis)
        elif self.duplicate_mode == DuplicateHandlingMode.CREATE_SEPARATE:
            logger.info(f"Applying CREATE_SEPARATE strategy for {security_symbol}")
            action_data = self.create_separate_holding(existing_holding, new_quantity, new_cost_basis)
        else:
            logger.warning(f"Unknown duplicate handling mode: {self.duplicate_mode}")
            # Default to create separate
            action_data = self.create_separate_holding(existing_holding, new_quantity, new_cost_basis)

        return True, action_data

    def set_duplicate_mode(self, mode: str) -> None:
        """
        Set the duplicate handling mode.

        Args:
            mode: DuplicateHandlingMode.MERGE or DuplicateHandlingMode.CREATE_SEPARATE

        Raises:
            ValueError: If mode is invalid

        Requirements: 12.5
        """
        if mode not in [DuplicateHandlingMode.MERGE, DuplicateHandlingMode.CREATE_SEPARATE]:
            raise ValueError(f"Invalid duplicate handling mode: {mode}")

        self.duplicate_mode = mode
        logger.info(f"Duplicate handling mode set to: {mode}")
