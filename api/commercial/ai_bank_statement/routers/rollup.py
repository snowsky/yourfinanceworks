"""Statement bookkeeping rollup endpoints.

Exposes preview + create-or-replace for the per-statement rollup Expense.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.utils.rbac import require_non_viewer
from core.utils.feature_gate import require_feature
from core.utils.audit import log_audit_event
from core.schemas.bank_statement import (
    RollupCreateRequest,
    RollupCreateResponse,
    RollupDebitPreview,
    RollupPreviewResponse,
)

from ..services.statement_rollup_service import (
    NoDebitsFound,
    RollupConflict,
    StatementNotFound,
    build_preview,
    create_rollup_expense,
)
from ._shared import get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{statement_id}/rollup-preview",
    response_model=RollupPreviewResponse,
)
@require_feature("ai_bank_statement")
async def get_rollup_preview(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Compute the rollup that would be created without persisting anything."""
    require_non_viewer(current_user, "preview rollup expense")
    get_tenant_id()
    try:
        preview = build_preview(db, statement_id, user_tags=[])
    except StatementNotFound:
        raise HTTPException(status_code=404, detail="Statement not found")

    return RollupPreviewResponse(
        statement_id=preview.statement.id,
        count=len(preview.debits),
        total=preview.total,
        currency=preview.currency,
        latest_date=preview.latest_date,
        auto_labels=preview.auto_labels,
        debits=[
            RollupDebitPreview(
                transaction_id=d.transaction_id,
                date=d.date,
                description=d.description,
                amount=d.amount,
                category=d.category,
                linked_expense_id=d.linked_expense_id,
            )
            for d in preview.debits
        ],
        notes_preview=preview.notes,
        existing_rollup_id=preview.existing_rollup_id,
    )


@router.post(
    "/{statement_id}/create-rollup-expense",
    response_model=RollupCreateResponse,
)
@require_feature("ai_bank_statement")
async def create_rollup(
    statement_id: int,
    payload: RollupCreateRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Create one rollup Expense per statement (bookkeeping summary of all debits).

    Returns 409 with `existing_expense_id` if a rollup already exists and
    `replace=False`. Send `replace=true` to soft-delete the prior rollup and
    create a fresh one.
    """
    require_non_viewer(current_user, "create rollup expense")
    get_tenant_id()
    try:
        result = create_rollup_expense(
            db=db,
            statement_id=statement_id,
            user_id=current_user.id,
            user_tags=payload.user_tags,
            replace=payload.replace,
        )
    except StatementNotFound:
        raise HTTPException(status_code=404, detail="Statement not found")
    except NoDebitsFound:
        raise HTTPException(status_code=400, detail="Statement has no debit transactions to roll up")
    except RollupConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Rollup expense already exists for this statement",
                "existing_expense_id": exc.existing_expense_id,
            },
        )

    expense = result.expense
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="CREATE",
        resource_type="expense",
        resource_id=str(expense.id),
        resource_name=f"Statement rollup #{expense.id}",
        details={
            "statement_id": statement_id,
            "rollup": True,
            "replace": payload.replace,
            "amount": expense.amount,
            "debit_count": result.debit_count,
        },
        status="success",
    )

    labels_list = list(expense.labels) if isinstance(expense.labels, list) else []
    return RollupCreateResponse(
        expense_id=expense.id,
        statement_id=statement_id,
        amount=float(expense.amount or 0),
        currency=expense.currency,
        labels=labels_list,
        debit_count=result.debit_count,
    )
