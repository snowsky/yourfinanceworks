# Enforced Invoice Approval Before Send — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a tenant require invoices to be approved before they can be emailed to a client (optionally only above an amount threshold), enforced by a send-guard, with the UI/coverage polish to make it coherent.

**Architecture:** A single backend helper module reads the tenant policy from the existing `invoice_settings` blob and decides whether an invoice must be approved (inert unless the commercial `approvals` feature is on). The `POST /email/send-invoice` route calls it to block sending unapproved invoices (HTTP 422). The settings router serves/validates the new keys; the React settings tab edits them; the invoice list shows approval-status badges; the send action is disabled in the UI; and the invoice-approval API gains a real type.

**Tech Stack:** FastAPI + SQLAlchemy (per-tenant DBs), Jinja-free service helper, pytest (`db_session` fixture + monkeypatched `feature_enabled` seam), React/TS + Vitest.

**Spec:** `docs/superpowers/specs/2026-06-12-invoice-approval-before-send-design.md`

**Branch:** `feat/invoice-approval-before-send` (already exists, spec committed). Do NOT create new branches.

**Test invocation:** backend runs inside Docker — `docker compose exec api bash -c "cd /app && python -m pytest <path> -v"` (a bare `docker compose exec api pytest` fails with `No module named 'core'`). UI: `cd ui && npx vitest run <path>` and `npx tsc --noEmit -p tsconfig.app.json`. The stack is up.

---

## File structure

**Backend**
- `api/core/services/invoice_approval_policy.py` *(new)* — policy helpers: `invoice_requires_approval`, `send_blocked_by_approval`, `validate_approval_threshold`. Single source of truth for the policy.
- `api/core/routers/email.py` *(modify)* — call the send-guard in `send_invoice_email`.
- `api/core/routers/settings.py` *(modify)* — defaults for the two new keys (GET) + threshold validation (PUT).
- `api/core/schemas/settings.py` *(modify)* — document the two new keys on `InvoiceSettings`.
- `api/tests/test_invoice_approval_policy.py` *(new)* — covers the helpers + threshold validation.

**Frontend**
- `ui/src/lib/api/settings.ts` *(modify)* — add the two keys to the `InvoiceSettings` interface.
- `ui/src/components/settings/InvoiceSettingsTab.tsx` *(modify)* — toggle + threshold reveal.
- `ui/src/i18n/locales/en.json` *(modify)* — settings labels for the new controls.
- `ui/src/components/invoices/InvoiceCard.tsx` *(modify)* — export + extend `getStatusConfig` with three approval statuses.
- `ui/src/components/invoices/InvoiceCard.statusConfig.test.tsx` *(new)* — asserts the mapping.
- `ui/src/types/index.ts` *(modify)* — export a shared `PendingInvoiceApproval` interface.
- `ui/src/lib/api/approvals.ts` *(modify)* — type `getPendingInvoiceApprovals`.
- `ui/src/components/approvals/ApprovalDashboard.tsx` *(modify)* — import the shared type instead of a local one.
- `ui/src/lib/invoiceSendPolicy.ts` *(new)* — pure `isSendBlockedByApproval(invoice, settings)` helper.
- `ui/src/lib/invoiceSendPolicy.test.ts` *(new)* — covers the helper.
- `ui/src/pages/ViewInvoice.tsx` + `ui/src/components/invoices/InvoiceForm.tsx` *(modify)* — disable the send action when blocked; surface the 422.

---

## Task 1: Policy helper module

**Files:**
- Create: `api/core/services/invoice_approval_policy.py`
- Test: `api/tests/test_invoice_approval_policy.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_invoice_approval_policy.py`:

```python
"""Tests for the invoice approval-before-send policy helpers.

The policy lives in the ``invoice_settings`` blob and is inert unless the
commercial ``approvals`` feature is enabled. ``feature_enabled`` is the seam we
monkeypatch (mirroring test_invoice_dunning.py) so no real feature config is hit.
"""

from types import SimpleNamespace

import pytest

from core.models.models_per_tenant import Settings
from core.services import invoice_approval_policy as mod
from core.services.invoice_approval_policy import (
    invoice_requires_approval,
    send_blocked_by_approval,
    validate_approval_threshold,
)


@pytest.fixture
def approvals_on(monkeypatch):
    monkeypatch.setattr(mod, "feature_enabled", lambda fid, db: True)


def _policy(db, *, enabled=True, threshold=0):
    db.add(Settings(key="invoice_settings", value={
        "require_approval_before_send": enabled,
        "approval_threshold_amount": threshold,
    }))
    db.commit()


def _invoice(amount=100.0, status="draft"):
    return SimpleNamespace(amount=amount, status=status)


def test_inert_when_feature_disabled(db_session, monkeypatch):
    monkeypatch.setattr(mod, "feature_enabled", lambda fid, db: False)
    _policy(db_session, enabled=True, threshold=0)
    assert invoice_requires_approval(db_session, _invoice()) is False


def test_false_when_policy_off(db_session, approvals_on):
    _policy(db_session, enabled=False)
    assert invoice_requires_approval(db_session, _invoice()) is False


def test_false_when_no_settings_row(db_session, approvals_on):
    assert invoice_requires_approval(db_session, _invoice()) is False


def test_true_when_policy_on_threshold_zero(db_session, approvals_on):
    _policy(db_session, enabled=True, threshold=0)
    assert invoice_requires_approval(db_session, _invoice(amount=5.0)) is True


def test_threshold_boundary(db_session, approvals_on):
    _policy(db_session, enabled=True, threshold=100)
    assert invoice_requires_approval(db_session, _invoice(amount=99.99)) is False
    assert invoice_requires_approval(db_session, _invoice(amount=100.0)) is True
    assert invoice_requires_approval(db_session, _invoice(amount=250.0)) is True


def test_send_blocked_only_for_unapproved_statuses(db_session, approvals_on):
    _policy(db_session, enabled=True, threshold=0)
    for status in ("draft", "pending_approval", "rejected"):
        assert send_blocked_by_approval(db_session, _invoice(status=status)) is True
    for status in ("approved", "sent", "paid", "partially_paid", "overdue", "cancelled"):
        assert send_blocked_by_approval(db_session, _invoice(status=status)) is False


def test_send_not_blocked_when_policy_off(db_session, approvals_on):
    _policy(db_session, enabled=False)
    assert send_blocked_by_approval(db_session, _invoice(status="draft")) is False


def test_validate_approval_threshold_accepts_valid():
    validate_approval_threshold({})  # absent -> ok
    validate_approval_threshold({"approval_threshold_amount": 0})
    validate_approval_threshold({"approval_threshold_amount": 1500})
    validate_approval_threshold({"approval_threshold_amount": 12.5})


@pytest.mark.parametrize("bad", [-1, -0.01, "abc", None])
def test_validate_approval_threshold_rejects(bad):
    with pytest.raises(ValueError):
        validate_approval_threshold({"approval_threshold_amount": bad})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_approval_policy.py -v"`
Expected: collection/import error (`No module named 'core.services.invoice_approval_policy'`).

- [ ] **Step 3: Create the module**

Create `api/core/services/invoice_approval_policy.py`:

```python
"""Tenant policy: require invoice approval before an invoice can be sent.

Stored in the ``invoice_settings`` blob:
- ``require_approval_before_send`` (bool, default off)
- ``approval_threshold_amount`` (number >= 0, default 0 = all invoices)

The policy is inert unless the commercial ``approvals`` feature is enabled — a
require-approval rule is meaningless if approvals can't be performed. The amount
threshold is compared directly against ``invoice.amount`` in the invoice's own
currency (no FX normalisation — see the spec's multi-currency caveat).
"""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from core.models.models_per_tenant import Settings
from core.utils.feature_gate import feature_enabled

logger = logging.getLogger(__name__)

# Statuses meaning the invoice has not yet cleared approval.
_UNAPPROVED_STATUSES = frozenset({"draft", "pending_approval", "rejected"})


def _invoice_settings(db: Session) -> Dict[str, Any]:
    record = db.query(Settings).filter(Settings.key == "invoice_settings").first()
    return (record.value if record and record.value else {}) or {}


def invoice_requires_approval(db: Session, invoice) -> bool:
    """True when this invoice must be approved before it can be sent."""
    if not feature_enabled("approvals", db):
        return False
    cfg = _invoice_settings(db)
    if not cfg.get("require_approval_before_send"):
        return False
    try:
        threshold = float(cfg.get("approval_threshold_amount") or 0)
    except (TypeError, ValueError):
        threshold = 0.0
    if threshold <= 0:
        return True
    return float(invoice.amount) >= threshold


def send_blocked_by_approval(db: Session, invoice) -> bool:
    """True when sending must be refused: approval required but not yet granted."""
    return (
        invoice_requires_approval(db, invoice)
        and invoice.status in _UNAPPROVED_STATUSES
    )


def validate_approval_threshold(invoice_settings: Dict[str, Any]) -> None:
    """Raise ValueError if ``approval_threshold_amount`` is present and not a
    non-negative number. Mirrors validate_invoice_branding's contract so the
    settings router can convert it to a 400."""
    if "approval_threshold_amount" not in invoice_settings:
        return
    value = invoice_settings["approval_threshold_amount"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("approval_threshold_amount must be a number")
    if value < 0:
        raise ValueError("approval_threshold_amount must be zero or positive")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_approval_policy.py -v"`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_approval_policy.py api/tests/test_invoice_approval_policy.py
