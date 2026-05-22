"""Merge two or more expenses into one bookkeeping record.

Sources are soft-deleted (visible in the recycle bin, restorable).
Their attachments are re-linked to the merged expense.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.services.expense_merge_service import (
    MergeValidationError,
    build_merge_preview,
    merge_expenses,
)
from core.utils.audit import log_audit_event
from core.utils.rbac import require_non_viewer

logger = logging.getLogger(__name__)
router = APIRouter()


class MergePreviewRequest(BaseModel):
    expense_ids: List[int] = Field(..., description="Source expense ids in selection order")
    user_tags: List[str] = Field(default_factory=list)
    notes_prefix: Optional[str] = Field(default=None)
    keep_sources: bool = Field(
        default=False,
        description="If true, sources stay alive and attachments are duplicated. "
        "If false (default), sources are soft-deleted and attachments are re-linked.",
    )


class MergeRequest(MergePreviewRequest):
    pass


class MergeSourceRow(BaseModel):
    id: int
    expense_date: Optional[str] = None  # ISO date
    vendor: Optional[str] = None
    amount: float
    category: Optional[str] = None
    currency: str


class MergePreviewResponse(BaseModel):
    count: int
    total: float
    currency: str
    latest_date: str
    category: Optional[str] = None
    vendor: Optional[str] = None
    labels: List[str]
    notes_preview: str
    sources: List[MergeSourceRow]


class MergeResultResponse(BaseModel):
    expense_id: int
    amount: float
    currency: str
    labels: List[str]
    source_count: int

    model_config = ConfigDict(from_attributes=True)


def _to_preview_response(preview) -> MergePreviewResponse:
    return MergePreviewResponse(
        count=len(preview.sources),
        total=preview.total,
        currency=preview.currency,
        latest_date=preview.latest_date.strftime("%Y-%m-%d") if preview.latest_date else "",
        category=preview.category,
        vendor=preview.vendor,
        labels=preview.labels,
        notes_preview=preview.notes,
        sources=[
            MergeSourceRow(
                id=s.id,
                expense_date=s.expense_date.strftime("%Y-%m-%d") if s.expense_date else None,
                vendor=s.vendor,
                amount=s.amount,
                category=s.category,
                currency=s.currency,
            )
            for s in preview.sources
        ],
    )


@router.post("/merge-preview", response_model=MergePreviewResponse)
async def merge_preview(
    payload: MergePreviewRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Compute what the merge would produce, without persisting anything."""
    require_non_viewer(current_user, "preview expense merge")
    try:
        preview = build_merge_preview(
            db,
            expense_ids=payload.expense_ids,
            user_tags=payload.user_tags,
            notes_prefix=payload.notes_prefix,
            keep_sources=payload.keep_sources,
        )
    except MergeValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": str(exc)},
        )
    return _to_preview_response(preview)


@router.post("/merge", response_model=MergeResultResponse)
async def merge(
    payload: MergeRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Create the merged expense, re-link attachments, soft-delete sources."""
    require_non_viewer(current_user, "merge expenses")
    try:
        merged = merge_expenses(
            db,
            expense_ids=payload.expense_ids,
            user_id=current_user.id,
            user_tags=payload.user_tags,
            notes_prefix=payload.notes_prefix,
            keep_sources=payload.keep_sources,
        )
    except MergeValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": str(exc)},
        )

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="MERGE",
        resource_type="expense",
        resource_id=str(merged.id),
        resource_name=f"Merged expense #{merged.id}",
        details={
            "source_ids": payload.expense_ids,
            "source_count": len(payload.expense_ids),
            "amount": merged.amount,
            "keep_sources": payload.keep_sources,
        },
        status="success",
    )

    labels_list = list(merged.labels) if isinstance(merged.labels, list) else []
    return MergeResultResponse(
        expense_id=merged.id,
        amount=float(merged.amount or 0),
        currency=merged.currency,
        labels=labels_list,
        source_count=len(payload.expense_ids),
    )
