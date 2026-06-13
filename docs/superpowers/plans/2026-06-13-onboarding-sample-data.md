# Onboarding Sample-Data Seeding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a brand-new tenant one-click load a small, status-diverse set of sample clients/invoices/expenses (marked `is_sample`, removable in one click) so the first session shows populated dashboards instead of blank empty states.

**Architecture:** A `SampleDataService` (seed/clear/status) operates on a tenant DB session; rows carry an `is_sample` flag (Client/Invoice/Expense). A small `onboarding` router exposes GET/POST/DELETE. A Dashboard banner (`Index.tsx`) loads or removes sample data based on status. No signup-flow, AI, or checklist work (separate slices).

**Tech Stack:** FastAPI + SQLAlchemy (per-tenant DBs), pytest (`db_session` fixture), React/TS + Vitest.

**Spec:** `docs/superpowers/specs/2026-06-13-onboarding-sample-data-design.md`
**Branch:** `feat/onboarding-sample-data` (exists, spec committed). Do NOT create branches.

**Reality notes (verified):** the `/dashboard` route renders `ui/src/pages/Index.tsx` (not `Dashboard.tsx`). `Client` has **no `is_deleted`** column (no soft-delete) — client queries must NOT filter `is_deleted`. `Invoice.subtotal` is NOT NULL with no default — the seeder must set it. `require_non_viewer(user)` is in `core/utils/rbac.py` (a function that raises, called as `require_non_viewer(current_user)`).

**Test invocation:** backend `docker compose exec api bash -c "cd /app && python -m pytest <path> -v"` (bare `docker compose exec api pytest` fails: `No module named 'core'`). UI: `cd ui && npx vitest run <path>` + `npx tsc --noEmit -p tsconfig.app.json`. Stack is up. Run touched test files individually.

---

## File structure

**Backend**
- `api/core/models/models_per_tenant.py` *(modify)* — `is_sample` on Client/Invoice/Expense.
- `api/db_init.py` *(modify)* — ALTER each of the 3 tables for existing tenant DBs.
- `api/core/services/sample_data.py` *(new)* — `SampleDataService`, `SampleDataError`.
- `api/core/routers/onboarding.py` *(new)* — GET/POST/DELETE.
- `api/main.py` *(modify)* — register the router.
- `api/tests/test_sample_data.py` *(new)*.

**Frontend**
- `ui/src/lib/api/onboarding.ts` *(new)* — 3 client methods.
- `ui/src/components/onboarding/SampleDataBanner.tsx` *(new)* + `.test.tsx` *(new)*.
- `ui/src/pages/Index.tsx` *(modify)* — mount the banner.
- `ui/src/i18n/locales/en.json` *(modify)* — `onboarding.*` keys.

---

## Task 1: `is_sample` columns + tenant-DB migration

**Files:**
- Modify: `api/core/models/models_per_tenant.py` (Client ~line 49, Invoice ~line 175, Expense ~line 320)
- Modify: `api/db_init.py` (`ensure_tenant_required_columns`, near the existing invoices/clients ALTER blocks ~line 225-245)

- [ ] **Step 1: Add the model columns**

In `api/core/models/models_per_tenant.py`, add to each of the three models a column (place it next to other booleans, e.g. just after the `is_deleted`/status columns; for `Client` which has no `is_deleted`, add it near `relationship_status`/`stage`):

```python
    is_sample = Column(Boolean, default=False, nullable=False, index=True)
```

Add to `Client`, `Invoice`, and `Expense`. (`Column`, `Boolean` are already imported in this file.)

- [ ] **Step 2: Add the tenant-DB ALTERs**

In `api/db_init.py` `ensure_tenant_required_columns`, after the existing `invoices` column block (the `reminder_last_offset`/`reminder_last_sent_at` loop), add a block that adds `is_sample` to all three tables:

```python
            # Sample-data flag for onboarding (mirrors models_per_tenant).
            for table in ("clients", "invoices", "expenses"):
                if table in inspector.get_table_names():
                    cols = {c["name"] for c in inspector.get_columns(table)}
                    if "is_sample" not in cols:
                        logger.info(f"[tenant {tenant_id}] Adding {table}.is_sample")
                        conn.execute(
                            text(f"ALTER TABLE {table} ADD COLUMN is_sample BOOLEAN NOT NULL DEFAULT FALSE")
                        )
                        conn.commit()
```

- [ ] **Step 3: Verify imports + model loads**

