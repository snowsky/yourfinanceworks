# AI-Guided Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a commercial, conversational setup wizard that walks new tenants to first value by proposing onboarding actions (create client, set branding, draft invoice, record expense) and executing them only after an explicit confirm.

**Architecture:** Option B — extend the existing `/ai/chat` fast-path with an opt-in `mode:"onboarding"`. An isolated `_handle_onboarding_action` branch added to `action_handlers.py` returns a `proposed_action` envelope instead of writing; a follow-up call carrying `confirmed_action` executes one whitelisted MCP tool. The live assistant's immediate-write behavior is untouched (the branch only runs under `mode:"onboarding"`). Two thin frontend entry points (a dashboard card and a chat quick-action) share one hook + one confirm component. Progress is read from the existing derive-on-read activation checklist (no new progress state).

**Tech Stack:** FastAPI, SQLAlchemy (per-tenant DB), LiteLLM, pytest (backend); React + TypeScript, TanStack Query, Vitest + React Testing Library (frontend).

## Global Constraints

- Commercial gating: the chat endpoint is already guarded by `@require_feature("ai_chat")`. No new feature flag is introduced. Frontend entry points must check `isFeatureEnabled('ai_chat')`.
- Onboarding writes are limited to a fixed whitelist: `create_client`, `set_branding`, `create_invoice`, `create_expense`. No other action is ever executed by onboarding mode.
- Nothing writes without an explicit user Confirm (propose → confirm/edit → execute).
- `mode:"onboarding"` is opt-in; default (absent) behavior of `/ai/chat` must remain byte-for-byte unchanged.
- `set_branding` writes only the validated `invoice_branding` keys (`brand_color`, `accent_color`); company name is NOT a branding field and stays out of scope (deep-link only).
- Backend code: PEP8, type annotations on all signatures, `logging` not `print` in new code.
- Settings persistence pattern: a single `Settings` row with `key`/`value` (JSON)/`category` (see `onboarding_checklist.py:67-85`).

---

### Task 1: Extend `ChatRequest` with onboarding fields

**Files:**
- Modify: `api/commercial/ai/routers/chat_models.py:12-15`
- Test: `api/tests/test_chat_models.py` (create)

**Interfaces:**
- Produces: `ChatRequest` with two new optional fields — `mode: Optional[str] = None` and `confirmed_action: Optional[Dict[str, Any]] = None`. `confirmed_action`, when present, has shape `{"action": str, "params": dict}`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_chat_models.py
from commercial.ai.routers.chat_models import ChatRequest


def test_chat_request_defaults_have_no_onboarding_fields():
    req = ChatRequest(message="hi")
    assert req.mode is None
    assert req.confirmed_action is None


def test_chat_request_accepts_onboarding_mode_and_confirmed_action():
    req = ChatRequest(
        message="create my first client",
        mode="onboarding",
        confirmed_action={"action": "create_client", "params": {"name": "Acme", "email": "ap@acme.com"}},
    )
    assert req.mode == "onboarding"
    assert req.confirmed_action["action"] == "create_client"
    assert req.confirmed_action["params"]["name"] == "Acme"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest api/tests/test_chat_models.py -v`
Expected: FAIL — `ChatRequest` has no field `mode` (Pydantic ignores/raises on unknown kwargs).

- [ ] **Step 3: Add the fields**

```python
# api/commercial/ai/routers/chat_models.py
class ChatRequest(BaseModel):
    message: str
    config_id: int = 0  # Default to 0 if not provided
    page_context: Optional[Dict[str, Any]] = None
    mode: Optional[str] = None  # "onboarding" enables the propose/confirm gate
    confirmed_action: Optional[Dict[str, Any]] = None  # {"action": str, "params": dict}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api pytest api/tests/test_chat_models.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add api/commercial/ai/routers/chat_models.py api/tests/test_chat_models.py
git commit -m "feat(ai): add mode + confirmed_action fields to ChatRequest"
```

---

### Task 2: `set_branding` MCP tool + `update_settings` API-client method

**Files:**
- Modify: `api/MCP/tools/settings.py` (add `SetBrandingArgs` + `SettingsToolsMixin.set_branding`)
- Modify: `api/commercial/ai/routers/auth_client.py` (add `update_settings`)
- Modify: `api/MCP/api_client.py` (add `update_settings` so the standalone MCP client matches)
- Test: `api/tests/test_set_branding_tool.py` (create)

**Interfaces:**
- Consumes: `self.api_client.update_settings(settings_data: Dict[str, Any]) -> Dict[str, Any]` (PUT `/settings/`).
- Produces: `SettingsToolsMixin.set_branding(self, brand_color: Optional[str] = None, accent_color: Optional[str] = None) -> Dict[str, Any]` returning `{"success": bool, "data": ..., "message": ...}` on success or `{"success": False, "error": ...}`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_set_branding_tool.py
import pytest
from MCP.tools.settings import SettingsToolsMixin


class _FakeClient:
    def __init__(self):
        self.sent = None

    async def update_settings(self, settings_data):
        self.sent = settings_data
        return {"invoice_branding": settings_data["invoice_branding"]}


class _Tools(SettingsToolsMixin):
    def __init__(self, client):
        self.api_client = client


@pytest.mark.asyncio
async def test_set_branding_sends_only_provided_colors():
    client = _FakeClient()
    tools = _Tools(client)
    result = await tools.set_branding(accent_color="#3b82f6")
    assert result["success"] is True
    assert client.sent == {"invoice_branding": {"accent_color": "#3b82f6"}}


@pytest.mark.asyncio
async def test_set_branding_includes_both_colors_when_given():
    client = _FakeClient()
    tools = _Tools(client)
    await tools.set_branding(brand_color="#1e3a8a", accent_color="#3b82f6")
    assert client.sent["invoice_branding"] == {"brand_color": "#1e3a8a", "accent_color": "#3b82f6"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest api/tests/test_set_branding_tool.py -v`
Expected: FAIL — `AttributeError: 'set_branding'`.

- [ ] **Step 3: Add the tool method**

```python
# api/MCP/tools/settings.py  (add near the other Args classes)
class SetBrandingArgs(BaseModel):
    brand_color: Optional[str] = Field(default=None, description="Primary brand color as #RRGGBB hex")
    accent_color: Optional[str] = Field(default=None, description="Accent color as #RRGGBB hex")
```