git commit -m "feat(approval): invoice approval-before-send policy helpers"
```

---

## Task 2: Send-guard on the email route

**Files:**
- Modify: `api/core/routers/email.py` (`send_invoice_email`, after the 404 check ~line 92)
- Test: covered by `test_invoice_approval_policy.py::test_send_blocked_only_for_unapproved_statuses` (the guard delegates to `send_blocked_by_approval`, already tested in Task 1).

- [ ] **Step 1: Add the guard import and call**

In `api/core/routers/email.py`, add to the imports near the other `core.services` imports:

```python
from core.services.invoice_approval_policy import send_blocked_by_approval
```

In `send_invoice_email`, immediately after the existing `if not invoice:` 404 block (the invoice is loaded just above it), insert:

```python
        if send_blocked_by_approval(db, invoice):
            raise HTTPException(
                status_code=422,
                detail="This invoice requires approval before it can be sent.",
            )
```

(`HTTPException` and `status` are already imported in this file.)

- [ ] **Step 2: Verify the module imports cleanly (no syntax/import error)**

Run: `docker compose exec api bash -c "cd /app && python -c 'import core.routers.email'"`
Expected: no output (clean import).

- [ ] **Step 3: Re-run the policy tests (guard logic is covered there)**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_approval_policy.py -v"`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add api/core/routers/email.py
git commit -m "feat(approval): block sending invoices that require approval"
```

---

## Task 3: Settings defaults, schema, and threshold validation

**Files:**
- Modify: `api/core/routers/settings.py` (GET default `~line 73-82`; PUT invoice_settings handler `~line 268`)
- Modify: `api/core/schemas/settings.py` (`InvoiceSettings`, `~line 13-23`)
- Test: `api/tests/test_invoice_approval_policy.py` (threshold validation already covered in Task 1; add a default-shape assertion)

- [ ] **Step 1: Add a default-shape test**

Append to `api/tests/test_invoice_approval_policy.py`:

```python
def test_defaults_present_in_router_defaults():
    # The GET /settings default dict must carry the two new keys so the UI and
    # the policy helper see a defined shape for never-configured tenants.
    import inspect
    from core.routers import settings as settings_router

    src = inspect.getsource(settings_router)
    assert '"require_approval_before_send": False' in src
    assert '"approval_threshold_amount": 0' in src
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_approval_policy.py::test_defaults_present_in_router_defaults -v"`
Expected: FAIL (keys not present yet).

- [ ] **Step 3: Add the defaults to GET**

In `api/core/routers/settings.py`, in the `default_invoice_settings` dict (currently ending with `"reminder_cadence": [-7, -1, 3, 7, 14]`), add the two keys:

```python
        default_invoice_settings = {
            "prefix": "INV-",
            "next_number": "0001",
            "terms": "",
            "notes": "",
            "send_copy": True,
            "auto_reminders": True,
            "thank_you_email": True,
            "payment_reminders_enabled": False,
            "reminder_cadence": [-7, -1, 3, 7, 14],
            "require_approval_before_send": False,
            "approval_threshold_amount": 0,
        }
```

- [ ] **Step 4: Add threshold validation to PUT**

