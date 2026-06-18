# AI-Guided Onboarding — Design Spec

**Date:** 2026-06-17
**Status:** Approved design — ready for implementation planning
**Competitor feature:** #10 (AI-guided / conversational onboarding), slice C — the deferred AI layer. Slices A (activation checklist) and B (sample-data seeding) already shipped.

## Goal

Give new tenants a **conversational setup wizard** that walks them to first value: it greets them, asks what they invoice for, recommends the next incomplete setup step, and — with an explicit confirm — performs the action for them (create a client, set branding, draft an invoice, record an expense). It reuses the existing commercial AI chat infrastructure rather than building a parallel one.

## Decisions (locked during brainstorming)

| Decision | Choice |
| --- | --- |
| Core experience | Conversational setup wizard |
| Availability / gating | Commercial only — reuse the existing `ai_chat` feature flag (no new flag) |
| Action capability | Perform actions **with a confirm step** (propose → confirm/edit → execute) |
| Primary surface | Inline on the dashboard, augmenting the existing activation-checklist card |
| Secondary surface | A quick-action shortcut inside the existing `AIAssistant` widget (re-enterable any time) |
| Architecture | **Option B** — extend the existing `/ai/chat` fast-path with an `onboarding` mode (not a separate module) |
| Action catalog (MVP) | create_client, set_branding, create_invoice (draft), create_expense |
| Precondition | AI provider must be configured first; otherwise the card deep-links to Settings → AI Provider Configurations |

## Background — what already exists (reused, not rebuilt)

- **Activation checklist (slice A)** — `api/core/services/onboarding_checklist.py`, derive-on-read 5 steps (`add_client`, `create_invoice`, `record_expense`, `customize_branding`, `send_invoice`) + a `onboarding_checklist` dismiss Settings key. Endpoints in `api/core/routers/onboarding.py`. Rendered by `ui/src/components/onboarding/OnboardingChecklist.tsx` in `ProfessionalDashboard.tsx`.
- **AI chat (commercial)** — `POST /ai/chat` (`api/commercial/ai/routers/chat.py`), gated `@require_feature("ai_chat")`. A **pre-LLM write fast-path** lives in `api/commercial/ai/routers/action_handlers.py`: it already executes `create_client` (`:301`) and `create_expense` (`:397`) **immediately** (no confirm). `suggest_actions` and the intent registry are read-only.
- **MCP tool layer** — `api/MCP/tools/`: `create_client` (`clients.py:107`), `create_invoice` (`invoices.py:103`, tool exists but not wired into chat), `create_expense` (`expenses.py:119`). **No** branding/settings setter exists (`settings.py` only has discount-rule + notification setters).
- **Per-tenant AI config** — `AIConfig` model (`core/models/models_per_tenant.py:494`), Settings → `AIConfigTab.tsx`, `/ai-config` router. Resolution + "not configured" signal in `chat.py:48-100` (returns `{success:false, error:"No AI configuration found..."}` when no usable config; a config must be `is_active && tested`, else env fallback).
- **Quick actions in the widget** — `AIAssistant.tsx` renders quick-action buttons via `handleQuickAction` (`:1190`, `:1366`); the send-handler routes on the translated text (e.g. `suggestActions` → `/ai/suggest-actions`, `:1091`).
- **Feature flags** — registry `feature_config_service.py` FEATURES dict; backend `@require_feature`; frontend `useFeatures()` / `<FeatureGate>`.

## Architecture (Option B — extend `/ai/chat`)

### Backend

**1. Onboarding mode + confirm gate (no regression to the live assistant).**
Extend the `/ai/chat` request with an optional `mode: "onboarding"` and an optional `confirmed_action` payload. In `action_handlers.py`:

- **Normal mode (default):** unchanged. Write intents execute immediately exactly as today. **Zero behavior change** for the existing assistant — this is the key regression guard.
- **Onboarding mode, no `confirmed_action`:** when a write intent is detected, **do not execute**. Return a `proposed_action` envelope `{ type: "proposed_action", action, params }` with the extracted fields (e.g. `{ action: "create_client", params: { name, email } }`).
- **Onboarding mode, with `confirmed_action`:** skip extraction entirely; execute that whitelisted action's MCP tool directly with the (possibly user-edited) params; return the existing success envelope.

The confirm gate is therefore a two-call dance over the **same** endpoint: propose → user confirms/edits → execute. The gate only activates under `mode:onboarding`, so the shared fast-path stays intact.

**2. New / wired actions.**

