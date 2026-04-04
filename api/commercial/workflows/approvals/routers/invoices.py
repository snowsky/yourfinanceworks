"""
Invoice approval workflow endpoints.

Covers: submit, unsubmit, pending, approve, reject, history.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, text
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.schemas.approval import ApprovalStatus
from core.exceptions.approval_exceptions import (
    ApprovalWorkflowError,
    InsufficientApprovalPermissions,
    InvalidApprovalState,
    ValidationError,
)
from core.utils.audit import log_audit_event
from core.utils.rbac import require_non_viewer
from commercial.workflows.approvals.routers._shared import get_approval_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["approvals"])


@router.post("/{invoice_id}/submit-approval", response_model=List[dict])
async def submit_invoice_for_approval(
    invoice_id: int,
    submission_data: dict,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Submit an invoice for approval."""
    try:
        require_non_viewer(current_user)

        approver_id = submission_data.get("approver_id")
        notes = submission_data.get("notes")

        if not approver_id:
            raise HTTPException(status_code=400, detail="approver_id is required")

        approvals = approval_service.submit_invoice_for_approval(
            invoice_id=invoice_id,
            submitter_id=current_user.id,
            approver_id=approver_id,
            notes=notes,
        )

        from core.models.models_per_tenant import (
            Invoice,
            RecurrencePattern,
            Reminder,
            ReminderNotification,
            ReminderPriority,
            ReminderStatus,
        )

        now = datetime.now(timezone.utc)
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

        for approval in approvals:
            if approval.approver_id:
                db.add(
                    ReminderNotification(
                        reminder_id=None,
                        user_id=approval.approver_id,
                        notification_type="invoice_approval",
                        channel="in_app",
                        scheduled_for=now,
                        subject=f"Invoice Approval Request #{invoice_id}",
                        message=(
                            f"New invoice approval request from {current_user.email}: "
                            f"Invoice #{invoice.number if invoice else 'N/A'} - "
                            f"${invoice.amount if invoice else 'N/A'}"
                        ),
                        is_sent=True,
                        sent_at=now,
                    )
                )

                priority = ReminderPriority.MEDIUM
                if invoice and invoice.amount:
                    if invoice.amount >= 10000:
                        priority = ReminderPriority.URGENT
                    elif invoice.amount >= 5000:
                        priority = ReminderPriority.HIGH

                db.add(
                    Reminder(
                        title=f"Approve Invoice: #{invoice.number if invoice else 'N/A'} - ${invoice.amount if invoice else 'N/A'}",
                        description=(
                            f"Invoice approval request from {current_user.email}\n\n"
                            f"Invoice Number: {invoice.number if invoice else 'N/A'}\n"
                            f"Amount: ${invoice.amount if invoice else 'N/A'}\n"
                            f"Client: {invoice.client.name if invoice and invoice.client else 'N/A'}\n"
                            f"Due Date: {invoice.due_date if invoice and invoice.due_date else 'N/A'}\n\n"
                            f"Notes: {notes or 'No notes provided'}"
                        ),
                        due_date=now + timedelta(days=3),
                        priority=priority,
                        status=ReminderStatus.PENDING,
                        recurrence_pattern=RecurrencePattern.NONE,
                        assigned_to_id=approval.approver_id,
                        created_by_id=current_user.id,
                        tags=["approval", "invoice", f"invoice-{invoice_id}"],
                        extra_metadata={
                            "invoice_id": invoice_id,
                            "approval_id": approval.id,
                            "approval_level": approval.approval_level,
                            "submitter_id": current_user.id,
                            "submitter_email": current_user.email,
                        },
                    )
                )

        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="invoice_submitted_for_approval",
            resource_type="invoice",
            resource_id=str(invoice_id),
            details={"invoice_id": invoice_id, "approval_count": len(approvals), "notes": notes},
        )

        logger.info("User %s submitted invoice %s for approval", current_user.id, invoice_id)
        return [{"id": a.id, "status": a.status, "approval_level": a.approval_level, "approver_id": a.approver_id} for a in approvals]

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidApprovalState as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalWorkflowError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error submitting invoice %s: %s", invoice_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{invoice_id}/unsubmit", response_model=dict)
async def unsubmit_invoice_approval(
    invoice_id: int,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Unsubmit an invoice approval request, reverting status and cancelling pending approvals."""
    try:
        require_non_viewer(current_user)

        success = approval_service.unsubmit_invoice_approval(
            invoice_id=invoice_id,
            submitter_id=current_user.id,
        )

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="invoice_approval_unsubmitted",
            resource_type="invoice",
            resource_id=str(invoice_id),
            details={"invoice_id": invoice_id},
        )

        logger.info("User %s unsubmitted invoice %s", current_user.id, invoice_id)
        return {"message": "Invoice approval request unsubmitted successfully", "success": success}

    except InvalidApprovalState as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error unsubmitting invoice %s: %s", invoice_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pending")
async def get_pending_invoice_approvals(
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get pending invoice approvals for the current user."""
    try:
        require_non_viewer(current_user)

        from core.models.models_per_tenant import Client, Invoice, InvoiceApproval
        from core.schemas.approval import PendingInvoiceApprovalDetail

        query = (
            db.query(
                InvoiceApproval.id,
                InvoiceApproval.invoice_id,
                Invoice.number.label("invoice_number"),
                Client.name.label("client_name"),
                Invoice.amount,
                Invoice.currency,
                InvoiceApproval.status,
                InvoiceApproval.submitted_at,
                InvoiceApproval.approver_id,
                InvoiceApproval.approval_level,
            )
            .join(Invoice, InvoiceApproval.invoice_id == Invoice.id)
            .join(Client, Invoice.client_id == Client.id)
            .filter(
                and_(
                    InvoiceApproval.approver_id == current_user.id,
                    InvoiceApproval.status == ApprovalStatus.PENDING,
                    InvoiceApproval.is_current_level == True,
                )
            )
            .order_by(InvoiceApproval.submitted_at.asc())
        )

        total = query.count()
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        approvals = [
            PendingInvoiceApprovalDetail(
                id=row.id,
                invoice_id=row.invoice_id,
                invoice_number=row.invoice_number,
                client_name=row.client_name,
                amount=row.amount,
                currency=row.currency or "USD",
                status=row.status,
                submitted_at=row.submitted_at,
                approver_id=row.approver_id,
                approval_level=row.approval_level,
            )
            for row in query.all()
        ]

        logger.info("Retrieved %d pending invoice approvals (total: %d) for user %s", len(approvals), total, current_user.id)
        return {"approvals": approvals, "total": total}

    except Exception as e:
        logger.error("Error retrieving pending invoice approvals for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{approval_id}/approve")
async def approve_invoice(
    approval_id: int,
    decision_data: dict,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Approve an invoice."""
    try:
        require_non_viewer(current_user)

        notes = decision_data.get("notes")
        approval = approval_service.approve_invoice(
            approval_id=approval_id,
            approver_id=current_user.id,
            notes=notes,
        )

        from core.models.models_per_tenant import Invoice, Reminder, ReminderNotification, ReminderStatus

        try:
            notif = db.query(ReminderNotification).filter(
                ReminderNotification.user_id == current_user.id,
                ReminderNotification.notification_type == "invoice_approval",
                ReminderNotification.is_read == False,
                ReminderNotification.subject.contains(f"#{approval.invoice_id}"),
            ).first()
            if notif:
                notif.is_read = True
                db.add(notif)
        except Exception as e:
            logger.warning("Failed to mark notification as read for invoice %s: %s", approval.invoice_id, e)

        now = datetime.now(timezone.utc)
        invoice = db.query(Invoice).filter(Invoice.id == approval.invoice_id).first()

        reminder_for_approval = db.query(Reminder).filter(
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata"),
        ).params(metadata=f'{{"approval_id": {approval.id}}}').first()

        submitter_id = (
            reminder_for_approval.extra_metadata.get("submitter_id")
            if reminder_for_approval and reminder_for_approval.extra_metadata
            else None
        )

        if submitter_id and invoice:
            db.add(ReminderNotification(
                reminder_id=None,
                user_id=submitter_id,
                notification_type="invoice_approved",
                channel="in_app",
                scheduled_for=now,
                subject=f"Invoice Approved #{approval.invoice_id}",
                message=f"Your invoice #{invoice.number} has been approved by {current_user.email}",
                is_sent=True,
                sent_at=now,
            ))

        reminder = db.query(Reminder).filter(
            Reminder.assigned_to_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata"),
        ).params(metadata=f'{{"approval_id": {approval_id}}}').first()
        if reminder:
            reminder.status = ReminderStatus.COMPLETED
            reminder.completed_at = now
            reminder.completed_by_id = current_user.id
            db.add(reminder)

        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="invoice_approved",
            resource_type="invoice_approval",
            resource_id=str(approval_id),
            details={"invoice_id": approval.invoice_id, "approval_level": approval.approval_level, "notes": notes},
        )

        logger.info("User %s approved invoice approval %s", current_user.id, approval_id)
        return {"id": approval.id, "status": approval.status, "invoice_id": approval.invoice_id}

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientApprovalPermissions as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidApprovalState as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error approving invoice %s: %s", approval_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{approval_id}/reject")
async def reject_invoice(
    approval_id: int,
    decision_data: dict,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Reject an invoice. A rejection reason is required."""
    try:
        require_non_viewer(current_user)

        rejection_reason = decision_data.get("rejection_reason")
        notes = decision_data.get("notes")

        if not rejection_reason or not rejection_reason.strip():
            raise HTTPException(status_code=400, detail="Rejection reason is required when rejecting an invoice")

        approval = approval_service.reject_invoice(
            approval_id=approval_id,
            approver_id=current_user.id,
            rejection_reason=rejection_reason,
            notes=notes,
        )

        from core.models.models_per_tenant import Invoice, Reminder, ReminderNotification, ReminderStatus

        try:
            notif = db.query(ReminderNotification).filter(
                ReminderNotification.user_id == current_user.id,
                ReminderNotification.notification_type == "invoice_approval",
                ReminderNotification.is_read == False,
                ReminderNotification.subject.contains(f"#{approval.invoice_id}"),
            ).first()
            if notif:
                notif.is_read = True
                db.add(notif)
        except Exception as e:
            logger.warning("Failed to mark notification as read for invoice %s: %s", approval.invoice_id, e)

        now = datetime.now(timezone.utc)
        invoice = db.query(Invoice).filter(Invoice.id == approval.invoice_id).first()

        reminder_for_approval = db.query(Reminder).filter(
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata"),
        ).params(metadata=f'{{"approval_id": {approval.id}}}').first()

        submitter_id = (
            reminder_for_approval.extra_metadata.get("submitter_id")
            if reminder_for_approval and reminder_for_approval.extra_metadata
            else None
        )

        if submitter_id and invoice:
            db.add(ReminderNotification(
                reminder_id=None,
                user_id=submitter_id,
                notification_type="invoice_rejected",
                channel="in_app",
                scheduled_for=now,
                subject=f"Invoice Rejected #{approval.invoice_id}",
                message=f"Your invoice #{invoice.number} was rejected by {current_user.email}. Reason: {rejection_reason}",
                is_sent=True,
                sent_at=now,
            ))

        reminder = db.query(Reminder).filter(
            Reminder.assigned_to_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata"),
        ).params(metadata=f'{{"approval_id": {approval_id}}}').first()
        if reminder:
            reminder.status = ReminderStatus.CANCELLED
            db.add(reminder)

        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="invoice_rejected",
            resource_type="invoice_approval",
            resource_id=str(approval_id),
            details={
                "invoice_id": approval.invoice_id,
                "approval_level": approval.approval_level,
                "rejection_reason": rejection_reason,
                "notes": notes,
            },
        )

        logger.info("User %s rejected invoice approval %s", current_user.id, approval_id)
        return {"id": approval.id, "status": approval.status, "invoice_id": approval.invoice_id}

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientApprovalPermissions as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidApprovalState as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error rejecting invoice %s: %s", approval_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/{invoice_id}")
async def get_invoice_approval_history(
    invoice_id: int,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Get complete approval history for an invoice."""
    try:
        require_non_viewer(current_user)

        history = approval_service.get_invoice_approval_history(invoice_id)

        from core.models.models_per_tenant import InvoiceApproval
        from core.services.attribution_service import AttributionService
        from sqlalchemy.orm import joinedload

        approvals = (
            db.query(InvoiceApproval)
            .options(joinedload(InvoiceApproval.approved_by), joinedload(InvoiceApproval.rejected_by))
            .filter(InvoiceApproval.invoice_id == invoice_id)
            .order_by(InvoiceApproval.approval_level.asc(), InvoiceApproval.submitted_at.asc())
            .all()
        )
        approval_map = {a.id: a for a in approvals}

        enriched_history_items = []
        for item in history.approval_history:
            approval = approval_map.get(item.id)
            item_dict = item.dict()
            item_dict["approved_by_username"] = None
            item_dict["rejected_by_username"] = None
            if approval:
                if approval.status == "approved" and approval.approved_by:
                    item_dict["approved_by_username"] = AttributionService.get_display_name(approval.approved_by)
                elif approval.status == "rejected" and approval.rejected_by:
                    item_dict["rejected_by_username"] = AttributionService.get_display_name(approval.rejected_by)
            enriched_history_items.append(item_dict)

        logger.info("Retrieved approval history for invoice %s by user %s", invoice_id, current_user.id)
        return {
            "invoice_id": history.invoice_id,
            "current_status": history.current_status,
            "approval_history": enriched_history_items,
        }

    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Error retrieving approval history for invoice %s: %s", invoice_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")
