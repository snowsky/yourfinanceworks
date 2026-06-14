# Finances Hub + Net Worth Tab — Design Spec

**Date:** 2026-06-14
**Status:** Approved (design), pending spec review
**Feature flags:** existing `cash_flow` and `net_worth` (both commercial; no new flag)
**Parent:** Net worth (competitor #3, Personal Capital / Empower). The net-worth *engine* is
already built and tested (aggregator combines bank + investments + liabilities, snapshots,
month-over-month history; 7 backend tests). The gap is the **product surface**: net worth
lives only in a cramped dashboard widget with no dedicated page or navigation.

## Problem

Net worth has no page and no nav — it's a single dashboard widget showing combined totals,
a fixed 12-month mini-chart, and add/delete-only liabilities. The `summary` endpoint already
returns a **per-account breakdown** (each investment portfolio, bank, and liability) that
nothing displays; `history` accepts up to 60 months but the widget hardcodes 12; the
`liabilities` API supports `interest_rate`/`notes` and PATCH-edit that the UI ignores.

Rather than add a standalone page (the sidebar is already ~14 items) **or** fold net worth
into the unrelated "Cash Flow" page (different mental model — flow vs. balance — and the two
are independently licensed), we introduce a **"Finances" hub**: one nav item with tabs
**Cash Flow | Net Worth**, each individually feature-gated. This groups the two
financial-position views, avoids a new sidebar entry, and sets up Budgets/Goals as future tabs.

## Goal

A `/finances` hub page with a Net Worth tab that delivers the full Empower-style view —
per-account breakdown, trend chart with timeframe control, prominent delta, snapshot action,
and full liabilities management — entirely over **existing** backend endpoints.

## Non-goals (out of scope)

- **No backend changes.** Every capability reuses existing endpoints (`/networth/summary`,
  `/networth/history?months=`, `/networth/snapshot`, `/networth/liabilities` CRUD incl. PATCH).
- **No automatic/scheduled snapshots.** Snapshots stay manual + on-statement-import (a
  scheduled job is a separate, infra-heavy follow-up).
- **No full-feature i18n.** New strings follow the existing inline / `defaultValue` pattern
  the cashflow + networth UI already use; centralizing is separate cleanup.
- **No money Decimal migration.** Out of scope.
- **No Budgets/Goals tabs** (this design only makes the hub that would later host them).

## Architecture / composition

New thin page `ui/src/pages/Finances.tsx`:
- Renders ONE `PageHeader` (title "Finances") and a shadcn `Tabs` bar
  (`@/components/ui/tabs`).
- Tab state driven by the `?tab=` query param via `useSearchParams`, so `/finances?tab=networth`
  deep-links to the Net Worth tab. Valid values: `cashflow`, `networth`.
- **Only enabled features render a tab**: `isFeatureEnabled('cash_flow')` → "Cash Flow",
  `isFeatureEnabled('net_worth')` → "Net Worth". Default selected tab = `cashflow` if cash_flow
  enabled, else `networth`. If the `?tab` value points at a disabled/absent tab, fall back to
  the default. If neither feature is enabled the hub still mounts (route is reachable) and shows
  a single `FeatureGate` upgrade prompt (gate on `cash_flow`) — but in practice the sidebar item
  is hidden when neither is enabled, so this is an edge fallback.

Contained refactor of `ui/src/pages/CashFlow.tsx` (currently 968 lines, main component at
line 888 = `FeatureGate(cash_flow)` → `div.space-y-6` → `PageHeader("Cash Flow")` → content
grid driven by `period` state + 3 queries):
- Extract the `period` state, the three queries (`forecast`/`runway`/`alerts`), and the content
  grid into an exported `CashFlowTabContent` component that renders **no** `PageHeader` and
  **no** `FeatureGate`.
- The hub renders `<CashFlowTabContent/>` under the Cash Flow tab. Because that tab only mounts
  when `cash_flow` is enabled, the per-component `FeatureGate` is unnecessary.
- Remove the old `CashFlow` default export / page wrapper (its only consumer was the `/cashflow`
  route, which becomes a redirect). The helper sub-components in that file
  (`AlertsBanner`, `RunwayCard`, `ForecastChart`, `InflowOutflowBreakdown`, `ScenarioBuilder`,
  `StatementPatternSidebar`, etc.) are untouched.

New `ui/src/components/networth/NetWorthTabContent.tsx` renders the Net Worth tab body
(details below). It reuses `networth-helpers.ts` (`formatCurrency`, `monthOverMonthDelta`,
`KIND_LABELS`) and the `networthApi` client. No `PageHeader`/`FeatureGate` of its own.

## Net Worth tab (`NetWorthTabContent`)

Data: `networthApi.summary()` (current totals + `accounts: AccountBalanceResponse[]`),
`networthApi.history(months)` (timeframe-driven), `networthApi.snapshot()` mutation. All
TanStack Query under `['networth', ...]` keys; mutations invalidate `['networth']`.

1. **Header row + delta callout** — current `summary.net_worth` (large), "as of
   {snapshot_date}", and a month-over-month delta badge (amount + %, up/down/flat color +
   icon) from `monthOverMonthDelta(history.points)`. Shown when `history.points.length > 1`.
   A "Snapshot now" button triggers `snapshot()` (disabled while pending; toast on success).