| Action | MCP tool | Work needed |
| --- | --- | --- |
| `create_client` | `create_client` (`clients.py:107`) | Honor the confirm gate |
| `create_expense` | `create_expense` (`expenses.py:119`) | Honor the confirm gate |
| `create_invoice` | `create_invoice` (`invoices.py:103`) | New onboarding intent handler + draft-invoice extraction branch (tool already exists) |
| `set_branding` | **new** `set_branding(company_name, accent_color)` in `settings.py` | New MCP tool method + backing API-client method that writes the `invoice_branding` Settings key. Logo upload stays deep-linked (no file upload via chat). |

**3. AI-provider precondition endpoint.**
`GET /onboarding/assistant/status` → `{ ai_configured: bool }`, reusing the same resolution the chat uses (usable default `AIConfig`, or env fallback). Drives the card's "configure AI first" state.

**4. Dismiss endpoint.**
A small dismiss endpoint mirroring the checklist's, writing a **separate** `onboarding_assistant` Settings key (so dismissing the conversational card is independent of the checklist card).

### Frontend

**Shared core (DRY across both entry points):**
- `useOnboardingConversation` hook — owns the message thread, calls `/ai/chat` with `mode:"onboarding"`, and surfaces a returned `proposed_action` as state.
- `ConfirmActionCard` component — renders the proposed action with **editable fields** + `[Confirm] [Edit] [Cancel]`. Confirm re-calls `/ai/chat` with `confirmed_action` (edited params). On success, the derive-on-read checklist auto-reflects progress.

**Entry point 1 — `OnboardingAssistantCard` on the dashboard (inline).**
Reads `GET /onboarding/assistant/status` first:
- `ai_configured:false` → "Set up your AI provider first" state, deep-linking to Settings → `AIConfigTab`.
- `ai_configured:true` → the conversational wizard (shared hook + confirm card). The existing `OnboardingChecklist` card remains below it as the visual progress ledger.
- Hidden when checklist `all_complete` or the `onboarding_assistant` card is dismissed.

**Entry point 2 — quick-action shortcut in `AIAssistant.tsx`.**
Add a quick-action button (`t('aiAssistant.getStarted')` → "Help me get set up") alongside the existing ones. Clicking routes the send-handler into onboarding mode (mirroring the `suggestActions` detection at `:1091`) and renders the **same** `ConfirmActionCard`. Respects the AI-config precondition (replies with a configure-AI deep-link when not configured).

## Conversation design

The onboarding system prompt: (1) states the goal (reach first value), (2) is fed the **current checklist state** (`/onboarding/checklist`) so it suggests the next *incomplete* step, (3) lists the whitelisted action catalog, (4) instructs it to propose **one action at a time** and never invent IDs. The thread is short-lived (client-side state; not persisted to `chat_history`).

**Action catalog — the only writes onboarding mode will propose:**

| Action | Confirm-card fields |
| --- | --- |
| `create_client` | name, email (phone optional) |
| `set_branding` | company_name, accent_color |
| `create_invoice` | client (last-created / picker), amount, due_date |
| `create_expense` | amount, category, vendor |

Anything outside the catalog (logo upload, sending an invoice) → deep-link, never act. Nothing writes without an explicit Confirm.

## Gating & state

- **License:** commercial `ai_chat` (existing). No new feature flag.
- **Dashboard card visibility:** commercial tenant with `ai_chat`, checklist not `all_complete`, not dismissed.
- **State:** no new persisted onboarding progress state — the derive-on-read checklist is the single source of truth. The assistant card is purely a driver.
- **Dismissal:** dedicated `onboarding_assistant` Settings key + dismiss endpoint, independent of the checklist's `onboarding_checklist` key.

## Testing

**Backend**
- Onboarding mode returns `proposed_action` (no write) for each of the 4 actions.
- Onboarding mode with `confirmed_action` executes the correct MCP tool with the given params.
- **Regression:** normal mode still executes writes immediately (unchanged).
- New `set_branding` tool writes the `invoice_branding` Settings key.
- `GET /onboarding/assistant/status` reports `ai_configured` correctly across: configured DB config, env fallback, none.
- `@require_feature("ai_chat")` blocks non-licensed tenants.
- Dismiss endpoint writes the `onboarding_assistant` key and is independent of the checklist key.

**Frontend**
- `useOnboardingConversation` surfaces `proposed_action` → renders `ConfirmActionCard`.
- Confirm posts edited params; success updates the checklist.
- Card hides when complete / dismissed / not-configured; the not-configured state deep-links to AIConfigTab.
- Quick-action shortcut routes into onboarding mode and renders the same confirm card.

## Out of scope (deferred)

- Logo upload via chat (deep-link only).
- Sending an invoice from the wizard (deep-link only).
- Persisting the onboarding conversation to chat history.
- Proactive/unprompted assistant nudges (this design is user-initiated from card or shortcut).
- A non-commercial / free-tier AI onboarding path.
