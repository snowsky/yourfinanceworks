import uuid
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.models.database import get_db, get_master_db, SessionLocal, set_tenant_context, clear_tenant_context
from core.models.models import MasterUser, ShareToken
from core.models.models_per_tenant import (
    Invoice, InvoiceItem, Expense, Payment, Client,
    BankStatement, BankStatementTransaction,
)
from core.routers.auth import get_current_user
from core.schemas.share_token import (
    ALLOWED_RECORD_TYPES,
    ShareTokenCreate,
    ShareTokenResponse,
    PublicInvoiceView,
    PublicInvoiceItem,
    PublicExpenseView,
    PublicPaymentView,
    PublicClientView,
    PublicBankStatementView,
    PublicBankStatementTransaction,
    PublicPortfolioView,
    PublicPortfolioHolding,
)

from core.utils.audit import log_audit_event_master

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sharing"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")


def _build_share_url(token: str) -> str:
    return f"{FRONTEND_URL}/shared/{token}"


def _token_to_response(share: ShareToken) -> ShareTokenResponse:
    return ShareTokenResponse(
        token=share.token,
        record_type=share.record_type,
        record_id=share.record_id,
        share_url=_build_share_url(share.token),
        created_at=share.created_at,
        expires_at=share.expires_at,
        is_active=share.is_active,
    )


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------

@router.post("/share-tokens/", response_model=ShareTokenResponse)
def create_share_token(
    payload: ShareTokenCreate,
    request: Request,
    current_user: MasterUser = Depends(get_current_user),
    master_db: Session = Depends(get_master_db),
):
    """Generate a shareable link token for a record. Idempotent — returns existing token if one is active."""
    if payload.record_type not in ALLOWED_RECORD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid record_type. Must be one of: {', '.join(sorted(ALLOWED_RECORD_TYPES))}",
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)

    # Idempotency: return existing active non-expired token for this record
    existing = (
        master_db.query(ShareToken)
        .filter(
            ShareToken.tenant_id == current_user.tenant_id,
            ShareToken.record_type == payload.record_type,
            ShareToken.record_id == payload.record_id,
            ShareToken.is_active == True,
            ShareToken.expires_at > now,
        )
        .first()
    )
    if existing:
        return _token_to_response(existing)

    share = ShareToken(
        token=uuid.uuid4().hex,
        tenant_id=current_user.tenant_id,
        record_type=payload.record_type,
        record_id=payload.record_id,
        created_by_user_id=current_user.id,
        expires_at=expires_at,
    )
    master_db.add(share)
    master_db.commit()
    master_db.refresh(share)

    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="SHARE_TOKEN_CREATED",
        resource_type=payload.record_type.upper(),
        resource_id=str(payload.record_id),
        details={
            "token": share.token,
            "record_type": payload.record_type,
            "record_id": payload.record_id,
            "expires_at": expires_at.isoformat(),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
        tenant_id=current_user.tenant_id,
    )

    return _token_to_response(share)


@router.get("/share-tokens/{record_type}/{record_id}", response_model=Optional[ShareTokenResponse])
def get_share_token(
    record_type: str,
    record_id: int,
    current_user: MasterUser = Depends(get_current_user),
    master_db: Session = Depends(get_master_db),
):
    """Get the active share token for a record, if one exists."""
    share = (
        master_db.query(ShareToken)
        .filter(
            ShareToken.tenant_id == current_user.tenant_id,
            ShareToken.record_type == record_type,
            ShareToken.record_id == record_id,
            ShareToken.is_active == True,
        )
        .first()
    )
    if not share:
        return None
    return _token_to_response(share)


