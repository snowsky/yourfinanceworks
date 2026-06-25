"""Tenant-facing anomaly / fraud detection endpoints.

The detection engine (``commercial/anomaly_detection``) already writes
``Anomaly`` rows into each tenant DB; the only existing reader was the
cross-tenant super-admin aggregator (``/super-admin/anomalies``). This router
exposes the *current tenant's* anomalies so they can be surfaced on the
dashboard. Read-only and licensing-gated.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models_per_tenant import Anomaly, User as TenantUser
from core.routers.auth import get_current_user
from core.services.feature_config_service import FeatureConfigService

logger = logging.getLogger(__name__)

router = APIRouter()

# Highest-severity first when ordering / summarizing.
RISK_LEVELS = ("critical", "high", "medium", "low")

RESOLVABLE_STATUSES = ("confirmed", "dismissed")


def _serialize_anomaly(a, statement_by_txn=None):
    statement_by_txn = statement_by_txn or {}
    return {
        "id": a.id,
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "risk_score": a.risk_score,
        "risk_level": a.risk_level,
        "reason": a.reason,
        "rule_id": a.rule_id,
        "details": a.details,
        "created_at": a.created_at,
        "status": a.status,
        "resolution_note": a.resolution_note,
        "resolved_at": a.dismissed_at,
        "resolved_by_id": a.dismissed_by_id,
        "statement_id": statement_by_txn.get(a.entity_id),
    }


def _apply_resolution(anomaly, status: str, note, user) -> None:
    """Set the resolution fields + keep the is_dismissed mirror in sync."""
    anomaly.status = status
    anomaly.is_dismissed = status != "open"
    anomaly.dismissed_at = datetime.now(timezone.utc)
    anomaly.dismissed_by_id = user.id
    anomaly.resolution_note = note
    anomaly.dismiss_notes = note  # keep the legacy column in sync


@router.get("")
async def list_anomalies(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    status: Optional[str] = Query(None, description="Filter by resolution status (open/confirmed/dismissed)"),
    is_dismissed: bool = Query(False, description="Return dismissed items instead of open ones"),
    db: Session = Depends(get_db),
    current_user: TenantUser = Depends(get_current_user),
):
    """List the current tenant's anomalies (open / un-dismissed by default).

    Returns a ``summary`` count by risk level (for the dashboard card) plus a
    paginated ``items`` list ordered highest-risk first. Reads precomputed rows
    only — no AI/Kafka in the request path.
    """
    if not FeatureConfigService.is_enabled("anomaly_detection", db=db):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Anomaly detection is not available in your current license",
        )

    if status is not None:
        query = db.query(Anomaly).filter(Anomaly.status == status)
    else:
        query = db.query(Anomaly).filter(Anomaly.is_dismissed == is_dismissed)
    if risk_level:
        query = query.filter(Anomaly.risk_level == risk_level)

    total = query.count()

    items = (
        query.order_by(Anomaly.risk_score.desc(), Anomaly.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Resolve the parent statement id for bank-transaction anomalies so the UI
    # can deep-link to the exact statement + transaction (entity_id is the
    # transaction id, which isn't routable on its own).
    statement_by_txn: dict[int, int] = {}
    bank_txn_ids = [
        a.entity_id for a in items if a.entity_type == "bank_statement_transaction"
    ]
    if bank_txn_ids:
        from core.models.models_per_tenant import BankStatementTransaction

        rows = (
            db.query(
                BankStatementTransaction.id, BankStatementTransaction.statement_id
            )
            .filter(BankStatementTransaction.id.in_(bank_txn_ids))
            .all()
        )
        statement_by_txn = {txn_id: stmt_id for txn_id, stmt_id in rows}

    # Open-anomaly counts by risk level, in one grouped query.
    summary = {level: 0 for level in RISK_LEVELS}
    rows = (
        db.query(Anomaly.risk_level, func.count(Anomaly.id))
        .filter(Anomaly.is_dismissed == False)  # noqa: E712 — SQLAlchemy column comparison
        .group_by(Anomaly.risk_level)
        .all()
    )
    for level, count in rows:
        if level in summary:
            summary[level] = count

    return {
        "total": total,
        "summary": summary,
        "skip": skip,
        "limit": limit,
        "items": [_serialize_anomaly(a, statement_by_txn) for a in items],
    }


class DismissAnomalyRequest(BaseModel):
    notes: Optional[str] = None


@router.patch("/{anomaly_id}/dismiss")
async def dismiss_anomaly(
    anomaly_id: int,
    payload: DismissAnomalyRequest = DismissAnomalyRequest(),
    db: Session = Depends(get_db),
    current_user: TenantUser = Depends(get_current_user),
):
    """Dismiss (acknowledge) one of the current tenant's anomalies."""
    if not FeatureConfigService.is_enabled("anomaly_detection", db=db):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Anomaly detection is not available in your current license",
        )

    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Anomaly not found")

    _apply_resolution(anomaly, "dismissed", payload.notes, current_user)
    db.commit()

    return {"id": anomaly.id, "is_dismissed": True}


class ResolveAnomalyRequest(BaseModel):
    status: str
    note: Optional[str] = None


@router.patch("/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: int,
    payload: ResolveAnomalyRequest,
    db: Session = Depends(get_db),
    current_user: TenantUser = Depends(get_current_user),
):
    """Resolve an anomaly as confirmed (true positive) or dismissed (false positive)."""
    if not FeatureConfigService.is_enabled("anomaly_detection", db=db):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Anomaly detection is not available in your current license",
        )
    if payload.status not in RESOLVABLE_STATUSES:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status must be 'confirmed' or 'dismissed'",
        )
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Anomaly not found")

    _apply_resolution(anomaly, payload.status, payload.note, current_user)
    db.commit()
    return {"id": anomaly.id, "status": anomaly.status}


@router.get("/{anomaly_id}")
async def get_anomaly(
    anomaly_id: int,
    db: Session = Depends(get_db),
    current_user: TenantUser = Depends(get_current_user),
):
    """Fetch a single anomaly (for the detail drawer / deep-links)."""
    if not FeatureConfigService.is_enabled("anomaly_detection", db=db):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Anomaly detection is not available in your current license",
        )
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Anomaly not found")

    statement_by_txn = {}
    if anomaly.entity_type == "bank_statement_transaction":
        from core.models.models_per_tenant import BankStatementTransaction
        row = (
            db.query(BankStatementTransaction.statement_id)
            .filter(BankStatementTransaction.id == anomaly.entity_id)
            .first()
        )
        if row:
            statement_by_txn[anomaly.entity_id] = row[0]
    return _serialize_anomaly(anomaly, statement_by_txn)
