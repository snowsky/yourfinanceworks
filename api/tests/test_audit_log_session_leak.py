"""Regression guard: super-admin audit aggregation must release each tenant
session even when that tenant's query raises (otherwise it leaks a connection
per failing tenant and exhausts the pool)."""

import core.models.database as db_mod
import core.services.tenant_database_manager as tdm_mod
from core.routers import audit_log as al


class _FailingSession:
    def __init__(self, closed):
        self._closed = closed

    def query(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        raise RuntimeError("simulated tenant query failure")

    def close(self):
        self._closed["count"] += 1


class _FakeTenant:
    id = 1
    name = "T1"


class _MasterDB:
    def query(self, *a, **k):
        return self

    def all(self):
        return [_FakeTenant()]

    def close(self):
        pass


def test_audit_aggregation_closes_tenant_session_on_query_error(monkeypatch):
    closed = {"count": 0}

    def _fake_get_master_db():
        yield _MasterDB()

    class _FakeTDM:
        def tenant_database_exists(self, tid):
            return True

        def get_tenant_session(self, tid):
            return lambda: _FailingSession(closed)

    monkeypatch.setattr(db_mod, "get_master_db", _fake_get_master_db)
    monkeypatch.setattr(db_mod, "set_tenant_context", lambda *a, **k: None)
    monkeypatch.setattr(tdm_mod, "tenant_db_manager", _FakeTDM())

    # The per-tenant query fails, but the function must catch it, continue, and
    # still close the tenant session in the finally block.
    result = al.get_all_organizations_audit_logs(is_super_admin=True)

    assert closed["count"] == 1  # tenant_db.close() ran despite the query error
    assert result.total == 0
