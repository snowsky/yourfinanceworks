# Forgotten / Needs-Review Subscriptions — Design Spec

**Date:** 2026-06-14
**Status:** Approved (design), pending spec review
**Feature flag:** `subscription_detection` (existing commercial gate — no new flag)
**Parent:** Popular finance features — subscription detection (Rocket Money / Copilot). Detection,
price-change alerts, list/detail UI, dashboard widget, and cancel-reminder storage already shipped.

## Problem

Subscription detection is ~90% built. Of the four competitor promises, three are done
(active list + next-charge date, price-change alerts, cancel-reminder storage) but the
**"forgotten / unused subscription" flag is missing entirely** — no model field, no query,
no UI. This is the marquee Rocket Money promise: surface recurring charges the user has
forgotten about or that have silently lapsed.

We only have **bank-charge data** (no product-usage signal), so "forgotten" is derived
purely from charge dates. Two distinct, complementary signals:

- **Lapsed / possibly-canceled** — an `active` subscription whose charges have *stopped*
  (overdue well past its expected next charge). Either it was canceled (clean it up) or
  something is wrong.
- **Long-running** — an `active` subscription *still charging* that has been running long
  enough to be easy to forget. Show how long / how much so the user can judge.

## Goal

Surface a **"Needs review"** treatment on the existing Subscriptions page, detail page, and
dashboard widget, derived on read from dates already stored. No new columns, no migration,
no scheduler, no notifications.

## Non-goals (out of scope)

- **No notifications / scheduler.** A lapsed sub can become lapsed with no scan running, so
  reliable alerts would need `reminder_scheduler` wiring — deferred. This slice is
  derive-on-read UI only.
- **No draft cancellation email.** Separate, larger feature.
- **No money threshold for long-running.** Age-only rule (currency-agnostic); cumulative
  spend is *shown*, not used as a filter.
- **No full-feature i18n pass.** The subscription UI currently uses inline hardcoded strings /
  `defaultValue` fallbacks (zero keys in `en.json`). New strings follow that same inline
  pattern to stay consistent with surrounding code; centralizing the whole feature's strings
  is a separate cleanup.
- **No new DB columns / Alembic migration.** Everything is derived from existing fields.

## Detection rules (pure function)

New module `api/commercial/subscriptions/services/subscription_review.py`, one pure,
deterministic, testable function:

```python
def evaluate_review(sub: DetectedSubscription, *, today: date) -> ReviewInfo
```

`ReviewInfo` is a frozen dataclass: `reason: Optional[Literal["lapsed", "long_running"]]`,
`days_overdue: Optional[int]`, `months_running: Optional[int]`.

Rules (evaluated in order; at most one reason):

1. **Only `status == "active"`** rows are eligible. Any other status → `reason=None`.
2. **`lapsed`** — `next_expected_date` is not None and
   `today > next_expected_date + grace`, where
   `grace = max(7, round(0.5 * cadence_days))`.
   - `days_overdue = (today - next_expected_date).days`.
   - Rationale: a monthly (30d) sub flags ~15 days after a missed charge; a weekly (7d) sub
     flags ~7 days after; quarterly (90d) ~45 days after. Conservative — avoids flagging a
     charge that is merely a few days late.
3. **`long_running`** — not lapsed, and `(today - first_seen_date).days >= 180`.
   - `months_running = (today - first_seen_date).days // 30`.
4. **Precedence:** a lapsed sub is, by definition, not currently charging, so it cannot also
   be "still-charging long-running." `lapsed` wins; `long_running` is only considered when not
   lapsed. At most one reason is ever returned.

Constants (module-level, named): `LONG_RUNNING_MIN_DAYS = 180`, `LAPSED_MIN_GRACE_DAYS = 7`,
`LAPSED_GRACE_CADENCE_FRACTION = 0.5`.

## Backend shape

- **`SubscriptionResponse`** (`schemas/subscription.py`) gains three optional derived fields,
  all defaulting to `None`:
  - `review_reason: Optional[Literal["lapsed", "long_running"]] = None`
  - `days_overdue: Optional[int] = None`
  - `months_running: Optional[int] = None`
- **Builder** `to_response(sub, *, today: date | None = None) -> SubscriptionResponse` (in the
  review module or router helpers): `today = today or date.today()`, then
  `resp = SubscriptionResponse.model_validate(sub)`, compute `evaluate_review(sub, today=today)`,
  and set the three fields (`model_copy(update=...)` or direct attribute set on the model
  instance). `today` is injectable so router/summary tests are deterministic.
- **Replace the five bare `SubscriptionResponse.model_validate(sub)` call-sites** in
  `router.py` (get, status, cancel-reminder, acknowledge, and the list item-building inside
  `_build_summary`) with `to_response(...)` so every endpoint returns review info consistently.
- **`SubscriptionSummary`** gains `needs_review_count: int` — count of active rows whose
  `evaluate_review` returns a reason. Computed in `_build_summary` over the full row set
  *before* any `needs_review` post-filter, so the headline number is stable.
- **List endpoint** (`GET /subscriptions`) gains `needs_review: bool = Query(False)`. When
  true, the built items are post-filtered in Python (the flag is derived, not a SQL column) to
  rows with a non-null `review_reason`. `needs_review_count` is still computed over the
  pre-filter active set. `_build_summary` takes a `needs_review` flag (and `today`) to drive
  this; existing `monthly_cost` / `annual_cost` / `next_charge_date` are unchanged.

`evaluate_review` reads only fields already present on `DetectedSubscription`
(`status`, `next_expected_date`, `cadence_days`, `first_seen_date`). No model change.

## Frontend surfacing (`ui/src/...`)