```python
# api/MCP/tools/settings.py  (add inside SettingsToolsMixin)
    async def set_branding(self, brand_color: Optional[str] = None, accent_color: Optional[str] = None) -> Dict[str, Any]:
        """Set invoice branding colors (onboarding). Only provided colors are written."""
        try:
            branding: Dict[str, Any] = {}
            if brand_color is not None:
                branding["brand_color"] = brand_color
            if accent_color is not None:
                branding["accent_color"] = accent_color
            if not branding:
                return {"success": False, "error": "No branding values provided"}

            settings = await self.api_client.update_settings({"invoice_branding": branding})
            return {"success": True, "data": settings, "message": "Branding updated successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to set branding: {e}"}
```

- [ ] **Step 4: Add `update_settings` to both API clients**

```python
# api/commercial/ai/routers/auth_client.py  (add near update_cashflow_thresholds, ~line 193)
    async def update_settings(self, settings_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._make_request("PUT", "/settings/", json=settings_data)
```

```python
# api/MCP/api_client.py  (add near get_settings, ~line 702; mirror that method's request style)
    async def update_settings(self, settings_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._make_request("PUT", "/settings/", json=settings_data)
```

(If `api/MCP/api_client.py` uses a differently-named request helper than `_make_request`, match the helper used by its existing `get_settings` at line 702.)

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose exec api pytest api/tests/test_set_branding_tool.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add api/MCP/tools/settings.py api/commercial/ai/routers/auth_client.py api/MCP/api_client.py api/tests/test_set_branding_tool.py
git commit -m "feat(ai): add set_branding MCP tool + update_settings client method"
```

---

### Task 3: Onboarding confirm gate in `action_handlers.py`

This is the core. Add an isolated onboarding branch that (a) when `confirmed_action` is present, executes one whitelisted tool, and (b) otherwise returns a `proposed_action` envelope (no write). The branch runs only under `mode == "onboarding"` and early-returns before the existing statement/client/expense code, so the live path is untouched.

**Files:**
- Modify: `api/commercial/ai/routers/action_handlers.py` (new helpers + branch; extend `handle_early_actions` signature)
- Modify: `api/commercial/ai/routers/chat.py:151-158` (pass `mode` + `confirmed_action`)
- Test: `api/tests/test_onboarding_actions.py` (create)

**Interfaces:**
- Consumes: `_init_tools(current_user_email)` (existing, `action_handlers.py:25`); MCP tools `create_client(name, email, phone)`, `set_branding(brand_color, accent_color)`, `create_invoice(client_id, amount, due_date, status, notes)`, `create_expense(amount, currency, expense_date, category, vendor)`.
- Produces:
  - `_ONBOARDING_ACTIONS: dict[str, callable]` mapping action name → async dispatch over a `tools` object.
  - `_extract_onboarding_action(message: str, ai_config: Any) -> Optional[Dict[str, Any]]` → `{"action": str, "params": dict}` or `None` (tests monkeypatch this).
  - `_handle_onboarding_action(message, confirmed_action, ai_config, current_user_email) -> Optional[Dict[str, Any]]`.
  - Propose envelope: `{"success": True, "data": {"type": "proposed_action", "action": str, "params": dict, "source": "onboarding"}}`.
  - Execute envelope: `{"success": True, "data": {"response": str, "executed_action": str, "result": dict, "source": "onboarding"}}` (or `{"success": False, "error": ...}`).
- `handle_early_actions(...)` gains kwargs `mode: Optional[str] = None, confirmed_action: Optional[Dict[str, Any]] = None`.

- [ ] **Step 1: Write the failing tests (execute path + propose path + whitelist + passthrough)**

```python
# api/tests/test_onboarding_actions.py
import pytest

import commercial.ai.routers.action_handlers as ah


class _FakeTools:
    def __init__(self):
        self.calls = []

    async def create_client(self, name, email=None, phone=None, address=None):
        self.calls.append(("create_client", {"name": name, "email": email, "phone": phone}))
        return {"success": True, "data": {"id": 1, "name": name}}

    async def set_branding(self, brand_color=None, accent_color=None):
        self.calls.append(("set_branding", {"brand_color": brand_color, "accent_color": accent_color}))
        return {"success": True, "data": {"accent_color": accent_color}}


class _Cfg:
    provider_name = "openai"
    model_name = "gpt-4o-mini"


@pytest.fixture
def patch_tools(monkeypatch):
    fake = _FakeTools()

    async def _fake_init(email):
        return fake

    monkeypatch.setattr(ah, "_init_tools", _fake_init)
    return fake


@pytest.mark.asyncio
async def test_onboarding_confirmed_action_executes_tool(patch_tools):
    result = await ah.handle_early_actions(
        message="", lower_message="", page_context=None, ai_config=_Cfg(), db=None,
        current_user_email="u@x.com", mode="onboarding",
        confirmed_action={"action": "create_client", "params": {"name": "Acme", "email": "ap@acme.com"}},
    )
    assert result["success"] is True
    assert result["data"]["executed_action"] == "create_client"
    assert patch_tools.calls == [("create_client", {"name": "Acme", "email": "ap@acme.com", "phone": None})]


@pytest.mark.asyncio
async def test_onboarding_proposes_without_executing(monkeypatch, patch_tools):
    monkeypatch.setattr(
        ah, "_extract_onboarding_action",
        lambda message, ai_config: {"action": "create_client", "params": {"name": "Acme", "email": "ap@acme.com"}},
    )
    result = await ah.handle_early_actions(
        message="add a client called Acme ap@acme.com", lower_message="add a client called acme ap@acme.com",
        page_context=None, ai_config=_Cfg(), db=None, current_user_email="u@x.com", mode="onboarding",
    )
    assert result["data"]["type"] == "proposed_action"
    assert result["data"]["action"] == "create_client"
    assert patch_tools.calls == []  # nothing executed


@pytest.mark.asyncio
async def test_onboarding_rejects_non_whitelisted_action(patch_tools):
    result = await ah.handle_early_actions(
        message="", lower_message="", page_context=None, ai_config=_Cfg(), db=None,
        current_user_email="u@x.com", mode="onboarding",
        confirmed_action={"action": "delete_everything", "params": {}},
    )
    assert result["success"] is False
    assert patch_tools.calls == []


