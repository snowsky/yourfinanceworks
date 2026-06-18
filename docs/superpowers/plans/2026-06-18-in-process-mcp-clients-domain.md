# In-Process MCP Client — Clients Domain + Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the in-process API client (eliminating self-HTTP from the AI chat path) and migrate the **clients** domain as the reference pattern; all not-yet-migrated methods fall back to the existing HTTP client so nothing breaks.

**Architecture:** A new `InProcessAPIClient` (same duck-typed method surface as `AuthenticatedAPIClient`) is injected at the two chat-path construction sites, reusing the request's tenant `db` session + `current_user` (tenant context is already set by middleware). Implemented methods run in-process against the models/shared helpers; unimplemented ones delegate to a lazily-built `AuthenticatedAPIClient` (HTTP). The standalone MCP server (different client class) is untouched.

**Tech Stack:** FastAPI, SQLAlchemy (per-tenant DB), pytest (+ pytest-asyncio), conftest with in-memory SQLite + mocked `tenant_db_manager`.

## Global Constraints

- Reuse, do not re-derive, every shared sub-helper the real route handler uses: `require_component_permission` (RBAC), `log_audit_event` (audit), `ClientCreate` (validation), `_client_to_dict` (serialization), notification service. Reimplement only orchestration glue + model reads/writes.
- All DB work uses the **request's existing `db` session** (`self._db`) — never open a new tenant connection. Writes wrap the mutation in `db.begin_nested()` (SAVEPOINT) then `db.commit()`.
- In-process methods **raise on failure** (the tool mixins already wrap calls in `try/except` → `{success, error}`); return shapes must match what the current `AuthenticatedAPIClient` returns so `_extract_items_from_response` keeps working.
- Do NOT modify `InvoiceTools` or any `api/MCP/tools/` mixin.
- Do NOT modify the standalone MCP server (`api/MCP/server/`, `api/MCP/api_client.py`).
- Spyable shared helpers are imported at module top of the domain mixin (so tests can monkeypatch them); `_client_to_dict` is imported lazily inside methods to avoid a circular import with the `core.routers.clients` module.
- Backend tests run in-container: `docker compose exec api python -m pytest tests/<file> -v` (use `python -m pytest`, never bare `pytest`; the conftest provides the SQLite `db_session`).

---

### Task 1: Extract `maybe_send_operation_notification` helper

The `create_client` route handler has a ~30-line inline notification block that also references an **unbound `APP_NAME`** (`core/routers/clients.py:292`, never imported → latent `NameError` in the `tenant is None` branch). Extract it into one shared helper that both the route handler and the in-process client call. This is the only route-handler change in this plan.

**Files:**
- Create: `api/core/services/operation_notifications.py`
- Modify: `api/core/routers/clients.py` (replace the inline notification block ~lines 285-310 with a call)
- Test: `api/tests/test_operation_notifications.py`

**Interfaces:**
- Produces: `maybe_send_operation_notification(db, *, event_type: str, user_id: int, tenant_id: int, resource_type: str, resource_id: str, resource_name: str, details: dict) -> None`. No-op (and never raises) unless a tenant `Settings` row `key=="email_config"` has truthy `value["enabled"]`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_operation_notifications.py
import core.services.operation_notifications as on


class _FakeSettings:
    def __init__(self, value):
        self.value = value


class _Q:
    def __init__(self, row):
        self._row = row
    def filter(self, *a, **k):
        return self
    def first(self):
        return self._row


class _DB:
    def __init__(self, email_config_row=None):
        self._row = email_config_row
    def query(self, *a, **k):
        return _Q(self._row)


def test_noop_when_email_config_absent():
    # No Settings row -> returns None, sends nothing, never raises.
    on.maybe_send_operation_notification(
        _DB(None), event_type="client_created", user_id=1, tenant_id=1,
        resource_type="client", resource_id="5", resource_name="Acme", details={},
    )


