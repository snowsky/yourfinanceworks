"""Disposable SQLite ORM fixtures; run with --noconftest."""
from datetime import datetime, date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.models.models_per_tenant import Base, User, Client, AuditLog
from plugins.time_tracking.models import Project, TimeEntry
from plugins.time_tracking.cost_models import TimeEntryCost
from plugins.time_tracking.cost_schemas import CostRateWrite
from plugins.time_tracking.cost_service import set_cost_rate, snapshot_entry_cost, preview_cost_backfill, apply_cost_backfill, require_cost_admin


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("ENCRYPTION_ENABLED", "false")
    monkeypatch.setenv("MASTER_KEY_PATH", str(tmp_path / "master.key"))
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # Avoid encryption configuration: these tests never read encrypted fields.
        session.execute(User.__table__.insert(), [dict(id=1, email='admin', hashed_password='x', role='admin', is_active=True), dict(id=2, email='worker', hashed_password='x', role='user', is_active=True)])
        session.execute(Client.__table__.insert().values(id=1, name='client'))
        session.add(Project(id=1, client_id=1, name='project', currency='USD'))
        session.add(TimeEntry(id=1, project_id=1, client_id=1, user_id=2, started_at=datetime(2026, 2, 1), duration_minutes=90, hourly_rate=100, status='logged'))
        session.commit()
        yield session
    engine.dispose()


actor = SimpleNamespace(id=1, email='admin', role='admin', is_superuser=True)


def rate(db, amount='40', effective=date(2026, 1, 1), user_id=2):
    return set_cost_rate(db, actor, CostRateWrite(user_id=user_id, currency='USD', effective_from=effective, hourly_cost=amount))


@pytest.mark.parametrize('user_id', [2, 99])
def test_tenant_role_overrides_global_superuser(db, user_id):
    with pytest.raises(HTTPException) as exc:
        require_cost_admin(db, SimpleNamespace(id=user_id, role='admin', is_superuser=True))
    assert exc.value.status_code == 403


@pytest.mark.parametrize('amount', ['-1', 'NaN', 'Infinity', '-Infinity'])
def test_invalid_rate(amount):
    with pytest.raises(ValidationError):
        CostRateWrite(user_id=2, currency='USD', effective_from=date.today(), hourly_cost=amount)


def test_zero_and_effective_dates(db):
    rate(db, '0')
    rate(db, '60', date(2026, 3, 1))
    cost = snapshot_entry_cost(db, db.get(TimeEntry, 1))
    assert cost.hourly_cost == 0
    assert cost.currency == 'USD'
    assert db.get(TimeEntryCost, 1) is cost


def test_backfill_recomputes_and_rejects_stale(db):
    rate(db)
    preview = preview_cost_backfill(db, 1, [1])
    assert preview.after_total == Decimal('60')
    db.get(TimeEntry, 1).duration_minutes = 120
    with pytest.raises(HTTPException) as exc:
        apply_cost_backfill(db, actor, preview)
    assert exc.value.status_code == 409
    assert db.get(TimeEntryCost, 1) is None


def test_apply_is_missing_only_and_audit_has_no_costs(db):
    rate(db)
    preview = preview_cost_backfill(db, 1, [1])
    assert apply_cost_backfill(db, actor, preview).applied_entry_ids == [1]
    with pytest.raises(HTTPException):
        apply_cost_backfill(db, actor, preview)
    assert apply_cost_backfill(db, actor, preview_cost_backfill(db, 1, [1])).applied_entry_ids == []
    db.get(User, 2).is_active = False
    assert preview_cost_backfill(db, 1, [1]).after_total == Decimal('60')
    assert all('hourly_cost' not in str(row.details) and '40' not in str(row.details) for row in db.query(AuditLog))


def test_foreign_references_and_inactive_contributor(db):
    with pytest.raises(HTTPException):
        rate(db, user_id=999)
    with pytest.raises(HTTPException):
        preview_cost_backfill(db, 999, [1])
    db.add(Project(id=2, client_id=1, name='other', currency='USD'))
    db.flush()
    with pytest.raises(HTTPException):
        preview_cost_backfill(db, 2, [1])
    db.get(User, 2).is_active = False
    with pytest.raises(HTTPException):
        rate(db)


def test_selected_rate_changes_invalidate_preview_and_client_costs_ignored(db):
    rate(db)
    preview = preview_cost_backfill(db, 1, [1])
    rate(db, '80', date(2026, 2, 1))
    with pytest.raises(HTTPException) as exc:
        apply_cost_backfill(db, actor, preview)
    assert exc.value.status_code == 409
    current = preview_cost_backfill(db, 1, [1])
    assert current.after_total == Decimal('120')
    # Fingerprint is a concurrency token, not authority to specify costs.
    forged = current.model_copy(update={'entries': [], 'after_total': Decimal('0')})
    apply_cost_backfill(db, actor, forged)
    assert db.get(TimeEntryCost, 1).hourly_cost == Decimal('80')


def test_deactivated_admin_denied_and_extra_fields_rejected(db):
    db.get(User, 1).is_active = False
    with pytest.raises(HTTPException) as exc:
        require_cost_admin(db, actor)
    assert exc.value.status_code == 403
    with pytest.raises(ValidationError):
        CostRateWrite(user_id=2, currency='USD', effective_from=date.today(), hourly_cost='0', is_admin=True)
