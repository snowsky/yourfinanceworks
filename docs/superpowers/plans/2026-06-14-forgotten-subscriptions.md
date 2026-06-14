# Forgotten / Needs-Review Subscriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a derived "needs review" treatment to the existing subscription-detection feature that flags `active` subscriptions whose charges have lapsed ("possibly canceled") or that have run ≥6 months ("long-running"), surfaced on the Subscriptions list, detail page, and dashboard widget.

**Architecture:** Pure derive-on-read. A new pure module computes a `ReviewInfo` from dates already stored on `DetectedSubscription` (no new columns, no migration, no scheduler). The router attaches three derived fields to every `SubscriptionResponse` and a `needs_review_count` to the summary. The frontend adds a tile, a filter option, a per-row badge, a detail alert card, and a dashboard line.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2 (backend), React + TypeScript + Vite + TanStack Query + Vitest/RTL (frontend). Backend tests via Docker (`docker compose exec -T api …`); the new pure tests need no DB. Frontend via `docker compose exec -T ui npx vitest run …`.

**Spec:** `docs/superpowers/specs/2026-06-14-forgotten-subscriptions-design.md`

**Reference facts (verified against current code):**
- `DetectedSubscription` fields used: `status` (str, `"active"` = `SubscriptionStatus.ACTIVE.value`), `next_expected_date` (date|None), `cadence_days` (int), `first_seen_date` (date). Model: `api/commercial/subscriptions/models/detected_subscription.py`.
- `SubscriptionResponse` uses `ConfigDict(from_attributes=True)`; Pydantic v2 falls back to field defaults when an attribute is absent, so adding optional fields is safe with `model_validate(orm_row)`.
- Router currently builds items with `SubscriptionResponse.model_validate(r)` in `_build_summary` and at 4 single-row endpoints. `_build_summary(rows)` computes `monthly_cost`/`annual_cost`/`next_charge_date` over `status == active` rows.
- Frontend test helper `ui/src/test/test-utils.tsx` exports `render` (= `renderWithProviders`) which mocks `FeatureContext` (`isFeatureEnabled → true`) and `react-i18next` (`t(key, {defaultValue}) → defaultValue`), and wraps in `QueryClientProvider` + `BrowserRouter`.

---

## Task 1: Backend — `evaluate_review` pure function

**Files:**
- Create: `api/commercial/subscriptions/services/subscription_review.py`
- Test: `api/tests/commercial/subscriptions/test_subscription_review.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/commercial/subscriptions/test_subscription_review.py`:

```python
"""Unit tests for subscription needs-review derivation.

Pure tests: ``evaluate_review`` reads attributes duck-typed, so we use
``SimpleNamespace`` stand-ins and never touch the database (no db_session
fixture needed).
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from commercial.subscriptions.services.subscription_review import (
    LONG_RUNNING_MIN_DAYS,
    ReviewInfo,
    evaluate_review,
)

TODAY = date(2026, 6, 14)


def _sub(**over):
    base = dict(
        status="active",
        cadence_days=30,
        next_expected_date=TODAY,           # on-time by default
        first_seen_date=TODAY - timedelta(days=30),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_on_time_active_sub_has_no_reason():
    assert evaluate_review(_sub(), today=TODAY) == ReviewInfo()


def test_lapsed_just_within_grace_is_not_flagged():
    # monthly cadence -> grace = max(7, round(0.5*30)) = 15 days
    sub = _sub(next_expected_date=TODAY - timedelta(days=15))
    assert evaluate_review(sub, today=TODAY).reason is None


def test_lapsed_past_grace_is_flagged_with_days_overdue():
    sub = _sub(next_expected_date=TODAY - timedelta(days=16))
    info = evaluate_review(sub, today=TODAY)
    assert info.reason == "lapsed"
    assert info.days_overdue == 16


def test_long_running_below_threshold_is_not_flagged():
    sub = _sub(
        next_expected_date=TODAY,
        first_seen_date=TODAY - timedelta(days=LONG_RUNNING_MIN_DAYS - 1),
    )
    assert evaluate_review(sub, today=TODAY).reason is None


def test_long_running_at_threshold_is_flagged_with_months():
    sub = _sub(
        next_expected_date=TODAY,
        first_seen_date=TODAY - timedelta(days=LONG_RUNNING_MIN_DAYS),
    )
    info = evaluate_review(sub, today=TODAY)
    assert info.reason == "long_running"
    assert info.months_running == LONG_RUNNING_MIN_DAYS // 30  # 6


def test_lapsed_takes_precedence_over_long_running():
    sub = _sub(
        next_expected_date=TODAY - timedelta(days=60),       # very overdue
        first_seen_date=TODAY - timedelta(days=400),         # also old
    )
    assert evaluate_review(sub, today=TODAY).reason == "lapsed"


def test_non_active_status_is_never_flagged():
    sub = _sub(
        status="dismissed",
        next_expected_date=TODAY - timedelta(days=90),
        first_seen_date=TODAY - timedelta(days=400),
    )
    assert evaluate_review(sub, today=TODAY) == ReviewInfo()


def test_missing_next_expected_date_can_still_be_long_running():
    sub = _sub(
        next_expected_date=None,
        first_seen_date=TODAY - timedelta(days=400),
    )
    assert evaluate_review(sub, today=TODAY).reason == "long_running"


def test_zero_cadence_falls_back_to_min_grace_without_crashing():
    sub = _sub(cadence_days=0, next_expected_date=TODAY - timedelta(days=8))
    # grace falls back to 7 -> 8 > 7 -> lapsed
    assert evaluate_review(sub, today=TODAY).reason == "lapsed"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/commercial/subscriptions/test_subscription_review.py -v"`