def test_noop_when_email_disabled():
    row = _FakeSettings({"enabled": False, "provider": "ses"})
    on.maybe_send_operation_notification(
        _DB(row), event_type="client_created", user_id=1, tenant_id=1,
        resource_type="client", resource_id="5", resource_name="Acme", details={},
    )


def test_sends_when_enabled(monkeypatch):
    sent = {}

    class _NS:
        def __init__(self, db, email_service):
            sent["constructed"] = True
        def send_operation_notification(self, **kwargs):
            sent["call"] = kwargs
            return True

    monkeypatch.setattr(on, "NotificationService", _NS)
    monkeypatch.setattr(on, "EmailService", lambda config: object())
    monkeypatch.setattr(on, "EmailProviderConfig", lambda **k: object())
    monkeypatch.setattr(on, "EmailProvider", lambda v: v)
    monkeypatch.setattr(on, "_tenant_company_name", lambda tenant_id: "Acme Inc")

    row = _FakeSettings({"enabled": True, "provider": "ses", "from_email": "a@b.com"})
    on.maybe_send_operation_notification(
        _DB(row), event_type="client_created", user_id=1, tenant_id=1,
        resource_type="client", resource_id="5", resource_name="Acme", details={"email": "x@y.com"},
    )
    assert sent["call"]["event_type"] == "client_created"
    assert sent["call"]["company_name"] == "Acme Inc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/test_operation_notifications.py -v`
Expected: FAIL — module `core.services.operation_notifications` does not exist.

- [ ] **Step 3: Implement the helper**

```python
# api/core/services/operation_notifications.py
"""Shared 'best-effort operation notification' used by route handlers and the
in-process AI client, so the notification orchestration lives in exactly one place."""

import logging

from sqlalchemy.orm import Session

from core.services.notification_service import NotificationService
from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider

logger = logging.getLogger(__name__)


def _tenant_company_name(tenant_id: int) -> str:
    from config import APP_NAME
    from core.models.database import get_master_db
    from core.models.models import Tenant

    master_db = next(get_master_db())
    try:
        tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
        return tenant.name if tenant else APP_NAME
    finally:
        master_db.close()


def maybe_send_operation_notification(
    db: Session,
    *,
    event_type: str,
    user_id: int,
    tenant_id: int,
    resource_type: str,
    resource_id: str,
    resource_name: str,
    details: dict,
) -> None:
    """Send an operation notification if the tenant has email enabled. Never raises."""
    try:
        from core.models.models_per_tenant import Settings

        email_settings = db.query(Settings).filter(Settings.key == "email_config").first()
        if not (email_settings and email_settings.value and email_settings.value.get("enabled")):
            return

        ecd = email_settings.value
        config = EmailProviderConfig(
            provider=EmailProvider(ecd["provider"]),
            from_email=ecd.get("from_email"),
            from_name=ecd.get("from_name"),
            aws_access_key_id=ecd.get("aws_access_key_id"),
            aws_secret_access_key=ecd.get("aws_secret_access_key"),
            aws_region=ecd.get("aws_region"),
            azure_connection_string=ecd.get("azure_connection_string"),
            mailgun_api_key=ecd.get("mailgun_api_key"),
            mailgun_domain=ecd.get("mailgun_domain"),
        )
        notification_service = NotificationService(db, EmailService(config))
        notification_service.send_operation_notification(
            event_type=event_type,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details,
            company_name=_tenant_company_name(tenant_id),
        )
    except Exception as e:  # noqa: BLE001 - notifications must never break the operation
        logger.warning("Failed to send %s notification: %s", event_type, e)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/test_operation_notifications.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Refactor the route handler to use the helper**

In `api/core/routers/clients.py`, replace the inline notification block (the `try:` that loads `email_config`, builds `EmailProviderConfig`/`EmailService`/`NotificationService`, looks up the tenant, and calls `send_operation_notification` — currently ~lines 285-310, ending before `# Return client data as dict`) with:

```python
        # Send notification if email service is configured (shared helper; never raises)
        from core.services.operation_notifications import maybe_send_operation_notification
        maybe_send_operation_notification(
            db,
            event_type="client_created",
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            resource_type="client",
            resource_id=str(db_client.id),
            resource_name=db_client.name,
            details={
                "email": db_client.email,
                "phone": db_client.phone or "N/A",
                "preferred_currency": db_client.preferred_currency,
            },
        )
```

- [ ] **Step 6: Verify the clients router still imports + existing client tests pass**

Run: `docker compose exec api python -m pytest tests/test_clients.py -v` (if present) and `docker compose exec api python -c "import core.routers.clients"`
Expected: import OK; existing client tests still pass (notification path now routed through the helper).

- [ ] **Step 7: Commit**

```bash
git add api/core/services/operation_notifications.py api/core/routers/clients.py api/tests/test_operation_notifications.py
git commit -m "refactor(clients): extract maybe_send_operation_notification helper (fixes unbound APP_NAME)"
```

---

### Task 2: `InProcessAPIClient` base with HTTP fallback

**Files:**
- Create: `api/commercial/ai/inprocess/__init__.py` (empty)
- Create: `api/commercial/ai/inprocess/base.py`
- Test: `api/tests/test_inprocess_base.py`

**Interfaces:**
- Produces: `InProcessAPIClient(db: Session, current_user)` — stores `self._db`, `self._current_user`. Any attribute it does not implement is resolved via `__getattr__` to a lazily-constructed `AuthenticatedAPIClient` (self-HTTP), so the full ~30-method surface keeps working during migration.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_inprocess_base.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/test_inprocess_base.py -v`
Expected: FAIL — module `commercial.ai.inprocess.base` does not exist.

- [ ] **Step 3: Implement the base**

```python
# api/commercial/ai/inprocess/__init__.py
```

```python
# api/commercial/ai/inprocess/base.py
"""In-process API client for the AI chat path.

Implements the AuthenticatedAPIClient method surface by talking directly to the
models/services using the chat request's existing tenant session — no JWT, no
httpx, no second DB connection. Methods not yet migrated delegate to a lazily
built AuthenticatedAPIClient (self-HTTP) so the full surface keeps working.
"""

import logging
from datetime import timedelta

from core.routers.auth import create_access_token
from commercial.ai.routers.auth_client import AuthenticatedAPIClient

logger = logging.getLogger(__name__)

_SELF_BASE_URL = "http://localhost:8000/api/v1"


