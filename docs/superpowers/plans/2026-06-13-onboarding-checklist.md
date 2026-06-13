# Onboarding Activation Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dashboard "Get started — N of 5 done" activation checklist whose steps are derived live from real tenant data, is dismissible (tenant-level flag), and stacks below the slice-B sample-data banner.

**Architecture:** A new `OnboardingChecklistService` computes five fixed steps from existing data (Client/Invoice/Expense queries + the `invoice_branding` Settings row) and reads/writes a single `onboarding_checklist` Settings row for dismissal. Two endpoints extend the existing onboarding router. One React card (`OnboardingChecklist`) mounts in `ProfessionalDashboard` (the dashboard that actually renders).

**Tech Stack:** FastAPI + SQLAlchemy (tenant DB, key/value `Settings` model), React + TypeScript, react-router `Link`, react-i18next, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-06-13-onboarding-checklist-design.md`

**Conventions (verified against the codebase):**
- Run a backend test: `docker compose exec api bash -c "cd /app && python -m pytest <path> -v"`.
- Run a UI test: `docker compose exec ui npx vitest run <path>`.
- Tenant models import from `core.models.models_per_tenant` (`Client`, `Invoice`, `Expense`, `Settings`).
- `Client` has **no** `is_deleted`; `Invoice`/`Expense` have `is_deleted` (filter `== False`).
- Services import tenant models lazily inside methods (mirrors `invoice_branding.py`).
- The onboarding router already imports `get_db`, `get_current_user`, `MasterUser`, `require_non_viewer`.
- `onboardingApi` lives in `ui/src/lib/api/onboarding.ts` and is re-exported via `index.ts`.

---

## File Structure

**Backend**
- `api/core/services/onboarding_checklist.py` (new) — `OnboardingChecklistService`: derive step completion, read/write the dismiss flag.
- `api/core/routers/onboarding.py` (modify) — add `GET /onboarding/checklist` and `POST /onboarding/checklist/dismiss`.
- `api/tests/test_onboarding_checklist.py` (new) — service-level tests.

**Frontend**
- `ui/src/lib/api/onboarding.ts` (modify) — `ChecklistStatus`/`ChecklistStep` types + `getChecklist`/`dismissChecklist`.
- `ui/src/components/onboarding/OnboardingChecklist.tsx` (new) — the card.
- `ui/src/components/onboarding/OnboardingChecklist.test.tsx` (new) — component tests.
- `ui/src/components/dashboard/ProfessionalDashboard.tsx` (modify) — mount the card below the banner.
- `ui/src/i18n/locales/en.json` (modify) — `onboarding.checklist_*` keys.

---

## Task 1: Backend service — derive step completion

**Files:**
- Create: `api/core/services/onboarding_checklist.py`
- Test: `api/tests/test_onboarding_checklist.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_onboarding_checklist.py`:

```python
"""Tests for the onboarding activation checklist."""

from datetime import datetime, timezone

from core.models.models_per_tenant import Client, Expense, Invoice, Settings
from core.services.onboarding_checklist import (
    OnboardingChecklistService,
    CHECKLIST_DISMISS_KEY,
)


def _service(db):
    return OnboardingChecklistService(db)


def _status(db):
    return _service(db).checklist_status()


def _done_keys(status):
    return {s["key"] for s in status["steps"] if s["done"]}


def test_empty_tenant_all_incomplete(db_session):
    s = _status(db_session)
    assert s["total"] == 5
    assert s["completed"] == 0
    assert s["all_complete"] is False
    assert s["dismissed"] is False
    assert _done_keys(s) == set()
    # fixed order
    assert [step["key"] for step in s["steps"]] == [
        "add_client",
        "create_invoice",
        "record_expense",
        "customize_branding",
        "send_invoice",
    ]


def test_add_client_step(db_session):
    db_session.add(Client(name="Acme", email="a@x.com"))
    db_session.commit()
    assert _done_keys(_status(db_session)) == {"add_client"}


def test_draft_invoice_completes_create_not_send(db_session):
    db_session.add(Client(name="Acme", email="a@x.com"))
    db_session.commit()
    client = db_session.query(Client).first()
    db_session.add(
        Invoice(
            number="INV-1",
            amount=100.0,
            subtotal=100.0,
            currency="USD",
            status="draft",
            due_date=datetime.now(timezone.utc),
            client_id=client.id,
        )
    )
    db_session.commit()
    done = _done_keys(_status(db_session))
    assert "create_invoice" in done
    assert "send_invoice" not in done


