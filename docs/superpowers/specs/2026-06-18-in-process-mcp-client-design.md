# In-Process MCP Client — Design Spec

**Date:** 2026-06-18
**Status:** Approved design — ready for implementation planning
**Context:** Root-cause fix for per-tenant DB connection-pool exhaustion (Layer 2a). See `project_db_connection_pool` memory and PR #409 (the "stop the bleeding" mitigations). This eliminates the self-HTTP amplification; **2b (holding a connection across the LLM call) is explicitly deferred.**

## Problem

When the AI assistant's MCP tools run inside the `/ai/chat` request, they call back to the **same** API server over HTTP (`AuthenticatedAPIClient` → `http://localhost:8000/api/v1`). Each nested call re-enters the ASGI stack and opens a **second tenant DB connection** (the request already holds one via `Depends(get_db)`). The worst case — the intent-dispatch path — fires up to 3 nested calls, so one chat turn can hold 2–4 connections on a 15-slot per-tenant pool. A handful of concurrent AI chats starve unrelated endpoints like `read_invoices`.

## Goal

Eliminate the self-HTTP in the chat path: reimplement the tool methods to run **in-process**, reusing the chat request's existing tenant session — no JWT, no httpx, no second connection. The standalone MCP server (a separate process that legitimately needs HTTP) is untouched.

## Decisions (locked during brainstorming)

| Decision | Choice |
| --- | --- |
| How tool calls execute in-process | **Reimplement data access in a new client** (not "call route handlers", not "extract services") |
| Scope | **All ~30 chat-path methods** (no permanent fallback) |
| 2b (connection held across LLM call) | **Deferred** — do 2a, re-measure, decide later |
| Transaction isolation | **SAVEPOINT per write** (`db.begin_nested()`) on the shared request session |
| Cross-cutting concerns | **Reuse existing shared helpers** (RBAC, audit, validators, notifications) — reimplement only orchestration glue |
| Notification/audit | **Full parity** — AI-initiated writes behave identically to UI writes |
| Rollout | **Incremental** — delegate un-migrated methods to a wrapped `AuthenticatedAPIClient`, domain-by-domain, delete fallback at the end |

## Background (verified against source)

- **The seam is the injected `api_client`.** `InvoiceTools` (`api/MCP/tools/__init__.py:28`) is composed of 18 domain mixins whose only state is `self.api_client`; every method delegates to `self.api_client.<name>(...)`. The client is constructed in exactly **two** chat-path sites: `chat.py:217-221` and `action_handlers.py:_init_tools` (`:25-38`, called at `:165,224,245,321,381,505`).
- **No service layer exists.** The target endpoints (`POST /clients/`, `GET/POST /invoices/`, `GET/POST /expenses/`, `PUT /settings/`, etc.) keep their logic *inside* FastAPI route handlers that take `Depends(get_db)`/`Depends(get_current_user)` and raise `HTTPException`. (This is why we reimplement rather than call a service.)
- **Tenant context + session already available.** `current_tenant_id` contextvar (`core/models/database.py:20`) is set by `tenant_context_middleware` before the handler runs; `ai_chat` already holds a tenant-scoped `db` (`chat.py:36`) and threads it into `handle_early_actions(..., db=db)` and `dispatch_intent(..., db=db)` / `IntentContext.db`. So an in-process call reuses the correct tenant session directly.
- **Standalone MCP server uses a different client class** (`MCP/api_client.py::InvoiceAPIClient`, email/password auth) constructed at `MCP/server/_shared.py:55`. Swapping only the chat-path client leaves it fully intact.
- **One direct bypass:** `action_handlers.py:348` calls `tools.api_client.replace_bank_statement_transactions(...)` directly, so the in-process client must implement that method too.

## Architecture

### The client
A new `InProcessAPIClient` exposing the **same async method names/signatures** as `AuthenticatedAPIClient` (methods take dicts / simple args, return dicts — exactly what the mixins pass and expect). Injected at the two chat-path sites only:
- `chat.py`: `InProcessAPIClient(db=db, current_user=current_user)` instead of `AuthenticatedAPIClient(base_url=..., jwt_token=...)`.
- `action_handlers.py:_init_tools`: thread the request's `db` + `current_user` in (today it takes only `current_user_email`); construct `InProcessAPIClient(db=db, current_user=current_user)`.

`InvoiceTools` and all 18 mixins are **unchanged**.

### Structure (anti-drift)
`InProcessAPIClient` is a **package of domain mixins** mirroring `api/MCP/tools/` — `clients`, `invoices`, `expenses`, `settings`, `payments`, `cashflow`, `statements`, `investments`, `currencies`, `ai_analytics` — so no single file grows unwieldy and each is independently testable. Proposed location: `api/commercial/ai/inprocess/` (`client.py` assembles the mixins; one module per domain).

