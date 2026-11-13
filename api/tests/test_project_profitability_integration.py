"""Imported HTTP routers, real JWT authentication and isolated tenant databases.

Run with --noconftest. No production database, auth-success override, or extracted
route bodies are used. Only database factories are redirected to disposable DBs.
"""
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models.database import current_tenant_id, get_master_db
from core.models.models import Base as MasterBase, MasterUser, Tenant
from core.models.models_per_tenant import Base, User, Client, Expense, Payment
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.auth import create_access_token
from plugins.time_tracking.models import Project, TimeEntry
from plugins.time_tracking.cost_models import TimeEntryCost
from plugins.time_tracking.profitability_router import profitability_router
from plugins.time_tracking.router import projects_router, time_entries_router


@pytest.fixture
def http(monkeypatch, tmp_path):
    monkeypatch.setenv('ENCRYPTION_ENABLED', 'false')
    monkeypatch.setenv('MASTER_KEY_PATH', str(tmp_path / 'master.key'))
    engines = [create_engine(f'sqlite:///{tmp_path / name}', connect_args={'check_same_thread': False})
               for name in ('master.db', 'tenant-a.db', 'tenant-b.db')]
    master, *tenants = [sessionmaker(bind=e) for e in engines]
    MasterBase.metadata.create_all(engines[0])
    with master() as db:
        db.add_all([Tenant(id=1, name='A'), Tenant(id=2, name='B')])
        db.flush()
        db.add_all([MasterUser(id=i, email=email, hashed_password='unused', tenant_id=tenant, role=role)
                    for i, email, tenant, role in [(1, 'admin@a.test', 1, 'admin'),
                    (2, 'worker@a.test', 1, 'user'), (3, 'admin@b.test', 2, 'admin')]])
        db.commit()
    for index, engine in enumerate(engines[1:]):
        Base.metadata.create_all(engine)
        with tenants[index]() as db:
            ids = [(1, 'admin@a.test', 'admin'), (2, 'worker@a.test', 'user')] if index == 0 else [(3, 'admin@b.test', 'admin')]
            db.execute(User.__table__.insert(), [dict(id=i, email=email, role=role, hashed_password='unused', is_active=True) for i, email, role in ids])
            db.execute(Client.__table__.insert().values(id=1, name='Client'))
            # Tenant B deliberately has no project 41.
            if index == 0:
                db.add(Project(id=41, client_id=1, name='Hourly project', currency='USD', hourly_rate=100, billing_method='hourly'))
            db.commit()
    monkeypatch.setattr(tenant_db_manager, 'get_tenant_session', lambda tenant: tenants[int(tenant)-1])
    app = FastAPI()

    @app.middleware('http')
    async def tenant_context(request, call_next):
        token = current_tenant_id.set(int(request.headers.get('X-Test-Tenant', '1')))
        try:
            return await call_next(request)
        finally:
            current_tenant_id.reset(token)

    def master_db():
        with master() as db:
            yield db

    app.dependency_overrides[get_master_db] = master_db
    app.include_router(profitability_router, prefix='/projects')
    app.include_router(projects_router, prefix='/projects')
    app.include_router(time_entries_router, prefix='/time-entries')
    with TestClient(app) as client:
        def headers(email='admin@a.test', tenant=1):
            return {'Authorization': 'Bearer ' + create_access_token({'sub': email}), 'X-Test-Tenant': str(tenant)}
        yield SimpleNamespace(client=client, headers=headers, tenants=tenants)
    for engine in engines:
        engine.dispose()


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def rate(http, user=1, amount='40', effective='2026-01-01'):
    return ok(http.client.post('/projects/cost-rates', headers=http.headers(), json={
        'user_id': user, 'currency': 'USD', 'effective_from': effective, 'hourly_cost': amount}))