def test_sent_invoice_completes_send(db_session):
    db_session.add(Client(name="Acme", email="a@x.com"))
    db_session.commit()
    client = db_session.query(Client).first()
    db_session.add(
        Invoice(
            number="INV-2",
            amount=100.0,
            subtotal=100.0,
            currency="USD",
            status="sent",
            due_date=datetime.now(timezone.utc),
            client_id=client.id,
        )
    )
    db_session.commit()
    assert "send_invoice" in _done_keys(_status(db_session))


def test_expense_and_branding_steps(db_session):
    db_session.add(
        Expense(
            category="Software",
            currency="USD",
            amount=49.0,
            expense_date=datetime.now(timezone.utc),
            status="recorded",
        )
    )
    db_session.add(
        Settings(key="invoice_branding", value={"primary_color": "#123456"}, category="appearance")
    )
    db_session.commit()
    done = _done_keys(_status(db_session))
    assert "record_expense" in done
    assert "customize_branding" in done


def test_empty_branding_value_does_not_complete(db_session):
    db_session.add(Settings(key="invoice_branding", value={}, category="appearance"))
    db_session.commit()
    assert "customize_branding" not in _done_keys(_status(db_session))


def test_all_complete(db_session):
    db_session.add(Client(name="Acme", email="a@x.com"))
    db_session.commit()
    client = db_session.query(Client).first()
    db_session.add(
        Invoice(
            number="INV-3",
            amount=100.0,
            subtotal=100.0,
            currency="USD",
            status="paid",
            due_date=datetime.now(timezone.utc),
            client_id=client.id,
        )
    )
    db_session.add(
        Expense(
            category="Travel",
            currency="USD",
            amount=10.0,
            expense_date=datetime.now(timezone.utc),
            status="recorded",
        )
    )
    db_session.add(
        Settings(key="invoice_branding", value={"primary_color": "#abcdef"}, category="appearance")
    )
    db_session.commit()
    s = _status(db_session)
    assert s["completed"] == 5
    assert s["all_complete"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_onboarding_checklist.py -v"`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.services.onboarding_checklist'`.

- [ ] **Step 3: Write the service**

Create `api/core/services/onboarding_checklist.py`:

```python
"""Onboarding activation checklist: derive setup-step completion from tenant data.

Each step is computed live from existing data (no persisted completion state), so it
can never drift from reality. The only persisted state is a dismiss flag, stored as a
single ``Settings`` row (key=``onboarding_checklist``).
"""

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CHECKLIST_DISMISS_KEY = "onboarding_checklist"

# Invoice statuses that mean "an invoice has actually been sent to a client".
_SENT_STATUSES = ("sent", "paid", "partially_paid", "overdue")

# Fixed step order. Keys are the API contract; labels/links live in the frontend.
_STEP_KEYS = (
    "add_client",
    "create_invoice",
    "record_expense",
    "customize_branding",
    "send_invoice",
)


class OnboardingChecklistService:
    """Computes activation-checklist status for a single tenant DB session."""

    def __init__(self, db: Session):
        self.db = db

    def checklist_status(self) -> dict:
        from core.models.models_per_tenant import Client, Expense, Invoice

        done = {
            "add_client": self.db.query(Client.id).first() is not None,
            "create_invoice": self.db.query(Invoice.id)
            .filter(Invoice.is_deleted == False)  # noqa: E712
            .first()
            is not None,
            "record_expense": self.db.query(Expense.id)
            .filter(Expense.is_deleted == False)  # noqa: E712
            .first()
            is not None,
            "customize_branding": self._has_branding(),
            "send_invoice": self.db.query(Invoice.id)
            .filter(
                Invoice.is_deleted == False,  # noqa: E712
                Invoice.status.in_(_SENT_STATUSES),
            )
            .first()
            is not None,
        }
        steps = [{"key": key, "done": done[key]} for key in _STEP_KEYS]
        completed = sum(1 for s in steps if s["done"])
        return {
            "steps": steps,
            "completed": completed,
            "total": len(_STEP_KEYS),
            "all_complete": completed == len(_STEP_KEYS),
            "dismissed": self._is_dismissed(),
        }

    def dismiss(self) -> dict:
        from core.models.models_per_tenant import Settings

        record = (
            self.db.query(Settings)
            .filter(Settings.key == CHECKLIST_DISMISS_KEY)
            .first()
        )
        if record is None:
            record = Settings(
                key=CHECKLIST_DISMISS_KEY,
                value={"dismissed": True},
                category="onboarding",
            )
            self.db.add(record)
        else:
            record.value = {"dismissed": True}
        self.db.commit()
        return self.checklist_status()

    def _has_branding(self) -> bool:
        from core.models.models_per_tenant import Settings

        record = (
            self.db.query(Settings)
            .filter(Settings.key == "invoice_branding")
            .first()
        )
        return bool(record and record.value)

    def _is_dismissed(self) -> bool:
        from core.models.models_per_tenant import Settings

        record = (
            self.db.query(Settings)
            .filter(Settings.key == CHECKLIST_DISMISS_KEY)
            .first()
        )
        return bool(record and record.value and record.value.get("dismissed") is True)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_onboarding_checklist.py -v"`
Expected: PASS — all 7 tests green.

- [ ] **Step 5: Commit**

```bash
git add api/core/services/onboarding_checklist.py api/tests/test_onboarding_checklist.py
git commit -m "feat(onboarding): checklist service deriving step completion from tenant data"
```

---

## Task 2: Backend service — dismiss flag round-trips

**Files:**
- Modify: `api/tests/test_onboarding_checklist.py`
- (No service change — `dismiss()` already exists from Task 1; this task proves it.)

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_onboarding_checklist.py`:

```python
def test_dismiss_sets_flag(db_session):
    assert _status(db_session)["dismissed"] is False
    result = _service(db_session).dismiss()
    assert result["dismissed"] is True
    assert _status(db_session)["dismissed"] is True
    row = (
        db_session.query(Settings)
        .filter(Settings.key == CHECKLIST_DISMISS_KEY)
        .first()
    )
    assert row is not None
    assert row.value == {"dismissed": True}


def test_dismiss_is_idempotent(db_session):
    _service(db_session).dismiss()
    _service(db_session).dismiss()  # must not raise / duplicate
    rows = (
        db_session.query(Settings)
        .filter(Settings.key == CHECKLIST_DISMISS_KEY)
        .all()
    )
    assert len(rows) == 1
    assert _status(db_session)["dismissed"] is True
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_onboarding_checklist.py -k dismiss -v"`
Expected: PASS — `test_dismiss_sets_flag` and `test_dismiss_is_idempotent` green. (These pass immediately because `dismiss()` was written in Task 1; they lock the behavior in.)

- [ ] **Step 3: Commit**

```bash
git add api/tests/test_onboarding_checklist.py
git commit -m "test(onboarding): cover checklist dismiss flag round-trip and idempotency"
```

---

## Task 3: Backend endpoints

**Files:**
- Modify: `api/core/routers/onboarding.py`

- [ ] **Step 1: Add the import**

In `api/core/routers/onboarding.py`, below the existing
`from core.services.sample_data import SampleDataError, SampleDataService` line, add:

```python
from core.services.onboarding_checklist import OnboardingChecklistService
```

- [ ] **Step 2: Add the two routes**

Append to the end of `api/core/routers/onboarding.py`:

```python
@router.get("/checklist")
async def get_onboarding_checklist(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    return OnboardingChecklistService(db).checklist_status()


@router.post("/checklist/dismiss")
async def dismiss_onboarding_checklist(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "dismiss the onboarding checklist")
    return OnboardingChecklistService(db).dismiss()
```

- [ ] **Step 3: Verify the router imports cleanly**

Run: `docker compose exec api bash -c "cd /app && python -c 'import core.routers.onboarding as o; print([r.path for r in o.router.routes])'"`
Expected: output includes `/onboarding/checklist` and `/onboarding/checklist/dismiss` (alongside the existing `/onboarding/sample-data`).

- [ ] **Step 4: Commit**

```bash
git add api/core/routers/onboarding.py
git commit -m "feat(onboarding): checklist status + dismiss endpoints"
```

---

## Task 4: Frontend API client

**Files:**
- Modify: `ui/src/lib/api/onboarding.ts`

- [ ] **Step 1: Add types and methods**

In `ui/src/lib/api/onboarding.ts`, add the interfaces after `SampleDataCounts`:

```ts
export interface ChecklistStep {
  key: string;
  done: boolean;
}

export interface ChecklistStatus {
  steps: ChecklistStep[];
  completed: number;
  total: number;
  all_complete: boolean;
  dismissed: boolean;
}
```

Then extend the `onboardingApi` object with two methods (add inside the existing object literal):

```ts
  getChecklist: () => apiRequest<ChecklistStatus>('/onboarding/checklist'),
  dismissChecklist: () =>
    apiRequest<ChecklistStatus>('/onboarding/checklist/dismiss', { method: 'POST' }),
```

The full object becomes:

```ts
export const onboardingApi = {
  getSampleDataStatus: () => apiRequest<SampleDataStatus>('/onboarding/sample-data'),
  seedSampleData: () => apiRequest<SampleDataCounts>('/onboarding/sample-data', { method: 'POST' }),
  clearSampleData: () => apiRequest<SampleDataCounts>('/onboarding/sample-data', { method: 'DELETE' }),
  getChecklist: () => apiRequest<ChecklistStatus>('/onboarding/checklist'),
  dismissChecklist: () =>
    apiRequest<ChecklistStatus>('/onboarding/checklist/dismiss', { method: 'POST' }),
};
```

- [ ] **Step 2: Type-check**

Run: `docker compose exec ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep "lib/api/onboarding.ts" || echo "no errors in onboarding.ts"`
Expected: `no errors in onboarding.ts`.

- [ ] **Step 3: Commit**

```bash
git add ui/src/lib/api/onboarding.ts
git commit -m "feat(onboarding): checklist API client methods + types"
```

---

## Task 5: Frontend checklist component (TDD)

**Files:**
- Create: `ui/src/components/onboarding/OnboardingChecklist.tsx`
- Test: `ui/src/components/onboarding/OnboardingChecklist.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/onboarding/OnboardingChecklist.test.tsx` (mirrors the
`SampleDataBanner.test.tsx` mock style — `react-i18next`, `sonner`, and a hoisted api mock):

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, any>) => {
      let s = (opts?.defaultValue as string) ?? key;
      if (opts) for (const [k, v] of Object.entries(opts)) {
        if (k !== 'defaultValue') s = s.replace(`{{${k}}}`, String(v));
      }
      return s;
    },
  }),
}));

