"""
External Developer API router — provides read endpoints for financial domains
(expenses, invoices, bank statements, investment portfolios) secured by API key.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from core.models.database import get_db, get_master_db, set_tenant_context  # get_db used via get_tenant_db
from core.models.api_models import APIClient
from core.services.external_api_auth_service import ExternalAPIAuthService, AuthContext
from core.schemas.api_schemas import (
    ExternalExpenseResponse,
    ExternalInvoiceResponse,
    ExternalStatementResponse,
    ExternalPortfolioResponse,
)

router = APIRouter(prefix="/external", tags=["developer-api"])
logger = logging.getLogger(__name__)

auth_service = ExternalAPIAuthService()


async def get_api_auth_context(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    master_db: Session = Depends(get_master_db),
) -> AuthContext:
    """Authenticate using API key from Authorization or X-API-Key header.

    Reuses the AuthContext already set by ExternalAPIAuthMiddleware when
    present to avoid calling authenticate_api_key twice (which would
    double-increment total_requests). Also re-calls set_tenant_context
    in this scope because BaseHTTPMiddleware runs call_next in a separate
    async task, so ContextVars set there do not carry into route handlers.
    """
    # Reuse auth already performed by middleware — avoids double-counting
    middleware_auth: Optional[AuthContext] = getattr(request.state, "auth", None)
    if middleware_auth and middleware_auth.is_authenticated:
        if middleware_auth.tenant_id:
            set_tenant_context(middleware_auth.tenant_id)
        return middleware_auth

    # Fallback: middleware was bypassed (e.g. direct test calls)
    api_key = None
    if authorization:
        api_key = authorization[7:] if authorization.startswith("Bearer ") else authorization
    if not api_key and x_api_key:
        api_key = x_api_key

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide via Authorization header (Bearer <key>) or X-API-Key header.",
        )

    client_ip = request.client.host if request.client else "unknown"
    auth_context = await auth_service.authenticate_api_key(master_db, api_key, client_ip)

    if not auth_context:
        raise HTTPException(status_code=401, detail="Invalid API key or access denied")

    if auth_context.tenant_id:
        set_tenant_context(auth_context.tenant_id)

    return auth_context


def get_tenant_db(
    auth_context: AuthContext = Depends(get_api_auth_context),
) -> Session:
    """Get tenant DB session — requires auth context to be resolved first so tenant context is set."""
    yield from get_db()


def _check_domain_access(master_db: Session, auth_context: AuthContext, domain: str):
    """Raise 403 if the API key does not have access to the requested domain."""
    api_client = master_db.query(APIClient).filter(
        APIClient.client_id == auth_context.api_key_id
    ).first()
    if not api_client or domain not in (api_client.allowed_document_types or []):
        raise HTTPException(
            status_code=403,
            detail=f"'{domain}' domain is not licensed for this API key.",
        )


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

@router.get("/expenses/")
async def list_expenses(
    skip: int = 0,
    limit: int = 100,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """List expenses for the tenant. Requires 'expense' domain access."""
    _check_domain_access(master_db, auth_context, "expense")

    from core.models.models_per_tenant import Expense
    expenses = (
        tenant_db.query(Expense)
        .filter(Expense.is_deleted == False)
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )
    return [ExternalExpenseResponse.from_orm(e) for e in expenses]


@router.get("/expenses/{expense_id}")
async def get_expense(
    expense_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Get a single expense by ID. Requires 'expense' domain access."""
    _check_domain_access(master_db, auth_context, "expense")

    from core.models.models_per_tenant import Expense
    expense = tenant_db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.is_deleted == False,
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return ExternalExpenseResponse.from_orm(expense)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@router.get("/invoices/")
async def list_invoices(
    skip: int = 0,
    limit: int = 100,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """List invoices for the tenant. Requires 'invoice' domain access."""
    _check_domain_access(master_db, auth_context, "invoice")

    from core.models.models_per_tenant import Invoice
    invoices = (
        tenant_db.query(Invoice)
        .filter(Invoice.is_deleted == False)
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )
    return [ExternalInvoiceResponse.from_orm(inv) for inv in invoices]


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Get a single invoice by ID. Requires 'invoice' domain access."""
    _check_domain_access(master_db, auth_context, "invoice")

    from core.models.models_per_tenant import Invoice
    invoice = tenant_db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.is_deleted == False,
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return ExternalInvoiceResponse.from_orm(invoice)


# ---------------------------------------------------------------------------
# Bank Statements
# ---------------------------------------------------------------------------

@router.get("/statements/")
async def list_statements(
    skip: int = 0,
    limit: int = 100,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """List bank statements for the tenant. Requires 'statement' domain access."""
    _check_domain_access(master_db, auth_context, "statement")

    from core.models.models_per_tenant import BankStatement
    statements = (
        tenant_db.query(BankStatement)
        .filter(BankStatement.is_deleted == False)
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )
    return [
        {
            "id": s.id,
            "statement_date": s.created_at,
            "account_name": s.original_filename,
            "status": s.status,
            "total_transactions": s.extracted_count,
        }
        for s in statements
    ]


@router.get("/statements/{statement_id}")
async def get_statement(
    statement_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Get a bank statement with transactions. Requires 'statement' domain access."""
    _check_domain_access(master_db, auth_context, "statement")

    from core.models.models_per_tenant import BankStatement
    statement = tenant_db.query(BankStatement).filter(
        BankStatement.id == statement_id,
        BankStatement.is_deleted == False,
    ).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    return ExternalStatementResponse.from_orm(statement)


# ---------------------------------------------------------------------------
# Investment Portfolios
# ---------------------------------------------------------------------------

@router.get("/portfolio/")
async def list_portfolios(
    skip: int = 0,
    limit: int = 100,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """List investment portfolios. Requires 'portfolio' domain access."""
    _check_domain_access(master_db, auth_context, "portfolio")

    try:
        from plugins.investments.services.portfolio_service import PortfolioService
        svc = PortfolioService(tenant_db)
        results, total = svc.get_portfolios_paginated(
            tenant_id=auth_context.tenant_id,
            skip=skip,
            limit=min(limit, 500),
        )
        return [
            ExternalPortfolioResponse(
                id=portfolio.id,
                name=portfolio.name,
                portfolio_type=portfolio.portfolio_type.value if hasattr(portfolio.portfolio_type, "value") else str(portfolio.portfolio_type),
                total_value=float(summary.get("total_value", 0) or 0),
                holdings_count=summary.get("holdings_count", 0),
            )
            for portfolio, summary in results
        ]
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Investment portfolio plugin is not available",
        )


@router.get("/portfolio/{portfolio_id}")
async def get_portfolio(
    portfolio_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Get a single portfolio with summary. Requires 'portfolio' domain access."""
    _check_domain_access(master_db, auth_context, "portfolio")

    try:
        from plugins.investments.services.portfolio_service import PortfolioService
        svc = PortfolioService(tenant_db)
        result = svc.get_portfolio_with_summary(portfolio_id, auth_context.tenant_id)
        if not result:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        portfolio, summary = result
        return ExternalPortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            portfolio_type=portfolio.portfolio_type.value if hasattr(portfolio.portfolio_type, "value") else str(portfolio.portfolio_type),
            total_value=float(summary.get("total_value", 0) or 0),
            holdings_count=summary.get("holdings_count", 0),
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Investment portfolio plugin is not available",
        )
