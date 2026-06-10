# Budgets + Savings Goals — Plan (DRAFT, brainstorming in progress)

**Status:** 🟡 Scoping — not started. Decisions still open (scope split, nav placement).
**Source:** Popular finance features (`docs/todos/popular-finance-features-todo.md` #2), inspired by YNAB / Monarch.
**Created:** 2026-06-09

## What it is
- **Budget envelopes:** per-category monthly limit, track spend-vs-limit, month-over-month rollover, variance alert when a category goes X% over mid-month.
- **Savings goals:** target amount + target date (e.g. "Emergency fund: $10k by Dec 2026"), progress tracking, on-track / off-track forecast.

## Key decision: DECOMPOSE (recommended)
Budgets and goals are **largely independent subsystems** (different data models, different UX). Recommend shipping **budget envelopes first** as its own spec → plan → PR cycle, then **savings goals** as a separate follow-up. (Alternative: both in one larger spec — slower to first ship.)
- **OPEN:** confirm scope split (budgets-first vs goals-first vs both-together).

## Key decision: nav placement (OPEN — user flagged sidebar is already crowded ~14 items)
A new top-level sidebar item is likely **not** wanted. Candidate placements:
1. **Tabs under Cash Flow** (recommended) — `/cashflow` gains `Forecast | Budgets | Goals` tabs. Best conceptual fit (both are on-track/off-track planning) and reuses `cashflow_service`. No new sidebar entry.
2. Tab under **Expenses** — budgets track spend vs expense categories; goals fit less naturally.
3. One new gated **"Planning"** sidebar item holding both as tabs.
4. **Dashboard widget + sub-route** (`/budgets`) — lowest clutter, lower discoverability.
- Sidebar gating pattern: items are conditionally added via `isFeatureEnabled('<flag>')` in `ui/src/components/layout/AppSidebar.tsx` (see the `subscription_detection` entry ~line 413). Tab- or item-level gating both viable.

## Commercial gating
New commercial feature flag (e.g. `budgets`), `license_tier: 'commercial'`, registered in:
- `api/core/services/feature_config_service.py` (FEATURES dict)
- Landing license catalog (4 places): `finace_app_landing` → `api/core/config.py`, `api/scripts/generate_license.py`, `api/license_generator/core.py`, `ui/src/lib/license.ts`
(Same wiring as `client_portal` / `subscription_detection`. New commercial features can't be granted by already-issued licenses — dev-grant via `licensed_features`.)

## Reuse points (from codebase research 2026-06-09)
- **Categories:** free-form strings on `Expense.category` (`models_per_tenant.py:275`, indexed). **No category table / master list** — budgets keyed on category string would need a canonical list or "as-used" category enumeration. ⚠️ design risk.
- **Cashflow service:** `core/services/cashflow_service.py` — `get_forecast()`, `get_runway()`, `get_alerts()`, threshold settings. Backbone for on-track/off-track projections.
- **Notifications:** `core/services/notification_service.py` → `send_operation_notification(event_type, user_id, resource_type, resource_id, resource_name, details, company_name)` for variance/over-budget alerts (event_type e.g. `budget_overspend`).
- **Models:** new per-tenant tables in `models_per_tenant.py` (Budget, BudgetCategory/allocation, SavingsGoal). Alembic migration + `db_init.ensure_tenant_required_columns` self-heal pattern.
- **Router/schema layout:** mirror `commercial/subscriptions/` (router.py + services/ + schemas/ + models/) or core router package like `core/routers/expenses/`.
- **Frontend:** new page + tabs, gated route in `App.tsx` (lazy import, RoleProtectedRoute), API client in `ui/src/lib/api/`, i18n keys straight into `en.json`, optional dashboard widget (see `SubscriptionsWidget.tsx` precedent).

## Open questions to resolve before spec
1. Scope split (budgets-first / goals-first / both).
2. Nav placement (4 options above).
3. Budget category source — canonical category list vs derive from used `Expense.category` values.
4. Rollover semantics — does unused budget carry to next month (YNAB-style) or reset each month?
5. Budget vs actual — actuals from Expenses only, or also bank-statement debits?
6. Savings goals — tracked against a real account/balance, or manual contributions?

## Next step
Resume `superpowers:brainstorming` from the nav-placement question → finalize design → write spec to `docs/superpowers/specs/`.