Expected: FAIL — `ModuleNotFoundError: No module named 'commercial.subscriptions.services.subscription_review'`.

- [ ] **Step 3: Write the minimal implementation**

Create `api/commercial/subscriptions/services/subscription_review.py`:

```python
"""Derive a 'needs review' reason for a detected subscription.

Pure, deterministic helpers. ``evaluate_review`` reads only attributes that
already exist on ``DetectedSubscription`` (status, next_expected_date,
cadence_days, first_seen_date), so it can be unit-tested against lightweight
stand-ins without a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

# "active" status string. Kept as a literal to keep this module import-light
# and DB-free; it mirrors ``SubscriptionStatus.ACTIVE.value``.
ACTIVE_STATUS = "active"

LONG_RUNNING_MIN_DAYS = 180
LAPSED_MIN_GRACE_DAYS = 7
LAPSED_GRACE_CADENCE_FRACTION = 0.5


@dataclass(frozen=True)
class ReviewInfo:
    reason: Optional[str] = None            # "lapsed" | "long_running" | None
    days_overdue: Optional[int] = None
    months_running: Optional[int] = None


def _lapsed_grace_days(cadence_days: int) -> int:
    if cadence_days and cadence_days > 0:
        return max(
            LAPSED_MIN_GRACE_DAYS,
            round(LAPSED_GRACE_CADENCE_FRACTION * cadence_days),
        )
    return LAPSED_MIN_GRACE_DAYS


def evaluate_review(sub, *, today: date) -> ReviewInfo:
    """Return the needs-review reason for ``sub`` as of ``today``.

    Only ``active`` subscriptions are eligible. ``lapsed`` (charges stopped)
    takes precedence over ``long_running`` (still charging but old). At most
    one reason is returned.
    """
    if sub.status != ACTIVE_STATUS:
        return ReviewInfo()

    next_expected = sub.next_expected_date
    if next_expected is not None:
        grace = _lapsed_grace_days(sub.cadence_days)
        days_overdue = (today - next_expected).days
        if days_overdue > grace:
            return ReviewInfo(reason="lapsed", days_overdue=days_overdue)

    first_seen = sub.first_seen_date
    if first_seen is not None:
        age_days = (today - first_seen).days
        if age_days >= LONG_RUNNING_MIN_DAYS:
            return ReviewInfo(
                reason="long_running", months_running=age_days // 30
            )

    return ReviewInfo()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/commercial/subscriptions/test_subscription_review.py -v"`
Expected: PASS (9 passed). If `pytest` is missing, first run:
`docker compose exec -T api pip install --no-cache-dir 'pytest==9.0.3' 'pytest-asyncio==1.3.0' 'pytest-mock==3.14.1' 'pytest-cov==6.2.1'`

- [ ] **Step 5: Commit**

```bash
git add api/commercial/subscriptions/services/subscription_review.py \
        api/tests/commercial/subscriptions/test_subscription_review.py
git commit -m "feat(subscriptions): evaluate_review needs-review derivation"
```

---