- **Types** (`lib/api/subscriptions.ts`): add `review_reason`, `days_overdue`,
  `months_running` to `SubscriptionResponse`; add `needs_review_count` to
  `SubscriptionSummary`; `list()` params accept `needsReview?: boolean` → `needs_review=true`.
- **`components/subscriptions/subscription-helpers.ts`**:
  - `reviewReasonLabel(sub)` → `"Possibly canceled"` (lapsed) / `"Long-running"` (long_running)
    / `null`.
  - `reviewReasonDetail(sub)` → one-line string: lapsed → `"{days_overdue} days overdue"`;
    long_running → `"Running {months_running} mo · ~{monthlyCost×months} paid"` using the
    existing `monthlyCost` + `formatCurrency` helpers (cumulative spend computed in UI, no new
    backend field).
- **`pages/Subscriptions.tsx`**:
  - A **"Needs review (N)"** summary tile (from `needs_review_count`), alongside the existing
    Active / Monthly / Annual / Next-charge tiles.
  - A **"Needs review"** option in the existing status filter dropdown; selecting it calls
    `list({ needsReview: true })`.
  - A per-row **reason badge** (amber tone, mirroring the existing unacknowledged
    price-change badge) showing `reviewReasonLabel` when set.
- **`pages/SubscriptionDetail.tsx`**: a "Needs review" alert card (same visual pattern as the
  existing price-change alert card) when `review_reason` is set — naming the reason and metric
  and pointing at the already-present Mark-canceled / Dismiss / Set-reminder actions. No new
  actions.
- **`components/dashboard/SubscriptionsWidget.tsx`**: one extra line — "N to review" — when
  `needs_review_count > 0`, for discovery.
- **i18n**: new strings use the same inline / `defaultValue` pattern the feature already uses.

## Data flow

`GET /subscriptions[?needs_review=true]` → `list_subscriptions` (unchanged SQL) → router
builds each item via `to_response(sub, today=...)`, which calls `evaluate_review` → optional
`needs_review` post-filter on items → `_build_summary` attaches `needs_review_count` →
frontend renders tile + filter + per-row badge; detail page and dashboard widget read the same
derived fields. No write path, no background job.

## Error handling

Pure function with no I/O; cannot fail on bad data — guards: `cadence_days <= 0` → grace
falls back to `LAPSED_MIN_GRACE_DAYS`; `next_expected_date is None` → never lapsed;
non-active status → always `reason=None`. The list/summary path is unchanged except for the
added derivation, which is total over the existing field domain.

## Testing (TDD)

- **Backend, local-runnable (pure):** `evaluate_review` unit tests —
  - lapsed just-before grace boundary → no reason; just-after → `lapsed` with correct
    `days_overdue`;
  - long-running 179 days → no reason; 180 days → `long_running` with correct `months_running`;
  - active & recent & on-time → no reason;
  - dismissed/canceled/not_a_subscription (even if overdue) → no reason;
  - `next_expected_date is None` → never lapsed (long_running still possible);
  - a sub that is BOTH overdue and ≥180 days old → `lapsed` (precedence);
  - `cadence_days = 0` → grace falls back to 7, no crash.
  These run without Docker (pure, no DB).
- **Backend, Docker:** router test asserting `needs_review_count` in the summary and that
  `GET /subscriptions?needs_review=true` returns only flagged rows.
- **Frontend:** `subscription-helpers` tests for `reviewReasonLabel` + `reviewReasonDetail`
  (lapsed, long_running, none); one `Subscriptions.tsx` render test asserting the
  "Needs review" tile and a per-row reason badge appear for a flagged row.

## Files touched

**Backend**
- `api/commercial/subscriptions/services/subscription_review.py` (new — `evaluate_review`,
  `ReviewInfo`, `to_response`, constants).
- `api/commercial/subscriptions/services/__init__.py` (export new helpers).
- `api/commercial/subscriptions/schemas/subscription.py` (3 fields on `SubscriptionResponse`,
  `needs_review_count` on `SubscriptionSummary`).
- `api/commercial/subscriptions/router.py` (use `to_response`; `needs_review` query param;
  `_build_summary` computes count + honors filter + `today`).
- `api/tests/commercial/subscriptions/test_subscription_review.py` (new — pure tests).
- `api/tests/commercial/subscriptions/test_review_endpoints.py` (new — Docker router tests).

**Frontend**
- `ui/src/lib/api/subscriptions.ts` (types + `needsReview` param).
- `ui/src/components/subscriptions/subscription-helpers.ts` (`reviewReasonLabel`,
  `reviewReasonDetail`).
- `ui/src/pages/Subscriptions.tsx` (tile, filter option, row badge).
- `ui/src/pages/SubscriptionDetail.tsx` (needs-review alert card).
- `ui/src/components/dashboard/SubscriptionsWidget.tsx` ("N to review" line).
- `ui/src/components/subscriptions/__tests__/subscription-helpers.test.ts` (extend).
- `ui/src/pages/__tests__/Subscriptions.review.test.tsx` (new — render test).

## Risks

- **Low data volume:** lapsed/long-running only appear once a tenant has ≥6 months of bank
  statement history with detected subscriptions. Correct regardless, but visible impact scales
  with data age.
- **Lapsed false-positives from import gaps:** if a tenant simply stopped *uploading*
  statements, every active sub looks lapsed. Acceptable — the flag is advisory ("did you
  cancel this?"), the user confirms, and dismiss/mark-canceled actions already exist. Worth a
  note in the UI copy ("we haven't seen a charge since …") so the cause is clear.
- **Derived-not-stored:** `needs_review` filtering happens in Python after the SQL query, so it
  doesn't reduce the DB scan. Fine at expected row counts (tens of subs per tenant).