class InProcessAPIClient:
    def __init__(self, db, current_user):
        self._db = db
        self._current_user = current_user
        self._fallback = None

    def _get_fallback(self) -> AuthenticatedAPIClient:
        if self._fallback is None:
            token = create_access_token(
                data={"sub": self._current_user.email},
                expires_delta=timedelta(minutes=30),
            )
            self._fallback = AuthenticatedAPIClient(base_url=_SELF_BASE_URL, jwt_token=token)
        return self._fallback

    def __getattr__(self, name):
        # Only reached for attributes NOT found normally (i.e. not yet migrated).
        if name.startswith("_"):
            raise AttributeError(name)
        logger.debug("InProcessAPIClient: delegating '%s' to HTTP fallback", name)
        return getattr(self._get_fallback(), name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/test_inprocess_base.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add api/commercial/ai/inprocess/__init__.py api/commercial/ai/inprocess/base.py api/tests/test_inprocess_base.py
git commit -m "feat(ai): InProcessAPIClient base with HTTP fallback"
```

---

### Task 3: Wire `InProcessAPIClient` into the chat path

After this task, every chat-path tool call goes through `InProcessAPIClient` → (all still unimplemented) → HTTP fallback. **No behavior change yet** — this is the plumbing that lets later tasks flip methods in-process.

**Files:**
- Modify: `api/commercial/ai/routers/chat.py:201-222` (construct `InProcessAPIClient`)
- Modify: `api/commercial/ai/routers/action_handlers.py` (`_init_tools` signature + 6 call sites; `handle_early_actions` gains `current_user`; `_handle_onboarding_action` gains `db` + `current_user`)
- Test: `api/tests/test_inprocess_wiring.py`

**Interfaces:**
- Consumes: `InProcessAPIClient(db, current_user)` (Task 2).
- Produces: `_init_tools(db, current_user)` → `InvoiceTools(InProcessAPIClient(db, current_user))`. `handle_early_actions(..., current_user, ...)` and `_handle_onboarding_action(message, confirmed_action, ai_config, db, current_user)`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_inprocess_wiring.py
import pytest
from types import SimpleNamespace

import commercial.ai.routers.action_handlers as ah
from commercial.ai.inprocess.base import InProcessAPIClient


@pytest.mark.asyncio
async def test_init_tools_builds_inprocess_client():
    user = SimpleNamespace(id=1, email="u@x.com", tenant_id=1, role="admin", is_superuser=False)
    tools = await ah._init_tools(db="DB", current_user=user)
    assert isinstance(tools.api_client, InProcessAPIClient)
    assert tools.api_client._db == "DB"
    assert tools.api_client._current_user is user
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/test_inprocess_wiring.py -v`
Expected: FAIL — `_init_tools` takes `current_user_email`, not `db`/`current_user`.

- [ ] **Step 3: Rewrite `_init_tools`**

```python
# api/commercial/ai/routers/action_handlers.py  (replace _init_tools, lines 25-38)
async def _init_tools(db, current_user):
    from MCP.tools import InvoiceTools
    from commercial.ai.inprocess.base import InProcessAPIClient

    return InvoiceTools(InProcessAPIClient(db=db, current_user=current_user))
```

- [ ] **Step 4: Thread `db` + `current_user` to every `_init_tools` call site**

In `action_handlers.py`, change `handle_early_actions` to accept the user object and pass both down. Signature (lines 198-207) becomes:

```python
async def handle_early_actions(
    message: str,
    lower_message: str,
    page_context: Optional[Dict[str, Any]],
    ai_config: Any,
    db: Session,
    current_user,
    mode: Optional[str] = None,
    confirmed_action: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
```

Replace `current_user_email` usages inside `handle_early_actions` with `current_user.email` where a string is needed, and update the 6 `_init_tools(...)` calls. Each of these five call sites (lines ~224, 245, 321, 381, 505) changes from `await _init_tools(current_user_email)` to:

```python
                tools = await _init_tools(db, current_user)
```

The onboarding branch call (line ~165) is inside `_handle_onboarding_action`; update that function's signature and the call from `handle_early_actions`:

```python
# _handle_onboarding_action signature (was: message, confirmed_action, ai_config, current_user_email)
async def _handle_onboarding_action(message, confirmed_action, ai_config, db, current_user):
    ...
        tools = await _init_tools(db, current_user)   # was: await _init_tools(current_user_email)
```

And where `handle_early_actions` calls it (the `if mode == "onboarding":` branch near the top):

```python
    if mode == "onboarding":
        return await _handle_onboarding_action(message, confirmed_action, ai_config, db, current_user)
```

(`_extract_onboarding_action(message, ai_config)` still uses `ai_config` only — unchanged.)

- [ ] **Step 5: Update the `chat.py` call + construction**

In `chat.py`, change the `handle_early_actions` call (lines 151-160) to pass the object:

```python
        result = await handle_early_actions(
            message=request.message,
            lower_message=lower_message,
            page_context=page_context,
            ai_config=ai_config,
            db=db,
            current_user=current_user,
            mode=request.mode,
            confirmed_action=request.confirmed_action,
        )
```

Replace the MCP tools construction block (chat.py:201-222) with:

```python
        # Initialize MCP tools using an in-process client (no self-HTTP, reuses this
        # request's tenant session). Unmigrated methods fall back to HTTP internally.
        from MCP.tools import InvoiceTools
        from commercial.ai.inprocess.base import InProcessAPIClient

        api_client = InProcessAPIClient(db=db, current_user=current_user)
        tools = InvoiceTools(api_client)
```

- [ ] **Step 6: Update `test_onboarding_actions.py` for the new signatures**

This signature change breaks the existing onboarding tests: they call `handle_early_actions(..., current_user_email="u@x.com", ...)` and the `patch_tools` fixture monkeypatches `_init_tools` with an `(email)` signature. Update both. In `api/tests/test_onboarding_actions.py`:

Change the `patch_tools` fixture's fake to the new `(db, current_user)` signature:

```python
@pytest.fixture
def patch_tools(monkeypatch):
    fake = _FakeTools()

    async def _fake_init(db, current_user):
        return fake

    monkeypatch.setattr(ah, "_init_tools", _fake_init)
    return fake
```

Add a module-level test user near `_Cfg`:

```python
_USER = SimpleNamespace(id=1, email="u@x.com", tenant_id=1, role="admin", is_superuser=True)
```

(add `from types import SimpleNamespace` at the top if not present), and in **every** `ah.handle_early_actions(...)` call in that file replace `current_user_email="u@x.com"` with `current_user=_USER`.

- [ ] **Step 7: Run wiring test + onboarding regression suite**

Run: `docker compose exec api python -m pytest tests/test_inprocess_wiring.py tests/test_onboarding_actions.py -v`
Expected: PASS (wiring test + all 7 onboarding tests).

- [ ] **Step 8: Commit**

```bash
git add api/commercial/ai/routers/chat.py api/commercial/ai/routers/action_handlers.py api/tests/test_inprocess_wiring.py api/tests/test_onboarding_actions.py
git commit -m "feat(ai): route chat tool calls through InProcessAPIClient (HTTP fallback for now)"
```

---

### Task 4: In-process `create_client`

**Files:**
- Create: `api/commercial/ai/inprocess/clients_domain.py`
- Modify: `api/commercial/ai/inprocess/base.py` (add the mixin to `InProcessAPIClient`'s bases)
- Test: `api/tests/test_inprocess_clients.py`

**Interfaces:**
- Produces: `ClientsInProcessMixin.create_client(self, client_data: dict) -> dict` — returns a `_client_to_dict`-shaped dict; raises on permission/duplicate failure (tool layer envelopes it).

- [ ] **Step 1: Write the failing test**

```python
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
    monkeypatch.setattr(cd, "require_component_permission", lambda *a, **k: None)
    monkeypatch.setattr(cd, "log_audit_event", lambda **k: None)
    monkeypatch.setattr(cd, "maybe_send_operation_notification", lambda *a, **k: None)
    client = InProcessAPIClient(db=db_session, current_user=_admin())
    await client.create_client({"name": "Acme", "email": "dup@acme.com"})
    with pytest.raises(Exception):
        await client.create_client({"name": "Acme", "email": "dup@acme.com"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/test_inprocess_clients.py -v`
Expected: FAIL — module `commercial.ai.inprocess.clients_domain` does not exist.

- [ ] **Step 3: Implement the clients mixin**

```python
# api/commercial/ai/inprocess/clients_domain.py
"""Clients-domain methods for the in-process AI client.

Mirrors core/routers/clients.py behavior but runs against the request's tenant
session, reusing the same shared helpers (RBAC, audit, validation, serialization,
notification). Spyable helpers are imported at module top for testability.
"""

from typing import Any, Dict

from core.utils.rbac import require_component_permission
from core.utils.audit import log_audit_event
from core.services.operation_notifications import maybe_send_operation_notification
from core.constants.error_codes import CLIENT_ALREADY_EXISTS


def _tenant_default_currency(tenant_id: int) -> str:
    from core.models.database import get_master_db
    from core.models.models import Tenant

    master_db = next(get_master_db())
    try:
        tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant and tenant.default_currency:
            return tenant.default_currency
        return "USD"
    except Exception:
        return "USD"
    finally:
        master_db.close()


class ClientsInProcessMixin:
    async def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        from core.models.models_per_tenant import Client
        from core.schemas.client import ClientCreate
        from core.utils.timezone import get_tenant_timezone_aware_datetime
        from core.routers.clients import _client_to_dict

        db = self._db
        user = self._current_user

        require_component_permission(db, user, "customers", "user", "create clients")

        # Validate + normalize via the same schema the route uses.
        payload = ClientCreate(**client_data)
        data = payload.model_dump()
        if data.get("email") is not None and data["email"].strip() == "":
            data["email"] = None

        # Duplicate guard (mirror the route: compare decrypted name+email).
        if data.get("email") is not None:
            for existing in db.query(Client).all():
                if existing.name == data.get("name") and existing.email == data["email"]:
                    raise ValueError(CLIENT_ALREADY_EXISTS)

        if not data.get("preferred_currency") or not str(data.get("preferred_currency")).strip():
            data["preferred_currency"] = _tenant_default_currency(user.tenant_id)

        with db.begin_nested():
            db_client = Client(
                **data,
                created_at=get_tenant_timezone_aware_datetime(db),
                updated_at=get_tenant_timezone_aware_datetime(db),
            )
            db.add(db_client)
        db.commit()
        db.refresh(db_client)

        log_audit_event(
            db=db,
            user_id=user.id,
            user_email=user.email,
            action="CREATE",
            resource_type="client",
            resource_id=str(db_client.id),
            resource_name=db_client.name,
            details=data,
            status="success",
        )
        maybe_send_operation_notification(
            db,
            event_type="client_created",
            user_id=user.id,
            tenant_id=user.tenant_id,
            resource_type="client",
            resource_id=str(db_client.id),
            resource_name=db_client.name,
            details={
                "email": db_client.email,
                "phone": db_client.phone or "N/A",
                "preferred_currency": db_client.preferred_currency,
            },
        )
        return _client_to_dict(db_client)
```

- [ ] **Step 4: Add the mixin to the base client**

In `api/commercial/ai/inprocess/base.py`, change the class declaration and import:

```python
from commercial.ai.inprocess.clients_domain import ClientsInProcessMixin
```
```python
class InProcessAPIClient(ClientsInProcessMixin):
```

(Keep `__init__`, `_get_fallback`, `__getattr__` exactly as in Task 2. `create_client` is now found normally, so `__getattr__` no longer delegates it.)

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/test_inprocess_clients.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add api/commercial/ai/inprocess/clients_domain.py api/commercial/ai/inprocess/base.py api/tests/test_inprocess_clients.py
git commit -m "feat(ai): in-process create_client (reuses RBAC/audit/notify/serializer)"
```

---

### Task 5: In-process `list_clients`

**Files:**
- Modify: `api/commercial/ai/inprocess/clients_domain.py`
- Test: `api/tests/test_inprocess_clients.py` (add a test)

**Interfaces:**
- Produces: `ClientsInProcessMixin.list_clients(self, skip: int = 0, limit: int = 100) -> dict` returning `{"items": [<_client_to_dict>...], "total": int}` (the shape `read_clients` returns; `_extract_items_from_response` reads `"items"`).

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_inprocess_clients.py  (append)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/test_inprocess_clients.py::test_list_clients_returns_items_shape -v`
Expected: FAIL — `list_clients` delegates to the HTTP fallback (no httpx target in tests → error/AttributeError).

- [ ] **Step 3: Implement `list_clients`**

Add to `ClientsInProcessMixin` (mirrors `read_clients`, `core/routers/clients.py:61-131`):

```python
    async def list_clients(self, skip: int = 0, limit: int = 100, label_filter=None) -> Dict[str, Any]:
        import sqlalchemy as sa
        from sqlalchemy import func, and_
        from core.models.models_per_tenant import Client, Invoice, Payment
        from core.routers.clients import _client_to_dict

        db = self._db
        query = db.query(
            Client,
            func.coalesce(func.sum(Payment.amount), 0).label("total_paid"),
            func.coalesce(func.sum(Invoice.amount), 0).label("total_invoiced"),
            func.coalesce(
                func.sum(
                    sa.case(
                        (and_(Invoice.status.in_(["pending", "overdue", "partially_paid"]), Invoice.is_deleted == False), Invoice.amount),  # noqa: E712
                        else_=0,
                    )
                ), 0
            ).label("pending_invoiced"),
            func.coalesce(
                func.sum(
                    sa.case(
                        (and_(Invoice.status.in_(["pending", "overdue", "partially_paid"]), Invoice.is_deleted == False), Payment.amount),  # noqa: E712
                        else_=0,
                    )
                ), 0
            ).label("pending_paid"),
        ).outerjoin(
            Invoice, and_(Invoice.client_id == Client.id, Invoice.is_deleted == False)  # noqa: E712
        ).outerjoin(
            Payment, Payment.invoice_id == Invoice.id
        )

        if label_filter:
            query = query.filter(sa.cast(Client.labels, sa.String).ilike(f"%{label_filter}%"))

        total_count = query.group_by(Client.id).count()
        rows = query.group_by(Client.id).offset(skip).limit(limit).all()

        items = []
        for client, total_paid, total_invoiced, pending_invoiced, pending_paid in rows:
            outstanding = float(pending_invoiced or 0) - float(pending_paid or 0)
            items.append(_client_to_dict(client, total_paid=float(total_paid), outstanding_balance=outstanding))
        return {"items": items, "total": total_count}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/test_inprocess_clients.py -v`
Expected: PASS (all clients tests).

- [ ] **Step 5: Commit**

```bash
git add api/commercial/ai/inprocess/clients_domain.py api/tests/test_inprocess_clients.py
git commit -m "feat(ai): in-process list_clients (aggregate shape parity with read_clients)"
```

---

### Task 6: In-process `get_clients_with_outstanding_balance`

The HTTP method targets `/clients/outstanding-balance`, which **does not exist** (the request 422s via the `/{client_id}` route), so today this always fails and `OutstandingHandler` falls through to the LLM. The in-process version implements the intended behavior: clients with `balance > 0`, shaped with the `outstanding_balance` key the consumer (`intents/outstanding.py`) expects. This cannot regress (the old path never returned data).

**Files:**
- Modify: `api/commercial/ai/inprocess/clients_domain.py`
- Test: `api/tests/test_inprocess_clients.py` (add a test)

**Interfaces:**
- Produces: `ClientsInProcessMixin.get_clients_with_outstanding_balance(self) -> list[dict]` — each dict has at least `name`, `outstanding_balance`, `email`, `phone`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_inprocess_clients.py  (append)
@pytest.mark.asyncio
async def test_outstanding_balance_lists_clients_with_positive_balance(db_session, monkeypatch):
    monkeypatch.setattr(cd, "require_component_permission", lambda *a, **k: None)
    monkeypatch.setattr(cd, "log_audit_event", lambda **k: None)
    monkeypatch.setattr(cd, "maybe_send_operation_notification", lambda *a, **k: None)
    client = InProcessAPIClient(db=db_session, current_user=_admin())
    await client.create_client({"name": "Owes", "email": "owes@x.com"})

    from core.models.models_per_tenant import Client
    row = db_session.query(Client).filter_by(name="Owes").first()
    row.balance = 150.0
    db_session.commit()

    result = await client.get_clients_with_outstanding_balance()
    assert isinstance(result, list)
    assert any(c["name"] == "Owes" and c["outstanding_balance"] == 150.0 for c in result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/test_inprocess_clients.py::test_outstanding_balance_lists_clients_with_positive_balance -v`
Expected: FAIL — method delegates to HTTP fallback.

- [ ] **Step 3: Implement the method**

Add to `ClientsInProcessMixin`:

```python
    async def get_clients_with_outstanding_balance(self):
        from core.models.models_per_tenant import Client

        rows = (
            self._db.query(Client)
            .filter(Client.balance > 0)
            .order_by(Client.balance.desc())
            .all()
        )
        return [
            {
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "outstanding_balance": float(c.balance or 0),
                "preferred_currency": c.preferred_currency,
            }
            for c in rows
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/test_inprocess_clients.py -v`
Expected: PASS (all clients tests).

- [ ] **Step 5: Commit**

```bash
git add api/commercial/ai/inprocess/clients_domain.py api/tests/test_inprocess_clients.py
git commit -m "feat(ai): in-process get_clients_with_outstanding_balance (balance>0)"
```

---

### Task 7: Verification

**Files:** none (verification only).

- [ ] **Step 1: Full in-process + onboarding + notifications suite**

Run: `docker compose exec api python -m pytest tests/test_inprocess_base.py tests/test_inprocess_wiring.py tests/test_inprocess_clients.py tests/test_operation_notifications.py tests/test_onboarding_actions.py -v`
Expected: all PASS.

- [ ] **Step 2: Standalone MCP server untouched (regression guard)**

Run: `docker compose exec api python -c "import MCP.server._shared as s; import inspect; assert 'InvoiceAPIClient' in inspect.getsource(s), 'standalone server must still use the HTTP InvoiceAPIClient'; print('standalone MCP unchanged')"`
Expected: prints "standalone MCP unchanged".

- [ ] **Step 3: Smoke the chat path imports**

Run: `docker compose exec api python -c "import commercial.ai.routers.chat, commercial.ai.routers.action_handlers, commercial.ai.inprocess.base, commercial.ai.inprocess.clients_domain; print('imports OK')"`
Expected: "imports OK".

- [ ] **Step 4: Manual — confirm clients calls no longer self-HTTP**

With `YFW_LOG_POOL_STATS=1` on the api service (see `api/core/utils/pool_stats.py` on the testing branch), send an AI chat that triggers a clients read/create (e.g. "list my clients", or onboarding "create a client …"). Confirm in logs that the tenant pool shows **one** checkout for the chat request (no second checkout from a nested `/clients/` self-call). Re-run `api/scripts/pool_loadtest.py` against a clients-listing prompt and confirm the per-request connection count is 1.

---

## Self-Review

**Spec coverage (clients slice):**
- New `InProcessAPIClient`, injected at the 2 sites, same surface, standalone MCP untouched → Tasks 2, 3, 7. ✓
- Reuse shared helpers (RBAC/audit/validation/serializer/notification), reimplement only glue → Task 4 (create_client) reuses `require_component_permission`/`log_audit_event`/`ClientCreate`/`_client_to_dict`/`maybe_send_operation_notification`. ✓
- Reuse request session, no new connection; SAVEPOINT per write → Task 4 `db.begin_nested()` + `db.commit()`. ✓
- Raise-on-failure + response-shape parity → Tasks 4-6 (raise; `{items,total}` / `_client_to_dict` / list shapes). ✓
- Incremental HTTP fallback → Task 2 `__getattr__`. ✓
- Notification parity + APP_NAME bug fix → Task 1. ✓
- Tests: RBAC enforced, audit written, shape parity, standalone-MCP regression → Tasks 4 + 7. ✓

**Placeholder scan:** No TBD/"handle appropriately". The `/clients/outstanding-balance` behavior change is explicit and justified (Task 6 preamble).

**Type consistency:** `_init_tools(db, current_user)`, `InProcessAPIClient(db, current_user)`, `_db`/`_current_user`/`_fallback`, `ClientsInProcessMixin`, and the `{items,total}` / `_client_to_dict` shapes are consistent across Tasks 2-6. `maybe_send_operation_notification(db, *, event_type, user_id, tenant_id, resource_type, resource_id, resource_name, details)` is identical in Task 1 (def), Task 1 Step 5 (route call), and Task 4 (mixin call).

**Scope:** One domain (clients, 3 methods) + the shared scaffolding all later domains reuse. Subsequent domains (invoices, expenses, settings, …) each get their own plan following Tasks 4-6 as the template; Tasks 1-3 are one-time scaffolding.