Run: `docker compose exec api bash -c "cd /app && python -c 'from core.models.models_per_tenant import Client, Invoice, Expense; print(Client.is_sample, Invoice.is_sample, Expense.is_sample)'"`
Expected: prints three column objects (no AttributeError), no import error.

- [ ] **Step 4: Commit**

```bash
git add api/core/models/models_per_tenant.py api/db_init.py
git commit -m "feat(onboarding): add is_sample flag to client/invoice/expense"
```

(Commit attribution is disabled repo-wide — no Co-Authored-By.)

---

## Task 2: SampleDataService

**Files:**
- Create: `api/core/services/sample_data.py`
- Test: `api/tests/test_sample_data.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_sample_data.py`:

```python
"""Tests for onboarding sample-data seeding."""

from datetime import datetime, timezone

import pytest

from core.models.models_per_tenant import Client, Expense, Invoice, Payment
from core.services.sample_data import SampleDataError, SampleDataService


def _service(db):
    return SampleDataService(db)


def _real_client(db):
    c = Client(name="Real Co", email="real@example.com", is_sample=False)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_status_empty_tenant(db_session):
    s = _service(db_session).sample_data_status()
    assert s == {"has_sample_data": False, "has_any_data": False}


def test_seed_creates_status_diverse_set(db_session):
    counts = _service(db_session).seed(user_id=None)
    assert counts["clients"] == 3
    assert counts["invoices"] == 6
    assert counts["expenses"] == 4
    assert counts["payments"] == 2

    invoices = db_session.query(Invoice).all()
    assert all(inv.is_sample for inv in invoices)
    assert all(inv.subtotal is not None for inv in invoices)
    statuses = {inv.status for inv in invoices}
    assert {"draft", "sent", "paid", "partially_paid", "overdue"} <= statuses
    assert all(c.is_sample for c in db_session.query(Client).all())
    assert all(e.is_sample for e in db_session.query(Expense).all())


def test_status_after_seed(db_session):
    _service(db_session).seed(user_id=None)
    s = _service(db_session).sample_data_status()
    assert s == {"has_sample_data": True, "has_any_data": True}


def test_seed_refused_when_real_data_exists(db_session):
    _real_client(db_session)
    with pytest.raises(SampleDataError):
        _service(db_session).seed(user_id=None)


def test_seed_refused_when_sample_already_exists(db_session):
    _service(db_session).seed(user_id=None)
    with pytest.raises(SampleDataError):
        _service(db_session).seed(user_id=None)


def test_clear_removes_only_sample(db_session):
    real = _real_client(db_session)
    real_inv = Invoice(
        number="REAL-1", amount=10.0, subtotal=10.0, currency="USD",
        due_date=datetime.now(timezone.utc), status="draft",
        client_id=real.id, is_sample=False,
    )
    db_session.add(real_inv)
    db_session.commit()

    # Seeding is refused because real data exists; force sample rows directly
    # to exercise clear() in isolation.
    sample_client = Client(name="Sample Co", email="s@example.com", is_sample=True)
    db_session.add(sample_client)
    db_session.commit()
    db_session.refresh(sample_client)
    sample_inv = Invoice(
        number="SAMPLE-9", amount=5.0, subtotal=5.0, currency="USD",
        due_date=datetime.now(timezone.utc), status="sent",
        client_id=sample_client.id, is_sample=True,
    )
    db_session.add(sample_inv)
    db_session.commit()
    db_session.refresh(sample_inv)
    db_session.add(Payment(invoice_id=sample_inv.id, amount=5.0, currency="USD",
                           payment_date=datetime.now(timezone.utc), payment_method="card"))
    db_session.commit()

    removed = _service(db_session).clear()
    assert removed["invoices"] == 1
    assert removed["clients"] == 1
    assert removed["payments"] == 1

    # Real data survives.
    assert db_session.query(Client).filter(Client.id == real.id).count() == 1
    assert db_session.query(Invoice).filter(Invoice.id == real_inv.id).count() == 1
    # Sample rows gone.
    assert db_session.query(Invoice).filter(Invoice.is_sample == True).count() == 0  # noqa: E712
    assert db_session.query(Client).filter(Client.is_sample == True).count() == 0  # noqa: E712
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_sample_data.py -v"`
Expected: import error (module missing).

- [ ] **Step 3: Implement the service**

Create `api/core/services/sample_data.py`:

```python
"""Onboarding sample-data seeding.

Seeds a small, status-diverse set of demo clients/invoices/expenses (marked
``is_sample``) so a brand-new tenant's first session shows populated dashboards.
Everything is removable in one call; real data is never touched.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from core.models.models_per_tenant import Client, Expense, Invoice, Payment

logger = logging.getLogger(__name__)


class SampleDataError(Exception):
    """Raised when sample data cannot be seeded (tenant not clean)."""


class SampleDataService:
    def __init__(self, db: Session):
        self.db = db

    # --- queries -----------------------------------------------------------

    def _has_real_data(self) -> bool:
        real_clients = (
            self.db.query(Client).filter(Client.is_sample == False).count()  # noqa: E712
        )
        real_invoices = (
            self.db.query(Invoice)
            .filter(Invoice.is_sample == False, Invoice.is_deleted == False)  # noqa: E712
            .count()
        )
        return bool(real_clients or real_invoices)

    def _has_sample_data(self) -> bool:
        return bool(
            self.db.query(Client).filter(Client.is_sample == True).count()  # noqa: E712
            or self.db.query(Invoice)
            .filter(Invoice.is_sample == True, Invoice.is_deleted == False)  # noqa: E712
            .count()
            or self.db.query(Expense)
            .filter(Expense.is_sample == True, Expense.is_deleted == False)  # noqa: E712
            .count()
        )

    def sample_data_status(self) -> Dict[str, bool]:
        has_any = bool(
            self.db.query(Client).count()
            or self.db.query(Invoice).filter(Invoice.is_deleted == False).count()  # noqa: E712
        )
        return {"has_sample_data": self._has_sample_data(), "has_any_data": has_any}

    # --- seed --------------------------------------------------------------

    def seed(self, user_id: Optional[int]) -> Dict[str, int]:
        if self._has_real_data():
            raise SampleDataError("Sample data can only be loaded into an empty workspace.")
        if self._has_sample_data():
            raise SampleDataError("Sample data already loaded.")

        now = datetime.now(timezone.utc)

        clients = [
            Client(name="Northwind Traders", email="ap@northwind.example", is_sample=True),
            Client(name="Acme Studio", email="billing@acmestudio.example", is_sample=True),
            Client(name="Riverside Cafe", email="owner@riverside.example", is_sample=True),
        ]
        self.db.add_all(clients)
        self.db.commit()
        for c in clients:
            self.db.refresh(c)

        # (status, due_offset_days, amount, paid_amount)
        specs = [
            ("draft", 14, 1200.0, 0.0),
            ("sent", 10, 850.0, 0.0),
            ("sent", 3, 450.0, 0.0),
            ("overdue", -20, 2000.0, 0.0),
            ("partially_paid", 7, 1500.0, 600.0),
            ("paid", -5, 700.0, 700.0),
        ]
        invoices = []
        for i, (status, due_off, amount, _paid) in enumerate(specs, start=1):
            inv = Invoice(
                number=f"SAMPLE-{i:04d}",
                amount=amount,
                subtotal=amount,
                currency="USD",
                due_date=now + timedelta(days=due_off),
                status=status,
                client_id=clients[i % len(clients)].id,
                created_by_user_id=user_id,
                is_sample=True,
            )
            invoices.append(inv)
        self.db.add_all(invoices)
        self.db.commit()
        for inv in invoices:
            self.db.refresh(inv)

        payments = []
        for inv, (status, _d, amount, paid) in zip(invoices, specs):
            if paid > 0:
                payments.append(Payment(
                    invoice_id=inv.id, amount=paid, currency="USD",
                    payment_date=now - timedelta(days=2), payment_method="card",
                    user_id=user_id,
                ))
        self.db.add_all(payments)

        expenses = [
            Expense(category="Office Supplies", currency="USD", amount=120.0,
                    expense_date=now - timedelta(days=4), status="recorded",
                    vendor="Staples", user_id=user_id, is_sample=True),
            Expense(category="Software", currency="USD", amount=49.0,
                    expense_date=now - timedelta(days=9), status="recorded",
                    vendor="Figma", user_id=user_id, is_sample=True),
            Expense(category="Travel", currency="USD", amount=320.0,
                    expense_date=now - timedelta(days=15), status="recorded",
                    vendor="Delta", user_id=user_id, is_sample=True),
            Expense(category="Meals", currency="USD", amount=64.0,
                    expense_date=now - timedelta(days=2), status="recorded",
                    vendor="Bistro", user_id=user_id, is_sample=True),
        ]
        self.db.add_all(expenses)
        self.db.commit()

        return {"clients": len(clients), "invoices": len(invoices),
                "expenses": len(expenses), "payments": len(payments)}

    # --- clear -------------------------------------------------------------

    def clear(self) -> Dict[str, int]:
        sample_invoice_ids = [
            row[0] for row in
            self.db.query(Invoice.id).filter(Invoice.is_sample == True).all()  # noqa: E712
        ]
        payments = 0
        if sample_invoice_ids:
            payments = (
                self.db.query(Payment)
                .filter(Payment.invoice_id.in_(sample_invoice_ids))
                .delete(synchronize_session=False)
            )
        invoices = (
            self.db.query(Invoice).filter(Invoice.is_sample == True)  # noqa: E712
            .delete(synchronize_session=False)
        )
        expenses = (
            self.db.query(Expense).filter(Expense.is_sample == True)  # noqa: E712
            .delete(synchronize_session=False)
        )
        clients = (
            self.db.query(Client).filter(Client.is_sample == True)  # noqa: E712
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return {"clients": clients, "invoices": invoices,
                "expenses": expenses, "payments": payments}
```