In `api/core/routers/settings.py`, in the PUT handler where `invoice_settings = settings.get("invoice_settings", {})` is read (around line 268), add validation right after the `if invoice_settings:` line opens — before the get-or-create record block:

```python
    if invoice_settings:
        from core.services.invoice_approval_policy import validate_approval_threshold
        try:
            validate_approval_threshold(invoice_settings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        # Get or create invoice settings record
        invoice_settings_record = db.query(Settings).filter(Settings.key == "invoice_settings").first()
        ...
```

(`HTTPException` is already imported in this router. Keep the rest of the existing block unchanged.)

- [ ] **Step 5: Document the keys on the Pydantic schema**

In `api/core/schemas/settings.py`, extend `InvoiceSettings` (after `reminder_cadence`):

```python
    reminder_cadence: List[int] = [-7, -1, 3, 7, 14]
    # Approval policy: opt-in gate requiring invoices be approved before send.
    # threshold 0 = all invoices; >0 = only invoices with amount >= threshold.
    require_approval_before_send: bool = False
    approval_threshold_amount: float = 0
```

- [ ] **Step 6: Run the policy test file**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_approval_policy.py -v"`
Expected: all PASS (including `test_defaults_present_in_router_defaults`).

- [ ] **Step 7: Verify routers import cleanly**

Run: `docker compose exec api bash -c "cd /app && python -c 'import core.routers.settings'"`
Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add api/core/routers/settings.py api/core/schemas/settings.py api/tests/test_invoice_approval_policy.py
git commit -m "feat(approval): serve + validate approval-policy invoice settings"
```

---

## Task 4: Settings UI — toggle + threshold

**Files:**
- Modify: `ui/src/lib/api/settings.ts` (`InvoiceSettings` interface, `~line 13-23`)
- Modify: `ui/src/components/settings/InvoiceSettingsTab.tsx` (useState defaults `~line 35-45`; new section near the `payment_reminders` block `~line 212-240`)
- Modify: `ui/src/i18n/locales/en.json` (settings section)

- [ ] **Step 1: Extend the API type**

In `ui/src/lib/api/settings.ts`, add to the `InvoiceSettings` interface:

```typescript
export interface InvoiceSettings {
  prefix: string;
  next_number: string;
  terms: string;
  notes?: string;
  send_copy: boolean;
  auto_reminders: boolean;
  thank_you_email?: boolean;
  payment_reminders_enabled?: boolean;
  reminder_cadence?: number[];
  require_approval_before_send?: boolean;
  approval_threshold_amount?: number;
}
```

- [ ] **Step 2: Add the two fields to the form's initial state**

In `ui/src/components/settings/InvoiceSettingsTab.tsx`, in the `useState<InvoiceSettings>({ ... })` initializer (where `payment_reminders_enabled: false,` and `reminder_cadence: [...]` are), add:

```typescript
        require_approval_before_send: false,
        approval_threshold_amount: 0,
```

- [ ] **Step 3: Add the toggle + threshold UI**

In `ui/src/components/settings/InvoiceSettingsTab.tsx`, after the closing of the `payment_reminders` block (the `{invoiceSettings.payment_reminders_enabled && ( ... )}` reveal, which ends near line 256), add a new block mirroring that pattern:

```tsx
                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                    <div className="space-y-0.5 pr-4">
                        <Label htmlFor="require_approval_before_send" className="text-base font-semibold">
                            {t('settings.require_approval_before_send')}
                        </Label>
                        <p className="text-sm text-muted-foreground">
                            {t('settings.require_approval_before_send_description')}
                        </p>
                    </div>
                    <Switch
                        id="require_approval_before_send"
                        checked={!!invoiceSettings.require_approval_before_send}
                        onCheckedChange={(checked) =>
                            setInvoiceSettings((prev) => ({ ...prev, require_approval_before_send: checked }))
                        }
                    />
                </div>
                {invoiceSettings.require_approval_before_send && (
                    <div className="pt-2 border-t">
                        <Label htmlFor="approval_threshold_amount" className="text-sm font-medium">
                            {t('settings.approval_threshold_amount')}
                        </Label>
                        <p className="text-sm text-muted-foreground mb-2">
                            {t('settings.approval_threshold_amount_description')}
                        </p>
                        <Input
                            id="approval_threshold_amount"
                            type="number"
                            min={0}
                            className="w-40"
                            value={invoiceSettings.approval_threshold_amount ?? 0}
                            onChange={(e) =>
                                setInvoiceSettings((prev) => ({
                                    ...prev,
                                    approval_threshold_amount: Math.max(0, Number(e.target.value) || 0),
                                }))
                            }
                        />
                    </div>
                )}