## Task 2: Backend — response fields, `to_response`, `build_summary`

**Files:**
- Modify: `api/commercial/subscriptions/schemas/subscription.py`
- Modify: `api/commercial/subscriptions/services/subscription_review.py`
- Test: `api/tests/commercial/subscriptions/test_subscription_review.py` (extend)

- [ ] **Step 1: Write the failing tests (extend the test file)**

Append to `api/tests/commercial/subscriptions/test_subscription_review.py`:

```python
from commercial.subscriptions.services.subscription_review import (
    build_summary,
    to_response,
)

# Full attribute set required by SubscriptionResponse.model_validate.
def _row(**over):
    base = dict(
        id=1,
        merchant_key="netflix",
        label="Netflix",
        category=None,
        amount=15.99,
        last_amount=15.99,
        currency="USD",
        cadence_days=30,
        confidence=0.9,
        first_seen_date=TODAY - timedelta(days=400),
        last_seen_date=TODAY,
        next_expected_date=TODAY,
        charge_count=12,
        status="active",
        cancel_reminder_at=None,
        price_change_acknowledged=False,
        source_transaction_ids=None,
        notes=None,
        dismissed_at=None,
        created_at=date(2025, 1, 1),
        updated_at=date(2025, 1, 1),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_to_response_attaches_review_fields():
    row = _row(first_seen_date=TODAY - timedelta(days=400))
    resp = to_response(row, today=TODAY)
    assert resp.review_reason == "long_running"
    assert resp.months_running == 400 // 30


def test_to_response_leaves_review_none_when_healthy():
    row = _row(first_seen_date=TODAY - timedelta(days=30))
    resp = to_response(row, today=TODAY)
    assert resp.review_reason is None
    assert resp.days_overdue is None
    assert resp.months_running is None


def test_build_summary_counts_needs_review():
    rows = [
        _row(id=1, first_seen_date=TODAY - timedelta(days=400)),   # long_running
        _row(id=2, next_expected_date=TODAY - timedelta(days=60)), # lapsed
        _row(id=3, first_seen_date=TODAY - timedelta(days=10)),    # healthy
    ]
    summary = build_summary(rows, today=TODAY)
    assert summary.needs_review_count == 2
    assert summary.total_count == 3


def test_build_summary_needs_review_filter_returns_only_flagged():
    rows = [
        _row(id=1, first_seen_date=TODAY - timedelta(days=400)),   # flagged
        _row(id=3, first_seen_date=TODAY - timedelta(days=10)),    # healthy
    ]
    summary = build_summary(rows, needs_review=True, today=TODAY)
    assert [i.id for i in summary.items] == [1]
    # count is computed before filtering, so it still reflects flagged rows
    assert summary.needs_review_count == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/commercial/subscriptions/test_subscription_review.py -v"`
Expected: FAIL — `ImportError: cannot import name 'build_summary'` (and `to_response`).

- [ ] **Step 3a: Add the schema fields**

In `api/commercial/subscriptions/schemas/subscription.py`, update the imports line and `SubscriptionResponse` / `SubscriptionSummary`.

Change the top `typing` import to include `Literal` (already present) — no change needed there. Add the three fields to `SubscriptionResponse` (after `updated_at`, before the `annual_cost` property):

```python
    created_at: datetime
    updated_at: datetime

    # Derived needs-review fields (attached by to_response; default None).
    review_reason: Optional[Literal["lapsed", "long_running"]] = None
    days_overdue: Optional[int] = None
    months_running: Optional[int] = None

    @property
    def annual_cost(self) -> float:
```

Add `needs_review_count` to `SubscriptionSummary`:

```python
class SubscriptionSummary(BaseModel):
    total_count: int
    active_count: int
    monthly_cost: float = Field(
        ..., description="Sum of amount * (30 / cadence_days) across active rows"
    )
    annual_cost: float = Field(
        ..., description="Sum of amount * (365 / cadence_days) across active rows"
    )
    next_charge_date: Optional[date] = None
    needs_review_count: int = 0
    items: List[SubscriptionResponse]
```

- [ ] **Step 3b: Add `to_response` and `build_summary` to the review module**

Append to `api/commercial/subscriptions/services/subscription_review.py`:

```python
from typing import List, Optional  # extend the existing typing import

from commercial.subscriptions.schemas import (
    SubscriptionResponse,
    SubscriptionSummary,
)


def to_response(sub, *, today: Optional[date] = None) -> SubscriptionResponse:
    """Build a SubscriptionResponse and attach derived review fields."""
    if today is None:
        today = date.today()
    resp = SubscriptionResponse.model_validate(sub)
    info = evaluate_review(sub, today=today)
    resp.review_reason = info.reason
    resp.days_overdue = info.days_overdue
    resp.months_running = info.months_running
    return resp


def build_summary(
    rows: List,
    *,
    needs_review: bool = False,
    today: Optional[date] = None,
) -> SubscriptionSummary:
    """Assemble the list summary. ``needs_review_count`` is computed over the
    full row set; when ``needs_review`` is set the returned ``items`` are
    filtered to flagged rows only (totals stay over the full set)."""
    if today is None:
        today = date.today()

    items = [to_response(r, today=today) for r in rows]
    active = [r for r in rows if r.status == ACTIVE_STATUS]
    monthly = sum(
        r.amount * (30.0 / r.cadence_days) for r in active if r.cadence_days
    )
    annual = sum(
        r.amount * (365.0 / r.cadence_days) for r in active if r.cadence_days
    )
    upcoming = [r.next_expected_date for r in active if r.next_expected_date]
    next_charge = min(upcoming) if upcoming else None
    needs_review_count = sum(1 for i in items if i.review_reason is not None)

    if needs_review:
        items = [i for i in items if i.review_reason is not None]

    return SubscriptionSummary(
        total_count=len(rows),
        active_count=len(active),
        monthly_cost=round(monthly, 2),
        annual_cost=round(annual, 2),
        next_charge_date=next_charge,
        needs_review_count=needs_review_count,
        items=items,
    )
```

> Note: keep the module's existing `from __future__ import annotations` at the very top. Place the two new imports (`from typing import ...` extension and the schemas import) with the other imports near the top rather than mid-file if your linter requires it; functionally either works because they resolve before first call.

- [ ] **Step 4: Run to verify it passes**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/commercial/subscriptions/test_subscription_review.py -v"`
Expected: PASS (13 passed).

- [ ] **Step 5: Commit**

```bash
git add api/commercial/subscriptions/schemas/subscription.py \
        api/commercial/subscriptions/services/subscription_review.py \
        api/tests/commercial/subscriptions/test_subscription_review.py
git commit -m "feat(subscriptions): to_response + build_summary with needs-review fields"
```

---

## Task 3: Backend — wire the router and service exports

**Files:**
- Modify: `api/commercial/subscriptions/services/__init__.py`
- Modify: `api/commercial/subscriptions/router.py`

- [ ] **Step 1: Export the new helpers**

In `api/commercial/subscriptions/services/__init__.py`, add an import block and extend `__all__`:

```python
from commercial.subscriptions.services.subscription_review import (
    build_summary,
    evaluate_review,
    to_response,
)
```

and add `"build_summary"`, `"evaluate_review"`, `"to_response"` to `__all__`.

- [ ] **Step 2: Use `to_response` and `build_summary` in the router**

In `api/commercial/subscriptions/router.py`:

(a) Extend the services import:

```python
from commercial.subscriptions.services import (
    acknowledge_price_change,
    build_summary,
    get_subscription,
    list_subscriptions,
    scan_tenant,
    set_cancel_reminder,
    to_response,
    update_status,
)
```

(b) Add `needs_review` to the list endpoint and delegate to `build_summary`:

```python
@router.get("", response_model=SubscriptionSummary)
@require_feature("subscription_detection")
async def list_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    include_low_confidence: bool = Query(False),
    needs_review: bool = Query(False),
    tenant_db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user),
) -> SubscriptionSummary:
    rows = list_subscriptions(
        tenant_db,
        status=status_filter,
        include_low_confidence=include_low_confidence,
    )
    return build_summary(rows, needs_review=needs_review)
```

(c) Replace the four single-row `SubscriptionResponse.model_validate(...)` returns with `to_response(...)`:
- `get_endpoint`: `return to_response(sub)`
- `update_status_endpoint`: `return to_response(updated)`
- `cancel_reminder_endpoint`: `return to_response(updated)`
- `acknowledge_endpoint`: `return to_response(updated)`

(d) Delete the now-unused `_build_summary` helper function (lines defining `def _build_summary(...)`), since `build_summary` from the service replaces it. Leave `_charge_history` untouched.