- [ ] **Step 4: Run to verify pass**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_sample_data.py -v"`
Expected: all PASS. (If `Client.email` unique constraint trips because a prior test left a same-email row, note that `db_session` is function-scoped and cleaned between tests per conftest — it should not. If a real failure occurs, read the error and adapt the seed data, not the assertions.)

- [ ] **Step 5: Commit**

```bash
git add api/core/services/sample_data.py api/tests/test_sample_data.py
git commit -m "feat(onboarding): SampleDataService seed/clear/status"
```

---

## Task 3: Onboarding router

**Files:**
- Create: `api/core/routers/onboarding.py`
- Modify: `api/main.py` (register the router)

- [ ] **Step 1: Create the router**

Create `api/core/routers/onboarding.py`:

```python
"""Onboarding endpoints: sample-data seeding for a new tenant."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer
from core.services.sample_data import SampleDataError, SampleDataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/sample-data")
async def get_sample_data_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return SampleDataService(db).sample_data_status()


@router.post("/sample-data")
async def seed_sample_data(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_non_viewer(current_user, "load sample data")
    try:
        return SampleDataService(db).seed(user_id=current_user.id)
    except SampleDataError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/sample-data")
async def clear_sample_data(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_non_viewer(current_user, "remove sample data")
    return SampleDataService(db).clear()
```

- [ ] **Step 2: Register the router in main.py**

In `api/main.py`, find where core routers are imported (`from core.routers import (...)` ~line 38) and add `onboarding` to that import list. Then near the other `app.include_router(..., prefix="/api/v1")` lines (e.g. after `settings.router` ~line 595), add:

```python
app.include_router(onboarding.router, prefix="/api/v1")
```

- [ ] **Step 3: Verify clean import**

Run: `docker compose exec api bash -c "cd /app && python -c 'import core.routers.onboarding, main' && echo OK"`
Expected: `OK` (after routine startup logs).

- [ ] **Step 4: Re-run the service tests (logic covered there)**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_sample_data.py -v"`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add api/core/routers/onboarding.py api/main.py
git commit -m "feat(onboarding): sample-data endpoints"
```

---

## Task 4: Frontend API client

**Files:**
- Create: `ui/src/lib/api/onboarding.ts`

- [ ] **Step 1: Create the client module**

Create `ui/src/lib/api/onboarding.ts`:

```typescript
import { apiRequest } from './_base';

export interface SampleDataStatus {
  has_sample_data: boolean;
  has_any_data: boolean;
}

export interface SampleDataCounts {
  clients: number;
  invoices: number;
  expenses: number;
  payments: number;
}

export const onboardingApi = {
  getSampleDataStatus: () => apiRequest<SampleDataStatus>('/onboarding/sample-data'),
  seedSampleData: () => apiRequest<SampleDataCounts>('/onboarding/sample-data', { method: 'POST' }),
  clearSampleData: () => apiRequest<SampleDataCounts>('/onboarding/sample-data', { method: 'DELETE' }),
};
```

If `ui/src/lib/api/index.ts` re-exports per-module (it does `export * from './settings'` etc.), add `export * from './onboarding';` there so `onboardingApi` is importable from `@/lib/api`.

- [ ] **Step 2: Type-check**

Run: `cd ui && npx tsc --noEmit -p tsconfig.app.json 2>&1 | grep onboarding`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add ui/src/lib/api/onboarding.ts ui/src/lib/api/index.ts
git commit -m "feat(onboarding): sample-data API client"
```

