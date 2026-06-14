"""Subscription detection API.

All endpoints are gated by ``@require_feature("subscription_detection")``.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from commercial.subscriptions.models import DetectedSubscription, SubscriptionStatus
from commercial.subscriptions.schemas import (
    CancelReminderRequest,
    ChargeHistoryEntry,
    ChargeHistoryResponse,
    ScanRequest,
    ScanResponse,
    StatusUpdateRequest,
    SubscriptionResponse,
    SubscriptionSummary,
)
from commercial.subscriptions.services import (
    acknowledge_price_change,
    build_summary,
    get_subscription,
    list_subscriptions,
    scan_tenant,
    set_cancel_reminder,
    to_response,
    update_status,
)
from core.models.models import MasterUser
from core.models.models_per_tenant import BankStatementTransaction
from core.routers.auth import get_current_user
from core.services.cashflow_patterns import normalize_transaction_description
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.feature_gate import require_feature

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def get_tenant_db(current_user: MasterUser = Depends(get_current_user)):
    """Yield a SQLAlchemy session scoped to the caller's tenant database."""
    session = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
    try:
        yield session
    finally:
        session.close()


def _require(sub: Optional[DetectedSubscription]) -> DetectedSubscription:
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    return sub


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=SubscriptionSummary)
@require_feature("subscription_detection")
async def list_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    include_low_confidence: bool = Query(False),
    needs_review: bool = Query(False),
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> SubscriptionSummary:
    rows = list_subscriptions(
        tenant_db,
        status=status_filter,
        include_low_confidence=include_low_confidence,
    )
    return build_summary(rows, needs_review=needs_review)


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
@require_feature("subscription_detection")
async def get_endpoint(
    subscription_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> SubscriptionResponse:
    sub = _require(get_subscription(tenant_db, subscription_id))
    return to_response(sub)


@router.get(
    "/{subscription_id}/charges", response_model=ChargeHistoryResponse
)
@require_feature("subscription_detection")
async def charge_history_endpoint(
    subscription_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> ChargeHistoryResponse:
    sub = _require(get_subscription(tenant_db, subscription_id))
    entries = _charge_history(tenant_db, sub)
    return ChargeHistoryResponse(subscription_id=sub.id, entries=entries)


# ---------------------------------------------------------------------------
# Mutating endpoints
# ---------------------------------------------------------------------------


@router.post("/scan", response_model=ScanResponse)
@require_feature("subscription_detection")
async def scan_endpoint(
    request: Optional[ScanRequest] = Body(default=None),
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> ScanResponse:
    """Run a fresh scan on demand. Body is optional; an empty POST runs
    with default lookback (365d) and notifications enabled."""
    payload = request or ScanRequest()
    result = scan_tenant(
        tenant_db,
        user_id=current_user.id,
        lookback_days=payload.lookback_days,
        emit_notifications=payload.emit_notifications,
    )
    return ScanResponse(**result.__dict__)


@router.post(
    "/{subscription_id}/status", response_model=SubscriptionResponse
)
@require_feature("subscription_detection")
async def update_status_endpoint(
    subscription_id: int,
    payload: StatusUpdateRequest,
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> SubscriptionResponse:
    sub = _require(get_subscription(tenant_db, subscription_id))
    try:
        new_status = SubscriptionStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown status: {payload.status}",
        ) from exc
    updated = update_status(
        tenant_db, sub, status=new_status, user_id=current_user.id
    )
    return to_response(updated)


@router.post(
    "/{subscription_id}/cancel-reminder",
    response_model=SubscriptionResponse,
)
@require_feature("subscription_detection")
async def cancel_reminder_endpoint(
    subscription_id: int,
    payload: CancelReminderRequest,
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> SubscriptionResponse:
    sub = _require(get_subscription(tenant_db, subscription_id))
    updated = set_cancel_reminder(tenant_db, sub, remind_on=payload.remind_on)
    return to_response(updated)


@router.post(
    "/{subscription_id}/acknowledge-price-change",
    response_model=SubscriptionResponse,
)
@require_feature("subscription_detection")
async def acknowledge_endpoint(
    subscription_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> SubscriptionResponse:
    sub = _require(get_subscription(tenant_db, subscription_id))
    updated = acknowledge_price_change(tenant_db, sub)
    return to_response(updated)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _charge_history(
    db: Session, sub: DetectedSubscription
) -> List[ChargeHistoryEntry]:
    """Return every bank statement transaction that maps to the same
    normalized merchant key, ordered oldest -> newest."""
    rows = (
        db.query(BankStatementTransaction)
        .filter(BankStatementTransaction.transaction_type == "debit")
        .all()
    )
    entries: List[ChargeHistoryEntry] = []
    for txn in rows:
        if normalize_transaction_description(txn.description) != sub.merchant_key:
            continue
        entries.append(
            ChargeHistoryEntry(
                transaction_id=txn.id,
                date=txn.date,
                amount=abs(float(txn.amount or 0.0)),
                description=txn.description or "",
            )
        )
    entries.sort(key=lambda e: e.date)
    return entries
