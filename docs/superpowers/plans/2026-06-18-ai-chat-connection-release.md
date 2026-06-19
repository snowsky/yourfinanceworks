# AI Chat Connection-Release (Layer 2b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `/ai/chat` from holding its tenant DB connection idle across LLM calls by routing every litellm call through a helper that releases the connection first.

**Architecture:** A new `llm_acompletion(db, **kwargs)` helper calls `db.rollback()` (returns the connection to the pool) before `await acompletion(**kwargs)`. The resolved AI config is materialized into a plain object right after resolution so post-release attribute access can't silently re-acquire the connection. All 7 LLM call sites in the chat path route through the helper; three functions gain a `db` parameter so they can release it. Nothing else changes.

**Tech Stack:** FastAPI, SQLAlchemy (per-tenant DB), litellm, pytest (+pytest-asyncio). Tests run in-container.

## Global Constraints

- Release mechanism is `db.rollback()` before the LLM round-trip (safe: no transaction spans the request; tool writes commit per-operation, so there's never pending write data to lose before an LLM call).
- The resolved `ai_config` must be a plain object (fields: `provider_name`, `model_name`, `api_key`, `provider_url`) before any LLM call — otherwise the first `rollback()` expires the ORM `AIConfig` and the next call's kwargs re-query/re-check-out the connection, defeating the release.
- Every litellm `acompletion`/`completion` call in the chat path goes through `llm_acompletion(db, …)`. After this work, no bare `await completion(`/`await acompletion(` may remain in `chat.py` or `action_handlers.py`.
- Do NOT change `Depends(get_db)`, the `@require_feature` gate, `InProcessAPIClient` (#410), or the tools.
- Backend tests run in-container: `docker compose exec -T api python -m pytest tests/<file> -v` (use `python -m pytest`, never bare `pytest`).

---

### Task 1: The `llm_acompletion` helper + `materialize_ai_config`

**Files:**
- Create: `api/commercial/ai/routers/llm.py`
- Test: `api/tests/test_llm_release.py`

**Interfaces:**
- Produces:
  - `async def llm_acompletion(db, **kwargs)` — calls `db.rollback()` (if `db` is not None) then returns `await acompletion(**kwargs)`.
  - `def materialize_ai_config(cfg)` → `SimpleNamespace(provider_name, model_name, api_key, provider_url)` copied from `cfg`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_llm_release.py
import pytest
from types import SimpleNamespace

import commercial.ai.routers.llm as llm


def test_materialize_ai_config_copies_four_fields():
    src = SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini",
                          api_key="k", provider_url="u", is_default=True, id=5)
    out = llm.materialize_ai_config(src)
    assert (out.provider_name, out.model_name, out.api_key, out.provider_url) == \
        ("openai", "gpt-4o-mini", "k", "u")
    assert not hasattr(out, "id")  # only the four fields carry over


def test_materialize_tolerates_missing_optional_fields():
    src = SimpleNamespace(provider_name="ollama", model_name="llama3")
    out = llm.materialize_ai_config(src)
    assert out.api_key is None and out.provider_url is None


@pytest.mark.asyncio
async def test_llm_acompletion_releases_connection_before_call(monkeypatch):
    order = []

    class _DB:
        def rollback(self):
            order.append("rollback")

    async def _fake_acompletion(**kwargs):
        order.append("acompletion")
        return {"ok": True, "kwargs": kwargs}

    monkeypatch.setattr(llm, "acompletion", _fake_acompletion, raising=False)
    result = await llm.llm_acompletion(_DB(), model="m", messages=[])
    assert order == ["rollback", "acompletion"]   # released BEFORE the LLM call
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_llm_acompletion_tolerates_none_db(monkeypatch):
    async def _fake_acompletion(**kwargs):
        return {"ok": True}
    monkeypatch.setattr(llm, "acompletion", _fake_acompletion, raising=False)
    result = await llm.llm_acompletion(None, model="m", messages=[])
    assert result["ok"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/test_llm_release.py -v`
Expected: FAIL — module `commercial.ai.routers.llm` does not exist.

- [ ] **Step 3: Implement the helper**

```python
# api/commercial/ai/routers/llm.py
"""Release the tenant DB connection before slow LLM round-trips.

ai_chat holds one tenant pool connection for the whole request. Routing every
litellm call through llm_acompletion() returns that connection to the pool
during the (multi-second) model call so it isn't held idle, preventing pool
exhaustion under concurrent chats.
"""

from types import SimpleNamespace

from litellm import acompletion


def materialize_ai_config(cfg) -> SimpleNamespace:
    """Copy the resolved AI config into a plain object so later attribute access
    cannot trigger an ORM re-query (which would re-check-out the connection)."""
    return SimpleNamespace(
        provider_name=getattr(cfg, "provider_name", None),
        model_name=getattr(cfg, "model_name", None),
        api_key=getattr(cfg, "api_key", None),
        provider_url=getattr(cfg, "provider_url", None),
    )


async def llm_acompletion(db, **kwargs):
    """Return the tenant connection to the pool, then run the LLM call."""
    if db is not None:
        db.rollback()  # ends the open read txn -> connection released to the pool
    return await acompletion(**kwargs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api python -m pytest tests/test_llm_release.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add api/commercial/ai/routers/llm.py api/tests/test_llm_release.py
git commit -m "feat(ai): llm_acompletion helper (release connection before LLM) + materialize_ai_config"
```

---

### Task 2: Route chat.py LLM calls through the helper + materialize config

**Files:**
- Modify: `api/commercial/ai/routers/chat.py`
- Test: `api/tests/test_chat_llm_routing.py`

**Interfaces:**
- Consumes: `llm_acompletion`, `materialize_ai_config` (Task 1).
- Produces: `_plan_mcp_tool_intents(*, message, page_context_block, ai_config, db)` and `_synthesize_tool_results(*, message, planned_results, page_context_block, ai_config, db)` — both gain a keyword-only `db` parameter.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_chat_llm_routing.py
import pytest
from types import SimpleNamespace

import commercial.ai.routers.chat as chat


@pytest.mark.asyncio
async def test_plan_routes_through_llm_acompletion_with_db(monkeypatch):
    captured = {}

    async def _spy(db, **kwargs):
        captured["db"] = db
        # minimal litellm-shaped response: empty content -> empty plan
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))])

    monkeypatch.setattr(chat, "llm_acompletion", _spy)
    cfg = SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini", api_key="k", provider_url=None)
    sentinel_db = object()
    await chat._plan_mcp_tool_intents(message="hi", page_context_block="", ai_config=cfg, db=sentinel_db)
    assert captured["db"] is sentinel_db   # the connection owner was passed to the helper


@pytest.mark.asyncio
async def test_synthesize_routes_through_llm_acompletion_with_db(monkeypatch):
    captured = {}

    async def _spy(db, **kwargs):
        captured["db"] = db
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    monkeypatch.setattr(chat, "llm_acompletion", _spy)
    cfg = SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini", api_key="k", provider_url=None)
    sentinel_db = object()
    out = await chat._synthesize_tool_results(
        message="hi", planned_results=[("clients", {"data": []})],
        page_context_block="", ai_config=cfg, db=sentinel_db,
    )
    assert captured["db"] is sentinel_db
    assert out == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/test_chat_llm_routing.py -v`
Expected: FAIL — `_plan_mcp_tool_intents`/`_synthesize_tool_results` take no `db` kwarg (TypeError), and `chat.llm_acompletion` doesn't exist.

- [ ] **Step 3: Import the helper + materialize config in `chat.py`**

Add the import near the other `commercial.ai.routers` imports (top of `chat.py`, alongside line 21-24):

```python
from commercial.ai.routers.llm import llm_acompletion, materialize_ai_config
```

Right after AIConfig resolution completes — immediately after `chat.py:99` (the env-fallback `logger.info(...)` line) and before `# Use AI to classify user intent` (`chat.py:101`) — insert:

```python
        # Materialize the config into a plain object BEFORE any LLM call, so that
        # releasing the connection (rollback inside llm_acompletion) cannot later
        # trigger an ORM re-query when building LLM kwargs.
        ai_config = materialize_ai_config(ai_config)
```

- [ ] **Step 4: Route the two inline `chat.py` LLM calls through the helper**

Intent classification — `chat.py:190-191`. Replace:
```python
            try:
                intent_response = await completion(**kwargs)
```
with:
```python
            try:
                intent_response = await llm_acompletion(db, **kwargs)
```

General-answer fallback — `chat.py:322`. Replace:
```python
        response = await completion(**kwargs)
```
with:
```python
        response = await llm_acompletion(db, **kwargs)
```
Also delete the now-unused local import `from litellm import acompletion as completion` at `chat.py:262` (and the one at `chat.py:106` if nothing else in `ai_chat`'s body still uses the `completion` alias — verify with `grep -n "completion(" chat.py`; remove an import only when its alias has no remaining call).

- [ ] **Step 5: Add `db` to `_plan_mcp_tool_intents` and route its call**

Change the signature (`chat.py:343-348`) to add a keyword-only `db`:
```python
async def _plan_mcp_tool_intents(
    *,
    message: str,
    page_context_block: str,
    ai_config,
    db,
) -> list[str]:
```
Inside it, replace `response = await completion(**kwargs)` (`chat.py:403`) with `response = await llm_acompletion(db, **kwargs)`, and remove the local `from litellm import acompletion as completion` (`chat.py:351`). Update the call site (`chat.py:163-167`) to pass `db=db`:
```python
        tool_plan = await _plan_mcp_tool_intents(
            message=request.message,
            page_context_block=page_context_block,
            ai_config=ai_config,
            db=db,
        )
```

- [ ] **Step 6: Add `db` to `_synthesize_tool_results` and route its call**

Change the signature (`chat.py:412-418`) to add keyword-only `db`:
```python
async def _synthesize_tool_results(
    *,
    message: str,
    planned_results: list[tuple[str, dict]],
    page_context_block: str,
    ai_config,
    db,
) -> str:
```
Inside it, replace `response = await completion(**kwargs)` (`chat.py:463`) with `response = await llm_acompletion(db, **kwargs)` and remove the local import (`chat.py:435`). Update the call site (`chat.py:229`) to pass `db=db`:
```python
                synthesized = await _synthesize_tool_results(
                    message=request.message,
                    planned_results=planned_results,
                    page_context_block=page_context_block,
                    ai_config=ai_config,
                    db=db,
                )
```
(Use the actual argument names already present at `chat.py:229-234`; only add `db=db`.)

- [ ] **Step 7: Run tests + grep guard**

Run: `docker compose exec -T api python -m pytest tests/test_chat_llm_routing.py -v`
Expected: PASS (2 tests).
Run: `docker compose exec -T api sh -c "grep -nE 'await completion\(|await acompletion\(' commercial/ai/routers/chat.py || echo CLEAN"`
Expected: `CLEAN` (no bare litellm calls remain in chat.py).

- [ ] **Step 8: Commit**

```bash
git add api/commercial/ai/routers/chat.py api/tests/test_chat_llm_routing.py
git commit -m "perf(ai): release tenant connection across chat.py LLM calls + materialize config"
```

---

### Task 3: Route action_handlers.py LLM calls through the helper

**Files:**
- Modify: `api/commercial/ai/routers/action_handlers.py`
- Modify: `api/tests/test_onboarding_actions.py` (signature ripple)
- Test: `api/tests/test_onboarding_actions.py`

**Interfaces:**
- Consumes: `llm_acompletion` (Task 1).
- Produces: `_extract_onboarding_action(message, ai_config, db)` — gains a `db` parameter.

- [ ] **Step 1: Update the failing tests for the new signature**

In `api/tests/test_onboarding_actions.py`, `_extract_onboarding_action` is called/monkeypatched. Update:

The propose-path monkeypatch (`test_onboarding_proposes_without_executing`) — its async fake gains `db`:
```python
    async def _fake_extract(message, ai_config, db):
        return {"action": "create_client", "params": {"name": "Acme", "email": "ap@acme.com"}}
```
The fall-through monkeypatch (`test_onboarding_no_action_falls_through`):
```python
    async def _none(message, ai_config, db):
        return None
```
The direct-call test (`test_extract_applies_name_cleaning`) — it monkeypatches `litellm.acompletion`; route stays valid through the helper, but the call needs a `db`:
```python
    out = await ah._extract_onboarding_action("create a client with john doe email jd@x.com", _Cfg(), None)
```
(`db=None` is tolerated by `llm_acompletion`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api python -m pytest tests/test_onboarding_actions.py -v`
Expected: FAIL — `_extract_onboarding_action()` currently takes 2 args, tests now pass 3.

- [ ] **Step 3: Add the helper import to `action_handlers.py`**

Add one top-level import near the existing imports (alongside `action_handlers.py:14-15`), used by all three extraction sites:
```python
from commercial.ai.routers.llm import llm_acompletion
```

- [ ] **Step 4: Add `db` to `_extract_onboarding_action` and route its call**

Change the signature (`action_handlers.py:93`):
```python
async def _extract_onboarding_action(message: str, ai_config: Any, db) -> Optional[Dict[str, Any]]:
```
Remove the local `from litellm import acompletion` (`action_handlers.py:103`) and change the call (`:122`):
```python
        resp = await acompletion(
            ...
        )
```
to:
```python
        resp = await llm_acompletion(
            db,
            ...
        )
```
(keep the same `model=`, `messages=`, `api_key=`, `api_base=`, `temperature=` kwargs that follow). Update the caller in `_handle_onboarding_action` (`action_handlers.py:173`) to pass `db`:
```python
    proposal = await _extract_onboarding_action(message, ai_config, db)
```

- [ ] **Step 5: Route the client- and expense-extraction calls**

Client-creation fast path — `action_handlers.py:401`. Replace `extract_response = await completion(**extraction_params)` with `extract_response = await llm_acompletion(db, **extraction_params)`, and remove the local `from litellm import acompletion as completion` at `:373`.

Expense-creation fast path — `action_handlers.py:528`. Replace `extract_response = await completion(**extraction_params)` with `extract_response = await llm_acompletion(db, **extraction_params)`, and remove the local import at `:497`.

Both sites are inside `handle_early_actions`, which has `db` in scope (its signature param).

- [ ] **Step 6: Run tests + grep guard**

Run: `docker compose exec -T api python -m pytest tests/test_onboarding_actions.py -v`
Expected: PASS (all 7).
Run: `docker compose exec -T api sh -c "grep -nE 'await completion\(|await acompletion\(' commercial/ai/routers/action_handlers.py || echo CLEAN"`
Expected: `CLEAN`.

- [ ] **Step 7: Commit**

```bash
git add api/commercial/ai/routers/action_handlers.py api/tests/test_onboarding_actions.py
git commit -m "perf(ai): release tenant connection across action_handlers LLM extraction calls"
```

---

### Task 4: Verification

**Files:** none (verification only).

- [ ] **Step 1: Full touched-area suite**

Run: `docker compose exec -T api python -m pytest tests/test_llm_release.py tests/test_chat_llm_routing.py tests/test_onboarding_actions.py tests/test_inprocess_clients.py -v`
Expected: all PASS.

- [ ] **Step 2: No bare litellm calls remain in the chat path**

Run: `docker compose exec -T api sh -c "grep -REn 'await completion\(|await acompletion\(' commercial/ai/routers/chat.py commercial/ai/routers/action_handlers.py || echo CLEAN"`
Expected: `CLEAN` — every LLM call routes through `llm_acompletion`.

- [ ] **Step 3: Imports load**

Run: `docker compose exec -T api python -c "import commercial.ai.routers.chat, commercial.ai.routers.action_handlers, commercial.ai.routers.llm; print('imports OK')"`
Expected: `imports OK`.

- [ ] **Step 4: Manual — pool no longer pinned during LLM calls**

With `YFW_LOG_POOL_STATS=1` on the api service, run `scripts/pool_loadtest.py --token <JWT> --tenant 1 --concurrency 20 --duration 30` (the default `list my clients` body). Success: the tenant pool's `checkedout` count stays low during the LLM waits (connections released), and the `/invoices/` probe no longer hangs 60s / the load no longer exhausts the pool. Contrast with the pre-Layer-2b run (60s `/invoices/` starvation).

---

## Self-Review

**Spec coverage:**
- `llm_acompletion(db)` helper that `rollback()`s before the LLM call → Task 1. ✓
- Config materialization (load-bearing) → Task 1 (`materialize_ai_config`) + Task 2 Step 3 (applied before any LLM call). ✓
- All 7 chat-path LLM calls routed through the helper (chat.py: 191, 322, 403, 463; action_handlers.py: 122, 401, 528) → Tasks 2 & 3, with grep guards (Task 2 Step 7, Task 3 Step 5, Task 4 Step 2). ✓
- `db` param added to `_plan_mcp_tool_intents`, `_synthesize_tool_results`, `_extract_onboarding_action` → Tasks 2 & 3. ✓
- `Depends(get_db)` / `@require_feature` / `InProcessAPIClient` / tools untouched → none of the tasks modify them. ✓
- Regression: `test_onboarding_actions.py` updated for the signature ripple → Task 3 Step 1. ✓
- Empirical success criterion → Task 4 Step 4. ✓

**Placeholder scan:** No TBD/"handle appropriately". The only conditional instruction (remove a local import only when its alias has no remaining call — Task 2 Step 4) names the exact grep to decide.

**Type consistency:** `llm_acompletion(db, **kwargs)`, `materialize_ai_config(cfg)`, and the `db` keyword threaded into `_plan_mcp_tool_intents`/`_synthesize_tool_results`/`_extract_onboarding_action` are consistent across Tasks 1-3. The `ai_config` plain object exposes exactly the four attributes (`provider_name`/`model_name`/`api_key`/`provider_url`) the call sites access (verified: those are the only `ai_config.<attr>` reads in chat.py + action_handlers.py).

**Scope:** One cohesive change (helper + route 7 call sites), 4 tasks. `client_notes.py` deferred per spec.
