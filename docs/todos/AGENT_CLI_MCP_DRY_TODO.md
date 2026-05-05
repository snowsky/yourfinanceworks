# Agent CLI & MCP DRY TODO

This document tracks follow-up refactoring work to reduce duplication between the Finance Agent CLI, backend AI chat routing, and MCP tools.

## Current State

The Agent CLI now supports:

- authenticated chat through `/api/v1/ai/chat`
- backend MCP tool planning with structured tool arguments
- formatted chat output by default
- document scanning and ingestion commands
- portfolio monitoring commands

There is still overlap between these layers:

- `cli/finance_agent_cli/api_client.py`
- `api/commercial/ai/routers/auth_client.py`
- `api/MCP/api_client.py`
- `api/MCP/tools/*.py`
- `api/commercial/ai/routers/intent_handlers.py`

## Target Direction

Use MCP tools as the canonical business operation layer.

Low-level API clients should focus on transport concerns:

- base URL handling
- authentication headers
- request/response execution
- small response normalization helpers

MCP tools should own domain operations:

- `list_expenses`
- `query_payments`
- `get_portfolio_summary`
- `get_cashflow_runway`
- `list_clients`

Agent planning should decide what to call and which arguments to pass, not reimplement domain logic.

## Immediate Tasks

- [ ] Inventory overlapping methods across:
  - [ ] CLI API client
  - [ ] AI chat authenticated API client
  - [ ] MCP API client
  - [ ] MCP tools
- [ ] Identify methods that are pure transport wrappers versus domain operations.
- [ ] Document which layer owns each operation.
- [ ] Keep deterministic CLI commands stable while refactoring internals.

## Response Normalization

- [ ] Create a shared helper for list/envelope extraction.
- [ ] Support common response shapes:
  - [ ] raw list
  - [ ] `{ "items": [...] }`
  - [ ] `{ "data": [...] }`
  - [ ] `{ "expenses": [...] }`, `{ "payments": [...] }`, etc.
- [ ] Replace local `_extract_items_from_response` clones or near-clones where practical.
- [ ] Add regression tests for paginated envelopes in payments, expenses, invoices, clients, and portfolios.

## Tool Planning & Execution

- [ ] Introduce a small tool execution registry for AI chat.
- [ ] Move intent-to-handler branching out of the large `dispatch_intent` function over time.
- [ ] Support tool plans with structured arguments:
  - [ ] `limit`
  - [ ] `skip`
  - [ ] `date_range`
  - [ ] `category`
  - [ ] `client_id`
  - [ ] `portfolio_id`
- [ ] Validate planner arguments before passing them to MCP tools.
- [ ] Return clear errors when the planner asks for unsupported arguments.

## Structured Data vs Formatting

- [ ] Make MCP tools return structured domain data consistently.
- [ ] Move dashboard/prose formatting out of MCP tool execution paths.
- [ ] Add dedicated formatters for:
  - [ ] payment dashboards
  - [ ] expense dashboards
  - [ ] invoice dashboards
  - [ ] client summaries
  - [ ] portfolio summaries
- [ ] Keep final answer synthesis grounded only in MCP tool outputs.

## API Client Consolidation

- [ ] Review whether `api/commercial/ai/routers/auth_client.py` can reuse `api/MCP/api_client.py`.
- [ ] Keep JWT-authenticated backend calls tenant-safe.
- [ ] Avoid duplicating endpoint paths across multiple client classes when a shared transport method is enough.
- [ ] Keep CLI sync behavior unless there is a clear reason to switch the CLI to async.

## CLI Direction

Short-term:

- [ ] Keep deterministic commands such as `portfolio list`, `portfolio monitor`, and `documents scan` working through the CLI API client.
- [ ] Keep `agent chat` routed through backend AI chat and MCP tool planning.

Medium-term:

- [ ] Add a backend tool-execution endpoint if deterministic CLI commands should call MCP tools directly.
- [ ] Consider a generic CLI command for planned tool execution, for example:
  - `agent tool expenses --limit 4`
  - `agent tool payments --date-range this_month`

Long-term:

- [ ] Decide whether deterministic CLI commands should remain REST-client commands or become MCP/tool commands.
- [ ] Remove duplicated transport wrappers only after command behavior is covered by tests.

## Testing Backlog

- [ ] Unit tests for tool plan parsing with arguments.
- [ ] Unit tests for tool argument validation.
- [ ] Unit tests for shared response normalization.
- [ ] Integration tests for agent chat using planned `limit` values.
- [ ] Regression tests for:
  - [ ] "how much did I get paid?"
  - [ ] "how much did I spend in the last 4 expenses?"
  - [ ] "what was my net income?"
  - [ ] "show overdue invoices"
- [ ] CLI tests for normal formatted output and `--json` output.

## Documentation Backlog

- [ ] Update `docs/features/AGENT_CLI.md` after the tool registry is introduced.
- [ ] Add an architecture note for Agent CLI, AI chat, and MCP layer ownership.
- [ ] Document supported planner arguments.
- [ ] Document how to add a new MCP-backed agent intent.

## Open Questions

- Should MCP tools be the only domain operation layer for AI workflows?
- Should deterministic CLI commands eventually call MCP tools, or remain direct REST client commands?
- Should tool planning return only one tool by default unless explicit multi-domain reasoning is needed?
- Should response formatting live in backend formatters, CLI renderers, or final LLM synthesis?
