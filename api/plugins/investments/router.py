"""
Investment Management API Router

This module defines the FastAPI router for investment management endpoints.
All routes are protected by commercial license requirements and tenant isolation.
Comprehensive error handling ensures consistent error responses across all endpoints.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Path
from fastapi.responses import JSONResponse, Response
from typing import List, Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError as PydanticValidationError

# Import core dependencies
from core.models.database import get_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.utils.feature_gate import require_feature

# Import schemas
from .schemas import (
    PortfolioCreate, PortfolioUpdate, PortfolioResponse,
    HoldingCreate, HoldingUpdate, HoldingResponse, PriceUpdate,
    BuyTransactionCreate, SellTransactionCreate, DividendTransactionCreate,
    OtherTransactionCreate, TransactionResponse,
    PerformanceMetrics, AssetAllocation, DividendSummary, TaxExport,
    DateRangeQuery, TaxYearQuery, ErrorResponse, RebalanceReport,
    FileAttachmentResponse, FileAttachmentDetailResponse, PortfolioWithAttachmentResponse
)

# Import models for enums
from .models import PortfolioType

# Import services
from .services.portfolio_service import PortfolioService
from .services.holdings_service import HoldingsService
from .services.transaction_service import TransactionService
from .services.analytics_service import AnalyticsService
from .services.rebalance_service import RebalanceService
from .services.portfolio_import_service import PortfolioImportService


# Import error handling
from .exceptions import (
    InvestmentError, ValidationError, TenantAccessError, ResourceNotFoundError,
    ConflictError, DuplicateTransactionError, FileValidationError, FileStorageError,
    FileUploadError, ExtractionError, CloudStorageError
)
from .error_handlers import (
    handle_investment_error, handle_pydantic_validation_error,
    handle_sqlalchemy_error, handle_generic_exception,
    raise_not_found_error, raise_tenant_access_error
)
from .validation import (
    PortfolioValidator, HoldingValidator, TransactionValidator,
    DuplicateTransactionDetector
)

# Import validation middleware
from .middleware import (
    ValidationMiddleware, RequestValidationMiddleware,
    validate_portfolio_id_param, validate_holding_id_param,
    validate_transaction_id_param, validate_tax_year_param,
    validate_date_range_params, validate_pagination_params
)

# Investment router
investment_router = APIRouter()

# Setup logging
logger = logging.getLogger(__name__)

# Note: Exception handlers are handled at the application level, not router level
# Individual endpoints will handle errors using try/catch blocks and return appropriate responses

# Placeholder endpoints - will be implemented in later tasks
@investment_router.get("/health")
async def health_check():
    """Health check endpoint for investment plugin"""
    return {"status": "ok", "plugin": "investment-management", "version": "1.0.0"}

# Portfolio endpoints
@investment_router.post("/portfolios", response_model=PortfolioWithAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    portfolio: PortfolioCreate,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new investment portfolio.

    Returns the created portfolio and a null attachment placeholder.
    File attachments should be uploaded via the separate holdings-files endpoint.

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
    """
    try:
        # Create portfolio
        service = PortfolioService(db)
        created_portfolio = service.create_portfolio(
            tenant_id=current_user.tenant_id,
            portfolio_data=portfolio
        )

        portfolio_response = PortfolioResponse.model_validate(created_portfolio)

        return PortfolioWithAttachmentResponse(
            portfolio=portfolio_response,
            attachment=None
        )
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to create portfolio: {str(e)}")

@investment_router.get("/portfolios")
async def get_portfolios(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_archived: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    portfolio_type: Optional[str] = Query(None),
    label: Optional[str] = Query(None)
):
    """Get all portfolios for the current tenant with pagination and filtering"""
    try:
        service = PortfolioService(db)
        portfolios_with_summaries, total = service.get_portfolios_paginated(
            tenant_id=current_user.tenant_id,
            include_archived=include_archived,
            skip=skip,
            limit=limit,
            search=search,
            portfolio_type=portfolio_type,
            label=label
        )
        
        items = []
        for p, s in portfolios_with_summaries:
            pr = PortfolioResponse.model_validate(p)
            pr.total_value = s.get('total_value', 0)
            pr.holdings_count = s.get('holdings_count', 0)
            pr.total_cost = s.get('total_cost_basis', 0)
            items.append(pr)

        return {
            "items": items,
            "total": total
        }
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve portfolios: {str(e)}")