- [ ] **Step 3: Verify the app imports cleanly and tests still pass**

Run: `docker compose exec -T api bash -c "cd /app && python -c 'import commercial.subscriptions.router' && python -m pytest tests/commercial/subscriptions -v"`
Expected: import prints nothing (success) and all subscription tests pass (existing detector tests + 13 review tests).

- [ ] **Step 4: Manual endpoint smoke (optional but recommended)**

Run: `docker compose exec -T api bash -c "cd /app && python -c \"from commercial.subscriptions.router import router; print([ (r.path, sorted(r.methods)) for r in router.routes ])\""`
Expected: lists routes including `('/subscriptions', ['GET'])`. Confirms the router object is intact after edits.

- [ ] **Step 5: Commit**

```bash
git add api/commercial/subscriptions/services/__init__.py \
        api/commercial/subscriptions/router.py
git commit -m "feat(subscriptions): expose needs_review on list + per-row responses"
```

---

## Task 4: Frontend — API types and review helpers

**Files:**
- Modify: `ui/src/lib/api/subscriptions.ts`
- Modify: `ui/src/components/subscriptions/subscription-helpers.ts`
- Test: `ui/src/components/subscriptions/__tests__/subscription-helpers.test.ts` (extend)

- [ ] **Step 1: Write the failing helper tests (extend the test file)**

Append to `ui/src/components/subscriptions/__tests__/subscription-helpers.test.ts` (mirror the existing fixture style in that file; if it has a `makeSub`/base-object helper, reuse it — otherwise inline the object):

```ts
import {
  reviewReasonLabel,
  reviewReasonDetail,
} from '../subscription-helpers';
import type { SubscriptionResponse } from '@/lib/api/subscriptions';

const baseSub: SubscriptionResponse = {
  id: 1,
  merchant_key: 'netflix',
  label: 'Netflix',
  amount: 15.99,
  currency: 'USD',
  cadence_days: 30,
  confidence: 0.9,
  first_seen_date: '2025-01-01',
  last_seen_date: '2026-06-01',
  charge_count: 12,
  status: 'active',
  price_change_acknowledged: false,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
};

describe('reviewReasonLabel', () => {
  it('labels lapsed and long_running, null otherwise', () => {
    expect(reviewReasonLabel({ ...baseSub, review_reason: 'lapsed' })).toBe(
      'Possibly canceled',
    );
    expect(
      reviewReasonLabel({ ...baseSub, review_reason: 'long_running' }),
    ).toBe('Long-running');
    expect(reviewReasonLabel(baseSub)).toBeNull();
  });
});

describe('reviewReasonDetail', () => {
  it('describes lapsed with days overdue', () => {
    expect(
      reviewReasonDetail({
        ...baseSub,
        review_reason: 'lapsed',
        days_overdue: 1,
      }),
    ).toBe('1 day overdue');
    expect(
      reviewReasonDetail({
        ...baseSub,
        review_reason: 'lapsed',
        days_overdue: 16,
      }),
    ).toBe('16 days overdue');
  });

  it('describes long_running with months and approx spend', () => {
    const detail = reviewReasonDetail({
      ...baseSub,
      review_reason: 'long_running',
      months_running: 6,
    });
    // monthlyCost = 15.99 * (30/30) = 15.99; spend ~= 95.94
    expect(detail).toContain('Running 6 mo');
    expect(detail).toContain('paid');
  });

  it('returns null when not flagged', () => {
    expect(reviewReasonDetail(baseSub)).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T ui npx vitest run src/components/subscriptions/__tests__/subscription-helpers.test.ts`
Expected: FAIL — `reviewReasonLabel`/`reviewReasonDetail` are not exported, plus TS errors that `review_reason` doesn't exist on `SubscriptionResponse`.

- [ ] **Step 3a: Add the API types and `needsReview` param**

In `ui/src/lib/api/subscriptions.ts`, add three fields to `SubscriptionResponse` (after `updated_at`):

```ts
  created_at: string;
  updated_at: string;
  review_reason?: 'lapsed' | 'long_running' | null;
  days_overdue?: number | null;
  months_running?: number | null;
}
```

Add `needs_review_count` to `SubscriptionSummary`:

```ts
export interface SubscriptionSummary {
  total_count: number;
  active_count: number;
  monthly_cost: number;
  annual_cost: number;
  next_charge_date?: string | null;
  needs_review_count: number;
  items: SubscriptionResponse[];
}
```

