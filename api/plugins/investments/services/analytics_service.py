"""
Analytics Service

This module implements the analytics service layer for investment portfolios.
It orchestrates the various calculators to provide comprehensive analytics
including performance metrics, asset allocation, dividend income, and tax data export.

The service provides high-level operations with proper validation, tenant isolation,
and integration with the existing repository layer.
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session

from ..repositories.portfolio_repository import PortfolioRepository
from ..repositories.holdings_repository import HoldingsRepository
from ..repositories.transaction_repository import TransactionRepository
from ..calculators.performance_calculator import PerformanceCalculator
from ..calculators.asset_allocation_analyzer import AssetAllocationAnalyzer
from ..calculators.tax_data_exporter import TaxDataExporter
from ..calculators.portfolio_data_exporter import PortfolioDataExporter
from ..schemas import (
    PerformanceMetrics, AssetAllocation, DividendSummary, TaxExport,
    TransactionResponse
)
from ..models import PortfolioType
from core.exceptions.base import NotFoundError, ValidationError


class AnalyticsService:
    """
    Service for investment analytics operations.

    This service orchestrates various calculators to provide comprehensive
    analytics for investment portfolios with proper validation and tenant isolation.
    """

    def __init__(self, db: Session):
        """
        Initialize the analytics service.

        Args:
            db: Database session
        """
        self.db = db
        self.portfolio_repo = PortfolioRepository(db)
        self.holdings_repo = HoldingsRepository(db)
        self.transaction_repo = TransactionRepository(db)

        # Initialize calculators
        self.performance_calculator = PerformanceCalculator()
        self.allocation_analyzer = AssetAllocationAnalyzer()
        self.tax_exporter = TaxDataExporter()
        self.portfolio_exporter = PortfolioDataExporter()

    def calculate_portfolio_performance(
        self,
        tenant_id: int,
        portfolio_id: int
    ) -> PerformanceMetrics:
        """
        Calculate portfolio performance metrics (inception-to-date only).

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            Performance metrics including total return, gains, and values

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get holdings and transactions
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)
        transactions = self.transaction_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Calculate metrics using performance calculator
        total_return_percentage = self.performance_calculator.calculate_total_return(holdings, transactions)
        unrealized_gain_loss = self.performance_calculator.calculate_unrealized_gains(holdings)
        realized_gain_loss = self.performance_calculator.calculate_realized_gains(transactions)
        total_value = self.performance_calculator.calculate_total_value(holdings)
        total_cost = self.performance_calculator.calculate_total_cost(transactions)

        # Calculate total gain/loss
        total_gain_loss = unrealized_gain_loss + realized_gain_loss

        return PerformanceMetrics(
            total_value=total_value,
            total_cost=total_cost,
            total_gain_loss=total_gain_loss,
            total_return_percentage=total_return_percentage,
            unrealized_gain_loss=unrealized_gain_loss,
            realized_gain_loss=realized_gain_loss
        )

    def calculate_asset_allocation(
        self,
        tenant_id: int,
        portfolio_id: int
    ) -> AssetAllocation:
        """
        Calculate asset allocation for a portfolio.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            Asset allocation with percentages by asset class

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get holdings
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Calculate allocation using analyzer
        return self.allocation_analyzer.calculate_asset_allocation(holdings)

    def calculate_dividend_income(
        self,
        tenant_id: int,
        portfolio_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> DividendSummary:
        """
        Calculate dividend income for a portfolio over a specified period.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            start_date: Start date for dividend calculation (inclusive)
            end_date: End date for dividend calculation (inclusive)

        Returns:
            Dividend summary with total income and transaction details

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
            ValidationError: If date range is invalid
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date must be before or equal to end date")

        # Get dividend transactions
        from ..models import TransactionType
        dividend_transactions = self.transaction_repo.get_by_portfolio(
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            transaction_types=[TransactionType.DIVIDEND]
        )

        # Calculate total dividend income
        total_dividends = self.performance_calculator.calculate_dividend_income(
            dividend_transactions, start_date, end_date
        )

        # Convert to response format
        transaction_responses = [
            TransactionResponse.model_validate(tx) for tx in dividend_transactions
        ]

        # Set default dates if not provided
        if not start_date:
            start_date = min(tx.transaction_date for tx in dividend_transactions) if dividend_transactions else date.today()
        if not end_date:
            end_date = max(tx.transaction_date for tx in dividend_transactions) if dividend_transactions else date.today()

        return DividendSummary(
            total_dividends=total_dividends,
            dividend_transactions=transaction_responses,
            period_start=start_date,
            period_end=end_date
        )

    def calculate_dividend_yield_by_holding(
        self,
        tenant_id: int,
        portfolio_id: int,
        period_months: int = 12
    ) -> Dict[str, Decimal]:
        """
        Calculate dividend yield for each holding in a portfolio.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            period_months: Number of months to look back for dividend calculation (default 12)

        Returns:
            Dictionary mapping security symbols to their dividend yields (as percentages)

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get all holdings
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Calculate date range for dividend lookup
        end_date = date.today()
        start_date = date(end_date.year - (period_months // 12),
                         end_date.month - (period_months % 12),
                         end_date.day)
        if start_date.month <= 0:
            start_date = date(start_date.year - 1, start_date.month + 12, start_date.day)

        dividend_yields = {}

        for holding in holdings:
            if holding.is_closed or holding.quantity <= 0:
                continue

            # Get dividend transactions for this holding
            from ..models import TransactionType
            holding_dividends = self.transaction_repo.get_by_portfolio(
                portfolio_id=portfolio_id,
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
                transaction_types=[TransactionType.DIVIDEND]
            )

            # Filter dividends for this specific holding
            holding_dividend_total = Decimal('0')
            for dividend in holding_dividends:
                if dividend.holding_id == holding.id:
                    holding_dividend_total += Decimal(str(dividend.total_amount))

            # Calculate yield if we have dividends and current value
            if holding_dividend_total > 0 and holding.current_value > 0:
                # Annualize the dividend if period is not 12 months
                annualized_dividends = holding_dividend_total * (Decimal('12') / Decimal(str(period_months)))
                dividend_yield = (annualized_dividends / holding.current_value) * Decimal('100')
                dividend_yields[holding.security_symbol] = dividend_yield
            else:
                dividend_yields[holding.security_symbol] = Decimal('0')

        return dividend_yields

    def get_dividend_frequency_analysis(
        self,
        tenant_id: int,
        portfolio_id: int,
        lookback_months: int = 24
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze dividend payment frequency for each holding.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            lookback_months: Number of months to analyze (default 24)

        Returns:
            Dictionary with dividend frequency analysis for each security

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Calculate date range
        end_date = date.today()
        start_date = date(end_date.year - (lookback_months // 12),
                         end_date.month - (lookback_months % 12),
                         end_date.day)
        if start_date.month <= 0:
            start_date = date(start_date.year - 1, start_date.month + 12, start_date.day)

        # Get all dividend transactions in the period
        from ..models import TransactionType
        dividend_transactions = self.transaction_repo.get_by_portfolio(
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            transaction_types=[TransactionType.DIVIDEND]
        )

        # Group by holding and analyze frequency
        frequency_analysis = {}
        holdings_dividends = {}

        # Group dividends by holding
        for dividend in dividend_transactions:
            if dividend.holding_id not in holdings_dividends:
                holdings_dividends[dividend.holding_id] = []
            holdings_dividends[dividend.holding_id].append(dividend)

        # Analyze frequency for each holding
        for holding_id, dividends in holdings_dividends.items():
            if not dividends:
                continue

            # Get holding info
            holding = self.holdings_repo.get_by_id(holding_id, tenant_id)
            if not holding:
                continue

            # Sort dividends by date
            dividends.sort(key=lambda x: x.transaction_date)

            # Calculate intervals between dividends
            intervals = []
            for i in range(1, len(dividends)):
                interval = (dividends[i].transaction_date - dividends[i-1].transaction_date).days
                intervals.append(interval)

            # Determine likely frequency
            avg_interval = sum(intervals) / len(intervals) if intervals else 0

            if avg_interval == 0:
                frequency = "Unknown"
                estimated_annual_payments = 0
            elif avg_interval <= 35:  # ~Monthly
                frequency = "Monthly"
                estimated_annual_payments = 12
            elif avg_interval <= 95:  # ~Quarterly
                frequency = "Quarterly"
                estimated_annual_payments = 4
            elif avg_interval <= 190:  # ~Semi-annual
                frequency = "Semi-Annual"
                estimated_annual_payments = 2
            elif avg_interval <= 380:  # ~Annual
                frequency = "Annual"
                estimated_annual_payments = 1
            else:
                frequency = "Irregular"
                estimated_annual_payments = len(dividends) / (lookback_months / 12)

            # Calculate average dividend amount
            avg_dividend = sum(Decimal(str(d.total_amount)) for d in dividends) / len(dividends)

            frequency_analysis[holding.security_symbol] = {
                "frequency": frequency,
                "payment_count": len(dividends),
                "average_amount": avg_dividend,
                "estimated_annual_payments": estimated_annual_payments,
                "last_payment_date": dividends[-1].transaction_date.isoformat(),
                "average_interval_days": int(avg_interval) if avg_interval > 0 else None
            }

        return frequency_analysis

    def forecast_dividend_income(
        self,
        tenant_id: int,
        portfolio_id: int,
        forecast_months: int = 12
    ) -> Dict[str, Any]:
        """
        Forecast future dividend income based on historical patterns.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            forecast_months: Number of months to forecast (default 12)

        Returns:
            Dictionary with dividend income forecast

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get frequency analysis for the past 24 months
        frequency_analysis = self.get_dividend_frequency_analysis(tenant_id, portfolio_id, 24)

        # Calculate forecast for each holding
        total_forecast = Decimal('0')
        holding_forecasts = {}

        for symbol, analysis in frequency_analysis.items():
            if analysis["estimated_annual_payments"] > 0:
                # Calculate expected payments in forecast period
                expected_payments = (analysis["estimated_annual_payments"] * forecast_months) / 12
                expected_income = analysis["average_amount"] * Decimal(str(expected_payments))

                holding_forecasts[symbol] = {
                    "expected_payments": round(expected_payments, 1),
                    "expected_income": expected_income,
                    "frequency": analysis["frequency"],
                    "average_amount": analysis["average_amount"]
                }

                total_forecast += expected_income

        return {
            "forecast_period_months": forecast_months,
            "total_forecast": total_forecast,
            "holding_forecasts": holding_forecasts,
            "forecast_generated_date": date.today().isoformat()
        }

    def export_tax_data(
        self,
        tenant_id: int,
        portfolio_id: int,
        tax_year: int,
        format: str = "json"
    ) -> str:
        """
        Export tax data for a portfolio and tax year.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            tax_year: Tax year to export
            format: Export format ("csv" or "json")

        Returns:
            Exported tax data as string

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
            ValidationError: If tax year or format is invalid
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Validate tax year
        current_year = date.today().year
        if tax_year < 1900 or tax_year > current_year:
            raise ValidationError(f"Invalid tax year: {tax_year}")

        # Validate format
        if format.lower() not in ["csv", "json"]:
            raise ValidationError(f"Unsupported export format: {format}")

        # Get all transactions for the portfolio
        transactions = self.transaction_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Export tax data
        return self.tax_exporter.export_transaction_data(transactions, tax_year, format)

    def get_tax_summary(
        self,
        tenant_id: int,
        portfolio_id: int,
        tax_year: int
    ) -> TaxExport:
        """
        Get comprehensive tax summary for a portfolio and tax year.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            tax_year: Tax year to summarize

        Returns:
            Tax export object with realized gains, dividends, and transactions

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
            ValidationError: If tax year is invalid
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Validate tax year
        current_year = date.today().year
        if tax_year < 1900 or tax_year > current_year:
            raise ValidationError(f"Invalid tax year: {tax_year}")

        # Get all transactions for the portfolio
        transactions = self.transaction_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Get tax export data
        return self.tax_exporter.get_tax_export_data(transactions, tax_year)

    def get_portfolio_summary(
        self,
        tenant_id: int,
        portfolio_id: int
    ) -> dict:
        """
        Get a comprehensive summary of portfolio analytics.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            Dictionary with performance, allocation, and summary data

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get performance metrics
        performance = self.calculate_portfolio_performance(tenant_id, portfolio_id)

        # Get asset allocation
        allocation = self.calculate_asset_allocation(tenant_id, portfolio_id)

        # Get holdings count and summary
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)
        tx_summary = self.transaction_repo.get_portfolio_transaction_summary(portfolio_id, tenant_id)
        active_holdings_count = len([h for h in holdings if not h.is_closed and h.quantity > 0])

        # Get recent dividend income (last 12 months)
        end_date = date.today()
        start_date = date(end_date.year - 1, end_date.month, end_date.day)
        if start_date.month <= 0:
            start_date = date(start_date.year - 1, start_date.month + 12, start_date.day)
        dividend_summary = self.calculate_dividend_income(tenant_id, portfolio_id, start_date, end_date)

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio.name,
            "portfolio_type": portfolio.portfolio_type.value,
            "performance": {
                "total_value": float(performance.total_value),
                "total_cost": float(performance.total_cost),
                "total_gain_loss": float(performance.total_gain_loss),
                "total_return_percentage": float(performance.total_return_percentage),
                "unrealized_gain_loss": float(performance.unrealized_gain_loss),
                "realized_gain_loss": float(performance.realized_gain_loss)
            },
            "allocation": {
                "total_value": float(allocation.total_value),
                "asset_classes": {
                    asset_class.value: {
                        "value": float(detail.value),
                        "percentage": float(detail.percentage),
                        "holdings_count": detail.holdings_count
                    }
                    for asset_class, detail in allocation.allocations.items()
                }
            },
            "holdings": {
                "active_count": active_holdings_count,
                "total_count": len(holdings)
            },
            "dividends_last_12_months": {
                "total_income": float(dividend_summary.total_dividends),
                "transaction_count": len(dividend_summary.dividend_transactions)
            }
        }

    def get_aggregated_analytics_by_type(
        self,
        tenant_id: int,
        portfolio_type: Optional[PortfolioType] = None
    ) -> dict:
        """
        Get aggregated analytics across multiple portfolios, optionally filtered by type.

        This method provides consolidated analytics for business reporting,
        allowing separation of personal vs business investment data.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_type: Optional portfolio type filter (TAXABLE, RETIREMENT, BUSINESS)

        Returns:
            Dictionary with aggregated performance, allocation, and summary data

        Requirements: 13.4 - Business data separation
        """
        # Get portfolios filtered by type if specified
        if portfolio_type:
            portfolios = self.portfolio_repo.get_by_type(
                tenant_id=tenant_id,
                portfolio_type=portfolio_type,
                include_archived=False
            )
        else:
            portfolios = self.portfolio_repo.get_by_tenant(
                tenant_id=tenant_id,
                include_archived=False
            )

        if not portfolios:
            return {
                "portfolio_type_filter": portfolio_type.value if portfolio_type else "all",
                "portfolio_count": 0,
                "total_value": 0.0,
                "total_cost": 0.0,
                "total_gain_loss": 0.0,
                "total_return_percentage": 0.0,
                "unrealized_gain_loss": 0.0,
                "realized_gain_loss": 0.0,
                "asset_allocation": {},
                "dividend_income_last_12_months": 0.0
            }

        # Aggregate metrics across portfolios
        total_value = Decimal('0')
        total_cost = Decimal('0')
        total_unrealized_gain_loss = Decimal('0')
        total_realized_gain_loss = Decimal('0')
        total_dividend_income = Decimal('0')

        # Asset allocation aggregation
        aggregated_allocations = {}

        for portfolio in portfolios:
            try:
                # Get performance for this portfolio
                performance = self.calculate_portfolio_performance(tenant_id, portfolio.id)
                total_value += performance.total_value
                total_cost += performance.total_cost
                total_unrealized_gain_loss += performance.unrealized_gain_loss
                total_realized_gain_loss += performance.realized_gain_loss

                # Get asset allocation for this portfolio
                allocation = self.calculate_asset_allocation(tenant_id, portfolio.id)
                for asset_class, detail in allocation.allocations.items():
                    if asset_class not in aggregated_allocations:
                        aggregated_allocations[asset_class] = {
                            "value": Decimal('0'),
                            "holdings_count": 0
                        }
                    aggregated_allocations[asset_class]["value"] += detail.value
                    aggregated_allocations[asset_class]["holdings_count"] += detail.holdings_count

                # Get dividend income (last 12 months)
                end_date = date.today()
                start_date = date(end_date.year - 1, end_date.month, end_date.day)
                dividend_summary = self.calculate_dividend_income(tenant_id, portfolio.id, start_date, end_date)
                total_dividend_income += dividend_summary.total_dividends

            except Exception:
                # Skip portfolios with calculation errors
                continue

        # Calculate aggregated return percentage
        total_gain_loss = total_unrealized_gain_loss + total_realized_gain_loss
        total_return_percentage = (total_gain_loss / total_cost * 100) if total_cost > 0 else Decimal('0')

        # Calculate aggregated allocation percentages
        aggregated_allocation_response = {}
        for asset_class, data in aggregated_allocations.items():
            percentage = (data["value"] / total_value * 100) if total_value > 0 else Decimal('0')
            aggregated_allocation_response[asset_class.value] = {
                "value": float(data["value"]),
                "percentage": float(percentage),
                "holdings_count": data["holdings_count"]
            }

        return {
            "portfolio_type_filter": portfolio_type.value if portfolio_type else "all",
            "portfolio_count": len(portfolios),
            "total_value": float(total_value),
            "total_cost": float(total_cost),
            "total_gain_loss": float(total_gain_loss),
            "total_return_percentage": float(total_return_percentage),
            "unrealized_gain_loss": float(total_unrealized_gain_loss),
            "realized_gain_loss": float(total_realized_gain_loss),
            "asset_allocation": aggregated_allocation_response,
            "dividend_income_last_12_months": float(total_dividend_income)
        }

    def get_diversification_analysis(
        self,
        tenant_id: int,
        portfolio_id: int
    ) -> dict:
        """
        Get diversification analysis for a portfolio.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            Dictionary with diversification metrics and recommendations

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get holdings
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Calculate diversification score
        diversification_score = self.allocation_analyzer.calculate_diversification_score(holdings)

        # Get asset class summary
        asset_class_summary = self.allocation_analyzer.get_asset_class_summary(holdings)

        # Calculate concentration risk (percentage in largest holding)
        if holdings:
            largest_holding_value = max(
                self.allocation_analyzer._calculate_holding_value(h)
                for h in holdings if not h.is_closed and h.quantity > 0
            ) if any(not h.is_closed and h.quantity > 0 for h in holdings) else Decimal('0')

            total_value = sum(
                self.allocation_analyzer._calculate_holding_value(h)
                for h in holdings if not h.is_closed and h.quantity > 0
            )

            concentration_percentage = (largest_holding_value / total_value * 100) if total_value > 0 else Decimal('0')
        else:
            concentration_percentage = Decimal('0')

        return {
            "diversification_score": float(diversification_score),
            "concentration_risk": {
                "largest_holding_percentage": float(concentration_percentage),
                "risk_level": "High" if concentration_percentage > 25 else "Medium" if concentration_percentage > 10 else "Low"
            },
            "asset_class_distribution": {
                asset_class.value: {
                    "holdings_count": summary["holdings_count"],
                    "total_value": float(summary["total_value"]),
                    "percentage_of_portfolio": float(
                        (summary["total_value"] / sum(s["total_value"] for s in asset_class_summary.values()) * 100)
                        if sum(s["total_value"] for s in asset_class_summary.values()) > 0 else 0
                    )
                }
                for asset_class, summary in asset_class_summary.items()
            },
            "recommendations": self._get_diversification_recommendations(diversification_score, concentration_percentage)
        }

    def _get_diversification_recommendations(
        self,
        diversification_score: Decimal,
        concentration_percentage: Decimal
    ) -> List[str]:
        """
        Get diversification recommendations based on analysis.

        Args:
            diversification_score: Portfolio diversification score
            concentration_percentage: Percentage in largest holding

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if diversification_score < 50:
            recommendations.append("Consider diversifying across more asset classes to reduce risk")

        if concentration_percentage > 25:
            recommendations.append("High concentration risk detected - consider reducing position size in largest holding")
        elif concentration_percentage > 10:
            recommendations.append("Moderate concentration risk - monitor largest holdings")

        if diversification_score > 80:
            recommendations.append("Well-diversified portfolio with good risk distribution")

        if not recommendations:
            recommendations.append("Portfolio shows reasonable diversification characteristics")

        return recommendations

    def export_portfolio_data(
        self,
        tenant_id: int,
        portfolio_id: int,
        format: str = "json",
        include_performance: bool = True
    ) -> str:
        """
        Export complete portfolio data for backup/migration purposes.

        This is separate from tax-specific export and provides comprehensive
        portfolio data including holdings, transactions, and performance metrics.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID
            format: Export format ("csv" or "json")
            include_performance: Whether to include performance metrics

        Returns:
            Exported portfolio data as string

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
            ValidationError: If format is invalid

        Requirements: 14.5
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Validate format
        if format.lower() not in ["csv", "json"]:
            raise ValidationError(f"Unsupported export format: {format}")

        # Get portfolio data
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)
        transactions = self.transaction_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Get performance data if requested
        performance_data = None
        if include_performance:
            try:
                performance = self.calculate_portfolio_performance(tenant_id, portfolio_id)
                allocation = self.calculate_asset_allocation(tenant_id, portfolio_id)

                performance_data = {
                    "total_value": str(performance.total_value),
                    "total_cost": str(performance.total_cost),
                    "total_gain_loss": str(performance.total_gain_loss),
                    "total_return_percentage": str(performance.total_return_percentage),
                    "unrealized_gain_loss": str(performance.unrealized_gain_loss),
                    "realized_gain_loss": str(performance.realized_gain_loss),
                    "asset_allocation": {
                        asset_class.value: {
                            "value": str(detail.value),
                            "percentage": str(detail.percentage),
                            "holdings_count": detail.holdings_count
                        }
                        for asset_class, detail in allocation.allocations.items()
                    }
                }
            except Exception:
                # If performance calculation fails, continue without it
                performance_data = {"error": "Performance calculation failed"}

        # Export using portfolio data exporter
        return self.portfolio_exporter.export_portfolio_data(
            portfolio=portfolio,
            holdings=holdings,
            transactions=transactions,
            performance_data=performance_data,
            format=format
        )

    def export_transactions_csv(
        self,
        tenant_id: int,
        portfolio_id: int
    ) -> str:
        """
        Export transactions to CSV format for spreadsheet analysis.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            CSV data as string

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant

        Requirements: 14.5
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get transactions
        transactions = self.transaction_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Export using portfolio data exporter
        return self.portfolio_exporter.export_transactions_csv(
            transactions=transactions,
            portfolio_name=portfolio.name
        )

    def export_holdings_csv(
        self,
        tenant_id: int,
        portfolio_id: int
    ) -> str:
        """
        Export holdings to CSV format for spreadsheet analysis.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            CSV data as string

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant

        Requirements: 14.5
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get holdings
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Export using portfolio data exporter
        return self.portfolio_exporter.export_holdings_csv(
            holdings=holdings,
            portfolio_name=portfolio.name
        )

    def get_portfolio_backup_data(
        self,
        tenant_id: int,
        portfolio_id: int
    ) -> dict:
        """
        Get complete portfolio data for backup purposes.

        This method returns a comprehensive data structure that can be used
        for backup, migration, or analysis purposes.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            Dictionary with complete portfolio data

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant

        Requirements: 14.5
        """
        # Validate tenant access to portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get portfolio data
        holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)
        transactions = self.transaction_repo.get_by_portfolio(portfolio_id, tenant_id)

        # Get performance data
        performance_data = None
        try:
            performance = self.calculate_portfolio_performance(tenant_id, portfolio_id)
            allocation = self.calculate_asset_allocation(tenant_id, portfolio_id)

            performance_data = {
                "total_value": str(performance.total_value),
                "total_cost": str(performance.total_cost),
                "total_gain_loss": str(performance.total_gain_loss),
                "total_return_percentage": str(performance.total_return_percentage),
                "unrealized_gain_loss": str(performance.unrealized_gain_loss),
                "realized_gain_loss": str(performance.realized_gain_loss),
                "asset_allocation": {
                    asset_class.value: {
                        "value": str(detail.value),
                        "percentage": str(detail.percentage),
                        "holdings_count": detail.holdings_count
                    }
                    for asset_class, detail in allocation.allocations.items()
                }
            }
        except Exception:
            # If performance calculation fails, continue without it
            performance_data = {"error": "Performance calculation failed"}

        # Get backup data using portfolio data exporter
        return self.portfolio_exporter.get_portfolio_backup_data(
            portfolio=portfolio,
            holdings=holdings,
            transactions=transactions,
            performance_data=performance_data
        )