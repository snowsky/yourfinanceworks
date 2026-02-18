"""
Performance Calculator

This module implements performance calculation algorithms for investment portfolios.
It provides methods to calculate total return, unrealized gains, and realized gains
using inception-to-date calculations for the MVP.

The calculator follows the design specification for performance metrics and
integrates with the existing holding and transaction data structures.
"""

from typing import List, Optional
from decimal import Decimal
from datetime import date

from ..models import InvestmentHolding, InvestmentTransaction, TransactionType


class PerformanceCalculator:
    """
    Calculator for investment performance metrics.

    This class provides methods to calculate various performance metrics
    for investment portfolios, including total return, unrealized gains,
    and realized gains using inception-to-date calculations.
    """

    def calculate_total_return(
        self,
        holdings: List[InvestmentHolding],
        transactions: List[InvestmentTransaction]
    ) -> Decimal:
        """
        Calculate total return percentage for a portfolio (inception-to-date only).

        Formula: ((Current Value + Total Sell Proceeds + Dividends - Total Buy Cost) / Total Buy Cost) * 100

        When no BUY transactions exist (e.g., PDF-imported holdings), falls back to
        using the sum of holdings.cost_basis as the cost denominator.

        Args:
            holdings: List of portfolio holdings
            transactions: List of portfolio transactions

        Returns:
            Total return percentage (can be negative for losses)

        Note:
            Returns 0 if no cost basis can be determined
        """
        # Calculate current value of all holdings
        current_value = Decimal('0')
        for holding in holdings:
            if not holding.is_closed and holding.quantity > 0:
                # Use current price if available, otherwise fall back to cost basis per share
                if holding.current_price and holding.current_price > 0:
                    holding_value = Decimal(str(holding.quantity)) * Decimal(str(holding.current_price))
                else:
                    # Fallback to cost basis per share
                    cost_per_share = Decimal(str(holding.cost_basis)) / Decimal(str(holding.quantity))
                    holding_value = Decimal(str(holding.quantity)) * cost_per_share
                current_value += holding_value

        # Calculate total buy cost (sum of all BUY transactions)
        total_buy_cost = Decimal('0')
        for transaction in transactions:
            if transaction.transaction_type == TransactionType.BUY:
                total_buy_cost += Decimal(str(transaction.total_amount))
                # Include fees in the cost basis
                if transaction.fees:
                    total_buy_cost += Decimal(str(transaction.fees))

        # Fallback: when no BUY transactions exist (e.g. PDF-imported holdings),
        # use the sum of holdings cost_basis as the denominator
        if total_buy_cost == 0:
            for holding in holdings:
                if not holding.is_closed and holding.cost_basis:
                    total_buy_cost += Decimal(str(holding.cost_basis))

        if total_buy_cost == 0:
            return Decimal('0')  # No cost basis to calculate return against

        # Calculate total sell proceeds (sum of all SELL transactions)
        total_sell_proceeds = Decimal('0')
        for transaction in transactions:
            if transaction.transaction_type == TransactionType.SELL:
                # Use net proceeds (total amount minus fees)
                sell_proceeds = Decimal(str(transaction.total_amount))
                if transaction.fees:
                    sell_proceeds -= Decimal(str(transaction.fees))
                total_sell_proceeds += sell_proceeds

        # Calculate total dividends
        total_dividends = Decimal('0')
        for transaction in transactions:
            if transaction.transaction_type == TransactionType.DIVIDEND:
                total_dividends += Decimal(str(transaction.total_amount))

        total_gain = current_value + total_sell_proceeds + total_dividends - total_buy_cost
        total_return_percentage = (total_gain / total_buy_cost) * Decimal('100')

        return total_return_percentage

    def calculate_unrealized_gains(self, holdings: List[InvestmentHolding]) -> Decimal:
        """
        Calculate total unrealized gains for a portfolio.

        Unrealized gain = (Current Value - Cost Basis) for all open holdings

        Args:
            holdings: List of portfolio holdings

        Returns:
            Total unrealized gains (can be negative for losses)
        """
        total_unrealized_gains = Decimal('0')

        for holding in holdings:
            if not holding.is_closed and holding.quantity > 0:
                # Calculate current value
                if holding.current_price and holding.current_price > 0:
                    current_value = Decimal(str(holding.quantity)) * Decimal(str(holding.current_price))
                else:
                    # If no current price, unrealized gain is zero (using cost basis as current value)
                    current_value = Decimal(str(holding.cost_basis))

                # Calculate unrealized gain for this holding
                cost_basis = Decimal(str(holding.cost_basis))
                unrealized_gain = current_value - cost_basis
                total_unrealized_gains += unrealized_gain

        return total_unrealized_gains

    def calculate_realized_gains(self, transactions: List[InvestmentTransaction]) -> Decimal:
        """
        Calculate total realized gains from all sell transactions.

        Args:
            transactions: List of portfolio transactions

        Returns:
            Total realized gains (can be negative for losses)
        """
        total_realized_gains = Decimal('0')

        for transaction in transactions:
            if transaction.transaction_type == TransactionType.SELL and transaction.realized_gain is not None:
                total_realized_gains += Decimal(str(transaction.realized_gain))

        return total_realized_gains

    def calculate_total_value(self, holdings: List[InvestmentHolding]) -> Decimal:
        """
        Calculate total current value of all holdings in a portfolio.

        Args:
            holdings: List of portfolio holdings

        Returns:
            Total portfolio value
        """
        total_value = Decimal('0')

        for holding in holdings:
            if not holding.is_closed and holding.quantity > 0:
                # Use current price if available, otherwise fall back to cost basis per share
                if holding.current_price and holding.current_price > 0:
                    holding_value = Decimal(str(holding.quantity)) * Decimal(str(holding.current_price))
                else:
                    # Fallback to cost basis per share
                    cost_per_share = Decimal(str(holding.cost_basis)) / Decimal(str(holding.quantity))
                    holding_value = Decimal(str(holding.quantity)) * cost_per_share
                total_value += holding_value

        return total_value

    def calculate_total_cost(
        self,
        transactions: List[InvestmentTransaction],
        holdings: Optional[List[InvestmentHolding]] = None
    ) -> Decimal:
        """
        Calculate total cost basis from all buy transactions.

        When no BUY transactions exist (e.g., PDF-imported holdings without transaction
        records), falls back to summing cost_basis from the provided holdings list.

        Args:
            transactions: List of portfolio transactions
            holdings: Optional list of holdings used as fallback when no BUY transactions exist

        Returns:
            Total cost basis
        """
        total_cost = Decimal('0')

        for transaction in transactions:
            if transaction.transaction_type == TransactionType.BUY:
                total_cost += Decimal(str(transaction.total_amount))
                # Include fees in the cost basis
                if transaction.fees:
                    total_cost += Decimal(str(transaction.fees))

        # Fallback: when no BUY transactions exist (e.g. PDF-imported holdings),
        # use the sum of holdings cost_basis
        if total_cost == 0 and holdings:
            for holding in holdings:
                if not holding.is_closed and holding.cost_basis:
                    total_cost += Decimal(str(holding.cost_basis))

        return total_cost

    def calculate_dividend_income(
        self,
        transactions: List[InvestmentTransaction],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Decimal:
        """
        Calculate total dividend income for a specified period.

        Args:
            transactions: List of portfolio transactions
            start_date: Start date for dividend calculation (inclusive)
            end_date: End date for dividend calculation (inclusive)

        Returns:
            Total dividend income for the period
        """
        total_dividends = Decimal('0')

        for transaction in transactions:
            if transaction.transaction_type == TransactionType.DIVIDEND:
                # Check date range if specified
                if start_date and transaction.transaction_date < start_date:
                    continue
                if end_date and transaction.transaction_date > end_date:
                    continue

                total_dividends += Decimal(str(transaction.total_amount))

        return total_dividends