@router.delete("/share-tokens/{token}", status_code=204)
def revoke_share_token(
    token: str,
    request: Request,
    current_user: MasterUser = Depends(get_current_user),
    master_db: Session = Depends(get_master_db),
):
    """Revoke a share token so the public link no longer works."""
    share = (
        master_db.query(ShareToken)
        .filter(
            ShareToken.token == token,
            ShareToken.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not share:
        raise HTTPException(status_code=404, detail="Token not found")
    share.is_active = False
    master_db.commit()

    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="SHARE_TOKEN_REVOKED",
        resource_type=share.record_type.upper(),
        resource_id=str(share.record_id),
        details={
            "token": token,
            "record_type": share.record_type,
            "record_id": share.record_id,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
        tenant_id=current_user.tenant_id,
    )


# ---------------------------------------------------------------------------
# Public endpoint — no auth, no tenant context dependency
# ---------------------------------------------------------------------------

def _fetch_public_record(
    tenant_db: Session,
    record_type: str,
    record_id: int,
) -> Union[
    PublicInvoiceView,
    PublicExpenseView,
    PublicPaymentView,
    PublicClientView,
    PublicBankStatementView,
    PublicPortfolioView,
]:
    if record_type == "invoice":
        invoice = (
            tenant_db.query(Invoice)
            .filter(Invoice.id == record_id, Invoice.is_deleted == False)
            .first()
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Record not found")
        client_name = None
        client_company = None
        if invoice.client:
            client_name = invoice.client.name
            client_company = invoice.client.company
        items = [
            PublicInvoiceItem(
                description=item.description,
                quantity=item.quantity,
                price=item.price,
                amount=item.amount,
                unit_of_measure=item.unit_of_measure,
            )
            for item in (invoice.items or [])
        ]
        return PublicInvoiceView(
            id=invoice.id,
            number=invoice.number,
            amount=invoice.amount,
            currency=invoice.currency,
            status=invoice.status,
            due_date=invoice.due_date,
            created_at=invoice.created_at,
            description=invoice.description,
            subtotal=invoice.subtotal,
            discount_type=invoice.discount_type,
            discount_value=invoice.discount_value,
            payer=invoice.payer,
            client_name=client_name,
            client_company=client_company,
            items=items,
        )

    elif record_type == "expense":
        expense = (
            tenant_db.query(Expense)
            .filter(Expense.id == record_id, Expense.is_deleted == False)
            .first()
        )
        if not expense:
            raise HTTPException(status_code=404, detail="Record not found")
        return PublicExpenseView(
            id=expense.id,
            amount=expense.amount,
            currency=expense.currency,
            expense_date=expense.expense_date,
            category=expense.category,
            vendor=expense.vendor,
            total_amount=expense.total_amount,
            payment_method=expense.payment_method,
            status=expense.status,
            created_at=expense.created_at,
        )

    elif record_type == "payment":
        payment = (
            tenant_db.query(Payment)
            .filter(Payment.id == record_id)
            .first()
        )
        if not payment:
            raise HTTPException(status_code=404, detail="Record not found")
        invoice_number = None
        if payment.invoice:
            invoice_number = payment.invoice.number
        return PublicPaymentView(
            id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            invoice_number=invoice_number,
            created_at=payment.created_at,
        )

    elif record_type == "client":
        client = (
            tenant_db.query(Client)
            .filter(Client.id == record_id)
            .first()
        )
        if not client:
            raise HTTPException(status_code=404, detail="Record not found")
        return PublicClientView(
            id=client.id,
            name=client.name,
            company=client.company,
            created_at=client.created_at,
        )

    elif record_type == "bank_statement":
        statement = (
            tenant_db.query(BankStatement)
            .filter(BankStatement.id == record_id, BankStatement.is_deleted == False)
            .first()
        )
        if not statement:
            raise HTTPException(status_code=404, detail="Record not found")
        transactions = [
            PublicBankStatementTransaction(
                date=tx.date,
                description=tx.description,
                amount=tx.amount,
                transaction_type=tx.transaction_type,
                balance=tx.balance,
                category=tx.category,
            )
            for tx in sorted(statement.transactions or [], key=lambda t: t.date)
        ]
        return PublicBankStatementView(
            id=statement.id,
            original_filename=statement.original_filename,
            bank_name=statement.bank_name,
            card_type=statement.card_type,
            status=statement.status,
            extracted_count=statement.extracted_count,
            created_at=statement.created_at,
            transactions=transactions,
        )

    elif record_type == "portfolio":
        try:
            from plugins.investments.models import InvestmentPortfolio, InvestmentHolding
        except ImportError:
            raise HTTPException(status_code=404, detail="Record not found")
        portfolio = (
            tenant_db.query(InvestmentPortfolio)
            .filter(InvestmentPortfolio.id == record_id, InvestmentPortfolio.is_archived == False)
            .first()
        )
        if not portfolio:
            raise HTTPException(status_code=404, detail="Record not found")
        holdings = [
            PublicPortfolioHolding(
                security_symbol=h.security_symbol,
                security_name=h.security_name,
                security_type=h.security_type,
                asset_class=h.asset_class,
                quantity=float(h.quantity),
                currency=h.currency,
            )
            for h in (portfolio.holdings or [])
            if not h.is_closed
        ]
        return PublicPortfolioView(
            id=portfolio.id,
            name=portfolio.name,
            portfolio_type=portfolio.portfolio_type,
            currency=portfolio.currency,
            created_at=portfolio.created_at,
            holdings=holdings,
        )

    raise HTTPException(status_code=400, detail="Unknown record type")


@router.get("/shared/{token}")
def get_shared_record(token: str, request: Request):
    """Public endpoint — no authentication required. Returns a sanitized view of a shared record."""
    master_db = SessionLocal()
    try:
        share = (
            master_db.query(ShareToken)
            .filter(ShareToken.token == token, ShareToken.is_active == True)
            .first()
        )
        if not share:
            raise HTTPException(status_code=404, detail="Link not found or has been revoked")

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Look up the token owner for audit context
        owner = master_db.query(MasterUser).filter(MasterUser.id == share.created_by_user_id).first()
        owner_id = owner.id if owner else share.created_by_user_id
        owner_email = owner.email if owner else "unknown"

        if share.expires_at and share.expires_at < datetime.now(timezone.utc):
            log_audit_event_master(
                db=master_db,
                user_id=owner_id,
                user_email=owner_email,
                action="SHARE_TOKEN_EXPIRED",
                resource_type=share.record_type.upper(),
                resource_id=str(share.record_id),
                details={
                    "token": token,
                    "record_type": share.record_type,
                    "record_id": share.record_id,
                    "expired_at": share.expires_at.isoformat(),
                    "accessed_from": ip_address,
                },
                ip_address=ip_address,
                user_agent=user_agent,
                status="failure",
                error_message="Share link expired",
                tenant_id=share.tenant_id,
            )
            raise HTTPException(status_code=410, detail="This link has expired")

        from core.services.tenant_database_manager import tenant_db_manager
        TenantSession = tenant_db_manager.get_tenant_session(share.tenant_id)
        tenant_db = TenantSession()
        try:
            # Set tenant context so EncryptedColumn can decrypt fields correctly
            set_tenant_context(share.tenant_id)
            result = _fetch_public_record(tenant_db, share.record_type, share.record_id)
        finally:
            clear_tenant_context()
            tenant_db.close()

        log_audit_event_master(
            db=master_db,
            user_id=owner_id,
            user_email=owner_email,
            action="SHARE_TOKEN_ACCESSED",
            resource_type=share.record_type.upper(),
            resource_id=str(share.record_id),
            details={
                "token": token,
                "record_type": share.record_type,
                "record_id": share.record_id,
                "accessed_from": ip_address,
            },
            ip_address=ip_address,
            user_agent=user_agent,
            status="success",
            tenant_id=share.tenant_id,
        )

        return result
    finally:
        master_db.close()
