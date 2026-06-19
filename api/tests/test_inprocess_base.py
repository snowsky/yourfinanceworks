import pytest
from types import SimpleNamespace

from commercial.ai.inprocess.base import InProcessAPIClient


def _user():
    return SimpleNamespace(id=1, email="u@x.com", tenant_id=1, role="admin", is_superuser=False)


def test_stores_db_and_user():
    c = InProcessAPIClient(db="DB", current_user=_user())
    assert c._db == "DB"
    assert c._current_user.email == "u@x.com"


@pytest.mark.asyncio
async def test_unimplemented_method_delegates_to_http_fallback(monkeypatch):
    calls = {}

    class _FakeHTTP:
        def __init__(self, base_url, jwt_token):
            calls["constructed"] = (base_url, jwt_token)
        async def list_statements(self, **kwargs):
            calls["list_statements"] = kwargs
            return {"items": []}

    import commercial.ai.inprocess.base as base_mod
    monkeypatch.setattr(base_mod, "AuthenticatedAPIClient", _FakeHTTP)
    monkeypatch.setattr(base_mod, "create_access_token", lambda data, expires_delta=None: "TOKEN")

    c = InProcessAPIClient(db="DB", current_user=_user())
    result = await c.list_statements(skip=0, limit=10)  # not implemented in-process -> fallback
    assert result == {"items": []}
    assert calls["constructed"] == ("http://localhost:8000/api/v1", "TOKEN")
    assert calls["list_statements"] == {"skip": 0, "limit": 10}


def test_dunder_and_private_attrs_do_not_trigger_fallback():
    c = InProcessAPIClient(db="DB", current_user=_user())
    with pytest.raises(AttributeError):
        _ = c._nonexistent_private
