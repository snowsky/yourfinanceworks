"""Isolated real-model lifecycle tests; never load destructive shared conftest."""
from datetime import date, datetime
from decimal import Decimal
import ast
from pathlib import Path

import pytest
from fastapi import HTTPException
from tests.test_project_cost_permissions import db, actor, rate
from core.models.models_per_tenant import Expense, AuditLog
from plugins.time_tracking.models import Project, TimeEntry
from plugins.time_tracking.cost_models import TimeEntryCost, TimeEntryCostExpense
from plugins.time_tracking import cost_service


def test_supplier_replacement_preserves_prior_snapshot(db):
    rate(db)
    entry = db.get(TimeEntry, 1)
    cost_service.snapshot_entry_cost(db, entry)
    db.add(Expense(id=1, project_id=1, amount=80, currency='USD', category='supplier'))
    db.flush()
    cost = cost_service.replace_entry_cost_method(db, actor, 1, 'supplier_expense', [1])
    assert cost.method == 'supplier_expense'
    assert cost.hourly_cost is None and cost.source_rate_id is None
    revisions = db.query(cost_service.TimeEntryCostRevision).all()
    assert len(revisions) == 1
    assert revisions[0].snapshot['hourly_cost'] == '40.000000'
    assert all('hourly_cost' not in str(row.details) for row in db.query(AuditLog))


@pytest.mark.parametrize('method,ids', [('supplier_expense', []), ('hourly', [1]), ('unknown', [])])
def test_conflicting_or_missing_supplier_links_rejected(db, method, ids):
    with pytest.raises(HTTPException):
        cost_service.replace_entry_cost_method(db, actor, 1, method, ids)
    assert db.get(TimeEntryCost, 1) is None


def test_same_project_only_and_tenant_admin(db):
    db.add(Project(id=2, client_id=1, name='other', currency='USD'))
    db.add(Expense(id=1, project_id=2, amount=80, currency='USD', category='supplier'))
    db.flush()
    with pytest.raises(HTTPException):
        cost_service.replace_entry_cost_method(db, actor, 1, 'supplier_expense', [1])
    from types import SimpleNamespace
    with pytest.raises(HTTPException) as exc:
        cost_service.replace_entry_cost_method(db, SimpleNamespace(id=2), 1, 'supplier_expense', [1])
    assert exc.value.status_code == 403


def test_supplier_shared_expense_and_restored_hourly(db):
    rate(db)
    db.add(Expense(id=1, project_id=1, amount=80, currency='USD', category='supplier'))
    db.add(TimeEntry(id=2, project_id=1, client_id=1, user_id=2, started_at=datetime(2026,2,1), duration_minutes=120, hourly_rate=100, status='logged'))
    db.flush()
    for entry_id in [1, 2]:
        cost_service.replace_entry_cost_method(db, actor, entry_id, 'supplier_expense', [1, 1])
    assert db.query(TimeEntryCostExpense).count() == 2
    assert {link.expense_id for link in db.query(TimeEntryCostExpense)} == {1}
    cost = cost_service.replace_entry_cost_method(db, actor, 1, 'hourly', [])
    assert cost.hourly_cost == Decimal('40')
    assert db.query(TimeEntryCostExpense).filter_by(time_entry_id=1).count() == 0


@pytest.mark.parametrize('amount', ['40', '0'])
def test_frozen_rate_duration_date_nonbillable_and_rollback(db, amount):
    rate(db, amount)
    entry = db.get(TimeEntry, 1)
    entry.billable = False
    entry.duration_minutes = 120
    cost = cost_service.snapshot_entry_cost(db, entry)
    assert Decimal(entry.duration_minutes) / 60 * cost.hourly_cost == Decimal(amount) * 2
    rate(db, '99', date(2026, 2, 1))
    entry.duration_minutes = 180
    entry.started_at = datetime(2026, 3, 1)
    assert cost_service.snapshot_entry_cost(db, entry).hourly_cost == Decimal(amount)
    assert Decimal(entry.duration_minutes) / 60 * cost.hourly_cost == Decimal(amount) * 3
    db.rollback()
    assert db.get(TimeEntryCost, 1) is None


