"""Invoice review and approval endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from core.models.database import get_db
from core.models.models_per_tenant import Invoice, User
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer
from core.utils.audit import log_audit_event
from core.schemas.invoice import Invoice as InvoiceSchema
from core.services.review_service import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{invoice_id}/accept-review", response_model=InvoiceSchema)
async def accept_review(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "review invoices")

    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    review_service = ReviewService(db)
    success = review_service.accept_review(invoice)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to accept review or no review available")

    db.commit()
    db.refresh(invoice)

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_ACCEPT_INVOICE",
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=getattr(invoice, "number", None),
        details={"invoice_id": invoice.id, "review_status": invoice.review_status}
    )

    return invoice


@router.post("/{invoice_id}/reject-review", response_model=InvoiceSchema)
async def reject_review(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_non_viewer(current_user, "review invoices")

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    review_service = ReviewService(db)
    success = review_service.reject_review(invoice)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject review")

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_REJECT_INVOICE",
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=getattr(invoice, "number", None),
        details={"invoice_id": invoice.id, "review_status": invoice.review_status}
    )

    return invoice


@router.post("/{invoice_id}/review", response_model=InvoiceSchema)
async def run_review(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Trigger a full re-review (reset status to not_started for the worker to pick up)"""
    require_non_viewer(current_user, "review invoices")

    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Check if review worker is enabled
    from commercial.ai.services.ai_config_service import AIConfigService
    if not AIConfigService.is_review_worker_enabled(db):
        raise HTTPException(
            status_code=400,
            detail="Review worker is currently disabled. Please enable it in Settings > AI Configuration before triggering a review."
        )

    # Reset review status to pending so it shows immediately in UI
    # The worker will pick it up and process it
    invoice.review_status = "pending"
    invoice.review_result = None
    invoice.reviewed_at = None

    db.commit()
    db.refresh(invoice)

    # Publish Kafka event to trigger review
    try:
        from core.services.review_event_service import get_review_event_service
        from core.models.database import get_tenant_context

        tenant_id = get_tenant_context()
        if tenant_id:
            event_service = get_review_event_service()
            event_service.publish_single_review_trigger(
                tenant_id=tenant_id,
                entity_type="invoice",
                entity_id=invoice_id
            )
            logger.info(f"Published Kafka event to trigger review for invoice {invoice_id}")
    except Exception as e:
        logger.warning(f"Failed to publish Kafka event for invoice review trigger: {e}")

    # Poll for completion with timeout
    import asyncio
    max_wait_time = 30  # Maximum 30 seconds
    poll_interval = 0.5  # Check every 500ms
    elapsed_time = 0

    while elapsed_time < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval

        # Refresh to get latest status
        db.refresh(invoice)

        # Check if worker has processed the invoice
        if invoice.review_status in ["reviewed", "failed", "diff_found"]:
            logger.info(f"Review processing completed for invoice {invoice_id}. Final status: {invoice.review_status}")
            break

    if invoice.review_status == "pending":
        logger.warning(f"Review processing timed out for invoice {invoice_id} after {max_wait_time} seconds")

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_TRIGGER_INVOICE",
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=getattr(invoice, "number", None),
        details={"invoice_id": invoice.id, "review_status": invoice.review_status}
    )

    return invoice


@router.post("/{invoice_id:int}/cancel-review", response_model=InvoiceSchema)
async def cancel_invoice_review(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Cancel an in-progress review for an invoice"""
    require_non_viewer(current_user, "review invoices")

    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Can only cancel if review is pending, not_started, rejected, or failed
    if invoice.review_status not in ["pending", "not_started", "rejected", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel review with status '{invoice.review_status}'. Only pending, rejected, failed, or not_started reviews can be cancelled."
        )

    # Cancel the review
    invoice.review_status = "not_started"
    invoice.review_result = None
    invoice.reviewed_at = None

    db.commit()
    db.refresh(invoice)

    logger.info(f"Cancelled review for invoice {invoice_id}")

    return invoice
