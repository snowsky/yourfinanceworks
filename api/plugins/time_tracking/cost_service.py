"""Private tenant cost setup and explicit missing-only historical backfill."""
import hashlib
import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.models.models_per_tenant import User, AuditLog
from .models import Project, TimeEntry
from .cost_models import ContributorCostRate, TimeEntryCost
from .cost_schemas import CostRateWrite, CostRateResponse, CostBackfillEntry, CostBackfillPreview, CostBackfillResult


def require_cost_admin(db: Session, actor):
    # The tenant database is authoritative; master/global privileges cannot grant access.
    member = db.query(User).filter(User.id == actor.id, User.is_active.is_(True), User.role == 'admin').first()
    if member is None:
        raise HTTPException(403, 'Tenant administrator access required')
    return member


def _audit(db, actor, action, resource_id, details):
    # Only identifiers and a fixed reason enter generic audit storage.
    db.add(AuditLog(user_id=actor.id, user_email=actor.email, action=action,
                    resource_type='project_cost', resource_id=str(resource_id), details=details))


def set_cost_rate(db: Session, actor, payload: CostRateWrite) -> CostRateResponse:
    require_cost_admin(db, actor)
    contributor = db.query(User).filter(User.id == payload.user_id, User.is_active.is_(True)).first()
    if contributor is None:
        raise HTTPException(404, 'Active tenant contributor not found')
    existing = db.query(ContributorCostRate).filter_by(user_id=payload.user_id, currency=payload.currency, effective_from=payload.effective_from).first()
    # Append-only rates preserve provenance for historical snapshots.
    if existing:
        raise HTTPException(409, 'A cost rate already exists for this effective date')
    row = ContributorCostRate(**payload.model_dump())
    db.add(row)
    db.flush()
    _audit(db, actor, 'CREATE', row.id, {'user_id': row.user_id, 'reason': 'contributor_cost_setup'})
    return CostRateResponse.model_validate(row)


def _rate(db, entry, currency):
    return db.query(ContributorCostRate).filter(
        ContributorCostRate.user_id == entry.user_id,
        ContributorCostRate.currency == currency,
        ContributorCostRate.effective_from <= entry.started_at.date(),
    ).order_by(ContributorCostRate.effective_from.desc()).first()


def snapshot_entry_cost(db: Session, entry: TimeEntry) -> TimeEntryCost | None:
    existing = db.get(TimeEntryCost, entry.id)
    if existing is not None:
        return existing
    project = db.get(Project, entry.project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    rate = _rate(db, entry, project.currency)
    if rate is None:
        return None
    cost = TimeEntryCost(time_entry_id=entry.id, method='hourly', hourly_cost=rate.hourly_cost,
                         currency=rate.currency, source_rate_id=rate.id, version=1)
    db.add(cost)
    db.flush()
    return cost


def _preview(db, project_id, entry_ids, locked=False):
    ids = sorted(set(entry_ids))
    if not ids or len(ids) > 1000:
        raise HTTPException(422, 'Select between 1 and 1000 entries')
    project_query = db.query(Project).filter_by(id=project_id)
    if locked:
        project_query = project_query.with_for_update()
    project = project_query.first()
    if project is None:
        raise HTTPException(404, 'Project not found')
    query = db.query(TimeEntry).filter(TimeEntry.project_id == project_id, TimeEntry.id.in_(ids)).order_by(TimeEntry.id)
    if locked:
        query = query.with_for_update()
    entries = query.populate_existing().all()
    if len(entries) != len(ids):
        raise HTTPException(404, 'Selected entries do not belong to this project')
    result = []
    for entry in entries:
        cost = db.query(TimeEntryCost).filter_by(time_entry_id=entry.id).populate_existing().first()
        rate = None if cost else _rate(db, entry, project.currency)
        hourly = cost.hourly_cost if cost else rate.hourly_cost if rate else None
        currency = cost.currency if cost else project.currency
        eligible = entry.status in {'logged', 'approved', 'invoiced', 'completed'} and entry.duration_minutes is not None and entry.duration_minutes >= 0
        amount = Decimal(entry.duration_minutes) / Decimal(60) * hourly if eligible and hourly is not None and currency == project.currency else None
        result.append(CostBackfillEntry(entry_id=entry.id, user_id=entry.user_id, status=entry.status,
            work_date=entry.started_at.date(), duration_minutes=entry.duration_minutes,
            entry_version=entry.updated_at.isoformat(), cost_version=cost.version if cost else None,
            source_rate_id=cost.source_rate_id if cost else rate.id if rate else None,
            hourly_cost=hourly, currency=currency, before_cost=amount if cost else None, after_cost=amount))
    data = dict(project_id=project_id, entry_ids=ids, entries=result,
                before_total=sum((r.before_cost for r in result if r.before_cost is not None), Decimal(0)),
                after_total=sum((r.after_cost for r in result if r.after_cost is not None), Decimal(0)))
    unsigned = CostBackfillPreview(**data, fingerprint='')
    fingerprint = hashlib.sha256(json.dumps(unsigned.model_dump(mode='json', exclude={'fingerprint'}), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return unsigned.model_copy(update={'fingerprint': fingerprint})


def preview_cost_backfill(db: Session, project_id: int, entry_ids: list[int]) -> CostBackfillPreview:
    return _preview(db, project_id, entry_ids)


def apply_cost_backfill(db: Session, actor, preview: CostBackfillPreview) -> CostBackfillResult:
    require_cost_admin(db, actor)
    # Locks include missing-snapshot entry rows, preventing concurrent backfills.
    current = _preview(db, preview.project_id, preview.entry_ids, locked=True)
    if current.fingerprint != preview.fingerprint:
        raise HTTPException(409, 'Cost preview is stale; preview again')
    applied = []
    for row in current.entries:
        if row.cost_version is None and row.after_cost is not None:
            db.add(TimeEntryCost(time_entry_id=row.entry_id, method='hourly', hourly_cost=row.hourly_cost,
                                 currency=row.currency, source_rate_id=row.source_rate_id, version=1))
            applied.append(row.entry_id)
    _audit(db, actor, 'UPDATE', current.project_id, {'entry_ids': applied, 'reason': 'explicit_missing_cost_backfill'})
    db.flush()
    return CostBackfillResult(applied_entry_ids=applied)