const api = vi.hoisted(() => ({
  getChecklist: vi.fn(),
  dismissChecklist: vi.fn(),
}));
vi.mock('@/lib/api', () => ({ onboardingApi: api }));
vi.mock('sonner', () => ({ toast: { error: vi.fn() } }));

import { OnboardingChecklist } from './OnboardingChecklist';

function renderCard() {
  return render(
    <MemoryRouter>
      <OnboardingChecklist />
    </MemoryRouter>,
  );
}

const mixed = {
  steps: [
    { key: 'add_client', done: true },
    { key: 'create_invoice', done: true },
    { key: 'record_expense', done: false },
    { key: 'customize_branding', done: false },
    { key: 'send_invoice', done: false },
  ],
  completed: 2,
  total: 5,
  all_complete: false,
  dismissed: false,
};

describe('OnboardingChecklist', () => {
  beforeEach(() => {
    api.getChecklist.mockReset();
    api.dismissChecklist.mockReset();
  });

  it('renders rows; incomplete steps are links, done steps are not', async () => {
    api.getChecklist.mockResolvedValue(mixed);
    renderCard();
    // an incomplete step links to its page
    const recordExpense = await screen.findByText('Record your first expense');
    expect(recordExpense.closest('a')).not.toBeNull();
    // a done step is not a link
    const addClient = screen.getByText('Add your first client');
    expect(addClient.closest('a')).toBeNull();
  });

  it('renders nothing when dismissed', async () => {
    api.getChecklist.mockResolvedValue({ ...mixed, dismissed: true });
    const { container } = renderCard();
    await waitFor(() => expect(api.getChecklist).toHaveBeenCalled());
    expect(container.querySelector('a')).toBeNull();
    expect(screen.queryByText('Add your first client')).toBeNull();
  });

  it('renders nothing when all complete', async () => {
    api.getChecklist.mockResolvedValue({ ...mixed, completed: 5, all_complete: true });
    const { container } = renderCard();
    await waitFor(() => expect(api.getChecklist).toHaveBeenCalled());
    expect(screen.queryByText('Add your first client')).toBeNull();
    expect(container.textContent).not.toContain('Get started');
  });

  it('dismiss click calls the API and hides the card', async () => {
    api.getChecklist.mockResolvedValue(mixed);
    api.dismissChecklist.mockResolvedValue({ ...mixed, dismissed: true });
    renderCard();
    const btn = await screen.findByRole('button', { name: /dismiss/i });
    fireEvent.click(btn);
    await waitFor(() => expect(api.dismissChecklist).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText('Add your first client')).toBeNull());
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec ui npx vitest run src/components/onboarding/OnboardingChecklist.test.tsx`
Expected: FAIL — cannot resolve `./OnboardingChecklist`.

- [ ] **Step 3: Write the component**

Create `ui/src/components/onboarding/OnboardingChecklist.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Circle } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { onboardingApi, type ChecklistStatus } from '@/lib/api';
import { Button } from '@/components/ui/button';

interface StepMeta {
  i18nKey: string;
  defaultLabel: string;
  to: string;
}

// key -> label + deep-link. Keeping this here keeps the API contract (keys) and the
// presentation (labels/links) in one place. Order is driven by the API response.
const STEP_META: Record<string, StepMeta> = {
  add_client: {
    i18nKey: 'onboarding.checklist_step_add_client',
    defaultLabel: 'Add your first client',
    to: '/clients/new',
  },
  create_invoice: {
    i18nKey: 'onboarding.checklist_step_create_invoice',
    defaultLabel: 'Create your first invoice',
    to: '/invoices/new',
  },
  record_expense: {
    i18nKey: 'onboarding.checklist_step_record_expense',
    defaultLabel: 'Record your first expense',
    to: '/expenses/new',
  },
  customize_branding: {
    i18nKey: 'onboarding.checklist_step_customize_branding',
    defaultLabel: 'Customize your invoice branding',
    to: '/settings',
  },
  send_invoice: {
    i18nKey: 'onboarding.checklist_step_send_invoice',
    defaultLabel: 'Send an invoice to a client',
    to: '/invoices',
  },
};

export function OnboardingChecklist() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ChecklistStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    onboardingApi
      .getChecklist()
      .then((s) => {
        if (active) setStatus(s);
      })
      .catch(() => {
        if (active) setStatus(null);
      });
    return () => {
      active = false;
    };
  }, []);

  if (!status || dismissed || status.dismissed || status.all_complete) return null;

  const dismiss = async () => {
    setBusy(true);
    try {
      await onboardingApi.dismissChecklist();
      setDismissed(true);
    } catch (e: any) {
      toast.error(
        e?.message ||
          t('onboarding.checklist_dismiss_failed', {
            defaultValue: 'Could not dismiss the checklist.',
          }),
      );
    } finally {
      setBusy(false);
    }
  };

  const pct = Math.round((status.completed / status.total) * 100);

  return (
    <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-3">
      <div className="flex items-center justify-between gap-4">
        <p className="font-semibold">
          {t('onboarding.checklist_title', {
            completed: status.completed,
            total: status.total,
            defaultValue: 'Get started — {{completed}} of {{total}} done',
          })}
        </p>
        <Button variant="ghost" size="sm" onClick={dismiss} disabled={busy}>
          {t('onboarding.checklist_dismiss', { defaultValue: 'Dismiss' })}
        </Button>
      </div>

      <div className="h-1.5 w-full rounded-full bg-muted">
        <div className="h-1.5 rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>

      <ul className="space-y-1.5">
        {status.steps.map((step) => {
          const meta = STEP_META[step.key];
          if (!meta) return null;
          const label = t(meta.i18nKey, { defaultValue: meta.defaultLabel });
          const icon = step.done ? (
            <Check className="h-4 w-4 text-primary shrink-0" />
          ) : (
            <Circle className="h-4 w-4 text-muted-foreground shrink-0" />
          );
          return (
            <li key={step.key} className="flex items-center gap-2 text-sm">
              {icon}
              {step.done ? (
                <span className="text-muted-foreground line-through">{label}</span>
              ) : (
                <Link to={meta.to} className="text-foreground hover:underline">
                  {label}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec ui npx vitest run src/components/onboarding/OnboardingChecklist.test.tsx`
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/onboarding/OnboardingChecklist.tsx ui/src/components/onboarding/OnboardingChecklist.test.tsx
git commit -m "feat(onboarding): OnboardingChecklist card with derived steps + dismiss"
```

---

## Task 6: i18n keys

**Files:**
- Modify: `ui/src/i18n/locales/en.json`

- [ ] **Step 1: Add the keys**

In `ui/src/i18n/locales/en.json`, inside the existing `"onboarding"` object, add after
`"sample_remove_failed"` (add a comma after that entry):

```json
    "checklist_title": "Get started — {{completed}} of {{total}} done",
    "checklist_step_add_client": "Add your first client",
    "checklist_step_create_invoice": "Create your first invoice",
    "checklist_step_record_expense": "Record your first expense",
    "checklist_step_customize_branding": "Customize your invoice branding",
    "checklist_step_send_invoice": "Send an invoice to a client",
    "checklist_dismiss": "Dismiss",
    "checklist_dismiss_failed": "Could not dismiss the checklist."
```

- [ ] **Step 2: Validate JSON**

Run: `docker compose exec ui node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/en.json','utf8')); console.log('valid')"`
Expected: `valid`.

- [ ] **Step 3: Commit**

```bash
git add ui/src/i18n/locales/en.json
git commit -m "i18n(onboarding): checklist title, step labels, dismiss keys"
```

---

## Task 7: Mount the card on the dashboard

**Files:**
- Modify: `ui/src/components/dashboard/ProfessionalDashboard.tsx`

- [ ] **Step 1: Add the import**

In `ui/src/components/dashboard/ProfessionalDashboard.tsx`, after the existing line
`import { SampleDataBanner } from '@/components/onboarding/SampleDataBanner';` add:

```ts
import { OnboardingChecklist } from '@/components/onboarding/OnboardingChecklist';
```

- [ ] **Step 2: Mount below the banner**

Find the existing mount:

```tsx
      {/* New-tenant onboarding: load/remove sample data (renders only on an empty workspace) */}
      <SampleDataBanner onChanged={() => window.location.reload()} />
```

Replace it with:

```tsx
      {/* New-tenant onboarding: load/remove sample data (renders only on an empty workspace) */}
      <SampleDataBanner onChanged={() => window.location.reload()} />

      {/* Activation checklist: derived setup-progress; hides when dismissed or complete */}
      <OnboardingChecklist />
```

- [ ] **Step 3: Type-check the touched file**

Run: `docker compose exec ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep "ProfessionalDashboard.tsx" || echo "no new errors in ProfessionalDashboard.tsx"`
Expected: `no new errors in ProfessionalDashboard.tsx` (a pre-existing `React` TS6133 unused line may already exist; ignore it — it is not from this change).

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/dashboard/ProfessionalDashboard.tsx
git commit -m "feat(onboarding): mount activation checklist below sample-data banner"
```

---

## Task 8: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Run the backend test file**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_onboarding_checklist.py -v"`
Expected: PASS — all 9 tests (7 from Task 1 + 2 from Task 2).

- [ ] **Step 2: Run the frontend test file**

Run: `docker compose exec ui npx vitest run src/components/onboarding/OnboardingChecklist.test.tsx`
Expected: PASS — all 4 tests.

- [ ] **Step 3: Confirm the onboarding router exposes all routes**

Run: `docker compose exec api bash -c "cd /app && python -c 'import core.routers.onboarding as o; print(sorted(r.path for r in o.router.routes))'"`
Expected: includes `/onboarding/checklist`, `/onboarding/checklist/dismiss`, `/onboarding/sample-data`.

- [ ] **Step 4: No commit** — verification only. If anything fails, fix in the relevant task's file and re-run.

---

## Self-Review (completed by plan author)

**Spec coverage:**
- 5 derived steps → Task 1 (`checklist_status`) + tests.
- Dismiss flag (tenant-level Settings) → Task 1 (`dismiss`) + Task 2 tests.
- Endpoints (GET unguarded, POST `require_non_viewer`) → Task 3.
- API client → Task 4.
- Card: hides on dismissed/all_complete, incomplete rows link, progress bar, dismiss button → Task 5.
- i18n keys → Task 6.
- Mount in `ProfessionalDashboard` below banner → Task 7.
- Branding reads raw `Settings` row (not merged defaults) → Task 1 `_has_branding` + `test_empty_branding_value_does_not_complete`.
- `Client` has no `is_deleted`; `Invoice`/`Expense` filtered → Task 1 queries.

**Placeholder scan:** none — every code step is complete.

**Type consistency:** `ChecklistStatus`/`ChecklistStep` (Task 4) match the dict shape from `checklist_status` (Task 1: `steps`, `completed`, `total`, `all_complete`, `dismissed`) and the component's usage (Task 5). `onboardingApi.getChecklist`/`dismissChecklist` names consistent across Tasks 4–5. Step keys consistent across service, tests, component `STEP_META`, and i18n keys.
