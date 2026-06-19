# AI Chat — Release DB Connection During LLM Calls (Layer 2b) — Design Spec

**Date:** 2026-06-18
**Status:** Approved design — ready for implementation planning
**Context:** Final piece of the per-tenant DB connection-pool exhaustion fix. Layer 2a (eliminating self-HTTP amplification, in-process MCP client) shipped in PR #410. This layer ("Layer 2b") stops `/ai/chat` from holding its tenant pool connection **idle across the slow LLM round-trips**. See `project_db_connection_pool` memory.

## Problem

`ai_chat` (`commercial/ai/routers/chat.py`) declares `db: Session = Depends(get_db)`, which checks out one tenant pool connection and holds it for the **entire request**. The connection is opened early (the `@require_feature("ai_chat")` gate queries the DB before the handler body) and then sits **checked-out but idle through every LLM call** — planning (~20s), classification (~30s), synthesis (~60s), general-answer (~60s), plus the extraction calls inside `handle_early_actions`. With ~15 concurrent chats and a slow AI provider, the 15-slot per-tenant pool is exhausted by these idle-held connections, starving unrelated endpoints (`read_invoices` times out). The empirical load test reproduced exactly this (60s `/invoices/` hangs under 20 concurrent chats).

Layer 2a (#410) removed the *extra* nested connection per tool call (amplification 2→1, verified). This layer removes the *idle hold* of the request's own connection during LLM calls.

## Decisions (locked during brainstorming)

| Decision | Choice |
| --- | --- |
| Approach | **Release-before-each-LLM-call** via a centralized helper (not scoped-sessions / not dropping `Depends(get_db)`) |
| Release mechanism | `db.rollback()` before the LLM round-trip |
| Config handling | **Materialize** the resolved AI config into a plain object (load-bearing — see below) |
| Scope | **`/ai/chat` only** (`client_notes.py` deferred) |
| Untouched | `Depends(get_db)`, `@require_feature`, `InProcessAPIClient` (#410), the tools |

## Background (verified against source)

- **Connection lifecycle** (`core/models/database.py:55-79`, sessionmaker `autocommit=False`): the tenant connection is checked OUT lazily on the first query and returned to the pool on `commit()`/`rollback()`/`close()`; the next query checks out a fresh one. So an explicit `rollback()` before an LLM call frees the connection for the duration of that call.
- **No transaction spans the request:** AIConfig resolution is read-only except an isolated one-time `db.commit()` (`chat.py:70`); in-process tool writes commit per-operation (`inprocess/clients_domain.py` `begin_nested()`+`commit()`); reads are independent SELECTs. So `rollback()` before an LLM call never discards needed pending writes.
- **The connection is already held at the first LLM call:** `@require_feature("ai_chat")` (`feature_gate.py:215-275`) reuses the request `db` and runs a license query (`:270`) before the handler body.
- **LLM call sites in the chat path** (all `await` litellm, db held at each): `_plan_mcp_tool_intents` (`chat.py:403`, timeout 20), intent classification (`chat.py:191`, timeout 30), `_synthesize_tool_results` (`chat.py:463`, timeout 60), general-answer fallback (`chat.py:322`, timeout 60); and in `action_handlers.py`: `_extract_onboarding_action` (`:122`), client-creation extraction (`:401`, timeout 30), expense-creation extraction (`:528`, timeout 30).
- **Blast radius:** only `client_notes.py:summarize_client_notes` shares the pattern (deferred). `invoice_analysis.py` / `chat_history.py` make no LLM calls.

## Architecture

### The release helper
New module `api/commercial/ai/routers/llm.py`:

```python
async def llm_acompletion(db, **kwargs):
    """Return the tenant DB connection to the pool before the (slow) LLM
    round-trip, so it is not held idle while waiting on the model."""
    if db is not None:
        db.rollback()  # ends the open read txn → connection released; no pending writes here
    from litellm import acompletion
    return await acompletion(**kwargs)
```

`rollback()` is safe (no spanning transaction; tool writes already committed). `db=None` is tolerated (skips the release). The next `db.query(...)` after the call lazily re-checks-out a connection.

### Config materialization (load-bearing)
Immediately after AIConfig resolution in `ai_chat`, materialize the config into a **plain object** carrying `provider_name`, `model_name`, `api_key`, `provider_url`, and use it everywhere downstream. Without this, the first `rollback()` expires the ORM `AIConfig`, and building the next LLM call's kwargs (`model=ai_config.model_name`, `api_key=ai_config.api_key`) would re-query and re-check-out the connection right before the LLM call — silently defeating the release. The existing env-fallback `EnvAIConfig` is already such a plain object; this makes the DB-config path match (same attribute names, so no downstream call sites change).

### Routing all LLM calls through the helper
Every litellm `acompletion`/`completion` call in the chat path is replaced with `await llm_acompletion(db, **kwargs)`. Three functions that currently lack `db` gain a `db` parameter so they can release it:
- `_plan_mcp_tool_intents(...)` → add `db`
- `_synthesize_tool_results(...)` → add `db`
- `_extract_onboarding_action(message, ai_config)` → add `db` (called from `_handle_onboarding_action`, which already has `db` after #410)

Net effect: the connection is freed during every LLM round-trip, and only briefly re-held during the short DB bursts (config read, tool queries) between calls.

### Unchanged
`Depends(get_db)`, the `@require_feature` gate, `InProcessAPIClient` (#410), and the tools are untouched — the session object still lives for the request; only *when its connection is checked out* changes. Brief millisecond holds during DB bursts don't exhaust the pool the way 60s LLM-held connections do.

## Testing

- **Helper unit test:** with a fake `db` (spy `.rollback()`) and a monkeypatched `acompletion`, assert `rollback()` is called before the awaited LLM call and the helper returns the LLM result; a `db=None` call skips rollback and still works.
- **Config materialization:** after resolution, `ai_config` is the plain object (has the four attrs; not an ORM instance), so later attribute access cannot trigger a re-query.
- **Regression:** the `db`-parameter additions ripple into `test_onboarding_actions.py` (which calls/monkeypatches `_extract_onboarding_action`); the plan updates those tests (as the #410 wiring task did). Existing chat/onboarding suites must stay green.
- **Empirical (manual, documented):** re-run `scripts/pool_loadtest.py` with the `list my clients` body against a healthy stack; success = the tenant pool no longer exhausts under 20 concurrent chats (the 60s `/invoices/` starvation disappears). With `YFW_LOG_POOL_STATS=1`, `checkedout` should stay low during the LLM waits instead of pinning at the pool ceiling.

## Out of scope (deferred)

- `client_notes.py:summarize_client_notes` — the only other held-across-LLM endpoint; uses raw `httpx`, so a different release point. Small noted follow-up.
- Dropping `Depends(get_db)` / scoped-session restructure (the heavier alternative we did not choose).
- Any change to Layer 2a (#410), the tools, or the feature gates.

## Risks & mitigations

- **A new LLM call added later forgets to release** → mitigated by funneling all LLM calls through the single `llm_acompletion` helper; a plain `acompletion` call becomes the thing to grep for in review.
- **Config materialization missed** → the release would silently re-query; covered by the materialization unit test and called out as load-bearing.
- **`rollback()` discards pending writes** → cannot happen here (no spanning transaction; tools commit per-op), asserted in the design and guarded by the regression suite.
