# Onboarding: Activation Checklist — Design Spec

**Date:** 2026-06-13
**Status:** Approved (design), pending spec review
**Competitor opportunity:** #10 "AI-guided onboarding + value-in-first-session"
(`YourFinanceWORKS_competitor_features.xlsx`) — this is **slice A** of three
(A = activation checklist, B = sample-data seeding [shipped, PR #400/#401],
C = AI-guided layer). C is a separate future spec.

## Problem

A brand-new tenant lands on the dashboard with no guidance on what to do to get
value from the product. The matrix calls "'aha' in the first 3 days" the highest-ROI
onboarding move, and first-3-days activation strongly predicts churn. Slice B
(sample-data seeding) lets a new tenant *see* a populated product; slice A tells them
what to *do* to make it their own, and shows progress as they do it.

The existing onboarding infra (`ui/src/components/onboarding/OnboardingProvider.tsx`)
is a **tour system** with localStorage-only state tracking completed *tours* — not
setup milestones, and not server-persisted. Slice A is genuinely new.

## Goals

- Show a dashboard "Get started — N of 5 done" checklist of concrete setup actions.
- Each step's completion is **derived live from real account data** (server truth,
  survives across devices/sessions, can never drift from reality).
- Each incomplete step deep-links to the page where the user performs it.
- The card auto-hides once all steps are complete, and can be dismissed early
  (one tenant-level flag) so a tenant that will never do a step isn't nagged forever.
- Stacks with the slice-B sample-data banner so loading samples produces an immediate,
  satisfying jump in checklist progress.

## Non-goals (out of scope / YAGNI)

- No per-step "first completed at" timestamps or activation analytics.
- No per-user checklist state (activation is a per-business concept → tenant-level).
- No reordering / configuration of steps; the five are fixed.
- No AI involvement (that is slice C).
- No new persisted state for *completion* — only the dismiss flag persists.

## The five steps (all derived)

| key | label (default) | `done` when | deep-link |
|-----|-----------------|-------------|-----------|
| `add_client` | Add your first client | any `Client` row exists | `/clients/new` |
| `create_invoice` | Create your first invoice | any non-deleted `Invoice` exists | `/invoices/new` |
| `record_expense` | Record your first expense | any non-deleted `Expense` exists | `/expenses/new` |
| `customize_branding` | Customize your invoice branding | a `Settings` row with `key="invoice_branding"` exists and `value` is non-empty | `/settings` |
| `send_invoice` | Send an invoice to a client | any `Invoice` with `status` in (`sent`, `paid`, `partially_paid`, `overdue`) | `/invoices` |

Notes:
- `Client` has no `is_deleted` column (per slice B); `Invoice`/`Expense` filter
  `is_deleted == False`.
- `customize_branding` checks the **raw** `Settings` record, not
  `get_invoice_branding(db)` (which merges defaults and would always look "set").
- Sample data (slice B) creates clients, invoices (incl. `sent`/`paid`/`overdue`/
  `partially_paid`), and expenses, but no branding — so loading samples ticks 4 of 5.

## Design

### Backend

**1. `OnboardingChecklistService` (new, `api/core/services/onboarding_checklist.py`).**
Takes a tenant `Session`.

- `CHECKLIST_DISMISS_KEY = "onboarding_checklist"`
- `checklist_status() -> dict`:
  ```python
  {
    "steps": [{"key": "add_client", "done": bool}, ... 5 total, fixed order],
    "completed": int,        # number of done steps
    "total": 5,
    "all_complete": bool,    # completed == total
    "dismissed": bool,       # from the Settings flag
  }
  ```
  Completion is computed with the queries in the table above. Step order is fixed
  and defined in the service.
- `dismiss()`: upsert a `Settings` row
  `key="onboarding_checklist"`, `value={"dismissed": True}`, `category="onboarding"`.
  If the row exists, set `value = {"dismissed": True}`; else create it. Commit once.
- Internal `_is_dismissed()` reads that row: `record and record.value and
  record.value.get("dismissed") is True`.

The service imports models lazily inside methods (mirrors `invoice_branding.py`).

**2. Endpoints (extend `api/core/routers/onboarding.py`).**

- `GET /api/v1/onboarding/checklist` → `OnboardingChecklistService(db).checklist_status()`.
  Authenticated, **no** `require_non_viewer` (read-only status; must render for viewers,
  consistent with the sample-data `GET`).
- `POST /api/v1/onboarding/checklist/dismiss` → `require_non_viewer(current_user,
  "dismiss the onboarding checklist")` then `OnboardingChecklistService(db).dismiss()`;
  returns the fresh `checklist_status()`.

No DB migration is required: the `Settings` table already exists in every tenant DB,
and completion needs no new columns.

### Frontend

**3. API client (extend `ui/src/lib/api/onboarding.ts`).**
Add:
```ts
export interface ChecklistStep { key: string; done: boolean; }
export interface ChecklistStatus {
  steps: ChecklistStep[];
  completed: number;
  total: number;
  all_complete: boolean;
  dismissed: boolean;
}
// on onboardingApi:
getChecklist(): Promise<ChecklistStatus>            // GET  /onboarding/checklist
dismissChecklist(): Promise<ChecklistStatus>        // POST /onboarding/checklist/dismiss
```
Re-exported via `ui/src/lib/api/index.ts` (already does `export * from './onboarding'`).