**Anti-drift rule:** each method MUST reuse every shared sub-helper its real route handler uses — RBAC (`require_component_permission`, `require_non_viewer`), audit (`log_audit_event`), validators (`validate_invoice_branding`, `CurrencyService`, invoice-number generation), and notification triggers. We reimplement **only** the orchestration glue + the model reads/writes on the request session. We never re-derive permission/audit/validation logic.

### Connection & transaction semantics (the fix)
- Every method uses the **chat request's existing `db` session** — no new connection, no JWT, no httpx.
- **Writes**: wrap the operation in `db.begin_nested()` (SAVEPOINT) so a single tool failure rolls back just that operation rather than poisoning the shared session, then `commit()` on success (matches today's per-endpoint commit). A second `master_db` is opened only where the corresponding handler needs one (e.g. settings, expenses), via `next(get_master_db())`, and closed in `finally`.
- **Reads**: never commit.

### Error contract & response-shape parity
- Methods **raise on failure** — the tools already wrap every call in `try/except` → `{success, error}`, so raising preserves their envelope behavior. Translate handler-style `HTTPException` into a lightweight raised error.
- Methods **return the same shapes** the current `AuthenticatedAPIClient` returns, so the tools' `_extract_items_from_response` (keys `items`/`data`/`<domain>`) and downstream formatting keep working. Response-shape parity is verified **method-by-method** (the fiddliest part; called out per task in the plan).

### Incremental rollout
`InProcessAPIClient` **delegates any not-yet-implemented method to a lazily-constructed wrapped `AuthenticatedAPIClient`** (self-HTTP) during migration — so each migrated method flips one path in-process while the rest keep working. Migrate **domain-by-domain**; delete the fallback once all 30 are implemented.

## Migration target (the ~30 methods, by domain)

- **clients:** `create_client`, `list_clients`, `get_clients_with_outstanding_balance`
- **invoices:** `list_invoices`, `create_invoice`, `get_invoice_stats`, `get_overdue_invoices`
- **expenses:** `create_expense`, `list_expenses`
- **settings:** `update_settings` (covers `set_branding`)
- **payments:** `list_payments`
- **cashflow:** `get_cashflow_forecast`, `get_cashflow_runway`, `get_cashflow_alerts`, `get_cashflow_thresholds`, `update_cashflow_thresholds`, `run_cashflow_scenario`
- **statements:** `list_statements`, `get_bank_statement`, `replace_bank_statement_transactions`, `reprocess_bank_statement`, `update_bank_statement_meta`
- **investments:** `list_portfolios`, `get_portfolio`, `get_portfolio_holdings`, `get_portfolio_performance`, `get_portfolio_allocation`, `get_portfolio_dividends`
- **currencies:** `list_currencies`
- **ai-analytics:** `analyze_invoice_patterns`, `suggest_invoice_actions`

(`search_clients`/`search_invoices`/`search_expenses` are client-side filters over the list methods — they come for free once the list methods are in-process.)

## Notification / audit parity

Write handlers fire side effects (e.g. `POST /clients/` writes an audit row and sends a client-created email). **AI-initiated writes reuse the same audit + notification calls** so behavior is identical to UI writes. (Not making AI writes "quiet" — that would create silent inconsistency.)

## Testing

- **Per-method unit tests** with a session fixture asserting: correct model reads/writes; **RBAC enforced** (a viewer/insufficient-permission user is rejected, same as the endpoint); **audit row written** for writes; **response shape** matches what the corresponding tool expects (parity with the `AuthenticatedAPIClient` return dict).
- **Parity spot-checks**: for a few representative methods, compare in-process result vs the HTTP result (where the stack is up).
- **Regression guard:** assert the standalone MCP server's construction path (`MCP/server/_shared.py`) is unchanged and still uses the HTTP client.
- **Concurrency validation (manual):** re-run `api/scripts/pool_loadtest.py` against the general intent-dispatch path; confirm the per-request connection count drops to 1 (no amplification) and the pool no longer exhausts under the prior load.

## Out of scope (deferred)

- **2b** — restructuring `ai_chat` so it doesn't pin a connection during the litellm call. Re-measure after 2a lands; only do 2b if the data still shows exhaustion.
- The standalone MCP server and `MCP/api_client.py` (legitimately HTTP).
- Any change to `InvoiceTools` / the tool mixins.

## Risks & mitigations

- **Logic drift** between reimplemented methods and the real endpoints → mitigated by the anti-drift rule (reuse all shared sub-helpers) + per-method parity tests; revisit if endpoints change.
- **Shared-transaction coupling** (tool write + chat request share one session) → mitigated by SAVEPOINT-per-write isolation.
- **Response-shape mismatches** breaking tool formatting → mitigated by method-by-method shape parity verification + the incremental fallback (a wrong reimpl can be reverted to HTTP for that one method).
- **Security:** reimplementation must not bypass RBAC → permission-enforcement assertions are mandatory per write method.
