"""Net Worth aggregation API.

All endpoints are gated by ``@require_feature("net_worth")``.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from commercial.networth.models import FinancialLiability, LiabilityKind
from commercial.networth.schemas import (
    AccountBalanceResponse,
    HistoryPointResponse,
    HistoryResponse,
    LiabilityCreateRequest,
    LiabilityResponse,
    LiabilityUpdateRequest,
    NetWorthSummaryResponse,
    SnapshotResponse,
)
from commercial.networth.services import (
    build_summary,
    capture_snapshot,
    history_by_month,
)
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.feature_gate import require_feature

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/networth", tags=["networth"])


def get_tenant_db(current_user: MasterUser = Depends(get_current_user)):
    """Yield a SQLAlchemy session scoped to the caller's tenant database."""
    session = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
    try:
        yield session
    finally:
        session.close()


def _to_summary_response(summary) -> NetWorthSummaryResponse:
    return NetWorthSummaryResponse(
        snapshot_date=summary.snapshot_date,
        total_assets=summary.total_assets,
        total_liabilities=summary.total_liabilities,
        net_worth=summary.net_worth,
        bank_total=summary.bank_total,
        investment_total=summary.investment_total,
        liability_total=summary.liability_total,
        accounts=[
            AccountBalanceResponse(
                account_kind=a.account_kind,
                label=a.label,
                balance=a.balance,
                currency=a.currency,
                account_ref=a.account_ref,
            )
            for a in summary.accounts
        ],
    )


# ---------------------------------------------------------------------------
# Summary / history / snapshot
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=NetWorthSummaryResponse)
@require_feature("net_worth")
async def summary_endpoint(
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> NetWorthSummaryResponse:
    summary = build_summary(tenant_db)
    return _to_summary_response(summary)


@router.get("/history", response_model=HistoryResponse)
@require_feature("net_worth")
async def history_endpoint(
    months: int = Query(default=12, ge=1, le=60),
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> HistoryResponse:
    points = history_by_month(tenant_db, months=months)
    return HistoryResponse(
        points=[
            HistoryPointResponse(
                snapshot_date=p.snapshot_date,
                total_assets=p.total_assets,
                total_liabilities=p.total_liabilities,
                net_worth=p.net_worth,
            )
            for p in points
        ]
    )


@router.post("/snapshot", response_model=SnapshotResponse)
@require_feature("net_worth")
async def snapshot_endpoint(
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> SnapshotResponse:
    """Manually trigger a snapshot run. Idempotent within a single day —
    re-running replaces today's rows."""
    result = capture_snapshot(tenant_db, user_id=current_user.id)
    return SnapshotResponse(
        snapshot_date=result.snapshot_date,
        rows_written=result.rows_written,
        summary=_to_summary_response(result.summary),
    )


# ---------------------------------------------------------------------------
# Liability CRUD
# ---------------------------------------------------------------------------


@router.get("/liabilities", response_model=List[LiabilityResponse])
@require_feature("net_worth")
async def list_liabilities(
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> List[LiabilityResponse]:
    rows = (
        tenant_db.query(FinancialLiability)
        .order_by(FinancialLiability.created_at.desc())
        .all()
    )
    return [LiabilityResponse.model_validate(r) for r in rows]


@router.post(
    "/liabilities",
    response_model=LiabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
@require_feature("net_worth")
async def create_liability(
    payload: LiabilityCreateRequest,
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> LiabilityResponse:
    row = FinancialLiability(
        name=payload.name,
        kind=LiabilityKind(payload.kind).value,
        balance=payload.balance,
        currency=payload.currency,
        interest_rate=payload.interest_rate,
        notes=payload.notes,
    )
    tenant_db.add(row)
    tenant_db.commit()
    tenant_db.refresh(row)
    return LiabilityResponse.model_validate(row)


@router.patch(
    "/liabilities/{liability_id}", response_model=LiabilityResponse
)
@require_feature("net_worth")
async def update_liability(
    liability_id: int,
    payload: LiabilityUpdateRequest,
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> LiabilityResponse:
    row = _require_liability(tenant_db, liability_id)
    if payload.name is not None:
        row.name = payload.name
    if payload.kind is not None:
        row.kind = LiabilityKind(payload.kind).value
    if payload.balance is not None:
        row.balance = payload.balance
    if payload.currency is not None:
        row.currency = payload.currency
    if payload.interest_rate is not None:
        row.interest_rate = payload.interest_rate
    if payload.notes is not None:
        row.notes = payload.notes
    tenant_db.commit()
    tenant_db.refresh(row)
    return LiabilityResponse.model_validate(row)


@router.delete(
    "/liabilities/{liability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@require_feature("net_worth")
async def delete_liability(
    liability_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> None:
    row = _require_liability(tenant_db, liability_id)
    tenant_db.delete(row)
    tenant_db.commit()


def _require_liability(
    db: Session, liability_id: int
) -> FinancialLiability:
    row = (
        db.query(FinancialLiability)
        .filter(FinancialLiability.id == liability_id)
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Liability not found",
        )
    return row
