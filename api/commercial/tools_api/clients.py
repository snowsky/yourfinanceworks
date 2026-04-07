"""
Tools API — Client endpoints.
Exposes read+write client operations for agent consumption.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.models.database import get_master_db

from .deps import (
    AuthContext,
    ToolResponse,
    get_api_auth_context,
    get_tenant_db,
    require_write,
)

router = APIRouter(prefix="/tools/clients", tags=["tools-clients"])
logger = logging.getLogger(__name__)

# Clients are a core entity — no domain-level gating, just require authentication.


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CreateClientBody(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    company: Optional[str] = None
    preferred_currency: Optional[str] = None


class UpdateClientBody(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    company: Optional[str] = None
    preferred_currency: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def list_clients(
    skip: int = 0,
    limit: int = 100,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
):
    """List all clients. Requires authentication."""
    from core.models.models_per_tenant import Client

    clients = (
        tenant_db.query(Client)
        .order_by(Client.name)
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )
    data = [_serialize_client(c) for c in clients]
    return ToolResponse(success=True, data=data, count=len(data))


@router.get("/with-outstanding-balance")
async def list_clients_with_balance(
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
):
    """List clients with outstanding balance > 0. Requires authentication."""
    from core.models.models_per_tenant import Client

    clients = (
        tenant_db.query(Client)
        .filter(Client.balance > 0)
        .order_by(Client.balance.desc())
        .all()
    )
    data = [_serialize_client(c) for c in clients]
    return ToolResponse(success=True, data=data, count=len(data))


@router.get("/{client_id}")
async def get_client(
    client_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
):
    """Get a single client by ID. Requires authentication."""
    return ToolResponse(success=True, data=_serialize_client(_get_or_404(tenant_db, client_id)))


@router.post("/")
async def create_client(
    body: CreateClientBody,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
):
    """Create a new client. Requires write permission."""
    require_write(auth_context)

    from core.models.models_per_tenant import Client

    client = Client(
        name=body.name,
        email=body.email,
        phone=body.phone,
        address=body.address,
        company=body.company,
        preferred_currency=body.preferred_currency,
    )
    tenant_db.add(client)
    tenant_db.commit()
    tenant_db.refresh(client)
    logger.info("Tools API: created client id=%s (api_key=%s)", client.id, auth_context.api_key_id)
    return ToolResponse(success=True, data=_serialize_client(client), message="Client created")


@router.patch("/{client_id}")
async def update_client(
    client_id: int,
    body: UpdateClientBody,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
):
    """Update a client. Requires write permission."""
    require_write(auth_context)

    client = _get_or_404(tenant_db, client_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    client.updated_at = datetime.now(timezone.utc)
    tenant_db.commit()
    tenant_db.refresh(client)
    return ToolResponse(success=True, data=_serialize_client(client), message="Client updated")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, client_id: int):
    from core.models.models_per_tenant import Client
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return c


def _serialize_client(c) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "company": c.company,
        "balance": c.balance,
        "paid_amount": c.paid_amount,
        "preferred_currency": c.preferred_currency,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