@investment_router.get("/portfolios/deleted")
async def get_deleted_portfolios(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Get all deleted (archived) portfolios for the current tenant"""
    try:
        service = PortfolioService(db)
        portfolios, total = service.get_deleted_portfolios(
            tenant_id=current_user.tenant_id,
            skip=skip,
            limit=limit
        )
        return {
            "items": [PortfolioResponse.model_validate(p) for p in portfolios],
            "total": total
        }
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve deleted portfolios: {str(e)}")

@investment_router.post("/portfolios/recycle-bin/empty", response_model=int)
async def empty_recycle_bin(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Permanently delete all archived portfolios for a tenant"""
    try:
        service = PortfolioService(db)
        count = service.empty_recycle_bin(tenant_id=current_user.tenant_id)
        return count
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to empty recycle bin: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific portfolio"""
    try:
        service = PortfolioService(db)

        # Validate tenant access
        if not service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        portfolio, summary = service.get_portfolio_with_summary(
            portfolio_id=portfolio_id,
            tenant_id=current_user.tenant_id
        )
        if not portfolio:
            raise_not_found_error("Portfolio", portfolio_id)

        # Add summary fields to portfolio response
        portfolio_response = PortfolioResponse.model_validate(portfolio)
        portfolio_response.total_value = summary.get('total_value', 0)
        portfolio_response.holdings_count = summary.get('holdings_count', 0)
        portfolio_response.total_cost = summary.get('total_cost_basis', 0)

        return portfolio_response
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve portfolio: {str(e)}")

@investment_router.put("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio: PortfolioUpdate,
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a portfolio"""
    try:
        service = PortfolioService(db)

        # Validate tenant access
        if not service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        updated_portfolio = service.update_portfolio(
            portfolio_id=portfolio_id,
            tenant_id=current_user.tenant_id,
            updates=portfolio
        )
        if not updated_portfolio:
            raise_not_found_error("Portfolio", portfolio_id)

        return PortfolioResponse.model_validate(updated_portfolio)
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to update portfolio: {str(e)}")

@investment_router.delete("/portfolios/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a portfolio (only if no holdings)"""
    try:
        service = PortfolioService(db)

        # Validate tenant access
        if not service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        success = service.delete_portfolio(
            portfolio_id=portfolio_id,
            tenant_id=current_user.tenant_id
        )
        if not success:
            raise_not_found_error("Portfolio", portfolio_id)

        return None
    except Exception as e:
        raise InvestmentError(f"Failed to delete portfolio: {str(e)}")

@investment_router.post("/portfolios/{portfolio_id}/restore", response_model=bool)
async def restore_portfolio(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Restore a deleted (archived) portfolio"""
    try:
        service = PortfolioService(db)
        success = service.restore_portfolio(
            portfolio_id=portfolio_id,
            tenant_id=current_user.tenant_id
        )
        if not success:
            raise_not_found_error("Portfolio", portfolio_id)
        return success
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to restore portfolio: {str(e)}")

@investment_router.delete("/portfolios/{portfolio_id}/permanent", response_model=bool)
async def permanent_delete_portfolio(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Permanently delete a portfolio"""
    try:
        service = PortfolioService(db)
        success = service.permanently_delete_portfolio(
            portfolio_id=portfolio_id,
            tenant_id=current_user.tenant_id
        )
        if not success:
            raise_not_found_error("Portfolio", portfolio_id)
        return success
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to permanently delete portfolio: {str(e)}")

# Holdings endpoints
@investment_router.post("/portfolios/{portfolio_id}/holdings", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
async def create_holding(
    holding: HoldingCreate,
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new holding in a portfolio"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        holdings_service = HoldingsService(db)
        created_holding = holdings_service.create_holding(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id,
            holding_data=holding
        )
        return HoldingResponse.model_validate(created_holding)
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to create holding: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/holdings", response_model=List[HoldingResponse])
async def get_holdings(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_closed: bool = False
):
    """Get all holdings for a portfolio"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        holdings_service = HoldingsService(db)
        holdings = holdings_service.get_holdings(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id,
            include_closed=include_closed
        )
        return [HoldingResponse.model_validate(h) for h in holdings]
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve holdings: {str(e)}")

# Static holdings routes must come BEFORE parameterized /holdings/{holding_id} routes
# to prevent FastAPI from matching e.g. "price-status" as a holding_id integer.
@investment_router.post("/holdings/update-prices")
async def update_all_prices(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update market prices for all holdings in the tenant's portfolios"""
    try:
        from .services.market_data_service import MarketDataService
        
        market_data_service = MarketDataService(db)
        result = await market_data_service.update_all_holdings_prices(current_user.tenant_id)
        
        return {
            "message": "Price update completed",
            "success": result.get("success", 0),
            "failed": result.get("failed", 0),
            "total": result.get("total", 0)
        }
    except Exception as e:
        raise InvestmentError(f"Failed to update prices: {str(e)}")

@investment_router.get("/holdings/price-status")
async def get_price_status(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get status of price updates for holdings"""
    try:
        from .services.market_data_service import MarketDataService
        
        market_data_service = MarketDataService(db)
        status = market_data_service.get_price_update_status(current_user.tenant_id)
        
        return status
    except Exception as e:
        raise InvestmentError(f"Failed to get price status: {str(e)}")

@investment_router.get("/holdings/{holding_id}", response_model=HoldingResponse)
async def get_holding(
    holding_id: int = Depends(validate_holding_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific holding"""
    try:
        holdings_service = HoldingsService(db)
        holding = holdings_service.get_holding(
            tenant_id=current_user.tenant_id,
            holding_id=holding_id
        )
        if not holding:
            raise_not_found_error("Holding", holding_id)

        return HoldingResponse.model_validate(holding)
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve holding: {str(e)}")

@investment_router.put("/holdings/{holding_id}", response_model=HoldingResponse)
async def update_holding(
    holding: HoldingUpdate,
    holding_id: int = Depends(validate_holding_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a holding"""
    try:
        holdings_service = HoldingsService(db)

        # Get existing holding to validate tenant access
        existing_holding = holdings_service.get_holding(
            tenant_id=current_user.tenant_id,
            holding_id=holding_id
        )
        if not existing_holding:
            raise_not_found_error("Holding", holding_id)

        updated_holding = holdings_service.update_holding(
            tenant_id=current_user.tenant_id,
            holding_id=holding_id,
            holding_data=holding
        )
        if not updated_holding:
            raise_not_found_error("Holding", holding_id)

        return HoldingResponse.model_validate(updated_holding)
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to update holding: {str(e)}")

@investment_router.patch("/holdings/{holding_id}/price", response_model=HoldingResponse)
async def update_holding_price(
    price_update: PriceUpdate,
    holding_id: int = Depends(validate_holding_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the current price of a holding"""
    try:
        holdings_service = HoldingsService(db)

        # Get existing holding to validate tenant access
        existing_holding = holdings_service.get_holding(
            tenant_id=current_user.tenant_id,
            holding_id=holding_id
        )
        if not existing_holding:
            raise_not_found_error("Holding", holding_id)

        updated_holding = holdings_service.update_price(
            tenant_id=current_user.tenant_id,
            holding_id=holding_id,
            price=price_update.current_price
        )
        if not updated_holding:
            raise_not_found_error("Holding", holding_id)

        return HoldingResponse.model_validate(updated_holding)
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to update holding price: {str(e)}")


@investment_router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    holding_id: int = Depends(validate_holding_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a holding permanently"""
    try:
        service = HoldingsService(db)
        success = service.delete_holding(
            tenant_id=current_user.tenant_id,
            holding_id=holding_id
        )
        if not success:
            raise_not_found_error("Holding", holding_id)

        return None
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to delete holding: {str(e)}")

# Transaction endpoints
@investment_router.post("/portfolios/{portfolio_id}/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction: dict,
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record a transaction (buy, sell, dividend, interest, fee, transfer, contribution)"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        # Check for duplicate transactions
        duplicate_detector = DuplicateTransactionDetector(db)
        duplicate_detector.check_for_duplicate(portfolio_id, current_user.tenant_id, transaction)

        transaction_service = TransactionService(db)
        created_transaction = transaction_service.record_transaction(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id,
            transaction_data=transaction
        )
        return created_transaction
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to create transaction: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    date_range: tuple = Depends(validate_date_range_params)
):
    """Get transactions for a portfolio with optional date filtering"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        start_date, end_date = date_range

        transaction_service = TransactionService(db)
        transactions = transaction_service.get_transactions(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id,
            start_date=start_date,
            end_date=end_date
        )

        return [TransactionResponse.model_validate(t) for t in transactions]
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve transactions: {str(e)}")

@investment_router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int = Depends(validate_transaction_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific transaction"""
    try:
        transaction_service = TransactionService(db)
        transaction = transaction_service.get_transaction(transaction_id)
        if not transaction:
            raise_not_found_error("Transaction", transaction_id)

        # Validate tenant access through portfolio
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(transaction.portfolio_id, current_user.tenant_id):
            raise_tenant_access_error("Transaction", transaction_id)

        return TransactionResponse.model_validate(transaction)
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve transaction: {str(e)}")

# Analytics endpoints
@investment_router.get("/portfolios/{portfolio_id}/performance", response_model=PerformanceMetrics)
async def get_portfolio_performance(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get portfolio performance metrics (inception-to-date)"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        performance = analytics_service.calculate_portfolio_performance(current_user.tenant_id, portfolio_id)
        return performance
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to calculate performance: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/allocation", response_model=AssetAllocation)
async def get_asset_allocation(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get asset allocation analysis"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        allocation = analytics_service.calculate_asset_allocation(current_user.tenant_id, portfolio_id)
        return allocation
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to calculate asset allocation: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/dividends", response_model=DividendSummary)
async def get_dividend_summary(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    date_range: tuple = Depends(validate_date_range_params)
):
    """Get dividend summary for a time period"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        start_date, end_date = date_range

        analytics_service = AnalyticsService(db)
        dividend_summary = analytics_service.calculate_dividend_income(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id,
            start_date=start_date,
            end_date=end_date
        )
        return dividend_summary
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to calculate dividend summary: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/rebalance", response_model=RebalanceReport)
async def get_rebalance_report(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get asset rebalancing analysis and recommendations"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        rebalance_service = RebalanceService(db)
        report = rebalance_service.generate_rebalance_report(
            portfolio_id=portfolio_id,
            tenant_id=current_user.tenant_id
        )

        if report is None:
            # Could be portfolio not found or no targets set
            # If access validated, it means no targets
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"detail": "No target allocations set for this portfolio. Please set targets first."}
            )

        return report
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to generate rebalance report: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/dividends/yields")
async def get_dividend_yields(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    period_months: int = Query(12, ge=1, le=60, description="Number of months to calculate yield over"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dividend yields for all holdings in a portfolio"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        dividend_yields = analytics_service.calculate_dividend_yield_by_holding(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id,
            period_months=period_months
        )

        return {
            "portfolio_id": portfolio_id,
            "period_months": period_months,
            "dividend_yields": dividend_yields
        }
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to calculate dividend yields: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/dividends/frequency")
async def get_dividend_frequency_analysis(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    lookback_months: int = Query(24, ge=6, le=60, description="Number of months to analyze"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dividend payment frequency analysis for holdings"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        frequency_analysis = analytics_service.get_dividend_frequency_analysis(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id,
            lookback_months=lookback_months
        )

        return {
            "portfolio_id": portfolio_id,
            "lookback_months": lookback_months,
            "frequency_analysis": frequency_analysis
        }
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to analyze dividend frequency: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/dividends/forecast")
async def get_dividend_forecast(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    forecast_months: int = Query(12, ge=1, le=36, description="Number of months to forecast"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dividend income forecast based on historical patterns"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        forecast = analytics_service.forecast_dividend_income(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id,
            forecast_months=forecast_months
        )

        return {
            "portfolio_id": portfolio_id,
            **forecast
        }
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to generate dividend forecast: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/tax-export", response_model=TaxExport)
async def export_tax_data(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    tax_year: int = Depends(validate_tax_year_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export tax data for a specific year"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        tax_export = analytics_service.export_tax_data(
            portfolio_id=portfolio_id,
            tax_year=tax_year
        )
        return tax_export
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to export tax data: {str(e)}")

# Portfolio data export endpoints (separate from tax export)
@investment_router.get("/portfolios/{portfolio_id}/export")
async def export_portfolio_data(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    format: str = "json",
    include_performance: bool = True,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export complete portfolio data for backup/migration purposes"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        export_data = analytics_service.export_portfolio_data(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id,
            format=format,
            include_performance=include_performance
        )

        # Return appropriate content type based on format
        if format.lower() == "csv":
            from fastapi.responses import Response
            return Response(
                content=export_data,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=portfolio_{portfolio_id}_export.csv"}
            )
        else:
            from fastapi.responses import Response
            return Response(
                content=export_data,
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=portfolio_{portfolio_id}_export.json"}
            )
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to export portfolio data: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/export/transactions")
async def export_transactions_csv(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export transactions to CSV format for spreadsheet analysis"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        csv_data = analytics_service.export_transactions_csv(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id
        )

        from fastapi.responses import Response
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=portfolio_{portfolio_id}_transactions.csv"}
        )
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to export transactions: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/export/holdings")
async def export_holdings_csv(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export holdings to CSV format for spreadsheet analysis"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        csv_data = analytics_service.export_holdings_csv(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id
        )

        from fastapi.responses import Response
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=portfolio_{portfolio_id}_holdings.csv"}
        )
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to export holdings: {str(e)}")

@investment_router.get("/portfolios/{portfolio_id}/backup")
async def get_portfolio_backup_data(
    portfolio_id: int = Depends(validate_portfolio_id_param),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get complete portfolio data for backup purposes"""
    try:
        # Validate portfolio access first
        portfolio_service = PortfolioService(db)
        if not portfolio_service.validate_tenant_access(portfolio_id, current_user.tenant_id):
            raise_not_found_error("Portfolio", portfolio_id)

        analytics_service = AnalyticsService(db)
        backup_data = analytics_service.get_portfolio_backup_data(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id
        )

        return backup_data
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to get portfolio backup data: {str(e)}")

# Business portfolio endpoints for portfolio type filtering
@investment_router.get("/portfolios/by-type/{portfolio_type}", response_model=List[PortfolioResponse])
async def get_portfolios_by_type(
    portfolio_type: PortfolioType,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_archived: bool = False
):
    """Get portfolios filtered by type (TAXABLE, RETIREMENT, BUSINESS)"""
    try:
        service = PortfolioService(db)
        portfolios = service.get_portfolios_by_type(
            tenant_id=current_user.tenant_id,
            portfolio_type=portfolio_type,
            include_archived=include_archived
        )
        return [PortfolioResponse.model_validate(p) for p in portfolios]
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve portfolios by type: {str(e)}")

@investment_router.get("/analytics/aggregated", response_model=dict)
async def get_aggregated_analytics(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    portfolio_type: Optional[PortfolioType] = None
):
    """Get aggregated analytics across portfolios, optionally filtered by type"""
    try:
        analytics_service = AnalyticsService(db)
        aggregated_data = analytics_service.get_aggregated_analytics_by_type(
            tenant_id=current_user.tenant_id,
            portfolio_type=portfolio_type
        )
        return aggregated_data
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to calculate aggregated analytics: {str(e)}")

@investment_router.get("/analytics/business-summary", response_model=dict)
async def get_business_analytics_summary(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get analytics summary specifically for business portfolios"""
    try:
        analytics_service = AnalyticsService(db)
        business_data = analytics_service.get_aggregated_analytics_by_type(
            tenant_id=current_user.tenant_id,
            portfolio_type=PortfolioType.BUSINESS
        )
        return business_data
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to calculate business analytics: {str(e)}")



@investment_router.get("/portfolios/{portfolio_id}/diversification", response_model=dict)
async def get_diversification_analysis(
    portfolio_id: int,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get diversification analysis for a portfolio"""
    try:
        analytics_service = AnalyticsService(db)
        diversification_data = analytics_service.get_diversification_analysis(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id
        )
        return diversification_data
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to calculate diversification analysis: {str(e)}")


# File Management Endpoints

@investment_router.post("/portfolios/{portfolio_id}/holdings-files", response_model=List[FileAttachmentResponse], status_code=status.HTTP_201_CREATED)
# @require_feature("investments")  # Temporarily disabled for testing
async def upload_portfolio_files(
    portfolio_id: int = Path(..., description="Portfolio ID"),
    files: Optional[List[UploadFile]] = File(None, description="Holdings files to upload"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload one or more holdings files to a portfolio.

    Accepts up to 12 PDF or CSV files for holdings import.
    Files are validated, stored in tenant-scoped directories, and enqueued for background processing.
    Returns immediately with file attachment metadata.

    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 9.5, 19.1, 19.2, 19.3, 19.4, 19.5, 8.1, 8.2, 8.3, 8.4, 8.5
    """
    logger.info(f"Upload holdings files endpoint called with portfolio_id={portfolio_id}, files count={len(files) if files else 0}")

    # Validate files are provided
    if not files or len(files) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one file is required")

    try:
        # Verify portfolio ownership
        portfolio_service = PortfolioService(db)
        portfolio = portfolio_service.get_portfolio(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id
        )
        if not portfolio:
            raise_not_found_error(f"Portfolio {portfolio_id} not found")

        # Convert UploadFile objects to tuples (file_content, filename, content_type)
        file_tuples = []
        for file in files:
            content = await file.read()
            file_tuples.append((content, file.filename, file.content_type))

        # Upload files using PortfolioImportService
        import_service = PortfolioImportService(db)
        attachments = await import_service.upload_files(
            portfolio_id=portfolio_id,
            tenant_id=current_user.tenant_id,
            files=file_tuples,
            user_id=current_user.id,
            user_email=current_user.email
        )

        return [FileAttachmentResponse.model_validate(att) for att in attachments]
    except (FileValidationError, FileStorageError, FileUploadError) as e:
        raise InvestmentError(str(e))
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to upload holdings files: {str(e)}")


@investment_router.get("/portfolios/{portfolio_id}/holdings-files", response_model=List[FileAttachmentResponse])
# @require_feature("investments")  # Temporarily disabled for testing
async def list_portfolio_files(
    portfolio_id: int,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all file attachments for a portfolio.

    Returns all uploaded files with their current processing status.
    Filters by tenant_id to ensure data isolation.

    Requirements: 10.2, 10.3, 19.1, 19.2, 19.3, 19.4, 19.5, 8.1, 8.2, 8.3, 8.4, 8.5
    """
    try:
        # Verify portfolio ownership
        portfolio_service = PortfolioService(db)
        portfolio = portfolio_service.get_portfolio(
            tenant_id=current_user.tenant_id,
            portfolio_id=portfolio_id
        )
        if not portfolio:
            raise_not_found_error(f"Portfolio {portfolio_id} not found")

        # Get file attachments
        import_service = PortfolioImportService(db)
        attachments = import_service.get_file_attachments(
            portfolio_id=portfolio_id,
            tenant_id=current_user.tenant_id
        )

        return [FileAttachmentResponse.model_validate(att) for att in attachments]
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve file attachments: {str(e)}")


@investment_router.get("/holdings-files/{attachment_id}", response_model=FileAttachmentDetailResponse)
# @require_feature("investments")  # Temporarily disabled for testing
async def get_portfolio_file_details(
    attachment_id: int,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific file attachment.

    Returns attachment metadata and extracted holdings data.
    Verifies tenant ownership before returning data.

    Requirements: 10.3, 10.4, 19.1, 19.2, 19.3, 19.4, 19.5, 8.1, 8.2, 8.3, 8.4, 8.5
    """
    try:
        # Get file attachment with tenant verification
        import_service = PortfolioImportService(db)
        attachment = import_service.get_file_attachment(
            attachment_id=attachment_id,
            tenant_id=current_user.tenant_id
        )

        if not attachment:
            raise_not_found_error(f"File attachment {attachment_id} not found")

        return FileAttachmentDetailResponse.model_validate(attachment)
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to retrieve file attachment details: {str(e)}")


@investment_router.get("/holdings-files/{attachment_id}/download")
# @require_feature("investments")  # Temporarily disabled for testing
async def download_portfolio_file(
    attachment_id: int,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download the original uploaded file.

    Returns the file with appropriate headers for download.
    Verifies tenant ownership before allowing download.

    Requirements: 10.5, 19.1, 19.2, 19.3, 19.4, 19.5, 8.1, 8.2, 8.3, 8.4, 8.5
    """
    try:
        # Download file with tenant verification
        import_service = PortfolioImportService(db)
        file_content, filename, content_type = await import_service.download_file(
            attachment_id=attachment_id,
            tenant_id=current_user.tenant_id
        )

        if file_content is None:
            raise_not_found_error(f"File attachment {attachment_id} not found")

        # Return file with appropriate headers
        return Response(
            content=file_content,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'}
        )
    except (FileStorageError, FileUploadError) as e:
        raise InvestmentError(str(e))
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to download file: {str(e)}")

@investment_router.post("/holdings-files/{attachment_id}/reprocess", response_model=FileAttachmentDetailResponse)
# @require_feature("investments")  # Temporarily disabled for testing
async def reprocess_portfolio_file(
    attachment_id: int,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reprocess a previously uploaded file.

    Resets the processing status and enqueues a new background task.
    Verifies tenant ownership before allowing reprocessing.

    Requirements: 10.3, 19.1, 19.2, 19.3, 19.4, 19.5, 8.1, 8.2, 8.3, 8.4, 8.5
    """
    try:
        # Reprocess file attachment with tenant verification
        import_service = PortfolioImportService(db)
        attachment = await import_service.reprocess_file(
            attachment_id=attachment_id,
            tenant_id=current_user.tenant_id,
            user_email=current_user.email
        )

        return FileAttachmentDetailResponse.model_validate(attachment)
    except (FileStorageError, FileUploadError) as e:
        raise InvestmentError(str(e))
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to reprocess file: {str(e)}")


@investment_router.delete("/holdings-files/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
# @require_feature("investments")  # Temporarily disabled for testing
async def delete_portfolio_file(
    attachment_id: int,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a file attachment.

    Removes the file from both local and cloud storage.
    Verifies tenant ownership before allowing deletion.

    Requirements: 14.1, 14.2, 19.1, 19.2, 19.3, 19.4, 19.5, 8.1, 8.2, 8.3, 8.4, 8.5
    """
    try:
        # Delete file attachment with tenant verification
        import_service = PortfolioImportService(db)
        success = import_service.delete_file_attachment(
            attachment_id=attachment_id,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id
        )

        if not success:
            raise_not_found_error(f"File attachment {attachment_id} not found")

        return None
    except (FileStorageError, FileUploadError) as e:
        raise InvestmentError(str(e))
    except InvestmentError:
        raise
    except Exception as e:
        raise InvestmentError(f"Failed to delete file attachment: {str(e)}")
