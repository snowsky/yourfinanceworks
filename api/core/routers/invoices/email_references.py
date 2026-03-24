"""Invoice email-references sub-resource."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.services.document_email_reference_service import DocumentEmailReferenceService

router = APIRouter()


@router.get("/{invoice_id}/email-references")
async def get_invoice_email_references(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Return all source emails linked to an invoice."""
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    svc = DocumentEmailReferenceService(db, current_user.id)
    return svc.get_email_references("invoice", invoice_id)
