"""
Investment MCP Provider

This module provides the MCP (Model Context Protocol) integration for the
investment management plugin, allowing the AI assistant to query investment data.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from decimal import Decimal
import logging
from sqlalchemy.orm import Session

from ..services.portfolio_service import PortfolioService
from ..services.holdings_service import HoldingsService
from ..services.analytics_service import AnalyticsService
from ..repositories.holdings_repository import HoldingsRepository
from ..repositories.transaction_repository import TransactionRepository
from ..models import TransactionType
from core.models.database import SessionLocal
from core.exceptions.base import NotFoundError

logger = logging.getLogger(__name__)

class InvestmentMCPProvider:
    """
    MCP provider for investment data integration with AI assistant.
    Provides investment portfolio data to the MCP assistant while enforcing
    tenant isolation and data privacy.

    Requirements: 9.1, 9.2, 9.3, 9.5
    """

    def __init__(self, db_session: Session = None):
        """
        Initialize the MCP provider with database session.

        Args:
            db_session: SQLAlchemy session. If None, will create a new session.
        """
        self.provider_name = "investments"
        self.version = "1.0.0"
        self.db = db_session or SessionLocal()

        # Initialize services
        self.portfolio_service = PortfolioService(self.db)
        self.holdings_service = HoldingsService(self.db)
        self.analytics_service = AnalyticsService(self.db)

        # Initialize repositories for direct queries
        self.holdings_repo = HoldingsRepository(self.db)
        self.transaction_repo = TransactionRepository(self.db)

    async def get_portfolio_summary(self, tenant_id: int) -> Dict[str, Any]:
        """
        Get portfolio summary for MCP assistant.

        Provides comprehensive overview of all portfolios owned by the tenant,
        including performance metrics, holdings count, and total values.

        Args:
            tenant_id: Tenant ID for isolation

        Returns:
            Dict containing portfolio summary data formatted for AI assistant

        Requirements: 9.1, 9.2
        """
        try:
            # Get all portfolios with summary data
            portfolios_with_summary = self.portfolio_service.get_portfolios_with_summary(tenant_id)

            # Calculate overall totals
            total_portfolio_value = Decimal('0')
            total_cost_basis = Decimal('0')
            total_holdings_count = 0

            portfolio_summaries = []

            for portfolio, summary in portfolios_with_summary:
                # Add to totals
                total_portfolio_value += summary['total_value']
                total_cost_basis += summary['total_cost_basis']
                total_holdings_count += summary['holdings_count']

                # Format portfolio data for AI
                portfolio_data = {
                    "id": portfolio.id,
                    "name": portfolio.name,
                    "type": portfolio.portfolio_type.value,
                    "created_date": portfolio.created_at.strftime("%Y-%m-%d"),
                    "is_archived": portfolio.is_archived,
                    "holdings_count": summary['holdings_count'],
                    "total_value": float(summary['total_value']),
                    "total_cost_basis": float(summary['total_cost_basis']),
                    "unrealized_gain_loss": float(summary['unrealized_gain_loss']),
                    "return_percentage": float(
                        (summary['unrealized_gain_loss'] / summary['total_cost_basis'] * 100)
                        if summary['total_cost_basis'] > 0 else 0
                    )
                }
                portfolio_summaries.append(portfolio_data)

            # Calculate overall return
            overall_return_percentage = float(
                ((total_portfolio_value - total_cost_basis) / total_cost_basis * 100)
                if total_cost_basis > 0 else 0
            )

            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "summary": {
                    "total_portfolios": len(portfolio_summaries),
                    "total_value": float(total_portfolio_value),
                    "total_cost_basis": float(total_cost_basis),
                    "total_unrealized_gain_loss": float(total_portfolio_value - total_cost_basis),
                    "overall_return_percentage": overall_return_percentage,
                    "total_holdings": total_holdings_count
                },
                "portfolios": portfolio_summaries,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting portfolio summary for tenant {tenant_id}: {str(e)}")
            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "error": f"Failed to retrieve portfolio summary: {str(e)}",
                "portfolios": [],
                "timestamp": datetime.now().isoformat()
            }

    async def get_holding_details(self, tenant_id: int, symbol: str) -> Dict[str, Any]:
        """
        Get holding details for a specific security symbol across all portfolios.

        Args:
            tenant_id: Tenant ID for isolation
            symbol: Security symbol (e.g., "AAPL")

        Returns:
            Dict containing holding details for the symbol across all portfolios

        Requirements: 9.2
        """
        try:
            # Get all portfolios for the tenant
            portfolios = self.portfolio_service.get_portfolios(tenant_id)

            holdings_data = []
            total_quantity = Decimal('0')
            total_cost_basis = Decimal('0')
            total_current_value = Decimal('0')

            # Search for holdings with the specified symbol across all portfolios
            for portfolio in portfolios:
                holdings = self.holdings_repo.get_by_portfolio(portfolio.id, portfolio.tenant_id)

                for holding in holdings:
                    if holding.security_symbol.upper() == symbol.upper() and not holding.is_closed:
                        current_value = holding.quantity * (holding.current_price or (holding.cost_basis / holding.quantity))
                        unrealized_gain_loss = current_value - holding.cost_basis

                        holding_data = {
                            "holding_id": holding.id,
                            "portfolio_id": portfolio.id,
                            "portfolio_name": portfolio.name,
                            "security_symbol": holding.security_symbol,
                            "security_name": holding.security_name,
                            "security_type": holding.security_type.value,
                            "asset_class": holding.asset_class.value,
                            "quantity": float(holding.quantity),
                            "cost_basis": float(holding.cost_basis),
                            "average_cost_per_share": float(holding.cost_basis / holding.quantity),
                            "current_price": float(holding.current_price) if holding.current_price else None,
                            "current_value": float(current_value),
                            "unrealized_gain_loss": float(unrealized_gain_loss),
                            "return_percentage": float(
                                (unrealized_gain_loss / holding.cost_basis * 100)
                                if holding.cost_basis > 0 else 0
                            ),
                            "purchase_date": holding.purchase_date.strftime("%Y-%m-%d"),
                            "price_updated_at": holding.price_updated_at.strftime("%Y-%m-%d %H:%M:%S") if holding.price_updated_at else None
                        }

                        holdings_data.append(holding_data)

                        # Add to totals
                        total_quantity += holding.quantity
                        total_cost_basis += holding.cost_basis
                        total_current_value += current_value

            # Calculate overall metrics for this symbol
            total_unrealized_gain_loss = total_current_value - total_cost_basis
            overall_return_percentage = float(
                (total_unrealized_gain_loss / total_cost_basis * 100)
                if total_cost_basis > 0 else 0
            )

            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "symbol": symbol.upper(),
                "summary": {
                    "total_holdings": len(holdings_data),
                    "total_quantity": float(total_quantity),
                    "total_cost_basis": float(total_cost_basis),
                    "total_current_value": float(total_current_value),
                    "total_unrealized_gain_loss": float(total_unrealized_gain_loss),
                    "overall_return_percentage": overall_return_percentage,
                    "average_cost_per_share": float(total_cost_basis / total_quantity) if total_quantity > 0 else 0
                },
                "holdings": holdings_data,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting holding details for symbol {symbol}, tenant {tenant_id}: {str(e)}")
            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "symbol": symbol,
                "error": f"Failed to retrieve holding details: {str(e)}",
                "holdings": [],
                "timestamp": datetime.now().isoformat()
            }

    async def get_performance_summary(self, tenant_id: int, portfolio_id: int) -> Dict[str, Any]:
        """
        Get performance summary for a specific portfolio.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            Dict containing comprehensive performance metrics

        Requirements: 9.2, 9.3
        """
        try:
            # Get comprehensive portfolio summary from analytics service
            portfolio_summary = self.analytics_service.get_portfolio_summary(tenant_id, portfolio_id)

            # Get diversification analysis
            diversification_analysis = self.analytics_service.get_diversification_analysis(tenant_id, portfolio_id)

            # Get recent dividend income (last 12 months)
            end_date = date.today()
            start_date = date(end_date.year - 1, end_date.month, end_date.day)
            dividend_summary = self.analytics_service.calculate_dividend_income(
                tenant_id, portfolio_id, start_date, end_date
            )

            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "portfolio_id": portfolio_id,
                "portfolio_name": portfolio_summary["portfolio_name"],
                "portfolio_type": portfolio_summary["portfolio_type"],
                "performance": portfolio_summary["performance"],
                "asset_allocation": portfolio_summary["allocation"],
                "holdings_summary": portfolio_summary["holdings"],
                "dividend_income_last_12_months": {
                    "total_income": float(dividend_summary.total_dividends),
                    "transaction_count": len(dividend_summary.dividend_transactions),
                    "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                },
                "diversification": diversification_analysis,
                "timestamp": datetime.now().isoformat()
            }

        except NotFoundError:
            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "portfolio_id": portfolio_id,
                "error": f"Portfolio {portfolio_id} not found or not accessible",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting performance summary for portfolio {portfolio_id}, tenant {tenant_id}: {str(e)}")
            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "portfolio_id": portfolio_id,
                "error": f"Failed to retrieve performance summary: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    async def get_dividend_forecast(self, tenant_id: int, portfolio_id: int) -> Dict[str, Any]:
        """
        Get dividend forecast and history for a portfolio.

        Provides dividend income history and enhanced forecasting based on
        historical dividend patterns, frequency analysis, and yield calculations.

        Args:
            tenant_id: Tenant ID for isolation
            portfolio_id: Portfolio ID

        Returns:
            Dict containing dividend forecast and historical data

        Requirements: 9.2, 9.5
        """
        try:
            # Validate portfolio access
            portfolio = self.portfolio_service.get_portfolio(portfolio_id, tenant_id)
            if not portfolio:
                return {
                    "provider": self.provider_name,
                    "tenant_id": tenant_id,
                    "portfolio_id": portfolio_id,
                    "error": f"Portfolio {portfolio_id} not found or not accessible",
                    "timestamp": datetime.now().isoformat()
                }

            # Get current holdings with dividend potential
            holdings = self.holdings_repo.get_by_portfolio(portfolio_id, tenant_id)
            dividend_holdings = []

            # Get dividend history for different periods
            current_date = date.today()

            # Last 12 months
            last_12_months_start = date(current_date.year - 1, current_date.month, current_date.day)
            dividends_12_months = self.analytics_service.calculate_dividend_income(
                tenant_id, portfolio_id, last_12_months_start, current_date
            )

            # Last 3 months
            last_3_months_start = date(current_date.year, max(1, current_date.month - 3), current_date.day)
            dividends_3_months = self.analytics_service.calculate_dividend_income(
                tenant_id, portfolio_id, last_3_months_start, current_date
            )

            # Current year
            current_year_start = date(current_date.year, 1, 1)
            dividends_current_year = self.analytics_service.calculate_dividend_income(
                tenant_id, portfolio_id, current_year_start, current_date
            )

            # Simple forecast based on last 12 months
            estimated_annual_income = float(dividends_12_months.total_dividends)
            estimated_quarterly_income = estimated_annual_income / 4
            estimated_monthly_income = estimated_annual_income / 12

            # Get holdings that have paid dividends
            for holding in holdings:
                if not holding.is_closed and holding.quantity > 0:
                    # Check if this holding has dividend transactions
                    transactions = self.transaction_repo.get_by_holding(holding.id)
                    dividend_transactions = [t for t in transactions if t.transaction_type.value == 'dividend']

                    if dividend_transactions:
                        total_dividends = sum(float(t.total_amount) for t in dividend_transactions)
                        dividend_holdings.append({
                            "symbol": holding.security_symbol,
                            "name": holding.security_name,
                            "quantity": float(holding.quantity),
                            "current_value": float(holding.quantity * holding.current_price) if holding.current_price else float(holding.cost_basis),
                            "total_dividends_received": total_dividends,
                            "dividend_payment_count": len(dividend_transactions),
                            "last_dividend_date": max(t.transaction_date.isoformat() for t in dividend_transactions) if dividend_transactions else None
                        })

            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "portfolio_id": portfolio_id,
                "portfolio_name": portfolio.name,
                "historical_income": {
                    "last_12_months": {
                        "total_income": float(dividends_12_months.total_dividends),
                        "transaction_count": len(dividends_12_months.dividend_transactions),
                        "period": f"{last_12_months_start.strftime('%Y-%m-%d')} to {current_date.strftime('%Y-%m-%d')}"
                    },
                    "last_3_months": {
                        "total_income": float(dividends_3_months.total_dividends),
                        "transaction_count": len(dividends_3_months.dividend_transactions),
                        "period": f"{last_3_months_start.strftime('%Y-%m-%d')} to {current_date.strftime('%Y-%m-%d')}"
                    },
                    "current_year": {
                        "total_income": float(dividends_current_year.total_dividends),
                        "transaction_count": len(dividends_current_year.dividend_transactions),
                        "period": f"{current_year_start.strftime('%Y-%m-%d')} to {current_date.strftime('%Y-%m-%d')}"
                    }
                },
                "forecast": {
                    "estimated_annual_income": estimated_annual_income,
                    "estimated_quarterly_income": estimated_quarterly_income,
                    "estimated_monthly_income": estimated_monthly_income,
                    "note": "Forecast based on historical dividend patterns and current holdings"
                },
                "dividend_holdings": dividend_holdings,
                "summary": {
                    "total_dividend_paying_holdings": len(dividend_holdings),
                    "total_holdings": len([h for h in holdings if not h.is_closed and h.quantity > 0])
                },
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting dividend forecast for portfolio {portfolio_id}, tenant {tenant_id}: {str(e)}")
            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "portfolio_id": portfolio_id,
                "error": f"Failed to retrieve dividend forecast: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    async def get_tax_summary(self, tenant_id: int, tax_year: int) -> Dict[str, Any]:
        """
        Get tax summary for all portfolios for a specific tax year.

        Args:
            tenant_id: Tenant ID for isolation
            tax_year: Tax year (e.g., 2024)

        Returns:
            Dict containing comprehensive tax summary across all portfolios

        Requirements: 9.2, 9.5
        """
        try:
            # Validate tax year
            current_year = date.today().year
            if tax_year < 1900 or tax_year > current_year:
                return {
                    "provider": self.provider_name,
                    "tenant_id": tenant_id,
                    "tax_year": tax_year,
                    "error": f"Invalid tax year: {tax_year}. Must be between 1900 and {current_year}",
                    "timestamp": datetime.now().isoformat()
                }

            # Get all portfolios for the tenant
            portfolios = self.portfolio_service.get_portfolios(tenant_id)

            portfolio_tax_data = []
            total_realized_gains = Decimal('0')
            total_dividend_income = Decimal('0')
            total_transactions = 0

            for portfolio in portfolios:
                try:
                    # Get tax summary for this portfolio
                    tax_export = self.analytics_service.get_tax_summary(tenant_id, portfolio.id, tax_year)

                    portfolio_data = {
                        "portfolio_id": portfolio.id,
                        "portfolio_name": portfolio.name,
                        "portfolio_type": portfolio.portfolio_type.value,
                        "realized_gains": float(tax_export.total_realized_gains),
                        "dividend_income": float(tax_export.total_dividends),
                        "transaction_count": len(tax_export.transactions),
                        "transactions": [
                            {
                                "id": tx.id,
                                "date": tx.transaction_date.strftime("%Y-%m-%d"),
                                "type": tx.transaction_type.value,
                                "amount": float(tx.total_amount),
                                "realized_gain": float(tx.realized_gain) if tx.realized_gain else None,
                                "holding_symbol": self._get_holding_symbol(tx.holding_id) if tx.holding_id else None
                            }
                            for tx in tax_export.transactions
                        ]
                    }

                    portfolio_tax_data.append(portfolio_data)

                    # Add to totals
                    total_realized_gains += tax_export.total_realized_gains
                    total_dividend_income += tax_export.total_dividends
                    total_transactions += len(tax_export.transactions)

                except Exception as portfolio_error:
                    logger.warning(f"Error processing tax data for portfolio {portfolio.id}: {str(portfolio_error)}")
                    # Continue with other portfolios
                    continue

            # Calculate tax implications (basic guidance)
            tax_guidance = self._generate_tax_guidance(total_realized_gains, total_dividend_income)

            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "tax_year": tax_year,
                "summary": {
                    "total_portfolios": len(portfolio_tax_data),
                    "total_realized_gains": float(total_realized_gains),
                    "total_dividend_income": float(total_dividend_income),
                    "total_taxable_income": float(total_realized_gains + total_dividend_income),
                    "total_transactions": total_transactions
                },
                "portfolios": portfolio_tax_data,
                "tax_guidance": tax_guidance,
                "disclaimer": "This is raw transaction data. Consult a tax professional for actual tax preparation and advice.",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting tax summary for tax year {tax_year}, tenant {tenant_id}: {str(e)}")
            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "tax_year": tax_year,
                "error": f"Failed to retrieve tax summary: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def _get_holding_symbol(self, holding_id: int) -> Optional[str]:
        """Get security symbol for a holding ID."""
        try:
            holding = self.holdings_repo.get_by_id(holding_id)
            return holding.security_symbol if holding else None
        except Exception:
            return None

    def _generate_tax_guidance(self, realized_gains: Decimal, dividend_income: Decimal) -> Dict[str, Any]:
        """Generate basic tax guidance based on investment income."""
        guidance = {
            "notes": [],
            "considerations": []
        }

        if realized_gains > 0:
            guidance["notes"].append(f"You have ${float(realized_gains):,.2f} in realized capital gains")
            guidance["considerations"].append("Capital gains may be subject to different tax rates depending on holding period")
        elif realized_gains < 0:
            guidance["notes"].append(f"You have ${float(abs(realized_gains)):,.2f} in realized capital losses")
            guidance["considerations"].append("Capital losses can offset capital gains and up to $3,000 of ordinary income")

        if dividend_income > 0:
            guidance["notes"].append(f"You have ${float(dividend_income):,.2f} in dividend income")
            guidance["considerations"].append("Qualified dividends may be taxed at capital gains rates")

        if realized_gains == 0 and dividend_income == 0:
            guidance["notes"].append("No taxable investment income for this year")

        guidance["considerations"].extend([
            "Consult a tax professional for specific advice",
            "Consider tax-loss harvesting strategies",
            "Review holding periods for capital gains treatment"
        ])

        return guidance

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information for registration"""
        return {
            "name": self.provider_name,
            "version": self.version,
            "description": "Investment portfolio data provider for MCP assistant",
            "methods": [
                "get_portfolio_summary",
                "get_holding_details",
                "get_performance_summary",
                "get_dividend_forecast",
                "get_tax_summary"
            ],
            "capabilities": [
                "Portfolio performance analysis",
                "Asset allocation insights",
                "Dividend income tracking and forecasting",
                "Tax reporting data aggregation",
                "Multi-portfolio investment overview",
                "Security-specific holding analysis"
            ]
        }

    def close(self):
        """Close database connections and clean up resources."""
        if hasattr(self, 'portfolio_service'):
            self.portfolio_service.close()
        if hasattr(self, 'holdings_service'):
            self.holdings_service.close()
        if hasattr(self, 'db'):
            self.db.close()