```

If `Input` is not already imported in the file, add `import { Input } from "@/components/ui/input";` next to the other `@/components/ui/*` imports.

- [ ] **Step 4: Add the i18n keys**

In `ui/src/i18n/locales/en.json`, inside the top-level `"settings"` object (next to the existing `thank_you_email` / `payment_reminders` keys), add:

```json
    "require_approval_before_send": "Require approval before sending",
    "require_approval_before_send_description": "Invoices must be approved by a reviewer before they can be emailed to a client. Requires the Approvals feature.",
    "approval_threshold_amount": "Approval threshold",
    "approval_threshold_amount_description": "Only require approval for invoices at or above this amount. Use 0 to require approval for all invoices.",
```

- [ ] **Step 5: Type-check**

Run: `cd ui && npx tsc --noEmit -p tsconfig.app.json 2>&1 | grep -E 'InvoiceSettingsTab|settings.ts'`
Expected: no output (no errors in the touched files).

- [ ] **Step 6: Commit**

```bash
git add ui/src/lib/api/settings.ts ui/src/components/settings/InvoiceSettingsTab.tsx ui/src/i18n/locales/en.json
git commit -m "feat(approval): settings UI for require-approval-before-send policy"
```

---

## Task 5: Invoice-list approval-status badges

**Files:**
- Modify: `ui/src/components/invoices/InvoiceCard.tsx` (`getStatusConfig`, `~line 23-58`)
- Create: `ui/src/components/invoices/InvoiceCard.statusConfig.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/invoices/InvoiceCard.statusConfig.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { getStatusConfig } from './InvoiceCard';

describe('getStatusConfig approval statuses', () => {
  it('maps pending_approval', () => {
    expect(getStatusConfig('pending_approval')).toEqual({
      variant: 'secondary',
      className: 'status-pending-approval',
      icon: '🕓',
    });
  });

  it('maps approved', () => {
    expect(getStatusConfig('approved')).toEqual({
      variant: 'default',
      className: 'status-approved',
      icon: '☑',
    });
  });

  it('maps rejected', () => {
    expect(getStatusConfig('rejected')).toEqual({
      variant: 'destructive',
      className: 'status-rejected',
      icon: '✕',
    });
  });

  it('keeps the generic default for unknown statuses', () => {
    expect(getStatusConfig('whatever').icon).toBe('📄');
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ui && npx vitest run src/components/invoices/InvoiceCard.statusConfig.test.tsx`
Expected: FAIL — `getStatusConfig` is not exported / new cases missing.

- [ ] **Step 3: Export and extend `getStatusConfig`**

In `ui/src/components/invoices/InvoiceCard.tsx`, change `const getStatusConfig = (status: string) => {` to `export const getStatusConfig = (status: string) => {`, and add three cases before the `default:` case:

```tsx
    case 'pending_approval':
      return {
        variant: 'secondary' as const,
        className: 'status-pending-approval',
        icon: '🕓'
      };
    case 'approved':
      return {
        variant: 'default' as const,
        className: 'status-approved',
        icon: '☑'
      };
    case 'rejected':
      return {
        variant: 'destructive' as const,
        className: 'status-rejected',
        icon: '✕'
      };
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ui && npx vitest run src/components/invoices/InvoiceCard.statusConfig.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/invoices/InvoiceCard.tsx ui/src/components/invoices/InvoiceCard.statusConfig.test.tsx
git commit -m "feat(approval): approval-status badges in the invoice list"
```

---

## Task 6: Typed invoice-approval API

**Files:**
- Modify: `ui/src/types/index.ts` (add exported interface)
- Modify: `ui/src/lib/api/approvals.ts` (`getPendingInvoiceApprovals` return type, `~line 113-120`)
- Modify: `ui/src/components/approvals/ApprovalDashboard.tsx` (use the shared type, `~line 32-43`)

- [ ] **Step 1: Add the shared interface**

In `ui/src/types/index.ts`, add (near the other approval interfaces such as `ExpenseApproval`):

```typescript
export interface PendingInvoiceApproval {
  id: number;
  invoice_id: number;
  invoice_number: string;
  client_name: string;
  amount: number;
  currency: string;
  status: string;
  submitted_at: string;
  approver_id: number;
  approval_level: number;
}
```

- [ ] **Step 2: Type the API method**

In `ui/src/lib/api/approvals.ts`, import the type at the top (next to the existing type imports, e.g. `import type { ... } from '@/types';`) and change `getPendingInvoiceApprovals` so the response is typed:

```typescript
    return apiRequest<{ approvals: PendingInvoiceApproval[]; total: number; }>(`/approvals/invoices/pending${queryString ? `?${queryString}` : ''}`);
```

- [ ] **Step 3: Use the shared type in the dashboard**

In `ui/src/components/approvals/ApprovalDashboard.tsx`, delete the local `interface PendingInvoiceApproval { ... }` (lines ~32-43) and import it from `@/types` instead (add it to the existing `@/types` import, or add a new `import type { PendingInvoiceApproval } from '@/types';`).

- [ ] **Step 4: Type-check**

Run: `cd ui && npx tsc --noEmit -p tsconfig.app.json 2>&1 | grep -E 'approvals.ts|ApprovalDashboard|types/index'`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add ui/src/types/index.ts ui/src/lib/api/approvals.ts ui/src/components/approvals/ApprovalDashboard.tsx
git commit -m "refactor(approval): share a typed PendingInvoiceApproval"
```

---

## Task 7: UI send-block

**Files:**
- Create: `ui/src/lib/invoiceSendPolicy.ts`
- Create: `ui/src/lib/invoiceSendPolicy.test.ts`
- Modify: `ui/src/pages/ViewInvoice.tsx` (the send button + its handler)
- Modify: `ui/src/components/invoices/InvoiceForm.tsx` (`sendInvoiceEmail`, `~line 347-370`)

- [ ] **Step 1: Write the failing test for the pure helper**

Create `ui/src/lib/invoiceSendPolicy.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { isSendBlockedByApproval } from './invoiceSendPolicy';

const settingsOn = { require_approval_before_send: true, approval_threshold_amount: 0 };

describe('isSendBlockedByApproval', () => {
  it('blocks unapproved statuses when policy applies', () => {
    for (const status of ['draft', 'pending_approval', 'rejected']) {
      expect(isSendBlockedByApproval({ status, amount: 100 }, settingsOn)).toBe(true);
    }
  });

  it('allows approved / downstream statuses', () => {
    for (const status of ['approved', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled']) {
      expect(isSendBlockedByApproval({ status, amount: 100 }, settingsOn)).toBe(false);
    }
  });

  it('does not block when policy is off', () => {
    expect(isSendBlockedByApproval({ status: 'draft', amount: 100 },
      { require_approval_before_send: false, approval_threshold_amount: 0 })).toBe(false);
  });

  it('respects the threshold', () => {
    const s = { require_approval_before_send: true, approval_threshold_amount: 500 };
    expect(isSendBlockedByApproval({ status: 'draft', amount: 499 }, s)).toBe(false);
    expect(isSendBlockedByApproval({ status: 'draft', amount: 500 }, s)).toBe(true);
  });

  it('does not block when settings are undefined', () => {
    expect(isSendBlockedByApproval({ status: 'draft', amount: 100 }, undefined)).toBe(false);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ui && npx vitest run src/lib/invoiceSendPolicy.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the helper (mirror of the backend policy)**

Create `ui/src/lib/invoiceSendPolicy.ts`:

```typescript
import type { InvoiceSettings } from '@/lib/api/settings';

const UNAPPROVED = new Set(['draft', 'pending_approval', 'rejected']);

/**
 * UX mirror of the backend send-guard (invoice_approval_policy.py). The backend
 * is the real enforcement; this only drives button state + messaging.
 */