---

## Task 5: SampleDataBanner component

**Files:**
- Create: `ui/src/components/onboarding/SampleDataBanner.tsx`
- Create: `ui/src/components/onboarding/SampleDataBanner.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/onboarding/SampleDataBanner.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string, opts?: any) => (opts?.defaultValue as string) ?? key }),
}));
const onboardingApi = {
  getSampleDataStatus: vi.fn(),
  seedSampleData: vi.fn(),
  clearSampleData: vi.fn(),
};
vi.mock('@/lib/api', () => ({ onboardingApi }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { SampleDataBanner } from './SampleDataBanner';

describe('SampleDataBanner', () => {
  beforeEach(() => {
    onboardingApi.getSampleDataStatus.mockReset();
    onboardingApi.seedSampleData.mockReset().mockResolvedValue({});
    onboardingApi.clearSampleData.mockReset().mockResolvedValue({});
  });

  it('shows the load CTA when the tenant has no data and seeds on click', async () => {
    onboardingApi.getSampleDataStatus.mockResolvedValue({ has_sample_data: false, has_any_data: false });
    render(<SampleDataBanner />);
    const btn = await screen.findByRole('button', { name: /load example data/i });
    fireEvent.click(btn);
    await waitFor(() => expect(onboardingApi.seedSampleData).toHaveBeenCalled());
  });

  it('shows the remove affordance when sample data exists', async () => {
    onboardingApi.getSampleDataStatus.mockResolvedValue({ has_sample_data: true, has_any_data: true });
    render(<SampleDataBanner />);
    const btn = await screen.findByRole('button', { name: /remove sample data/i });
    fireEvent.click(btn);
    await waitFor(() => expect(onboardingApi.clearSampleData).toHaveBeenCalled());
  });

  it('renders nothing when there is real data and no sample data', async () => {
    onboardingApi.getSampleDataStatus.mockResolvedValue({ has_sample_data: false, has_any_data: true });
    const { container } = render(<SampleDataBanner />);
    await waitFor(() => expect(onboardingApi.getSampleDataStatus).toHaveBeenCalled());
    expect(container.querySelector('button')).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ui && npx vitest run src/components/onboarding/SampleDataBanner.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `ui/src/components/onboarding/SampleDataBanner.tsx`:

```tsx
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { onboardingApi, type SampleDataStatus } from '@/lib/api';
import { Button } from '@/components/ui/button';

interface SampleDataBannerProps {
  onChanged?: () => void;
}