def test_authenticated_create_import_timer_supplier_backfill_invoice_and_cash(http):
    c, h = http.client, http.headers()
    rate(http)
    rate(http, user=2, amount='30')
    manual = ok(c.post('/time-entries', headers=h, json={'project_id': 41, 'hourly_rate': 100,
        'started_at': '2026-02-01T09:00:00', 'duration_minutes': 600}), 201)
    imported = ok(c.post('/time-entries/import/csv', headers=http.headers('worker@a.test'),
        files={'file': ('time.csv', 'project_id,date,hours,hourly_rate,billable\n41,2026-02-01,2,100,false\n', 'text/csv')}), 201)
    assert imported['created_time_entries'] == 1
    timer = ok(c.post('/time-entries/timer/start', headers=h, json={'project_id': 41, 'hourly_rate': 100,
        'started_at': '2026-02-02T09:00:00', 'billable': False}), 201)
    stopped = ok(c.post('/time-entries/timer/stop', headers=h, json={'ended_at': '2026-02-02T10:00:00'}))
    assert stopped['id'] == timer['id'] and stopped['duration_minutes'] == 60
    with http.tenants[0]() as db:
        assert db.get(TimeEntryCost, manual['id']).hourly_cost == Decimal('40')
        db.add(Expense(id=51, project_id=41, amount=100, currency='USD', expense_date=datetime(2026,2,1),
                       category='Supplier', status='recorded', is_deleted=False))
        db.add(TimeEntry(id=71, project_id=41, client_id=1, user_id=1, started_at=datetime(2026,2,3),
                         duration_minutes=60, hourly_rate=100, amount=0, billable=False, status='logged'))
        db.commit()
    replacement = ok(c.put(f"/projects/41/entry-costs/{timer['id']}", headers=h,
                           json={'method': 'supplier_expense', 'expense_ids': [51]}))
    assert replacement['method'] == 'supplier_expense'
    preview = ok(c.post('/projects/41/cost-backfill/preview', headers=h, json={'entry_ids': [71]}))
    assert Decimal(preview['after_total']) == 40
    assert ok(c.post('/projects/41/cost-backfill/apply', headers=h, json=preview))['applied_entry_ids'] == [71]
    invoice = ok(c.post('/projects/41/invoice', headers=h, json={'time_entry_ids': [manual['id']], 'expense_ids': [51]}), 201)
    # Payments are real canonical tenant ORM records. The independent payment
    # route has licensing/notification dependencies outside this feature's app.
    with http.tenants[0]() as db:
        db.add(Payment(invoice_id=invoice['invoice_id'], amount=250, currency='USD', payment_method='bank_transfer'))
        db.commit()
    result = ok(c.get('/projects/41/profitability', headers=h))
    assert Decimal(result['work_value']) == 1000
    assert Decimal(result['known_cost']) == 600  # 400 + 60 + 40 + supplier 100
    assert Decimal(result['contribution']) == 400
    assert result['status'] == 'complete'
    assert Decimal(result['billing']['invoiced_pre_tax']) == 1100
    assert Decimal(result['billing']['collected_cash']) == 250
    assert Decimal(result['billing']['unbilled_work_value']) == 0
    for path in ['/time-entries?project_id=41', '/projects/41', '/projects/41/summary', '/projects/41/unbilled']:
        public = ok(c.get(path, headers=http.headers('worker@a.test')))
        assert not any(key in str(public) for key in ('hourly_cost', 'known_delivery_cost', 'source_rate_id', 'estimated_contribution'))
    exported = c.get('/time-entries/export/monthly?year=2026&month=2', headers=http.headers('worker@a.test'))
    assert exported.status_code == 200, exported.text
    assert 'hourly_cost' not in exported.text and 'source_rate_id' not in exported.text


@pytest.mark.parametrize('path', ['/projects/41/profitability', '/projects/cost-rates?user_id=1&currency=USD'])
def test_actual_auth_and_tenant_cost_authorization(http, path):
    c = http.client
    assert c.get(path).status_code == 401
    assert c.get(path, headers={'Authorization': 'Bearer invalid'}).status_code == 401
    assert c.get(path, headers=http.headers('worker@a.test')).status_code == 403
    # An A session cannot select B's tenant, even though B is a valid DB.
    assert c.get(path, headers=http.headers(tenant=2)).status_code == 401
    foreign = c.get(path, headers=http.headers('admin@b.test', 2))
    assert foreign.status_code == (404 if path.endswith('profitability') else 200)
    if foreign.status_code == 200:
        assert foreign.json() == []


def test_forbidden_writes_and_stale_multi_entry_preview_are_atomic(http):
    c, h = http.client, http.headers()
    payload = {'user_id': 2, 'currency': 'USD', 'effective_from': '2026-01-01', 'hourly_cost': '40'}
    assert c.post('/projects/cost-rates', headers=http.headers('worker@a.test'), json=payload).status_code == 403
    rate(http)
    with http.tenants[0]() as db:
        db.add_all([TimeEntry(id=i, project_id=41, client_id=1, user_id=1, started_at=datetime(2026,2,1),
                             duration_minutes=60, hourly_rate=100, status='logged') for i in (80,81)])
        db.commit()
    preview = ok(c.post('/projects/41/cost-backfill/preview', headers=h, json={'entry_ids': [80,81]}))
    with http.tenants[0]() as db:
        db.get(TimeEntry,81).duration_minutes = 120
        db.commit()
    assert c.post('/projects/41/cost-backfill/apply', headers=h, json=preview).status_code == 409
    with http.tenants[0]() as db:
        assert db.query(TimeEntryCost).count() == 0