export function isSendBlockedByApproval(
  invoice: { status: string; amount: number },
  settings?: Pick<InvoiceSettings, 'require_approval_before_send' | 'approval_threshold_amount'>,
): boolean {
  if (!settings?.require_approval_before_send) return false;
  const threshold = settings.approval_threshold_amount ?? 0;
  const applies = threshold <= 0 || (invoice.amount ?? 0) >= threshold;
  return applies && UNAPPROVED.has(invoice.status);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ui && npx vitest run src/lib/invoiceSendPolicy.test.ts`
Expected: PASS.

- [ ] **Step 5: Wire it into ViewInvoice's send button**

In `ui/src/pages/ViewInvoice.tsx`: load settings via the existing settings query (the page or a parent already uses `settingsApi`/`useQuery(['settings'])`; if not, add `const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: settingsApi.getSettings });` and import `settingsApi`). Compute:

```tsx
import { isSendBlockedByApproval } from '@/lib/invoiceSendPolicy';
...
const sendBlocked = isSendBlockedByApproval(
  { status: invoice.status, amount: Number(invoice.amount) },
  settings?.invoice_settings,
);
```

On the existing "Send"/"Send email" button, add `disabled={sendBlocked || <existing disabled>}` and wrap it so a tooltip/`title` shows when blocked:

```tsx
<span title={sendBlocked ? t('invoices.send_blocked_pending_approval') : undefined}>
  <Button disabled={sendBlocked} onClick={handleSend}>...</Button>