**4. `OnboardingChecklist.tsx` (new, `ui/src/components/onboarding/`).**
- Fetches `getChecklist()` on mount (`useEffect`); on error → render nothing
  (catch → `null`), never blocks the dashboard.
- Renders nothing if `status.dismissed` or `status.all_complete`.
- Otherwise a card:
  - Header: `t('onboarding.checklist_title', { completed, total })` →
    "Get started — {{completed}} of {{total}} done" + a progress bar
    (`completed / total`).
  - Five rows in fixed order. Each row: a check icon (done → filled/`text-primary`,
    todo → outline/muted) and the step label
    (`t('onboarding.checklist_step_<key>')`). **Incomplete** rows are links
    (React Router `Link`) to the deep-link in the table; **done** rows are plain
    (non-link) muted/struck text.
  - A small ghost "Dismiss" button → `dismissChecklist()` → on success hide
    (set local state); on error `toast.error(...)`. A `busy` guard disables it
    during the call.
- A `STEP_META` constant in the component maps `key → { i18nKey, to }` so labels and
  links stay in one place. Unknown keys from the API are skipped defensively.

**5. Placement.** Mount `<OnboardingChecklist />` in
`ui/src/components/dashboard/ProfessionalDashboard.tsx`, **directly below**
`<SampleDataBanner ... />` (which is after the hero header, before the metrics grid).
This is the dashboard that actually renders — `Index.tsx`'s inline render path is dead
code (`useProfessionalMode` is hardcoded `true`); see PR #401.

**6. i18n.** Add under the existing `onboarding.*` namespace in
`ui/src/i18n/locales/en.json`:
`checklist_title` ("Get started — {{completed}} of {{total}} done"),
`checklist_step_add_client`, `checklist_step_create_invoice`,
`checklist_step_record_expense`, `checklist_step_customize_branding`,
`checklist_step_send_invoice`, `checklist_dismiss` ("Dismiss"),
`checklist_dismiss_failed` ("Could not dismiss the checklist.").

### Data flow

Card mounts → `GET /onboarding/checklist` → render. Loading sample data (slice B)
triggers `window.location.reload()`, which re-fetches and shows ~4/5 ticked. Doing a
real action (e.g. creating a client) and returning to the dashboard re-fetches and
reflects it. Dismiss → `POST` → component hides. The card naturally disappears once
the fifth step completes.

### Error handling

- `GET` failure → `null` (no card), mirroring `SampleDataBanner`. A broken checklist
  never blocks the dashboard.
- `POST dismiss` failure → toast error, card stays visible, `busy` released.

## Testing

**Backend (`api/tests/test_onboarding_checklist.py`, new) — using the `db_session`
fixture:**
- Empty tenant → all 5 steps `done == False`, `completed == 0`, `all_complete == False`,
  `dismissed == False`.
- Creating a `Client` flips `add_client`; an `Invoice` (draft) flips `create_invoice`
  but **not** `send_invoice`; an `Expense` flips `record_expense`; writing an
  `invoice_branding` `Settings` row flips `customize_branding`; an invoice with status
  `sent` flips `send_invoice`.
- A `draft`-only tenant shows `send_invoice` incomplete.
- All five present → `completed == 5`, `all_complete == True`.
- `dismiss()` upserts the flag; a second `checklist_status()` reports
  `dismissed == True`; calling `dismiss()` twice does not error (upsert).

**Frontend (`OnboardingChecklist.test.tsx`, new):**
- Renders the card with correct done/todo rows for a mixed `getChecklist` response;
  incomplete rows are links, done rows are not.
- Renders nothing when `dismissed: true`.
- Renders nothing when `all_complete: true`.
- Clicking "Dismiss" calls `dismissChecklist` and the card disappears.

## Files touched

**Backend:** `api/core/services/onboarding_checklist.py` (new),
`api/core/routers/onboarding.py` (extend with 2 routes),
`api/tests/test_onboarding_checklist.py` (new).

**Frontend:** `ui/src/lib/api/onboarding.ts` (extend),
`ui/src/components/onboarding/OnboardingChecklist.tsx` (new) + test,
`ui/src/components/dashboard/ProfessionalDashboard.tsx` (mount below the banner),
`ui/src/i18n/locales/en.json` (onboarding.* keys).

## Risks

- **No new persistence for completion** → can't drift; the only write is the dismiss
  flag, scoped to one `Settings` row.
- **Branding false-positive:** must read the raw `Settings` record, not the
  defaults-merged `get_invoice_branding`, or the step would always look done.
- **Wrong mount point:** must mount in `ProfessionalDashboard`, not `Index.tsx` (the
  slice-B banner bug). Spec pins this explicitly.
- **Viewer role:** `GET` is unguarded so the card renders for viewers; `dismiss` is
  `require_non_viewer` so viewers can't change tenant state — matches the sample-data
  endpoints.
