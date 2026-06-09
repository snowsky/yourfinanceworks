"""Client-portal endpoints (public + client-authenticated).

Magic-link login for a tenant's clients. These paths bypass the staff tenant
middleware and manage their own tenant context. Mounted under
``/api/v1/client-portal``.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.models.database import get_master_db, set_tenant_context, clear_tenant_context
from core.models.models import Tenant
from core.models.models_per_tenant import Client, backfill_client_email_hashes
from core.services.tenant_database_manager import tenant_db_manager
from core.services.client_email import build_tenant_email_service
from core.services.email_service import EmailMessage
from core.utils.client_email_hash import compute_email_hash, normalize_email
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


def _send_magic_link(tenant_db: Session, tenant: Tenant, email: str, raw_token: str) -> None:
    try:
        email_service = build_tenant_email_service(tenant_db)
        if not email_service:
            logger.warning("client portal: no email config for tenant %s; cannot send link", tenant.id)
            return
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
        email_service.send_email(
            EmailMessage(
                to_email=email,
                to_name=email,
                subject=subject,
                html_body=html,
                text_body=text,
                from_email=from_email,
                from_name=from_name,
            )
        )
    except Exception:
        logger.exception("client portal: failed to send magic link for tenant %s", tenant.id)


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
            _send_magic_link(tenant_db, tenant, body.email, token.token)
    finally:
        clear_tenant_context()
        tenant_db.close()

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
