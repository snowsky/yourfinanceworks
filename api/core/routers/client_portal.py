"""Client-portal endpoints (public + client-authenticated).

Magic-link login for a tenant's clients. These paths bypass the staff tenant
middleware and manage their own tenant context. Mounted under
``/api/v1/client-portal``.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.models.database import get_master_db, set_tenant_context, clear_tenant_context
from core.models.models import Tenant
from core.models.models_per_tenant import Client, Invoice, backfill_client_email_hashes
from core.services.tenant_database_manager import tenant_db_manager
from core.services.client_email import build_tenant_email_service
from core.services.email_service import EmailMessage
from core.services.invoice_branding import get_invoice_branding
from core.utils.client_email_hash import compute_email_hash, normalize_email
from core.utils.pdf_generator import generate_invoice_pdf
from core.utils.rate_limiter import record_and_check
from core.utils.feature_gate import check_feature
from core.services.client_portal_auth import (
    LOGIN_LINK_TTL_MINUTES,
    ClientContext,
    consume_login_token,
    create_login_token,
    decode_client_session_token,  # noqa: F401  (kept for explicitness)
    get_current_client,
    mint_client_session_token,
    resolve_tenant_by_portal_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client-portal", tags=["client-portal"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")

# When DEBUG is on, request-link returns the verify link + email-send status in
# its response (for local testing). MUST be off in production.
_DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Tenants whose existing clients have had email_hash backfilled this process —
# a one-time lazy migration so pre-existing clients can log in immediately.
_BACKFILLED_TENANTS: set = set()

# Uniform response so an attacker can't tell whether an email matched a client.
_GENERIC_LINK_RESPONSE = {
    "status": "ok",
    "message": "If that email matches an account, a login link is on its way.",
}


class RequestLinkBody(BaseModel):
    email: str


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _send_magic_link(tenant_db: Session, tenant: Tenant, email: str, raw_token: str) -> bool:
    """Send the magic-link email. Returns True if the provider accepted it."""
    try:
        email_service = build_tenant_email_service(tenant_db)
        if not email_service:
            logger.warning("client portal: no email config for tenant %s; cannot send link", tenant.id)
            return False
        link = f"{FRONTEND_URL}/portal/verify/{raw_token}"
        subject = f"Your {tenant.name} invoice portal sign-in link"
        html = (
            f"<p>Hello,</p>"
            f"<p>Use the link below to view your invoices from {tenant.name}. "
            f"It expires in {LOGIN_LINK_TTL_MINUTES} minutes and can only be used once.</p>"
            f'<p><a href="{link}">View my invoices</a></p>'
            f"<p>If you didn't request this, you can safely ignore this email.</p>"
        )
        text = (
            f"View your invoices from {tenant.name}: {link}\n"
            f"(expires in {LOGIN_LINK_TTL_MINUTES} minutes, one-time use)."
        )
        from_email = getattr(email_service.config, "from_email", None) or "noreply@yourfinanceworks.com"
        from_name = getattr(email_service.config, "from_name", None) or tenant.name
        return bool(email_service.send_email(
            EmailMessage(
                to_email=email,
                to_name=email,
                subject=subject,
                html_body=html,
                text_body=text,
                from_email=from_email,
                from_name=from_name,
            )
        ))
    except Exception:
        logger.exception("client portal: failed to send magic link for tenant %s", tenant.id)
        return False


@router.post("/{portal_public_id}/request-link")
def request_login_link(
    portal_public_id: str,
    body: RequestLinkBody,
    request: Request,
    master_db: Session = Depends(get_master_db),
):
    """Email a one-time login link if the address matches a client. Always
    returns the same response (no account enumeration)."""
    tenant = resolve_tenant_by_portal_id(master_db, portal_public_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Portal not found")

    ip = _client_ip(request)
    normalized = normalize_email(body.email)
    if (
        record_and_check(f"cportal_link:ip:{ip}", max_attempts=10, window_seconds=300)
        or record_and_check(f"cportal_link:{tenant.id}:{normalized}", max_attempts=5, window_seconds=300)
    ):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    debug_extra = {}
    set_tenant_context(tenant.id)
    tenant_db = tenant_db_manager.get_tenant_session(tenant.id)()
    try:
        # Feature gate (tenant-level; not an email-enumeration signal).
        check_feature("client_portal", tenant_db)

        # One-time lazy backfill so pre-existing clients (created before the
        # email_hash column) can be found by email.
        if tenant.id not in _BACKFILLED_TENANTS:
            try:
                backfill_client_email_hashes(tenant_db, tenant.id)
            except Exception:
                logger.exception("client portal: email_hash backfill failed for tenant %s", tenant.id)
            _BACKFILLED_TENANTS.add(tenant.id)

        email_hash = compute_email_hash(body.email, tenant.id)
        client = (
            tenant_db.query(Client).filter(Client.email_hash == email_hash).first()
            if email_hash else None
        )
        if client:
            token = create_login_token(master_db, tenant.id, client.id)
            sent = _send_magic_link(tenant_db, tenant, body.email, token.token)
            if _DEBUG:
                debug_extra = {
                    "debug_client_matched": True,
                    "debug_email_sent": sent,
                    "debug_verify_url": f"{FRONTEND_URL}/portal/verify/{token.token}",
                }
        elif _DEBUG:
            debug_extra = {"debug_client_matched": False, "debug_email_sent": False}
    finally:
        clear_tenant_context()
        tenant_db.close()

    # DEBUG only (never enable in production): surface the link + send status so
    # the portal can be tested without inspecting the DB / email. Guarded on the
    # DEBUG env flag, so the no-enumeration response is unchanged in prod.
    if _DEBUG and debug_extra:
        return {**_GENERIC_LINK_RESPONSE, **debug_extra}
    return _GENERIC_LINK_RESPONSE


@router.post("/verify/{token}")
def verify_login(token: str, master_db: Session = Depends(get_master_db)):
    """Consume a magic-link token and issue a client session JWT."""
    record = consume_login_token(master_db, token)
    tenant = master_db.query(Tenant).filter(Tenant.id == record.tenant_id).first()
    if not tenant or not tenant.is_enabled:
        raise HTTPException(status_code=400, detail="This login link is no longer valid.")

    set_tenant_context(tenant.id)
    tenant_db = tenant_db_manager.get_tenant_session(tenant.id)()
    try:
        client = tenant_db.query(Client).filter(Client.id == record.client_id).first()
        if not client:
            raise HTTPException(status_code=400, detail="This login link is no longer valid.")
        access_token = mint_client_session_token(client.id, tenant.id, client.email_hash)
        profile = {
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "company_name": tenant.name,
        }
    finally:
        clear_tenant_context()
        tenant_db.close()

    return {"access_token": access_token, "token_type": "bearer", "client": profile}


@router.get("/me")
def get_me(ctx: ClientContext = Depends(get_current_client)):
    c = ctx.client
    return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "address": c.address}


class UpdateProfileBody(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


@router.patch("/me")
def update_me(body: UpdateProfileBody, ctx: ClientContext = Depends(get_current_client)):
    """Let the client update their own contact details (email is immutable)."""
    c = ctx.client
    if body.name is not None:
        new_name = body.name.strip()
        if len(new_name) < 1:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        c.name = new_name
    if body.phone is not None:
        c.phone = body.phone.strip()
    if body.address is not None:
        c.address = body.address.strip()
    ctx.db.commit()
    return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "address": c.address}


def _paid_amount(invoice: Invoice) -> float:
    return float(sum((p.amount or 0) for p in (invoice.payments or [])))


def _invoice_summary(invoice: Invoice) -> dict:
    amount = float(invoice.amount or 0)
    paid = _paid_amount(invoice)
    return {
        "id": invoice.id,
        "number": invoice.number,
        "status": invoice.status,
        "currency": invoice.currency,
        "amount": amount,
        "due_date": invoice.due_date,
        "created_at": invoice.created_at,
        "paid_amount": paid,
        "outstanding": round(amount - paid, 2),
    }


def _client_invoice_query(ctx: ClientContext):
    """Issued (non-draft, non-deleted) invoices belonging to the logged-in client."""
    return (
        ctx.db.query(Invoice)
        .filter(
            Invoice.client_id == ctx.client.id,
            Invoice.is_deleted == False,
            Invoice.status != "draft",
        )
    )


@router.get("/invoices")
def list_invoices(ctx: ClientContext = Depends(get_current_client)):
    invoices = _client_invoice_query(ctx).order_by(Invoice.created_at.desc()).all()
    return {"invoices": [_invoice_summary(i) for i in invoices]}


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, ctx: ClientContext = Depends(get_current_client)):
    invoice = _client_invoice_query(ctx).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    summary = _invoice_summary(invoice)
    summary.update({
        "subtotal": float(invoice.subtotal or 0),
        "discount_type": invoice.discount_type,
        "discount_value": float(invoice.discount_value or 0),
        "description": invoice.description,
        "items": [
            {
                "description": it.description,
                "quantity": it.quantity,
                "price": it.price,
                "amount": it.amount,
                "unit_of_measure": it.unit_of_measure,
            }
            for it in (invoice.items or [])
        ],
    })
    return summary


@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: int,
    ctx: ClientContext = Depends(get_current_client),
    master_db: Session = Depends(get_master_db),
):
    invoice = _client_invoice_query(ctx).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    tenant = master_db.query(Tenant).filter(Tenant.id == ctx.tenant_id).first()
    company_data = {
        "name": tenant.name if tenant else "Your Company",
        "email": tenant.email if tenant else "",
        "phone": tenant.phone if tenant else "",
        "address": tenant.address if tenant else "",
        "tax_id": tenant.tax_id if tenant else "",
        "logo": tenant.company_logo_url if tenant else "",
    }
    client = ctx.client
    client_data = {
        "id": client.id,
        "name": client.name,
        "email": client.email,
        "phone": client.phone or "",
        "address": client.address or "",
    }
    # The ReportLab generator expects items as dicts (item.get(...)), not ORM rows.
    item_dicts = [
        {
            "description": it.description,
            "quantity": it.quantity,
            "price": it.price,
            "amount": it.amount,
            "unit_of_measure": it.unit_of_measure,
        }
        for it in (invoice.items or [])
    ]
    invoice_data = {
        "id": invoice.id,
        "number": invoice.number,
        "date": invoice.created_at.strftime("%Y-%m-%d") if invoice.created_at else "",
        "due_date": invoice.due_date.strftime("%Y-%m-%d") if invoice.due_date else "",
        "amount": float(invoice.amount or 0),
        "currency": invoice.currency,
        "subtotal": float(invoice.subtotal or 0),
        "discount_type": invoice.discount_type,
        "discount_value": float(invoice.discount_value or 0),
        "paid_amount": _paid_amount(invoice),
        "status": invoice.status,
        "notes": invoice.notes or "",
        "items": item_dicts,
    }
    pdf_bytes = generate_invoice_pdf(
        invoice_data=invoice_data,
        client_data=client_data,
        company_data=company_data,
        items=item_dicts,
        db=ctx.db,
        show_discount=invoice.show_discount_in_pdf,
        branding=get_invoice_branding(ctx.db),
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=invoice-{invoice.number}.pdf"},
    )


@router.get("/{portal_public_id}/branding")
def get_portal_branding(portal_public_id: str, master_db: Session = Depends(get_master_db)):
    """Public — lets the portal login page render company-branded before login."""
    tenant = resolve_tenant_by_portal_id(master_db, portal_public_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Portal not found")
    set_tenant_context(tenant.id)
    tenant_db = tenant_db_manager.get_tenant_session(tenant.id)()
    try:
        branding = get_invoice_branding(tenant_db)
    finally:
        clear_tenant_context()
        tenant_db.close()
    return {
        "company_name": tenant.name,
        "company_logo_url": tenant.company_logo_url or None,
        "brand_color": branding["brand_color"],
        "accent_color": branding["accent_color"],
        "footer_text": branding.get("footer_text") or None,
    }
