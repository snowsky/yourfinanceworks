"""
Tools API — Bank Statement endpoints.
Exposes read + metadata-update + soft-delete for agent consumption.
File upload (AI processing pipeline) is deferred to Phase 2.
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
    _check_domain_access,
    get_api_auth_context,
    get_tenant_db,
    require_write,
)

router = APIRouter(prefix="/api/v1/tools/bank-statements", tags=["tools-bank-statements"])
logger = logging.getLogger(__name__)

DOMAIN = "statement"


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class UpdateStatementMetaBody(BaseModel):
    account_name: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class DeleteStatementBody(BaseModel):
    confirm_deletion: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def list_statements(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    account_name: Optional[str] = None,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """List bank statements with optional filters. Requires 'statement' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    from core.models.models_per_tenant import BankStatement

    q = tenant_db.query(BankStatement).filter(BankStatement.is_deleted == False)
    if status:
        q = q.filter(BankStatement.status == status)
    if account_name:
        q = q.filter(BankStatement.original_filename.ilike(f"%{account_name}%"))

    statements = q.order_by(BankStatement.created_at.desc()).offset(skip).limit(min(limit, 500)).all()
    data = [_serialize_statement(s) for s in statements]
    return ToolResponse(success=True, data=data, count=len(data))


@router.get("/{statement_id}")
async def get_statement(
    statement_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Get a bank statement with its transactions. Requires 'statement' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    stmt = _get_or_404(tenant_db, statement_id)
    data = _serialize_statement(stmt)
    data["transactions"] = [_serialize_transaction(t) for t in stmt.transactions]
    return ToolResponse(success=True, data=data)


@router.patch("/{statement_id}/meta")
async def update_statement_meta(
    statement_id: int,
    body: UpdateStatementMetaBody,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Update statement metadata (notes, status). Requires 'statement' domain + write permission."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    require_write(auth_context)

    stmt = _get_or_404(tenant_db, statement_id)
    if body.notes is not None:
        stmt.notes = body.notes
    if body.status is not None:
        stmt.status = body.status
    stmt.updated_at = datetime.now(timezone.utc)
    tenant_db.commit()
    tenant_db.refresh(stmt)
    return ToolResponse(success=True, data=_serialize_statement(stmt), message="Statement updated")


@router.delete("/{statement_id}")
async def delete_statement(
    statement_id: int,
    body: DeleteStatementBody,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Soft-delete a statement. Requires confirm_deletion=true, 'statement' domain + write permission."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    require_write(auth_context)

    if not body.confirm_deletion:
        raise HTTPException(status_code=422, detail="Set confirm_deletion=true to delete")

    stmt = _get_or_404(tenant_db, statement_id)
    stmt.is_deleted = True
    stmt.deleted_at = datetime.now(timezone.utc)
    tenant_db.commit()
    return ToolResponse(success=True, message=f"Statement {statement_id} deleted")


@router.post("/{statement_id}/restore")
async def restore_statement(
    statement_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Restore a soft-deleted statement. Requires 'statement' domain + write permission."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    require_write(auth_context)

    from core.models.models_per_tenant import BankStatement
    stmt = tenant_db.query(BankStatement).filter(
        BankStatement.id == statement_id, BankStatement.is_deleted == True
    ).first()
    if not stmt:
        raise HTTPException(status_code=404, detail="Deleted statement not found")

    stmt.is_deleted = False
    stmt.deleted_at = None
    tenant_db.commit()
    return ToolResponse(success=True, message=f"Statement {statement_id} restored")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, statement_id: int):
    from core.models.models_per_tenant import BankStatement
    s = db.query(BankStatement).filter(
        BankStatement.id == statement_id, BankStatement.is_deleted == False
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")
    return s


def _serialize_statement(s) -> dict:
    return {
        "id": s.id,
        "original_filename": s.original_filename,
        "status": s.status,
        "extracted_count": s.extracted_count,
        "card_type": s.card_type,
        "notes": s.notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _serialize_transaction(t) -> dict:
    return {
        "id": t.id,
        "date": t.date.isoformat() if t.date else None,
        "description": t.description,
        "amount": float(t.amount) if t.amount is not None else None,
        "transaction_type": t.transaction_type,
        "balance": float(t.balance) if t.balance is not None else None,
    }