2. **Trend chart + timeframe** — full-width recharts `LineChart` of `net_worth` over
   `history.points`, with a `Select` timeframe control (6 / 12 / 24 / 60 months) whose value
   feeds `networthApi.history(months)` (query key includes `months`). Empty/short-history state:
   a hint to snapshot.
3. **Per-account breakdown table** — `summary.accounts` grouped by `account_kind`:
   - **Investments** (each portfolio by `label`), **Bank** (each account), **Liabilities**
     (each, shown as negative). Per-group subtotal; assets subtotal (bank + investment),
     liabilities subtotal, and the resulting net worth. Uses `formatCurrency(balance, currency)`.
   - Empty state when `accounts` is empty: prompt to snapshot.
4. **Liabilities management section** — a table of liabilities (`networthApi.listLiabilities()`)
   with name, kind (via `KIND_LABELS`), balance, interest rate, and edit/delete actions, plus an
   "Add liability" button. Add/edit go through the enhanced `LiabilitiesDialog` (below).

## Liabilities enhancement (`LiabilitiesDialog`)

Extend the existing dialog (currently create + delete only; ignores `interest_rate`/`notes`):
- Accept an optional `liability?: LiabilityResponse` prop → **edit mode** (prefills fields,
  submits via `networthApi.updateLiability(id, body)` = PATCH); absent → create mode (POST).
- Add **`interest_rate`** (optional number, 0–100) and **`notes`** (optional text) inputs to the
  form, included in create/update bodies (`LiabilityCreateRequest`/`LiabilityUpdateRequest`
  already carry them).
- The dialog keeps its existing in-dialog list + delete (so the dashboard widget's "Liabilities"
  button is unchanged). The Net Worth tab renders its **own** inline liabilities list (with
  edit/delete) and opens the same `LiabilitiesDialog` in add mode (no `liability` prop) or edit
  mode (with `liability`). Both surfaces share the one dialog component (DRY). On create/update/
  delete the dialog invalidates `['networth']` so summary/breakdown/history refresh.

## Routing / navigation / gating

- `ui/src/App.tsx`: add lazy route `/finances` → `<Finances/>` (RoleProtectedRoute,
  `['admin','user']`, mirroring the current cashflow route). Change `/cashflow` to render
  `<Navigate to="/finances" replace/>` so existing bookmarks/links keep working.
- `ui/src/components/layout/AppSidebar.tsx`: the current `cash_flow`-gated entry becomes a
  **"Finances"** item, `path: '/finances'`, shown when `isFeatureEnabled('cash_flow') ||
  isFeatureEnabled('net_worth')`. Keep an existing icon (e.g. `Landmark`).
