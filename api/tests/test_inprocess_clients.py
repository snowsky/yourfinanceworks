# api/tests/test_inprocess_clients.py
import pytest
from types import SimpleNamespace

import commercial.ai.inprocess.clients_domain as cd
from commercial.ai.inprocess.base import InProcessAPIClient


def _admin():
    return SimpleNamespace(id=1, email="u@x.com", tenant_id=1, role="admin", is_superuser=True)


@pytest.fixture(autouse=True)
def _tenant_ctx():
    from core.models.database import set_tenant_context, clear_tenant_context
    set_tenant_context(1)
    yield
    clear_tenant_context()


@pytest.mark.asyncio
async def test_create_client_persists_row_and_returns_dict(db_session, monkeypatch):
    seen = {}
    monkeypatch.setattr(cd, "require_component_permission",
                        lambda db, user, comp, level, action="": seen.setdefault("perm", (comp, level)))
    monkeypatch.setattr(cd, "log_audit_event", lambda **k: seen.setdefault("audit", k))
    monkeypatch.setattr(cd, "maybe_send_operation_notification", lambda *a, **k: seen.setdefault("notify", k))

    client = InProcessAPIClient(db=db_session, current_user=_admin())
    result = await client.create_client({"name": "Acme", "email": "ap@acme.com"})

    assert result["name"] == "Acme"
    assert result["email"] == "ap@acme.com"
    assert seen["perm"] == ("customers", "user")          # RBAC enforced
    assert seen["audit"]["action"] == "CREATE"            # audit written
    assert seen["audit"]["resource_type"] == "client"
    from core.models.models_per_tenant import Client
    assert db_session.query(Client).count() == 1          # row persisted on the request session


@pytest.mark.asyncio
async def test_create_client_enforces_permission(db_session, monkeypatch):
    from fastapi import HTTPException

    def _deny(db, user, comp, level, action=""):
        raise HTTPException(status_code=403, detail="nope")

    monkeypatch.setattr(cd, "require_component_permission", _deny)
    client = InProcessAPIClient(db=db_session, current_user=_admin())
    with pytest.raises(HTTPException):
        await client.create_client({"name": "Acme", "email": "ap@acme.com"})
    from core.models.models_per_tenant import Client
    assert db_session.query(Client).count() == 0          # nothing written when denied


@pytest.mark.asyncio
async def test_create_client_rejects_duplicate(db_session, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(cd, "require_component_permission", lambda *a, **k: None)
    monkeypatch.setattr(cd, "log_audit_event", lambda **k: None)
    monkeypatch.setattr(cd, "maybe_send_operation_notification", lambda *a, **k: None)
    client = InProcessAPIClient(db=db_session, current_user=_admin())
    await client.create_client({"name": "Acme", "email": "dup@acme.com"})
    with pytest.raises(HTTPException) as exc_info:
        await client.create_client({"name": "Acme", "email": "dup@acme.com"})
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_list_clients_returns_items_shape(db_session, monkeypatch):
    monkeypatch.setattr(cd, "require_component_permission", lambda *a, **k: None)
    monkeypatch.setattr(cd, "log_audit_event", lambda **k: None)
    monkeypatch.setattr(cd, "maybe_send_operation_notification", lambda *a, **k: None)
    client = InProcessAPIClient(db=db_session, current_user=_admin())
    await client.create_client({"name": "Acme", "email": "a@acme.com"})

    result = await client.list_clients(skip=0, limit=10)
    assert isinstance(result, dict)
    assert result["total"] == 1
    assert isinstance(result["items"], list)
    assert result["items"][0]["name"] == "Acme"
    assert "outstanding_balance" in result["items"][0]   # aggregate shape preserved
