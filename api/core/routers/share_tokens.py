import uuid
import logging
import math
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.models.database import (
    get_db,
    get_master_db,
    SessionLocal,
    clear_tenant_context,
    get_tenant_context,
    set_tenant_context,
)
from core.models.models import MasterUser, ShareToken
from core.models.models_per_tenant import (
    AuditLog, Settings,
    Invoice, InvoiceItem, Expense, Payment, Client,
    BankStatement, BankStatementTransaction,
)
from core.routers.auth import get_current_user
from core.utils.auth import get_password_hash, verify_password
from core.schemas.share_token import (
    ALLOWED_RECORD_TYPES,
    ShareTokenAccessRequest,
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sharing"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")


def _active_tenant_id(current_user: MasterUser) -> int:
    """Use the request's active tenant, falling back to the user's default tenant."""
    try:
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    return tenant_id or current_user.tenant_id


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
        access_type=share.access_type,
        security_question=share.security_question,
        one_time=share.max_access_count == 1,
        access_count=share.access_count or 0,
        max_access_count=share.max_access_count,
    )


def _safe_float(value: Optional[float], default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _get_sharing_settings(db: Session) -> dict:
    defaults = {
        "allow_public_links": True,
        "allow_password_links": True,
        "allow_question_links": True,
        "require_expiration": True,
    }
    record = db.query(Settings).filter(Settings.key == "sharing_settings").first()
    if record and record.value:
        return {**defaults, **record.value}
    return defaults


def _enforce_sharing_settings(payload: ShareTokenCreate, db: Session) -> None:
    settings = _get_sharing_settings(db)
    if payload.access_type == "public" and not settings.get("allow_public_links", True):
        raise HTTPException(status_code=403, detail="Public share links are disabled")
    if payload.access_type == "password" and not settings.get("allow_password_links", True):
        raise HTTPException(status_code=403, detail="Password share links are disabled")
    if payload.access_type == "question" and not settings.get("allow_question_links", True):
        raise HTTPException(status_code=403, detail="Question and answer share links are disabled")
    if settings.get("require_expiration", True) and payload.expires_in_hours == 0:
        raise HTTPException(status_code=400, detail="Share links must expire")


def _normalize_answer(answer: Optional[str]) -> str:
    return (answer or "").strip().casefold()


def _access_required_response(share: ShareToken):
    raise HTTPException(
        status_code=401,
        detail={
            "code": "share_access_required",
            "access_type": share.access_type,
            "security_question": share.security_question,
        },
    )


def _validate_share_access(share: ShareToken, payload: Optional[ShareTokenAccessRequest]) -> None:
    if share.max_access_count is not None and (share.access_count or 0) >= share.max_access_count:
        raise HTTPException(status_code=410, detail="This link has already been used")

    if share.access_type == "public":
        return

    if not payload:
        _access_required_response(share)

    if share.access_type == "password":
        if not share.password_hash or not payload.password:
            _access_required_response(share)
        if not verify_password(payload.password, share.password_hash):
            raise HTTPException(status_code=403, detail="Incorrect password")
        return

    if share.access_type == "question":
        answer = _normalize_answer(payload.security_answer)
        if not share.security_answer_hash or not answer:
            _access_required_response(share)
        if not verify_password(answer, share.security_answer_hash):
            raise HTTPException(status_code=403, detail="Incorrect answer")
        return

    raise HTTPException(status_code=400, detail="Unsupported share access type")


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------

@router.post("/share-tokens/", response_model=ShareTokenResponse)
def create_share_token(
    payload: ShareTokenCreate,
    request: Request,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
):
    """Generate a shareable link token for a record."""
    if payload.record_type not in ALLOWED_RECORD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid record_type. Must be one of: {', '.join(sorted(ALLOWED_RECORD_TYPES))}",
        )
    _enforce_sharing_settings(payload, db)

    now = datetime.now(timezone.utc)
    expires_at = None if payload.expires_in_hours == 0 else now + timedelta(hours=payload.expires_in_hours or 1)
    tenant_id = _active_tenant_id(current_user)

    password_hash = get_password_hash(payload.password) if payload.access_type == "password" and payload.password else None
    security_answer_hash = (
        get_password_hash(_normalize_answer(payload.security_answer))
        if payload.access_type == "question" and payload.security_answer
        else None
    )

    share = ShareToken(
        token=uuid.uuid4().hex,
        tenant_id=tenant_id,
        record_type=payload.record_type,
        record_id=payload.record_id,
        created_by_user_id=current_user.id,
        expires_at=expires_at,
        access_type=payload.access_type,
        password_hash=password_hash,
        security_question=payload.security_question.strip() if payload.security_question else None,
        security_answer_hash=security_answer_hash,
        max_access_count=1 if payload.one_time else None,
        access_count=0,
    )
    master_db.add(share)
    master_db.commit()
    master_db.refresh(share)

    try:
        db.add(AuditLog(
            user_id=current_user.id,
            user_email=current_user.email,
            action="SHARE_TOKEN_CREATED",
            resource_type=payload.record_type.upper(),
            resource_id=str(payload.record_id),
            details={
                "token": share.token,
                "record_type": payload.record_type,
                "record_id": payload.record_id,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "access_type": payload.access_type,
                "one_time": payload.one_time,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="success",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
    except Exception:
        logger.exception("Failed to write SHARE_TOKEN_CREATED audit log")
        try:
            db.rollback()
        except Exception:
            pass

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
            ShareToken.tenant_id == _active_tenant_id(current_user),
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
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
):
    """Revoke a share token so the public link no longer works."""
    share = (
        master_db.query(ShareToken)
        .filter(
            ShareToken.token == token,
            ShareToken.tenant_id == _active_tenant_id(current_user),
        )
        .first()
    )
    if not share:
        raise HTTPException(status_code=404, detail="Token not found")
    share.is_active = False
    master_db.commit()

    try:
        db.add(AuditLog(
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
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
    except Exception:
        logger.exception("Failed to write SHARE_TOKEN_REVOKED audit log")
        try:
            db.rollback()
        except Exception:
            pass


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
                description=tx.description or "",
                amount=_safe_float(tx.amount, 0) or 0,
                transaction_type=tx.transaction_type or "debit",
                balance=_safe_float(tx.balance),
                category=tx.category,
            )
            for tx in sorted(statement.transactions or [], key=lambda t: t.date)
        ]
        return PublicBankStatementView(
            id=statement.id,
            original_filename=statement.original_filename,
            bank_name=statement.bank_name,
            card_type=statement.card_type or "debit",
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


def _get_shared_record_response(token: str, request: Request, access_payload: Optional[ShareTokenAccessRequest] = None):
    """Public endpoint helper. Returns a sanitized view after optional link-level access checks."""
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

        from core.services.tenant_database_manager import tenant_db_manager
        TenantSession = tenant_db_manager.get_tenant_session(share.tenant_id)
        tenant_db = TenantSession()
        try:
            set_tenant_context(share.tenant_id)

            if share.expires_at and share.expires_at < datetime.now(timezone.utc):
                try:
                    tenant_db.add(AuditLog(
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
                        created_at=datetime.now(timezone.utc),
                    ))
                    tenant_db.commit()
                except Exception:
                    logger.exception("Failed to write SHARE_TOKEN_EXPIRED audit log")
                    try:
                        tenant_db.rollback()
                    except Exception:
                        pass
                raise HTTPException(status_code=410, detail="This link has expired")

            _validate_share_access(share, access_payload)
            result = _fetch_public_record(tenant_db, share.record_type, share.record_id)
            share.access_count = (share.access_count or 0) + 1
            master_db.commit()

            try:
                tenant_db.add(AuditLog(
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
                        "access_count": share.access_count,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="success",
                    created_at=datetime.now(timezone.utc),
                ))
                tenant_db.commit()
            except Exception:
                logger.exception("Failed to write SHARE_TOKEN_ACCESSED audit log")
                try:
                    tenant_db.rollback()
                except Exception:
                    pass

            return result
        finally:
            clear_tenant_context()
            tenant_db.close()
    finally:
        master_db.close()


@router.get("/shared/{token}")
def get_shared_record(token: str, request: Request):
    """Public endpoint. Open links return immediately; protected links describe required access."""
    return _get_shared_record_response(token, request)


@router.post("/shared/{token}/access")
def get_protected_shared_record(token: str, payload: ShareTokenAccessRequest, request: Request):
    """Public endpoint for password or question-protected shared records."""
    return _get_shared_record_response(token, request, payload)
