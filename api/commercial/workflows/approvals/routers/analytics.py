"""
Approval analytics and dashboard endpoints.

Covers: metrics, dashboard-stats, approved-expenses, processed-expenses, invoices/processed.
"""

from datetime import datetime, timedelta
from typing import Optional

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.schemas.approval import ApprovalMetrics
from core.utils.rbac import require_non_viewer
from commercial.workflows.approvals.routers._shared import get_approval_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["approvals"])


@router.get("/metrics", response_model=ApprovalMetrics)
async def get_approval_metrics(
    approver_id: Optional[int] = Query(None, description="Filter by specific approver ID"),
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
):
    """Get approval workflow metrics (approval rates, avg times, decision counts)."""
    try:
        require_non_viewer(current_user)
        target_approver_id = approver_id if approver_id is not None else current_user.id
        metrics = approval_service.get_approval_metrics(approver_id=target_approver_id)
        logger.info("Retrieved approval metrics for approver %s by user %s", target_approver_id, current_user.id)
        return metrics
    except Exception as e:
        logger.error("Error retrieving approval metrics: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dashboard-stats")
async def get_dashboard_stats(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get approval dashboard statistics (pending, approved/rejected today, overdue, avg time)."""
    try:
        require_non_viewer(current_user)

        from core.models.models_per_tenant import ExpenseApproval, InvoiceApproval

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        three_days_ago = datetime.now() - timedelta(days=3)

        expense_q = db.query(ExpenseApproval).filter(ExpenseApproval.approver_id == current_user.id)
        invoice_q = db.query(InvoiceApproval).filter(InvoiceApproval.approver_id == current_user.id)

        pending_count = (
            expense_q.filter(ExpenseApproval.status == "pending").count()
            + invoice_q.filter(InvoiceApproval.status == "pending").count()
        )
        approved_today = (
            expense_q.filter(and_(ExpenseApproval.status == "approved", ExpenseApproval.decided_at >= today_start, ExpenseApproval.decided_at < today_end)).count()
            + invoice_q.filter(and_(InvoiceApproval.status == "approved", InvoiceApproval.decided_at >= today_start, InvoiceApproval.decided_at < today_end)).count()
        )
        rejected_today = (
            expense_q.filter(and_(ExpenseApproval.status == "rejected", ExpenseApproval.decided_at >= today_start, ExpenseApproval.decided_at < today_end)).count()
            + invoice_q.filter(and_(InvoiceApproval.status == "rejected", InvoiceApproval.decided_at >= today_start, InvoiceApproval.decided_at < today_end)).count()
        )
        overdue_count = (
            expense_q.filter(and_(ExpenseApproval.status == "pending", ExpenseApproval.created_at < three_days_ago)).count()
            + invoice_q.filter(and_(InvoiceApproval.status == "pending", InvoiceApproval.created_at < three_days_ago)).count()
        )

        completed_expense = expense_q.filter(or_(ExpenseApproval.status == "approved", ExpenseApproval.status == "rejected")).all()
        completed_invoice = invoice_q.filter(or_(InvoiceApproval.status == "approved", InvoiceApproval.status == "rejected")).all()

        total_hours, count = 0.0, 0
        for a in completed_expense + completed_invoice:
            if a.decided_at and a.created_at:
                total_hours += (a.decided_at - a.created_at).total_seconds() / 3600
                count += 1

        stats = {
            "pending_count": pending_count,
            "approved_today": approved_today,
            "rejected_today": rejected_today,
            "overdue_count": overdue_count,
            "average_approval_time_hours": round(total_hours / count, 1) if count else 0.0,
        }

        logger.info("Retrieved dashboard stats for user %s: %s", current_user.id, stats)
        return stats

    except Exception as e:
        logger.error("Error retrieving dashboard stats for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


def _expense_to_dict(expense) -> dict:
    return {
        "id": expense.id,
        "amount": expense.amount,
        "description": expense.notes or f"{expense.category} - {expense.vendor or 'Unknown vendor'}",
        "category": expense.category,
        "date": expense.expense_date.isoformat() if expense.expense_date else None,
        "status": expense.status,
        "user_id": expense.user_id,
        "created_at": expense.created_at.isoformat() if expense.created_at else None,
        "updated_at": expense.updated_at.isoformat() if expense.updated_at else None,
        "receipt_path": expense.receipt_path,
        "notes": expense.notes,
        "vendor": expense.vendor,
        "tax_amount": expense.tax_amount,
        "currency": expense.currency,
        "labels": expense.labels or [],
        "analysis_status": expense.analysis_status,
        "analysis_error": expense.analysis_error,
        "invoice_id": expense.invoice_id,
        "is_inventory_consumption": expense.is_inventory_consumption,
        "consumption_items": expense.consumption_items or [],
    }


@router.get("/approved-expenses")
async def get_approved_expenses(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Get expenses approved by the current user."""
    try:
        require_non_viewer(current_user)

        from core.models.models_per_tenant import Expense, ExpenseApproval

        base = db.query(Expense).join(
            ExpenseApproval,
            and_(
                ExpenseApproval.expense_id == Expense.id,
                ExpenseApproval.approver_id == current_user.id,
                ExpenseApproval.status == "approved",
            ),
        ).order_by(ExpenseApproval.decided_at.desc())

        total_count = base.count()
        expenses = base.offset(skip).limit(limit).all()

        logger.info("Retrieved %d approved expenses for user %s", len(expenses), current_user.id)
        return {"expenses": [_expense_to_dict(e) for e in expenses], "total": total_count}

    except Exception as e:
        logger.error("Error retrieving approved expenses for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/processed-expenses")
async def get_processed_expenses(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Get expenses approved or rejected by the current user."""
    try:
        require_non_viewer(current_user)

        from core.models.models_per_tenant import Expense, ExpenseApproval

        base = db.query(Expense).join(
            ExpenseApproval,
            and_(
                ExpenseApproval.expense_id == Expense.id,
                ExpenseApproval.approver_id == current_user.id,
                or_(ExpenseApproval.status == "approved", ExpenseApproval.status == "rejected"),
            ),
        ).order_by(ExpenseApproval.decided_at.desc())

        total_count = base.count()
        expenses = base.offset(skip).limit(limit).all()

        logger.info("Retrieved %d processed expenses for user %s", len(expenses), current_user.id)
        return {"expenses": [_expense_to_dict(e) for e in expenses], "total": total_count}

    except Exception as e:
        logger.error("Error retrieving processed expenses for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/invoices/processed")
async def get_processed_invoices(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Get invoices approved or rejected by the current user."""
    try:
        require_non_viewer(current_user)

        from core.models.models_per_tenant import Client, Invoice, InvoiceApproval

        query = db.query(
            InvoiceApproval.id.label("approval_id"),
            Invoice.id,
            Invoice.number,
            Client.name.label("client_name"),
            Invoice.amount,
            Invoice.currency,
            InvoiceApproval.status,
            InvoiceApproval.decided_at,
            InvoiceApproval.submitted_at,
        ).join(
            Invoice, InvoiceApproval.invoice_id == Invoice.id
        ).join(
            Client, Invoice.client_id == Client.id
        ).filter(
            and_(
                InvoiceApproval.approver_id == current_user.id,
                or_(InvoiceApproval.status == "approved", InvoiceApproval.status == "rejected"),
            )
        ).order_by(InvoiceApproval.decided_at.desc())

        total_count = query.count()
        results = query.offset(skip).limit(limit).all()

        result_list = [
            {
                "id": row.id,
                "approval_id": row.approval_id,
                "number": row.number,
                "client_name": row.client_name,
                "amount": row.amount,
                "currency": row.currency or "USD",
                "status": row.status,
                "decided_at": row.decided_at.isoformat() if row.decided_at else None,
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
            }
            for row in results
        ]

        logger.info("Retrieved %d processed invoices for user %s", len(result_list), current_user.id)
        return {"invoices": result_list, "total": total_count}

    except Exception as e:
        logger.error("Error retrieving processed invoices for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal server error")