export function SampleDataBanner({ onChanged }: SampleDataBannerProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<SampleDataStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setStatus(await onboardingApi.getSampleDataStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const load = async () => {
    setBusy(true);
    try {
      await onboardingApi.seedSampleData();
      toast.success(t('onboarding.sample_loaded', { defaultValue: 'Example data loaded.' }));
      await refresh();
      onChanged?.();
    } catch (e: any) {
      toast.error(e?.message || t('onboarding.sample_load_failed', { defaultValue: 'Could not load example data.' }));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await onboardingApi.clearSampleData();
      toast.success(t('onboarding.sample_removed', { defaultValue: 'Sample data removed.' }));
      await refresh();
      onChanged?.();
    } catch (e: any) {
      toast.error(e?.message || t('onboarding.sample_remove_failed', { defaultValue: 'Could not remove sample data.' }));
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;

  if (!status.has_any_data) {
    return (
      <div className="flex items-center justify-between gap-4 rounded-xl border border-primary/30 bg-primary/5 p-4">
        <div>
          <p className="font-semibold">{t('onboarding.sample_title', { defaultValue: 'New here?' })}</p>
          <p className="text-sm text-muted-foreground">
            {t('onboarding.sample_body', { defaultValue: 'Load example data to see how everything works. You can remove it anytime.' })}
          </p>
        </div>
        <Button onClick={load} disabled={busy}>
          {t('onboarding.sample_load', { defaultValue: 'Load example data' })}
        </Button>
      </div>
    );
  }

  if (status.has_sample_data) {
    return (
      <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-muted/30 px-4 py-2 text-sm">
        <span className="text-muted-foreground">
          {t('onboarding.sample_viewing', { defaultValue: "You're viewing sample data." })}
        </span>
        <Button variant="ghost" size="sm" onClick={remove} disabled={busy}>
          {t('onboarding.sample_remove', { defaultValue: 'Remove sample data' })}
        </Button>
      </div>
    );
  }

  return null;
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ui && npx vitest run src/components/onboarding/SampleDataBanner.test.tsx`
Expected: all 3 PASS.

- [ ] **Step 5: Type-check**

Run: `cd ui && npx tsc --noEmit -p tsconfig.app.json 2>&1 | grep SampleDataBanner`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/onboarding/SampleDataBanner.tsx ui/src/components/onboarding/SampleDataBanner.test.tsx
git commit -m "feat(onboarding): SampleDataBanner (load/remove sample data)"
```

---

## Task 6: Mount banner + i18n

**Files:**
- Modify: `ui/src/pages/Index.tsx` (dashboard content, near the welcome header ~line 241)
- Modify: `ui/src/i18n/locales/en.json`

- [ ] **Step 1: Mount the banner**

In `ui/src/pages/Index.tsx`, add the import near the other imports:

```tsx
import { SampleDataBanner } from '@/components/onboarding/SampleDataBanner';
```

In the dashboard JSX (the returned content starting ~line 240, inside the main content `div`, right after the `data-tour="dashboard-welcome"` header block), mount it:

```tsx
        <SampleDataBanner onChanged={() => window.location.reload()} />
```

(`window.location.reload()` is a simple, reliable way to repopulate every dashboard widget after seed/clear; the dashboard uses mixed data sources, so a reload is the lowest-risk refresh. If the page already exposes a react-query `queryClient`, prefer `queryClient.invalidateQueries()` instead and report that you did.)

- [ ] **Step 2: Add i18n keys**

In `ui/src/i18n/locales/en.json`, add a top-level `"onboarding"` object (if absent) with:

```json
  "onboarding": {
    "sample_title": "New here?",
    "sample_body": "Load example data to see how everything works. You can remove it anytime.",
    "sample_load": "Load example data",
    "sample_loaded": "Example data loaded.",
    "sample_load_failed": "Could not load example data.",
    "sample_viewing": "You're viewing sample data.",
    "sample_remove": "Remove sample data",
    "sample_removed": "Sample data removed.",
    "sample_remove_failed": "Could not remove sample data."
  },
```

Validate JSON: `cd ui && node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/en.json','utf8'));console.log('JSON_OK')"`

- [ ] **Step 3: Type-check + banner test**

Run: `cd ui && npx tsc --noEmit -p tsconfig.app.json 2>&1 | grep -E 'Index.tsx|SampleDataBanner'`
Expected: no NEW errors referencing these (pre-existing baseline unrelated errors in Index.tsx, if any, are fine — confirm none mention SampleDataBanner).
Run: `cd ui && npx vitest run src/components/onboarding/SampleDataBanner.test.tsx` — 3 pass.

- [ ] **Step 4: Commit**

```bash
git add ui/src/pages/Index.tsx ui/src/i18n/locales/en.json
git commit -m "feat(onboarding): mount sample-data banner on the dashboard"
```

---

## Final verification (after all tasks)

- [ ] Backend: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_sample_data.py -v"` — all pass.
- [ ] Backend imports: `docker compose exec api bash -c "cd /app && python -c 'import core.routers.onboarding, core.services.sample_data, main' && echo OK"`.
- [ ] UI: `cd ui && npx vitest run src/components/onboarding/SampleDataBanner.test.tsx` — 3 pass.
- [ ] UI: `cd ui && npx tsc --noEmit -p tsconfig.app.json` — no new errors vs baseline.
- [ ] Manual (optional): brand-new tenant → dashboard shows the Load banner → click → dashboard populates (KPIs/charts/AR) → "Remove sample data" → back to empty.

## Notes for the implementer

- Backend tests run as `docker compose exec api bash -c "cd /app && python -m pytest ..."`.
- `Client` has no `is_deleted` — never filter clients by it.
- The seeder must set `Invoice.subtotal` (NOT NULL, no default) — it does (`subtotal=amount`).
- Sample invoice numbers use the `SAMPLE-####` prefix to avoid colliding with real numbering.
- Don't seed when the tenant has real data or existing sample data — the guard raises `SampleDataError` → 409.
- Out of scope: signup-flow changes, AI, activation checklist, auto-clear, banners on other pages.