@pytest.mark.asyncio
async def test_onboarding_no_action_falls_through(monkeypatch):
    monkeypatch.setattr(ah, "_extract_onboarding_action", lambda message, ai_config: None)
    result = await ah.handle_early_actions(
        message="what is an invoice?", lower_message="what is an invoice?", page_context=None,
        ai_config=_Cfg(), db=None, current_user_email="u@x.com", mode="onboarding",
    )
    assert result is None  # falls through to normal chat answer
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api pytest api/tests/test_onboarding_actions.py -v`
Expected: FAIL — `handle_early_actions() got an unexpected keyword argument 'mode'`.

- [ ] **Step 3: Add the action whitelist + dispatchers**

```python
# api/commercial/ai/routers/action_handlers.py  (add after _init_tools)
async def _dispatch_create_client(tools, params):
    return await tools.create_client(
        name=params["name"], email=params.get("email"), phone=params.get("phone")
    )


async def _dispatch_set_branding(tools, params):
    return await tools.set_branding(
        brand_color=params.get("brand_color"), accent_color=params.get("accent_color")
    )


async def _dispatch_create_invoice(tools, params):
    return await tools.create_invoice(
        client_id=int(params["client_id"]), amount=float(params["amount"]),
        due_date=params["due_date"], status="draft", notes=params.get("notes"),
    )


async def _dispatch_create_expense(tools, params):
    return await tools.create_expense(
        amount=float(params["amount"]), currency=params.get("currency", "USD"),
        expense_date=params["expense_date"], category=params["category"], vendor=params.get("vendor"),
    )


_ONBOARDING_ACTIONS = {
    "create_client": _dispatch_create_client,
    "set_branding": _dispatch_set_branding,
    "create_invoice": _dispatch_create_invoice,
    "create_expense": _dispatch_create_expense,
}

_ONBOARDING_LABELS = {
    "create_client": "Client created",
    "set_branding": "Branding updated",
    "create_invoice": "Draft invoice created",
    "create_expense": "Expense recorded",
}
```

- [ ] **Step 4: Add the extraction helper + onboarding handler**

```python
# api/commercial/ai/routers/action_handlers.py
def _extract_onboarding_action(message: str, ai_config: Any) -> Optional[Dict[str, Any]]:
    """Use the LLM to map an onboarding message to one whitelisted action + params.

    Returns {"action": str, "params": dict} or None when no action is clearly intended.
    """
    try:
        from litellm import completion
    except ImportError:
        return None

    system = (
        "You map a user's onboarding message to ONE setup action. "
        "Allowed actions: create_client (params: name, email, phone), "
        "set_branding (params: brand_color, accent_color as #RRGGBB hex), "
        "create_invoice (params: client_id, amount, due_date YYYY-MM-DD, notes), "
        "create_expense (params: amount, currency, expense_date YYYY-MM-DD, category, vendor). "
        "Respond with ONLY compact JSON: {\"action\": <name|null>, \"params\": {...}}. "
        "Use null when the message is a question or no action is clearly intended. "
        "Never invent IDs you were not given."
    )
    model = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name
    try:
        resp = completion(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": message}],
            api_key=getattr(ai_config, "api_key", None),
            api_base=getattr(ai_config, "provider_url", None),
            temperature=0,
        )
        content = resp["choices"][0]["message"]["content"].strip()
        parsed = json.loads(content)
    except Exception as exc:
        logger.warning("Onboarding action extraction failed: %s", exc)
        return None

    action = parsed.get("action")
    if action not in _ONBOARDING_ACTIONS:
        return None
    return {"action": action, "params": parsed.get("params") or {}}


async def _handle_onboarding_action(
    message: str, confirmed_action: Optional[Dict[str, Any]], ai_config: Any, current_user_email: str,
) -> Optional[Dict[str, Any]]:
    # Execute path: only after explicit confirmation.
    if confirmed_action:
        action = confirmed_action.get("action")
        params = confirmed_action.get("params") or {}
        dispatch = _ONBOARDING_ACTIONS.get(action)
        if dispatch is None:
            return {"success": False, "error": f"Unknown onboarding action: {action}"}
        tools = await _init_tools(current_user_email)
        try:
            result = await dispatch(tools, params)
        except Exception as exc:
            logger.warning("Onboarding action %s failed: %s", action, exc)
            return {"success": False, "error": f"Could not complete {action}: {exc}"}
        if not result.get("success"):
            return {"success": False, "error": result.get("error", f"{action} failed")}
        return {
            "success": True,
            "data": {
                "response": f"✅ {_ONBOARDING_LABELS.get(action, 'Done')}.",
                "executed_action": action,
                "result": result,
                "source": "onboarding",
            },
        }

    # Propose path: classify + return for confirmation, never execute.
    proposal = _extract_onboarding_action(message, ai_config)
    if proposal is None:
        return None  # let the normal chat path answer the question
    return {
        "success": True,
        "data": {
            "type": "proposed_action",
            "action": proposal["action"],
            "params": proposal["params"],
            "source": "onboarding",
        },
    }