def route_functions():
    """Execute exact route bodies without importing unavailable cloud/auth modules.

    This verifies business integration, NOT HTTP dependency authorization. Only
    post-commit generic audit emission is mocked; all cost permissions are real.
    """
    from datetime import timezone, timedelta, time
    from types import SimpleNamespace
    from core.models.models_per_tenant import Client
    from plugins.time_tracking.models import ProjectTask
    from plugins.time_tracking import schemas
    import io, csv
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'plugins/time_tracking/router.py').read_text())
    names = {'timer_start', 'timer_stop', 'create_time_entry', 'update_time_entry',
             'import_time_entries_csv', '_resolve_hourly_rate', '_enrich_time_entry',
             '_parse_float', '_parse_int', '_parse_bool', '_parse_datetime',
             '_parse_date', '_parse_time', '_canonicalize_csv_rows', '_apply_task_name_column_override'}
    nodes = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node.decorator_list = []
            node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
            nodes.append(node)
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TIME_IMPORT_FIELD_ALIASES' for t in node.targets):
            nodes.append(node)
    ns = dict(vars(schemas), TimeEntry=TimeEntry, Project=Project, ProjectTask=ProjectTask,
              Client=Client, HTTPException=HTTPException, datetime=datetime, timezone=timezone,
              timedelta=timedelta, time=time, csv=csv, io=io,
              snapshot_entry_cost=cost_service.snapshot_entry_cost,
              log_audit_event=lambda **kwargs: None)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<actual-time-router-bodies>', 'exec'), ns)
    return SimpleNamespace(**ns)


@pytest.mark.parametrize('path', ['manual', 'timer', 'import'])
@pytest.mark.parametrize('internal_rate', ['40', '0'])
def test_actual_route_bodies_freeze_costs_and_keep_private(db, path, internal_rate):
    from datetime import timedelta
    from types import SimpleNamespace
    import asyncio
    r = route_functions()
    rate(db, internal_rate)
    worker = SimpleNamespace(id=2, email='worker')
    started = datetime(2026, 2, 1, 9)
    if path == 'manual':
        result = r.create_time_entry(r.TimeEntryCreate(project_id=1, started_at=started,
            duration_minutes=120, hourly_rate=100, billable=False, hourly_cost=999), db, worker)
    elif path == 'timer':
        result = r.timer_start(r.TimerStartRequest(project_id=1, started_at=started, hourly_rate=100, billable=False), db, worker)
        # SQLite strips timezone, so use a matching naive explicit end.
        rate(db, '99', date(2026, 2, 1))
        result = r.timer_stop(r.TimerStopRequest(ended_at=started+timedelta(hours=2)), db, worker)
    else:
        from fastapi import UploadFile
        from io import BytesIO
        upload = UploadFile(filename='time.csv', file=BytesIO(b'project_id,started_at,hours,hourly_rate,billable\n1,2026-02-01T09:00:00,2,100,false\n'))
        result = asyncio.run(r.import_time_entries_csv(file=upload, use_ai=False,
            missing_project_strategy='error', fallback_project_name=None,
            fallback_project_id=None, task_name_column=None, db=db, current_user=worker))
        entry = db.query(TimeEntry).order_by(TimeEntry.id.desc()).first()
        result = r._enrich_time_entry(entry, db)
    entry = db.get(TimeEntry, result['id'])
    cost = db.get(TimeEntryCost, entry.id)
    assert cost.hourly_cost == Decimal(internal_rate)
    assert Decimal(entry.duration_minutes) / 60 * cost.hourly_cost == Decimal(internal_rate) * 2
    assert not entry.billable
    assert not {'hourly_cost', 'cost', 'source_rate_id', 'cost_method'} & result.keys()
    result = r.update_time_entry(entry.id, r.TimeEntryUpdate(duration_minutes=180, started_at=datetime(2026,3,1), hourly_cost=999, cost_method="supplier_expense"), db, worker)
    assert db.get(TimeEntryCost, entry.id).hourly_cost == Decimal(internal_rate)
    assert Decimal(entry.duration_minutes) / 60 * cost.hourly_cost == Decimal(internal_rate) * 3


@pytest.mark.parametrize('path', ['create_time_entry', 'timer_start'])
def test_snapshot_failure_rolls_back_entry_insert(db, path):
    from types import SimpleNamespace
    r = route_functions()
    def fail(db, entry):
        assert entry.id is not None  # Entry has been flushed, but never committed.
        raise RuntimeError('snapshot failure')
    getattr(r, path).__globals__['snapshot_entry_cost'] = fail
    payload = (r.TimeEntryCreate if path == 'create_time_entry' else r.TimerStartRequest)(
        project_id=1, started_at=datetime(2026,2,1), hourly_rate=100)
    with pytest.raises(RuntimeError):
        getattr(r, path)(payload, db, SimpleNamespace(id=2, email='worker'))
    assert db.query(TimeEntry).count() == 1