Extend the `list` params and query string:

```ts
  list: (
    params: {
      status?: SubscriptionStatus;
      includeLowConfidence?: boolean;
      needsReview?: boolean;
    } = {},
  ) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set('status', params.status);
    if (params.includeLowConfidence) qs.set('include_low_confidence', 'true');
    if (params.needsReview) qs.set('needs_review', 'true');
    const tail = qs.toString();
    return apiRequest<SubscriptionSummary>(`/subscriptions${tail ? `?${tail}` : ''}`);
  },
```

- [ ] **Step 3b: Add the helpers**

Append to `ui/src/components/subscriptions/subscription-helpers.ts`:

```ts
export const reviewReasonLabel = (sub: SubscriptionResponse): string | null => {
  if (sub.review_reason === 'lapsed') return 'Possibly canceled';
  if (sub.review_reason === 'long_running') return 'Long-running';
  return null;
};

export const reviewReasonDetail = (sub: SubscriptionResponse): string | null => {
  if (sub.review_reason === 'lapsed') {
    const days = sub.days_overdue ?? 0;
    return `${days} day${days === 1 ? '' : 's'} overdue`;
  }
  if (sub.review_reason === 'long_running') {
    const months = sub.months_running ?? 0;
    const spend = monthlyCost(sub) * months;
    return `Running ${months} mo · ~${formatCurrency(spend, sub.currency)} paid`;
  }
  return null;
};
```

- [ ] **Step 4: Run to verify it passes**

Run: `docker compose exec -T ui npx vitest run src/components/subscriptions/__tests__/subscription-helpers.test.ts`
Expected: PASS (all helper tests, old + new).

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/api/subscriptions.ts \
        ui/src/components/subscriptions/subscription-helpers.ts \
        ui/src/components/subscriptions/__tests__/subscription-helpers.test.ts
git commit -m "feat(subscriptions): review_reason API types + label/detail helpers"
```

---

## Task 5: Frontend — Subscriptions list (tile, filter, row badge)

**Files:**
- Modify: `ui/src/pages/Subscriptions.tsx`
- Test: `ui/src/pages/__tests__/Subscriptions.review.test.tsx` (create)

- [ ] **Step 1: Write the failing render test**

Create `ui/src/pages/__tests__/Subscriptions.review.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import type { SubscriptionSummary } from '@/lib/api/subscriptions';

const listMock = vi.fn();
vi.mock('@/lib/api/subscriptions', () => ({
  subscriptionsApi: {
    list: (...args: unknown[]) => listMock(...args),
    scan: vi.fn(),
    updateStatus: vi.fn(),
    setCancelReminder: vi.fn(),
    acknowledgePriceChange: vi.fn(),
  },
}));

import SubscriptionsPage from '../Subscriptions';

const summary: SubscriptionSummary = {
  total_count: 1,
  active_count: 1,
  monthly_cost: 15.99,
  annual_cost: 191.88,
  next_charge_date: null,
  needs_review_count: 1,
  items: [
    {
      id: 1,
      merchant_key: 'netflix',
      label: 'Netflix',
      amount: 15.99,
      currency: 'USD',
      cadence_days: 30,
      confidence: 0.9,
      first_seen_date: '2025-01-01',
      last_seen_date: '2026-04-01',
      next_expected_date: '2026-05-01',
      charge_count: 12,
      status: 'active',
      price_change_acknowledged: false,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
      review_reason: 'lapsed',
      days_overdue: 44,
    },
  ],
};

beforeEach(() => {
  listMock.mockReset();
  listMock.mockResolvedValue(summary);
});

