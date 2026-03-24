"""
Email reference endpoints — manual linking of RawEmail rows to documents
and search of stored emails.

Mounted under /email-integration (prefix from the parent router).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import RawEmail
from core.routers.auth import get_current_user
from core.services.document_email_reference_service import (
    DocumentEmailReferenceService,
    VALID_DOCUMENT_TYPES,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class LinkEmailBody(BaseModel):
    document_type: str
    document_id: int
    notes: Optional[str] = None


class UnlinkEmailBody(BaseModel):
    document_type: str
    document_id: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/emails/search")
async def search_emails(
    q: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Search stored RawEmails by subject or sender for manual linking."""
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    results = (
        db.query(RawEmail)
        .filter(
            or_(
                RawEmail.subject.ilike(f"%{q}%"),
                RawEmail.sender.ilike(f"%{q}%"),
            )
        )
        .order_by(RawEmail.date.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [
        {
            "id": e.id,
            "subject": e.subject,
            "sender": e.sender,
            "date": e.date.isoformat() if e.date else None,
            "status": e.status,
        }
        for e in results
    ]


@router.get("/emails/{raw_email_id}/documents")
async def get_documents_for_email(
    raw_email_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """List all documents linked to a specific email."""
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    svc = DocumentEmailReferenceService(db, current_user.id)
    return svc.get_documents_for_email(raw_email_id)


@router.post("/emails/{raw_email_id}/link")
async def link_email_to_document(
    raw_email_id: int,
    body: LinkEmailBody,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Manually link an email to a document."""
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    if body.document_type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"document_type must be one of: {sorted(VALID_DOCUMENT_TYPES)}",
        )

    # Verify the email exists
    email = db.query(RawEmail).filter(RawEmail.id == raw_email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    svc = DocumentEmailReferenceService(db, current_user.id)
    ref = svc.add_reference(
        raw_email_id=raw_email_id,
        document_type=body.document_type,
        document_id=body.document_id,
        link_type="manual",
        notes=body.notes,
    )
    return {
        "reference_id": ref.id,
        "raw_email_id": ref.raw_email_id,
        "document_type": ref.document_type,
        "document_id": ref.document_id,
        "link_type": ref.link_type,
        "notes": ref.notes,
        "created_at": ref.created_at.isoformat() if ref.created_at else None,
    }


@router.delete("/emails/{raw_email_id}/link")
async def unlink_email_from_document(
    raw_email_id: int,
    body: UnlinkEmailBody,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Unlink an email from a document."""
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    svc = DocumentEmailReferenceService(db, current_user.id)
    deleted = svc.remove_reference(raw_email_id, body.document_type, body.document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"status": "success"}