@pytest.mark.parametrize('is_deleted,currency,expense_id', [(True,'USD',1),(False,'EUR',1),(False,'USD',999)])
def test_invalid_expenses_cannot_replace_snapshot(db, is_deleted, currency, expense_id):
    rate(db)
    original = cost_service.snapshot_entry_cost(db, db.get(TimeEntry, 1))
    db.add(Expense(id=1, project_id=1, amount=80, currency=currency, is_deleted=is_deleted, category='supplier'))
    db.flush()
    with pytest.raises(HTTPException):
        cost_service.replace_entry_cost_method(db, actor, 1, 'supplier_expense', [expense_id])
    assert original.method == 'hourly' and original.hourly_cost == 40
    assert db.query(cost_service.TimeEntryCostRevision).count() == 0


def test_ordinary_schema_export_and_mcp_have_no_private_costs():
    from plugins.time_tracking import schemas
    private = {'hourly_cost', 'source_rate_id', 'cost_method', 'cost', 'expense_ids'}
    for name in ['TimeEntryCreate', 'TimeEntryUpdate', 'TimeEntryResponse', 'TimerStartRequest', 'TimerStopRequest']:
        assert not private & getattr(schemas, name).model_fields.keys()
    source = (Path(__file__).resolve().parents[1] / 'plugins/time_tracking/router.py').read_text()
    node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == 'export_monthly')
    assert not any(name in ast.get_source_segment(source, node) for name in private)
    mcp = (Path(__file__).resolve().parents[1] / 'plugins/time_tracking/mcp/time_tracking_provider.py').read_text()
    assert 'cost_service' not in mcp and 'TimeEntryCost' not in mcp and 'hourly_cost' not in mcp


def test_import_snapshot_failure_rolls_back_all_inserted_entries(db):
    from types import SimpleNamespace
    from io import BytesIO
    import asyncio
    from fastapi import UploadFile
    r = route_functions()
    def fail(db, entry):
        assert entry.id is not None
        raise RuntimeError('snapshot failure')
    r.import_time_entries_csv.__globals__['snapshot_entry_cost'] = fail
    upload = UploadFile(filename='time.csv', file=BytesIO(b'project_id,started_at,hours,hourly_rate\n1,2026-02-01T09:00:00,2,100\n'))
    with pytest.raises(RuntimeError):
        asyncio.run(r.import_time_entries_csv(file=upload, use_ai=False, missing_project_strategy='error',
            fallback_project_name=None, fallback_project_id=None, task_name_column=None,
            db=db, current_user=SimpleNamespace(id=2, email='worker')))
    assert db.query(TimeEntry).count() == 1


def test_replacement_service_never_commits_and_revision_is_atomic(db):
    rate(db)
    cost_service.snapshot_entry_cost(db, db.get(TimeEntry, 1))
    db.add(Expense(id=1, project_id=1, amount=80, currency='USD', category='supplier'))
    db.commit()
    cost_service.replace_entry_cost_method(db, actor, 1, 'supplier_expense', [1])
    assert db.query(cost_service.TimeEntryCostRevision).count() == 1
    db.rollback()
    assert db.get(TimeEntryCost, 1).method == 'hourly'
    assert db.query(cost_service.TimeEntryCostRevision).count() == 0
    assert db.query(TimeEntryCostExpense).count() == 0


def test_missing_rate_stays_unknown_after_ordinary_update(db):
    from types import SimpleNamespace
    r = route_functions()
    result = r.create_time_entry(r.TimeEntryCreate(project_id=1, started_at=datetime(2026,2,1),
        duration_minutes=120, hourly_rate=100), db, SimpleNamespace(id=2, email='worker'))
    assert db.get(TimeEntryCost, result['id']) is None
    rate(db)
    r.update_time_entry(result['id'], r.TimeEntryUpdate(duration_minutes=180), db, SimpleNamespace(id=2, email='worker'))
    assert db.get(TimeEntryCost, result['id']) is None
