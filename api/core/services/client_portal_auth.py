"""Client-portal authentication core.

Passwordless magic-link login for a tenant's *clients* (not staff). Kept
deliberately separate from staff auth:

- Login tokens are one-time, short-lived ``ClientLoginToken`` rows (master DB).
- The session JWT carries ``type="client"`` and is only ever accepted by
  ``get_current_client`` — a staff token can never satisfy it, and a client
  token can never satisfy a staff dependency (its ``sub`` is an email hash, not
  a MasterUser email, and the type guard rejects it).
- The portal only ever trusts ``client_id``/``tenant_id`` from the *verified
  token*, never from request input.
"""

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from core.models.database import (
    get_master_db,
    set_tenant_context,
    clear_tenant_context,
)
from core.models.models import Tenant, ClientLoginToken
from core.models.models_per_tenant import Client
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.auth import SECRET_KEY, ALGORITHM, create_access_token

logger = logging.getLogger(__name__)

CLIENT_TOKEN_TYPE = "client"
SESSION_TTL_HOURS = 24
LOGIN_LINK_TTL_MINUTES = 60


# --- Tenant portal slug -------------------------------------------------------

def get_or_create_portal_public_id(tenant: Tenant, master_db: Session) -> str:
    """Opaque, non-sequential public id used in the portal URL."""
    if not tenant.portal_public_id:
        tenant.portal_public_id = uuid.uuid4().hex
        master_db.commit()
    return tenant.portal_public_id


def resolve_tenant_by_portal_id(master_db: Session, portal_public_id: str) -> Optional[Tenant]:
    if not portal_public_id:
        return None
    return (
        master_db.query(Tenant)
        .filter(Tenant.portal_public_id == portal_public_id, Tenant.is_enabled == True)
        .first()
    )


# --- Magic-link login tokens --------------------------------------------------

def create_login_token(master_db: Session, tenant_id: int, client_id: int) -> ClientLoginToken:
    token = ClientLoginToken(
        token=secrets.token_urlsafe(32),
        tenant_id=tenant_id,
        client_id=client_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=LOGIN_LINK_TTL_MINUTES),
        is_used=False,
    )
    master_db.add(token)
    master_db.commit()
    master_db.refresh(token)
    return token


def consume_login_token(master_db: Session, raw_token: str) -> ClientLoginToken:
    """Validate + single-use-consume a magic-link token. Raises 400 if invalid."""
    record = (
        master_db.query(ClientLoginToken)
        .filter(ClientLoginToken.token == raw_token, ClientLoginToken.is_used == False)
        .first()
    )
    if not record:
        raise HTTPException(status_code=400, detail="This login link is invalid or has already been used.")
    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This login link has expired. Please request a new one.")
    record.is_used = True
    record.used_at = datetime.now(timezone.utc)
    master_db.commit()
    return record


# --- Session JWT --------------------------------------------------------------

def mint_client_session_token(client_id: int, tenant_id: int, email_hash: Optional[str]) -> str:
    return create_access_token(
        data={
            "sub": email_hash or f"client:{tenant_id}:{client_id}",
            "type": CLIENT_TOKEN_TYPE,
            "client_id": client_id,
            "tenant_id": tenant_id,
        },
        expires_delta=timedelta(hours=SESSION_TTL_HOURS),
    )


def decode_client_session_token(token: str) -> dict:
    """Decode + validate a client session JWT. Raises 401 on anything wrong,
    including a non-client (staff) token."""
    try:
        claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    if claims.get("type") != CLIENT_TOKEN_TYPE:
        raise HTTPException(status_code=401, detail="Invalid session")
    if not claims.get("client_id") or not claims.get("tenant_id"):
        raise HTTPException(status_code=401, detail="Invalid session")
    return claims


# --- Dependency: current authenticated client ---------------------------------

@dataclass
class ClientContext:
    client: Client
    db: Session
    tenant_id: int


def get_current_client(authorization: Optional[str] = Header(None)):
    """FastAPI dependency. Resolves the client from the session JWT, opens its
    tenant DB session, and yields a ClientContext (cleaned up after the request).
    The client_portal paths bypass the staff tenant middleware, so this sets the
    tenant context itself."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    claims = decode_client_session_token(authorization.split(" ", 1)[1])
    tenant_id = int(claims["tenant_id"])
    client_id = int(claims["client_id"])

    set_tenant_context(tenant_id)
    TenantSession = tenant_db_manager.get_tenant_session(tenant_id)
    db = TenantSession()
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=401, detail="Invalid session")
        yield ClientContext(client=client, db=db, tenant_id=tenant_id)
    finally:
        clear_tenant_context()
        db.close()