</span>
```

Add the i18n key to `ui/src/i18n/locales/en.json` under `"invoices"`:

```json
    "send_blocked_pending_approval": "This invoice must be approved before it can be sent.",
```

- [ ] **Step 6: Surface the backend 422 in InvoiceForm's send handler**

In `ui/src/components/invoices/InvoiceForm.tsx` `sendInvoiceEmail` (the `catch` block), ensure the server detail is shown. If the catch currently shows a generic message, change it to prefer the API error message, e.g.:

```tsx
    } catch (err: any) {
      const msg = err?.message || t('invoices.failed_to_send');
      toast.error(msg);
    }
```

(Use the file's existing toast import and the existing `failed_to_send` key if present; if the catch already surfaces `err.message`, leave it and note so in the report.)

- [ ] **Step 7: Type-check + run the helper test**

Run: `cd ui && npx tsc --noEmit -p tsconfig.app.json 2>&1 | grep -E 'invoiceSendPolicy|ViewInvoice|InvoiceForm'`
Expected: no output.
Run: `cd ui && npx vitest run src/lib/invoiceSendPolicy.test.ts`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add ui/src/lib/invoiceSendPolicy.ts ui/src/lib/invoiceSendPolicy.test.ts ui/src/pages/ViewInvoice.tsx ui/src/components/invoices/InvoiceForm.tsx ui/src/i18n/locales/en.json
git commit -m "feat(approval): disable send + surface guard in the invoice UI"
```

---

## Final verification (after all tasks)

- [ ] Backend: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_approval_policy.py tests/test_thank_you_email.py tests/test_invoice_dunning.py -v"` — all pass (the policy file in full + adjacent settings-touching suites as a regression check).
- [ ] Backend imports: `docker compose exec api bash -c "cd /app && python -c 'import core.routers.email, core.routers.settings'"` — clean.
- [ ] UI: `cd ui && npx vitest run src/lib/invoiceSendPolicy.test.ts src/components/invoices/InvoiceCard.statusConfig.test.tsx` — pass.
- [ ] UI: `cd ui && npx tsc --noEmit -p tsconfig.app.json` — no new errors vs the pre-existing baseline.
- [ ] Manual smoke (optional): enable the Approvals feature, turn the policy on in Settings → Invoices, create a draft invoice, confirm Send is disabled and `POST /email/send-invoice` returns 422; submit → approve → confirm Send works.

## Notes for the implementer

- The backend test invocation MUST be `docker compose exec api bash -c "cd /app && python -m pytest ..."`. A bare `docker compose exec api pytest` fails with `No module named 'core'`.
- Running many `api/tests` files together triggers PRE-EXISTING cross-file `sqlalchemy.IntegrityError` pollution (also fails on `main`); run the files named above individually.
- The `feature_enabled` seam: `invoice_approval_policy` imports it at module top so tests `monkeypatch.setattr(mod, "feature_enabled", ...)`.
- Do not consolidate the duplicated expense/invoice approval code — out of scope per the spec.