```

- [ ] **Step 5: Wire the branch into `handle_early_actions`**

Change the signature and add the early branch at the very top of the function body (before the statement/page-context logic at `action_handlers.py:49`):

```python
# api/commercial/ai/routers/action_handlers.py
async def handle_early_actions(
    message: str,
    lower_message: str,
    page_context: Optional[Dict[str, Any]],
    ai_config: Any,
    db: Session,
    current_user_email: str,
    mode: Optional[str] = None,
    confirmed_action: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    # Onboarding mode: propose/confirm gate, isolated from the live write fast-path.
    if mode == "onboarding":
        return await _handle_onboarding_action(message, confirmed_action, ai_config, current_user_email)

    # Page-aware statement actions (use current page context if available)
    entity = page_context.get("entity") if isinstance(page_context, dict) else None
    # ... existing body unchanged ...
```

- [ ] **Step 6: Pass the new fields from the chat endpoint**

```python
# api/commercial/ai/routers/chat.py:151-158
        result = await handle_early_actions(
            message=request.message,
            lower_message=lower_message,
            page_context=page_context,
            ai_config=ai_config,
            db=db,
            current_user_email=current_user.email,
            mode=request.mode,
            confirmed_action=request.confirmed_action,
        )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `docker compose exec api pytest api/tests/test_onboarding_actions.py -v`
Expected: PASS (all four tests).

- [ ] **Step 8: Commit**

```bash
git add api/commercial/ai/routers/action_handlers.py api/commercial/ai/routers/chat.py api/tests/test_onboarding_actions.py
git commit -m "feat(ai): onboarding propose/confirm action gate in /ai/chat"
```

---

### Task 4: Onboarding-assistant status + dismiss endpoints

**Files:**
- Create: `api/core/services/onboarding_assistant.py`
- Modify: `api/core/routers/onboarding.py` (add two routes)
- Test: `api/tests/test_onboarding_assistant_service.py` (create)

**Interfaces:**
- Produces: `OnboardingAssistantService(db)` with `status() -> {"ai_configured": bool, "dismissed": bool}` and `dismiss() -> {"ai_configured": bool, "dismissed": True}`.
- Routes: `GET /onboarding/assistant/status`, `POST /onboarding/assistant/dismiss` (the latter guarded by `require_non_viewer`).
- Settings key: `onboarding_assistant`, value `{"dismissed": True}`, category `"onboarding"`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_onboarding_assistant_service.py
from types import SimpleNamespace
from core.services.onboarding_assistant import OnboardingAssistantService, ASSISTANT_DISMISS_KEY


class _Query:
    def __init__(self, store, model_name):
        self._store = store
        self._model = model_name
        self._key = None

    def filter(self, *args):
        # crude: remember the key compared in tests via the store
        return self

    def first(self):
        return self._store.get(self._model)


class _FakeDB:
    """Minimal stand-in: maps a model to a single stored row."""
    def __init__(self, ai_config_row=None, settings_row=None):
        self.rows = {"AIConfig": ai_config_row, "Settings": settings_row}
        self.added = []
        self.committed = False

    def query(self, entity):
        name = getattr(entity, "__name__", getattr(getattr(entity, "class_", None), "__name__", "AIConfig"))
        return _Query(self.rows, name)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True


def test_status_reports_not_configured_and_not_dismissed():
    svc = OnboardingAssistantService(_FakeDB())
    status = svc.status()
    assert status == {"ai_configured": False, "dismissed": False}


def test_status_reports_configured_when_active_config_exists():
    active = SimpleNamespace(is_active=True, is_default=True)
    svc = OnboardingAssistantService(_FakeDB(ai_config_row=active))
    assert svc.status()["ai_configured"] is True
```

> Note: the query stub above is intentionally minimal. If `OnboardingAssistantService` queries with chained `.filter().first()` shapes the stub cannot satisfy, prefer writing this as an integration test using the real per-tenant DB fixture (see `api/tests/test_onboarding_checklist.py` for the established fixture pattern) and assert against seeded `AIConfig` / `Settings` rows instead.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest api/tests/test_onboarding_assistant_service.py -v`
Expected: FAIL — module `core.services.onboarding_assistant` does not exist.

- [ ] **Step 3: Implement the service**

```python
# api/core/services/onboarding_assistant.py
"""Onboarding assistant status: is AI usable, and has the card been dismissed."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ASSISTANT_DISMISS_KEY = "onboarding_assistant"


class OnboardingAssistantService:
    def __init__(self, db: Session):
        self.db = db

    def status(self) -> dict:
        return {"ai_configured": self._ai_configured(), "dismissed": self._is_dismissed()}

    def dismiss(self) -> dict:
        from core.models.models_per_tenant import Settings

        record = self.db.query(Settings).filter(Settings.key == ASSISTANT_DISMISS_KEY).first()
        if record is None:
            record = Settings(key=ASSISTANT_DISMISS_KEY, value={"dismissed": True}, category="onboarding")
            self.db.add(record)
        else:
            record.value = {"dismissed": True}
        self.db.commit()
        return {"ai_configured": self._ai_configured(), "dismissed": True}

    def _ai_configured(self) -> bool:
        # Mirror the resolution /ai/chat uses (chat.py:48-100): a usable DB config, else env.
        from core.models.models_per_tenant import AIConfig

        default = (
            self.db.query(AIConfig)
            .filter(AIConfig.is_default == True, AIConfig.is_active == True)  # noqa: E712
            .first()
        )
        if default is not None:
            return True
        any_active = self.db.query(AIConfig).filter(AIConfig.is_active == True).first()  # noqa: E712
        if any_active is not None:
            return True
        return self._env_ai_configured()

    def _env_ai_configured(self) -> bool:
        try:
            from commercial.ai.services.ai_config_service import AIConfigService
        except Exception:
            return False
        try:
            return bool(AIConfigService.get_ai_config(self.db, component="chat", require_ocr=False))
        except Exception as exc:
            logger.warning("env AI config check failed: %s", exc)
            return False

    def _is_dismissed(self) -> bool:
        from core.models.models_per_tenant import Settings

        record = self.db.query(Settings).filter(Settings.key == ASSISTANT_DISMISS_KEY).first()
        return bool(record and record.value and record.value.get("dismissed") is True)
```

- [ ] **Step 4: Add the routes**

```python
# api/core/routers/onboarding.py  (add import)
from core.services.onboarding_assistant import OnboardingAssistantService
```

```python
# api/core/routers/onboarding.py  (add routes after the checklist routes)
@router.get("/assistant/status")
async def get_onboarding_assistant_status(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    return OnboardingAssistantService(db).status()


@router.post("/assistant/dismiss")
async def dismiss_onboarding_assistant(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "dismiss the onboarding assistant")
    return OnboardingAssistantService(db).dismiss()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose exec api pytest api/tests/test_onboarding_assistant_service.py -v`
Expected: PASS (or, if you converted to the DB-fixture integration form, PASS against seeded rows).

- [ ] **Step 6: Commit**

```bash
git add api/core/services/onboarding_assistant.py api/core/routers/onboarding.py api/tests/test_onboarding_assistant_service.py
git commit -m "feat(onboarding): assistant status (ai_configured) + dismiss endpoints"
```

---

### Task 5: Frontend API client — onboarding-assistant calls

**Files:**
- Modify: `ui/src/lib/api/onboarding.ts`
- Test: `ui/src/lib/api/onboarding.test.ts` (create)

**Interfaces:**
- Produces (added to `onboardingApi`, or a new `onboardingAssistantApi`):
  - `getAssistantStatus(): Promise<AssistantStatus>` → GET `/onboarding/assistant/status`.
  - `dismissAssistant(): Promise<AssistantStatus>` → POST `/onboarding/assistant/dismiss`.
  - `sendOnboardingMessage(body: { message: string; confirmed_action?: OnboardingAction }): Promise<ChatEnvelope>` → POST `/ai/chat` with `mode:"onboarding"`.
- Types:
  - `AssistantStatus = { ai_configured: boolean; dismissed: boolean }`
  - `OnboardingAction = { action: string; params: Record<string, unknown> }`
  - `ProposedAction = { type: 'proposed_action'; action: string; params: Record<string, unknown>; source: 'onboarding' }`
  - `ChatEnvelope = { success: boolean; data?: any; error?: string }`

- [ ] **Step 1: Write the failing test**

```ts
// ui/src/lib/api/onboarding.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./_base', () => ({ apiRequest: vi.fn() }));
import { apiRequest } from './_base';
import { onboardingAssistantApi } from './onboarding';

describe('onboardingAssistantApi', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getAssistantStatus hits the status endpoint', async () => {
    (apiRequest as any).mockResolvedValue({ ai_configured: true, dismissed: false });
    const res = await onboardingAssistantApi.getAssistantStatus();
    expect(apiRequest).toHaveBeenCalledWith('/onboarding/assistant/status');
    expect(res.ai_configured).toBe(true);
  });

  it('sendOnboardingMessage posts to /ai/chat with onboarding mode', async () => {
    (apiRequest as any).mockResolvedValue({ success: true, data: {} });
    await onboardingAssistantApi.sendOnboardingMessage({ message: 'hi' });
    expect(apiRequest).toHaveBeenCalledWith('/ai/chat', {
      method: 'POST',
      body: { message: 'hi', mode: 'onboarding' },
    });
  });

  it('sendOnboardingMessage forwards confirmed_action', async () => {
    (apiRequest as any).mockResolvedValue({ success: true, data: {} });
    const confirmed = { action: 'create_client', params: { name: 'Acme' } };
    await onboardingAssistantApi.sendOnboardingMessage({ message: '', confirmed_action: confirmed });
    expect(apiRequest).toHaveBeenCalledWith('/ai/chat', {
      method: 'POST',
      body: { message: '', mode: 'onboarding', confirmed_action: confirmed },
    });
  });
});
```

> Verify the exact `apiRequest` body convention against `_base.ts` before implementing — if it expects `JSON.stringify(body)` rather than a raw object, match that in both the test and the implementation.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec ui npx vitest run src/lib/api/onboarding.test.ts`
Expected: FAIL — `onboardingAssistantApi` is not exported.

- [ ] **Step 3: Implement**

```ts
// ui/src/lib/api/onboarding.ts  (append)
export interface AssistantStatus {
  ai_configured: boolean;
  dismissed: boolean;
}

export interface OnboardingAction {
  action: string;
  params: Record<string, unknown>;
}

export interface ProposedAction extends OnboardingAction {
  type: 'proposed_action';
  source: 'onboarding';
}

export interface ChatEnvelope {
  success: boolean;
  data?: any;
  error?: string;
}

export const onboardingAssistantApi = {
  getAssistantStatus: () => apiRequest<AssistantStatus>('/onboarding/assistant/status'),
  dismissAssistant: () =>
    apiRequest<AssistantStatus>('/onboarding/assistant/dismiss', { method: 'POST' }),
  sendOnboardingMessage: (body: { message: string; confirmed_action?: OnboardingAction }) =>
    apiRequest<ChatEnvelope>('/ai/chat', {
      method: 'POST',
      body: {
        message: body.message,
        mode: 'onboarding',
        ...(body.confirmed_action ? { confirmed_action: body.confirmed_action } : {}),
      },
    }),
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec ui npx vitest run src/lib/api/onboarding.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/api/onboarding.ts ui/src/lib/api/onboarding.test.ts
git commit -m "feat(onboarding): frontend API for assistant status + onboarding chat"
```

---

### Task 6: `useOnboardingConversation` hook + `ConfirmActionCard`

**Files:**
- Create: `ui/src/components/onboarding/useOnboardingConversation.ts`
- Create: `ui/src/components/onboarding/ConfirmActionCard.tsx`
- Test: `ui/src/components/onboarding/useOnboardingConversation.test.tsx` (create)

**Interfaces:**
- Consumes: `onboardingAssistantApi.sendOnboardingMessage` (Task 5).
- Produces:
  - `useOnboardingConversation()` → `{ messages: ChatMessage[]; pendingAction: ProposedAction | null; send(text: string): Promise<void>; confirm(action: OnboardingAction): Promise<void>; cancelPending(): void; loading: boolean }` where `ChatMessage = { id: string; role: 'user' | 'assistant'; text: string }`.
  - `ConfirmActionCard({ action, onConfirm, onCancel })` — renders editable params for the four actions + Confirm/Cancel.

- [ ] **Step 1: Write the failing test**

```tsx
// ui/src/components/onboarding/useOnboardingConversation.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

vi.mock('@/lib/api/onboarding', () => ({
  onboardingAssistantApi: { sendOnboardingMessage: vi.fn() },
}));
import { onboardingAssistantApi } from '@/lib/api/onboarding';
import { useOnboardingConversation } from './useOnboardingConversation';

describe('useOnboardingConversation', () => {
  beforeEach(() => vi.clearAllMocks());

  it('surfaces a proposed_action as pendingAction without executing', async () => {
    (onboardingAssistantApi.sendOnboardingMessage as any).mockResolvedValue({
      success: true,
      data: { type: 'proposed_action', action: 'create_client', params: { name: 'Acme' }, source: 'onboarding' },
    });
    const { result } = renderHook(() => useOnboardingConversation());
    await act(async () => { await result.current.send('add a client Acme'); });
    await waitFor(() => expect(result.current.pendingAction?.action).toBe('create_client'));
  });

  it('confirm() forwards confirmed_action and clears the pending action', async () => {
    (onboardingAssistantApi.sendOnboardingMessage as any).mockResolvedValue({
      success: true,
      data: { response: '✅ Client created.', executed_action: 'create_client' },
    });
    const { result } = renderHook(() => useOnboardingConversation());
    await act(async () => {
      await result.current.confirm({ action: 'create_client', params: { name: 'Acme' } });
    });
    expect(onboardingAssistantApi.sendOnboardingMessage).toHaveBeenCalledWith({
      message: '',
      confirmed_action: { action: 'create_client', params: { name: 'Acme' } },
    });
    expect(result.current.pendingAction).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec ui npx vitest run src/components/onboarding/useOnboardingConversation.test.tsx`
Expected: FAIL — hook module does not exist.

- [ ] **Step 3: Implement the hook**

```ts
// ui/src/components/onboarding/useOnboardingConversation.ts
import { useState, useCallback } from 'react';
import {
  onboardingAssistantApi,
  type OnboardingAction,
  type ProposedAction,
} from '@/lib/api/onboarding';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

let _seq = 0;
const nextId = () => `m${_seq++}`;

export function useOnboardingConversation() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingAction, setPendingAction] = useState<ProposedAction | null>(null);
  const [loading, setLoading] = useState(false);

  const push = (role: ChatMessage['role'], text: string) =>
    setMessages((m) => [...m, { id: nextId(), role, text }]);

  const send = useCallback(async (text: string) => {
    push('user', text);
    setLoading(true);
    try {
      const res = await onboardingAssistantApi.sendOnboardingMessage({ message: text });
      const data = res?.data;
      if (data?.type === 'proposed_action') {
        setPendingAction(data as ProposedAction);
      } else if (data?.response) {
        push('assistant', data.response);
      } else if (res?.error) {
        push('assistant', res.error);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const confirm = useCallback(async (action: OnboardingAction) => {
    setLoading(true);
    try {
      const res = await onboardingAssistantApi.sendOnboardingMessage({ message: '', confirmed_action: action });
      setPendingAction(null);
      if (res?.data?.response) push('assistant', res.data.response);
      else if (res?.error) push('assistant', res.error);
    } finally {
      setLoading(false);
    }
  }, []);

  const cancelPending = useCallback(() => setPendingAction(null), []);

  return { messages, pendingAction, send, confirm, cancelPending, loading };
}
```

- [ ] **Step 4: Implement `ConfirmActionCard`**

```tsx
// ui/src/components/onboarding/ConfirmActionCard.tsx
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { OnboardingAction, ProposedAction } from '@/lib/api/onboarding';

const FIELDS: Record<string, { key: string; label: string; placeholder?: string }[]> = {
  create_client: [
    { key: 'name', label: 'Name' },
    { key: 'email', label: 'Email' },
  ],
  set_branding: [
    { key: 'brand_color', label: 'Brand color', placeholder: '#1e3a8a' },
    { key: 'accent_color', label: 'Accent color', placeholder: '#3b82f6' },
  ],
  create_invoice: [
    { key: 'client_id', label: 'Client ID' },
    { key: 'amount', label: 'Amount' },
    { key: 'due_date', label: 'Due date (YYYY-MM-DD)' },
  ],
  create_expense: [
    { key: 'amount', label: 'Amount' },
    { key: 'category', label: 'Category' },
    { key: 'vendor', label: 'Vendor' },
  ],
};

export function ConfirmActionCard({
  action,
  onConfirm,
  onCancel,
}: {
  action: ProposedAction;
  onConfirm: (a: OnboardingAction) => void;
  onCancel: () => void;
}) {
  const fields = FIELDS[action.action] ?? [];
  const [params, setParams] = useState<Record<string, unknown>>({ ...action.params });

  return (
    <div className="rounded-lg border p-3 space-y-2" data-testid="confirm-action-card">
      <div className="text-sm font-medium">Confirm: {action.action.replace('_', ' ')}</div>
      {fields.map((f) => (
        <label key={f.key} className="block text-xs">
          {f.label}
          <Input
            value={String(params[f.key] ?? '')}
            placeholder={f.placeholder}
            onChange={(e) => setParams((p) => ({ ...p, [f.key]: e.target.value }))}
          />
        </label>
      ))}
      <div className="flex gap-2 pt-1">
        <Button size="sm" onClick={() => onConfirm({ action: action.action, params })}>
          Confirm
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec ui npx vitest run src/components/onboarding/useOnboardingConversation.test.tsx`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/onboarding/useOnboardingConversation.ts ui/src/components/onboarding/ConfirmActionCard.tsx ui/src/components/onboarding/useOnboardingConversation.test.tsx
git commit -m "feat(onboarding): conversation hook + confirm-action card"
```

---

### Task 7: `OnboardingAssistantCard` + dashboard mount

**Files:**
- Create: `ui/src/components/onboarding/OnboardingAssistantCard.tsx`
- Modify: `ui/src/components/dashboard/ProfessionalDashboard.tsx:30,278` (import + mount above `<OnboardingChecklist />`)
- Test: `ui/src/components/onboarding/OnboardingAssistantCard.test.tsx` (create)

**Interfaces:**
- Consumes: `onboardingAssistantApi.getAssistantStatus/dismissAssistant` (Task 5), `useOnboardingConversation` + `ConfirmActionCard` (Task 6), `useFeatures` (`@/contexts/FeatureContext`), `onboardingApi.getChecklist` (existing) to hide when `all_complete`.
- Produces: `OnboardingAssistantCard` — self-contained dashboard card. Renders nothing when: `ai_chat` not licensed, status `dismissed`, checklist `all_complete`, or status load fails.

- [ ] **Step 1: Write the failing test**

```tsx
// ui/src/components/onboarding/OnboardingAssistantCard.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('@/contexts/FeatureContext', () => ({ useFeatures: () => ({ isFeatureEnabled: () => true }) }));
vi.mock('@/lib/api/onboarding', () => ({
  onboardingAssistantApi: {
    getAssistantStatus: vi.fn(),
    dismissAssistant: vi.fn(),
    sendOnboardingMessage: vi.fn(),
  },
  onboardingApi: { getChecklist: vi.fn().mockResolvedValue({ all_complete: false }) },
}));
import { onboardingAssistantApi } from '@/lib/api/onboarding';
import { OnboardingAssistantCard } from './OnboardingAssistantCard';

describe('OnboardingAssistantCard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows the configure-AI prompt when ai is not configured', async () => {
    (onboardingAssistantApi.getAssistantStatus as any).mockResolvedValue({ ai_configured: false, dismissed: false });
    render(<OnboardingAssistantCard />);
    await waitFor(() => expect(screen.getByText(/AI provider/i)).toBeInTheDocument());
  });

  it('shows the chat composer when ai is configured', async () => {
    (onboardingAssistantApi.getAssistantStatus as any).mockResolvedValue({ ai_configured: true, dismissed: false });
    render(<OnboardingAssistantCard />);
    await waitFor(() => expect(screen.getByPlaceholderText(/set up/i)).toBeInTheDocument());
  });

  it('renders nothing when dismissed', async () => {
    (onboardingAssistantApi.getAssistantStatus as any).mockResolvedValue({ ai_configured: true, dismissed: true });
    const { container } = render(<OnboardingAssistantCard />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec ui npx vitest run src/components/onboarding/OnboardingAssistantCard.test.tsx`
Expected: FAIL — component module does not exist.

- [ ] **Step 3: Implement the card**

```tsx
// ui/src/components/onboarding/OnboardingAssistantCard.tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useFeatures } from '@/contexts/FeatureContext';
import { onboardingApi, onboardingAssistantApi, type AssistantStatus } from '@/lib/api/onboarding';
import { useOnboardingConversation } from './useOnboardingConversation';
import { ConfirmActionCard } from './ConfirmActionCard';

export function OnboardingAssistantCard() {
  const { isFeatureEnabled } = useFeatures();
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [hidden, setHidden] = useState(false);
  const [input, setInput] = useState('');
  const { messages, pendingAction, send, confirm, cancelPending, loading } = useOnboardingConversation();

  useEffect(() => {
    if (!isFeatureEnabled('ai_chat')) { setHidden(true); return; }
    Promise.all([onboardingAssistantApi.getAssistantStatus(), onboardingApi.getChecklist()])
      .then(([s, checklist]) => {
        if (s.dismissed || checklist.all_complete) setHidden(true);
        else setStatus(s);
      })
      .catch(() => setHidden(true));
  }, [isFeatureEnabled]);

  if (hidden || !status) return null;

  const dismiss = () => { setHidden(true); onboardingAssistantApi.dismissAssistant().catch(() => {}); };

  if (!status.ai_configured) {
    return (
      <div className="rounded-lg border p-4 space-y-2" data-testid="onboarding-assistant-card">
        <div className="font-medium">Set up your AI provider first</div>
        <p className="text-sm text-muted-foreground">
          The setup assistant needs an AI provider. Add one to get guided, hands-on help.
        </p>
        <div className="flex gap-2">
          <Button asChild size="sm"><Link to="/settings?tab=ai">Configure AI provider</Link></Button>
          <Button size="sm" variant="ghost" onClick={dismiss}>Dismiss</Button>
        </div>
      </div>
    );
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput('');
    void send(text);
  };

  return (
    <div className="rounded-lg border p-4 space-y-3" data-testid="onboarding-assistant-card">
      <div className="flex items-center justify-between">
        <div className="font-medium">Let's get you set up</div>
        <Button size="sm" variant="ghost" onClick={dismiss}>Dismiss</Button>
      </div>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {messages.map((m) => (
          <div key={m.id} className={m.role === 'user' ? 'text-right text-sm' : 'text-sm'}>{m.text}</div>
        ))}
        {pendingAction && (
          <ConfirmActionCard action={pendingAction} onConfirm={confirm} onCancel={cancelPending} />
        )}
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <Input
          value={input}
          placeholder="Tell me what you'd like to set up…"
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <Button type="submit" size="sm" disabled={loading}>Send</Button>
      </form>
    </div>
  );
}
```

> Confirm the AIConfigTab deep-link route. The spec references Settings → AI Provider Configurations; verify the tab query param against `Settings.tsx` (it may be `?tab=ai-config` rather than `?tab=ai`) and use the real value.

- [ ] **Step 4: Mount on the dashboard**

```tsx
// ui/src/components/dashboard/ProfessionalDashboard.tsx:30  (add import)
import { OnboardingAssistantCard } from '@/components/onboarding/OnboardingAssistantCard';
```

```tsx
// ui/src/components/dashboard/ProfessionalDashboard.tsx  (mount directly above <OnboardingChecklist /> at line 278)
      <OnboardingAssistantCard />
      <OnboardingChecklist />
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec ui npx vitest run src/components/onboarding/OnboardingAssistantCard.test.tsx`
Expected: PASS (all three tests).

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/onboarding/OnboardingAssistantCard.tsx ui/src/components/dashboard/ProfessionalDashboard.tsx ui/src/components/onboarding/OnboardingAssistantCard.test.tsx
git commit -m "feat(onboarding): conversational assistant card on dashboard"
```

---

### Task 8: Quick-action shortcut in the AI assistant widget

**Files:**
- Modify: `ui/src/components/AIAssistant.tsx` (add a quick-action button + onboarding routing in the send handler)
- Modify: `ui/src/i18n/locales/en.json` (add `aiAssistant.getStarted`)
- Test: `ui/src/components/onboarding/onboardingShortcut.test.ts` (create — unit-test the routing helper)

**Interfaces:**
- Consumes: `onboardingAssistantApi.sendOnboardingMessage` (Task 5).
- Produces: an exported pure helper `isOnboardingIntent(text: string, getStartedLabel: string): boolean` used by `AIAssistant.tsx`'s send handler, so the routing is unit-testable without rendering the whole widget.

- [ ] **Step 1: Write the failing test**

```ts
// ui/src/components/onboarding/onboardingShortcut.test.ts
import { describe, it, expect } from 'vitest';
import { isOnboardingIntent } from './onboardingShortcut';

describe('isOnboardingIntent', () => {
  const label = 'Help me get set up';
  it('matches the exact quick-action label', () => {
    expect(isOnboardingIntent('Help me get set up', label)).toBe(true);
  });
  it('matches case-insensitively', () => {
    expect(isOnboardingIntent('help me get set up', label)).toBe(true);
  });
  it('does not match unrelated text', () => {
    expect(isOnboardingIntent('show my invoices', label)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec ui npx vitest run src/components/onboarding/onboardingShortcut.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the helper**

```ts
// ui/src/components/onboarding/onboardingShortcut.ts
export function isOnboardingIntent(text: string, getStartedLabel: string): boolean {
  const t = text.trim().toLowerCase();
  return t === getStartedLabel.trim().toLowerCase();
}
```

- [ ] **Step 4: Add the i18n key**

```json
// ui/src/i18n/locales/en.json  (inside the existing "aiAssistant" object)
    "getStarted": "Help me get set up",
```

- [ ] **Step 5: Add the quick-action button**

In `AIAssistant.tsx`, next to the Analyze Patterns button (around line 1366), add:

```tsx
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full bg-white/50 dark:bg-black/20 backdrop-blur border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 text-xs shadow-sm hover:shadow-md transition-all whitespace-nowrap"
                    onClick={() => handleQuickAction(t('aiAssistant.getStarted'))}
                  >
                    {t('aiAssistant.getStarted')}
                  </Button>
```

- [ ] **Step 6: Route the onboarding intent in the send handler**

In `AIAssistant.tsx`, import the helper and the API:

```tsx
import { isOnboardingIntent } from '@/components/onboarding/onboardingShortcut';
import { onboardingAssistantApi } from '@/lib/api/onboarding';
```

In the send handler (mirroring the `suggestActions` branch at ~line 1091), add a branch BEFORE the generic `/ai/chat` call:

```tsx
      } else if (isOnboardingIntent(lowerText, t('aiAssistant.getStarted').toLowerCase())) {
        const res = await onboardingAssistantApi.sendOnboardingMessage({ message: textToSend });
        if (res?.data?.type === 'proposed_action') {
          updateAiMessage(
            <ConfirmActionCard
              action={res.data}
              onConfirm={async (a) => {
                const done = await onboardingAssistantApi.sendOnboardingMessage({ message: '', confirmed_action: a });
                updateAiMessage(done?.data?.response ?? 'Done.');
              }}
              onCancel={() => updateAiMessage('No problem — let me know when you\'re ready.')}
            />,
          );
        } else {
          updateAiMessage(res?.data?.response ?? res?.error ?? 'Let me help you get set up.');
        }
      }
```

(Import `ConfirmActionCard` at the top: `import { ConfirmActionCard } from '@/components/onboarding/ConfirmActionCard';`. `lowerText`, `textToSend`, and `updateAiMessage` are the existing locals in this handler — reuse them as the surrounding branches do.)

- [ ] **Step 7: Run tests + typecheck**

Run: `docker compose exec ui npx vitest run src/components/onboarding/onboardingShortcut.test.ts`
Expected: PASS.
Run: `docker compose exec ui npx tsc --noEmit`
Expected: no new errors in the files touched by this task.

- [ ] **Step 8: Commit**

```bash
git add ui/src/components/AIAssistant.tsx ui/src/components/onboarding/onboardingShortcut.ts ui/src/components/onboarding/onboardingShortcut.test.ts ui/src/i18n/locales/en.json
git commit -m "feat(onboarding): 'Help me get set up' quick-action in AI assistant"
```

---

### Task 9: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Backend tests for the touched areas**

Run: `docker compose exec api pytest api/tests/test_chat_models.py api/tests/test_set_branding_tool.py api/tests/test_onboarding_actions.py api/tests/test_onboarding_assistant_service.py -v`
Expected: all PASS.

- [ ] **Step 2: Regression — existing AI chat behavior unchanged**

Run: `docker compose exec api pytest -k "chat or action or onboarding" -v`
Expected: all PASS (no regression in the existing fast-path tests).

- [ ] **Step 3: Frontend tests for the touched areas**

Run: `docker compose exec ui npx vitest run src/components/onboarding src/lib/api/onboarding.test.ts`
Expected: all PASS.

- [ ] **Step 4: Frontend typecheck**

Run: `docker compose exec ui npx tsc --noEmit`
Expected: no new errors introduced by this branch.

- [ ] **Step 5: Manual smoke (documented, not automated)**

As a commercial tenant with `ai_chat` and no real data: (a) dashboard shows the assistant card; with no AI provider it shows the configure-AI deep-link; (b) after configuring AI, typing "add a client Acme ap@acme.com" yields a confirm card; Confirm creates the client and the activation checklist's `add_client` step ticks; (c) the "Help me get set up" quick-action in the floating assistant reproduces the same confirm flow.

---

## Self-Review

**Spec coverage:**
- Conversational wizard performing actions with confirm → Tasks 1, 3, 6 (propose/confirm gate + hook + confirm card). ✓
- Commercial-only via `ai_chat`, no new flag → Task 3 inherits `@require_feature("ai_chat")`; Tasks 7/8 check `isFeatureEnabled('ai_chat')`. ✓
- Action catalog (create_client, set_branding, create_invoice, create_expense) → Task 3 `_ONBOARDING_ACTIONS`; Task 2 adds the missing `set_branding` tool. ✓ (Note: `set_branding` writes colors only — company name is not an `invoice_branding` field; documented in Global Constraints.)
- AI-provider precondition + deep-link → Task 4 `ai_configured` + Task 7 configure-AI state. ✓
- Inline dashboard card augmenting the checklist → Task 7 mounts above `OnboardingChecklist`; progress read from existing derive-on-read checklist (no new state). ✓
- Quick-action shortcut in the widget → Task 8. ✓
- Separate `onboarding_assistant` dismiss key → Task 4. ✓
- No-regression to the live `/ai/chat` fast-path → Task 3 early-returns only under `mode:"onboarding"`; Task 9 Step 2 guards it. ✓

**Placeholder scan:** No "TBD"/"handle appropriately". Two explicit *verify-before-coding* notes (apiRequest body convention in Task 5; Settings AI-tab query param in Task 7) point at exact files to confirm a fact, not deferred work.

**Type consistency:** Action names (`create_client`, `set_branding`, `create_invoice`, `create_expense`), envelope type string (`proposed_action`), request fields (`mode`, `confirmed_action`), and `confirmed_action` shape (`{action, params}`) are identical across backend Tasks 1/3 and frontend Tasks 5/6/8. `OnboardingAction`/`ProposedAction`/`AssistantStatus` defined in Task 5 are the types consumed in Tasks 6–8.

**Scope:** One cohesive feature, ~9 tasks, each independently testable. No decomposition needed.