describe('Subscriptions needs-review surfacing', () => {
  it('shows the Needs review tile and a per-row reason badge', async () => {
    render(<SubscriptionsPage />);
    expect(await screen.findByText('Needs review')).toBeInTheDocument();
    expect(await screen.findByText('Possibly canceled')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T ui npx vitest run src/pages/__tests__/Subscriptions.review.test.tsx`
Expected: FAIL — neither "Needs review" nor "Possibly canceled" is rendered yet.

- [ ] **Step 3a: Update imports in `Subscriptions.tsx`**

Add `AlertTriangle` to the lucide import block:

```ts
import {
  AlertTriangle,
  Calendar,
  DollarSign,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
```

Add the review helpers to the existing helpers import:

```ts
import {
  annualizedCost,
  cadenceLabel,
  formatCurrency,
  hasUnacknowledgedPriceChange,
  priceChangePercent,
  reviewReasonDetail,
  reviewReasonLabel,
} from '@/components/subscriptions/subscription-helpers';
```

- [ ] **Step 3b: Extend the status-filter type and query**

Change the state type:

```ts
  const [statusFilter, setStatusFilter] = useState<
    SubscriptionStatus | 'all' | 'needs_review'
  >('active');
```

Change the query function to branch on `needs_review`:

```ts
  const summaryQuery = useQuery({
    queryKey: ['subscriptions', statusFilter],
    queryFn: () =>
      subscriptionsApi.list(
        statusFilter === 'needs_review'
          ? { needsReview: true }
          : { status: statusFilter === 'all' ? undefined : statusFilter },
      ),
  });
```

Update the `onValueChange` cast on the status `Select`:

```ts
                onValueChange={(v) =>
                  setStatusFilter(v as SubscriptionStatus | 'all' | 'needs_review')
                }
```

- [ ] **Step 3c: Add the "Needs review" tile**

Change the metrics grid to 5 columns and add the tile after "Next charge":

```tsx
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
          <MetricCard
            title="Active"
            value={String(summaryQuery.data?.active_count ?? 0)}
            icon={Calendar}
          />
          <MetricCard
            title="Monthly cost"
            value={formatCurrency(summaryQuery.data?.monthly_cost ?? 0)}
            icon={DollarSign}
          />
          <MetricCard
            title="Annual cost"
            value={formatCurrency(summaryQuery.data?.annual_cost ?? 0)}
            icon={DollarSign}
          />
          <MetricCard
            title="Next charge"
            value={summaryQuery.data?.next_charge_date ?? '—'}
            icon={TrendingUp}
          />
          <MetricCard
            title="Needs review"
            value={String(summaryQuery.data?.needs_review_count ?? 0)}
            icon={AlertTriangle}
          />
        </div>
```

- [ ] **Step 3d: Add the filter option**

Add a `SelectItem` inside the status `SelectContent` (after "Active"):

```tsx
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="needs_review">Needs review</SelectItem>
                  <SelectItem value="dismissed">Dismissed</SelectItem>
                  <SelectItem value="canceled_by_user">Canceled</SelectItem>
                  <SelectItem value="all">All (incl. archive)</SelectItem>
```

- [ ] **Step 3e: Add the per-row reason badge**

In the Merchant `TableCell`, after the category block, add the badge:

```tsx
                        <TableCell>
                          <div className="font-medium">{sub.label}</div>
                          {sub.category ? (
                            <div className="text-xs text-muted-foreground">
                              {sub.category}
                            </div>
                          ) : null}
                          {reviewReasonLabel(sub) ? (
                            <Badge
                              className="mt-1 bg-amber-500/10 text-amber-600"
                              title={reviewReasonDetail(sub) ?? undefined}
                            >
                              <AlertTriangle className="mr-1 h-3 w-3" />
                              {reviewReasonLabel(sub)}
                            </Badge>
                          ) : null}
                        </TableCell>
```

- [ ] **Step 4: Run to verify it passes**

Run: `docker compose exec -T ui npx vitest run src/pages/__tests__/Subscriptions.review.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/pages/Subscriptions.tsx \
        ui/src/pages/__tests__/Subscriptions.review.test.tsx
git commit -m "feat(subscriptions): needs-review tile, filter, and row badge"
```

---

## Task 6: Frontend — detail alert card and dashboard line

**Files:**
- Modify: `ui/src/pages/SubscriptionDetail.tsx`
- Modify: `ui/src/components/dashboard/SubscriptionsWidget.tsx`

- [ ] **Step 1: Add the needs-review alert card to the detail page**

In `ui/src/pages/SubscriptionDetail.tsx`:

(a) Add `AlertTriangle` to the lucide import:

```ts
import { AlertTriangle, ArrowLeft, Bell, TrendingDown, TrendingUp } from 'lucide-react';
```

(b) Add the review helpers to the helpers import:

```ts
import {
  annualizedCost,
  cadenceLabel,
  formatCurrency,
  hasUnacknowledgedPriceChange,
  monthlyCost,
  priceChangePercent,
  reviewReasonDetail,
  reviewReasonLabel,
} from '@/components/subscriptions/subscription-helpers';
```

(c) Insert a review alert card immediately AFTER the price-alert block (after the `) : null}` that closes `showPriceAlert`, before the `{sub ? (` metrics grid):

```tsx
        {sub && reviewReasonLabel(sub) ? (
          <ProfessionalCard className="border-amber-500/30 bg-amber-500/10">
            <ProfessionalCardContent className="flex items-center gap-3 py-3">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <div>
                <div className="text-sm font-medium">
                  {reviewReasonLabel(sub)}
                </div>
                <div className="text-xs text-muted-foreground">
                  {sub.review_reason === 'lapsed'
                    ? `We haven't seen a charge as expected — ${reviewReasonDetail(
                        sub,
                      )}. If you canceled it, mark it below.`
                    : `${reviewReasonDetail(sub)}. Still need it?`}
                </div>
              </div>
            </ProfessionalCardContent>
          </ProfessionalCard>
        ) : null}
```

- [ ] **Step 2: Verify the detail page type-checks**

Run: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit`
Expected: no errors related to `SubscriptionDetail.tsx`.

- [ ] **Step 3: Add the "N to review" line to the dashboard widget**

In `ui/src/components/dashboard/SubscriptionsWidget.tsx`:

(a) Add `AlertTriangle` to the lucide import:

```ts
import { AlertTriangle, ArrowRight, Repeat, TrendingUp } from 'lucide-react';
```

(b) Compute the count near `priceChanges`:

```ts
  const priceChanges =
    data?.items.filter(hasUnacknowledgedPriceChange).length ?? 0;
  const needsReview = data?.needs_review_count ?? 0;
  const next = data?.next_charge_date;
```

(c) Add a badge in the badges row, after the price-changes badge:

```tsx
              {priceChanges > 0 ? (
                <Badge className="bg-destructive/10 text-destructive">
                  <TrendingUp className="mr-1 h-3 w-3" />
                  {priceChanges} price change{priceChanges === 1 ? '' : 's'}
                </Badge>
              ) : null}
              {needsReview > 0 ? (
                <Badge className="bg-amber-500/10 text-amber-600">
                  <AlertTriangle className="mr-1 h-3 w-3" />
                  {needsReview} to review
                </Badge>
              ) : null}
```

- [ ] **Step 4: Type-check again**

Run: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add ui/src/pages/SubscriptionDetail.tsx \
        ui/src/components/dashboard/SubscriptionsWidget.tsx
git commit -m "feat(subscriptions): needs-review alert card + dashboard badge"
```

---

## Task 7: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Backend — full subscriptions suite**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/commercial/subscriptions -v"`
Expected: all pass (existing detector tests + 13 review tests).

- [ ] **Step 2: Frontend — subscriptions tests + typecheck**

Run: `docker compose exec -T ui npx vitest run src/components/subscriptions src/pages/__tests__/Subscriptions.review.test.tsx`
Expected: all pass.

Run: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit`
Expected: clean (ignore pre-existing unrelated errors if any; none should reference the files in this plan).

- [ ] **Step 3: Manual sanity (optional)**

With the stack up and a tenant that has detected subscriptions, hit `GET /api/v1/subscriptions?needs_review=true` and confirm only flagged rows return and the summary carries `needs_review_count`.

- [ ] **Step 4: No commit needed** (verification only). If anything failed, return to the relevant task.

---

## Self-Review notes (already reconciled)

- **Spec coverage:** detection rules → Task 1; response fields + summary count + filter → Tasks 2–3; API types + helpers → Task 4; list tile/filter/badge → Task 5; detail card + dashboard line → Task 6; tests → Tasks 1,2,4,5 + Task 7. i18n inline pattern honored (no en.json keys added). Out-of-scope items (notifications, draft email, money threshold, migration) intentionally absent.
- **Type consistency:** `evaluate_review(sub, *, today)` → `ReviewInfo(reason, days_overdue, months_running)`; `to_response(sub, *, today)`; `build_summary(rows, *, needs_review, today)`. Frontend `review_reason`/`days_overdue`/`months_running` on `SubscriptionResponse`, `needs_review_count` on `SubscriptionSummary`, `reviewReasonLabel`/`reviewReasonDetail` helpers, `needsReview` list param — all consistent across tasks.
- **No placeholders:** every code step shows full code and an exact command with expected output.