- Dashboard links: `CashFlowForecastCard` `navigate('/cashflow')` → `'/finances'`;
  `NetWorthWidget` "View all" link → `'/finances?tab=networth'`. Both dashboard widgets are
  otherwise unchanged.

## Data flow

Hub mounts → reads `?tab` + feature flags → renders enabled tabs → active tab's content
component runs its own queries (cashflow forecast/runway/alerts, or networth summary/history)
→ user actions (timeframe change, snapshot, liability add/edit/delete) mutate via existing
endpoints and invalidate the relevant query keys. No new API surface, no write path beyond the
existing networth mutation endpoints.

## Error handling

Reuse existing patterns: TanStack Query loading/empty states; `toast.error(getErrorMessage(err, t))`
on mutation failure; snapshot/liability buttons disabled while pending. An invalid `?tab` value
falls back to the default tab rather than rendering an empty page.

## Testing (Vitest / RTL)

- **`Finances` hub:** tab visibility by feature flags (both enabled → both tabs; only
  `net_worth` → only Net Worth tab, defaulted; only `cash_flow` → only Cash Flow);
  `?tab=networth` selects the Net Worth tab. Mock `useFeatures` (test-utils already does → true;
  override per-case) and the content components / APIs.
- **`NetWorthTabContent`:** render with mocked `networthApi.summary` (accounts across all three
  kinds) + `history` → asserts per-account breakdown rows (a portfolio name, a bank, a liability),
  the delta callout, the chart presence, and the liabilities section. Timeframe change refetches
  with the new `months`.
- **`LiabilitiesDialog`:** edit mode prefills and submits via PATCH; create mode still POSTs;
  `interest_rate`/`notes` are sent.
- **`networth-helpers`:** `monthOverMonthDelta` (up / down / flat / null-prev) if not already
  covered.
- **No backend tests** (no backend change; engine already covered by 7 tests).
- Type-check: `tsc -p tsconfig.app.json --noEmit` clean on all touched files.

## Files touched

**New**
- `ui/src/pages/Finances.tsx` (hub: header + tabs + ?tab + gating)
- `ui/src/components/networth/NetWorthTabContent.tsx` (Net Worth tab body)
- Test files: `ui/src/pages/__tests__/Finances.test.tsx`,
  `ui/src/components/networth/__tests__/NetWorthTabContent.test.tsx`,
  `ui/src/components/networth/__tests__/LiabilitiesDialog.test.tsx` (if not present),
  `ui/src/components/networth/__tests__/networth-helpers.test.ts` (if not present).

**Modified**
- `ui/src/pages/CashFlow.tsx` (extract `CashFlowTabContent`; drop page wrapper/header/gate)
- `ui/src/components/networth/LiabilitiesDialog.tsx` (edit mode + interest_rate/notes)
- `ui/src/App.tsx` (`/finances` route + `/cashflow` redirect)
- `ui/src/components/layout/AppSidebar.tsx` (Finances item, gated on either feature)
- `ui/src/components/dashboard/CashFlowForecastCard.tsx` (link → `/finances`)
- `ui/src/components/dashboard/NetWorthWidget.tsx` ("View all" → `/finances?tab=networth`)

## Risks

- **CashFlow extraction regression:** the 968-line file is being restructured (state/queries/grid
  moved into `CashFlowTabContent`). Mitigation: pure cut-move of an existing block, keep all
  sub-components and query keys identical; verify the Cash Flow tab renders the same content via
  manual check + tsc. No logic changes.
- **Tab/route churn:** several link sites updated; the `/cashflow → /finances` redirect preserves
  external links. Sidebar gating widened to either feature.
- **Sparse history:** snapshots remain manual/on-import, so the trend chart can be sparse for
  infrequent importers. Accepted (auto-snapshot is an explicit follow-up); the UI shows a
  snapshot prompt when history is thin.
