# Enforced Invoice Approval Before Send — Design Spec

**Date:** 2026-06-12
**Status:** Approved (design), pending spec review
**Competitor opportunity:** #7 "Invoice approval workflow (2nd-person review before send)"
(`YourFinanceWORKS_competitor_features.xlsx`).

## Problem

The invoice approval workflow is ~75% built: an `InvoiceApproval` model, working
submit/approve/reject service + endpoints (`api/commercial/workflows/approvals/`),
an approver dashboard at `/approvals`, in-app notifications, a self-approval guard,
and UI feature/license gating. **But two things make it not actually deliver
"review before send":**

1. **No send-guard.** `POST /email/send-invoice` (`api/core/routers/email.py:70`)
   never checks approval status — an invoice that is `pending_approval` or
   `rejected` can be emailed to the client. The UI send action has no guard either.
2. **Approval is opt-in per invoice** (a user ticks "submit for approval"). There
   is no tenant policy that *requires* approval, so review can always be bypassed
   by simply not submitting.

This spec closes both: a tenant **policy** that requires approval before send
(optionally above an amount threshold), enforced by a **send-guard**, plus the
UI/coverage polish to make it coherent.

## Goals

- A tenant can require that invoices are approved before they can be emailed to a
  client, optionally only above an amount threshold.
- Sending an invoice that needs approval and hasn't got it is blocked (API + UI).
- Approval status is legible in the invoice list, not just the detail view.
- The new behaviour is covered by backend tests; the invoice-approval API is typed.

## Non-goals (explicitly out of scope)

- Generic expense/invoice approval consolidation refactor (invoice approval is
  ~85% copy-paste of expense approval — a real but separate cleanup).
- Multi-level approval for invoices (`approval_level` stays 1).
- Per-amount approver-routing rules (`ApprovalRule`) for invoices — the threshold
  here is a simple "requires approval: yes/no", not approver selection.
- Changing the existing draft→sent status behaviour (send does not currently set
  `status = "sent"`; that stays as-is).
- Guarding share-link / client-portal *distribution* — only the explicit
  "send invoice email" path is guarded. (Follow-up note below.)
- Deeper per-endpoint permission / feature-gate hardening of the approval
  endpoints (a separate track; user chose policy+threshold, not hardening).

## Design

### 1. Tenant policy (settings)

Stored in the existing `invoice_settings` JSON blob (same pattern as
`thank_you_email` / `payment_reminders_enabled`). New keys + defaults:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `require_approval_before_send` | bool | `false` | Opt-in. Off = today's behaviour. |
| `approval_threshold_amount` | number | `0` | `0` = all invoices need approval; `>0` = only invoices with `amount ≥ threshold`. |

Defaults added to `default_invoice_settings` in `api/core/routers/settings.py` and
documented in the `InvoiceSettings` Pydantic model
(`api/core/schemas/settings.py`). The PUT path already merges raw JSON, so no new
write-validation is required beyond coercing `approval_threshold_amount` to a
non-negative number (reject negatives with 400, mirroring how branding validates).

**Multi-currency caveat (documented, not solved):** the threshold is compared
directly against `invoice.amount` in the invoice's own currency. A tenant invoicing
in mixed currencies should set the threshold conservatively. FX normalisation is a
future enhancement.

### 2. The gate — one reusable helper

New module `api/core/services/invoice_approval_policy.py`:

```python
def invoice_requires_approval(db: Session, invoice: Invoice) -> bool:
    """True when this invoice must be approved before it can be sent.

    Inert unless the commercial ``approvals`` feature is enabled — a
    require-approval policy is meaningless if approvals can't be performed.
    """
```

Logic: `feature_enabled("approvals", db)` AND
`invoice_settings.require_approval_before_send` AND
(`threshold <= 0` OR `float(invoice.amount) >= threshold`).

This single helper is the source of truth for both the send-guard and the UI
(exposed via settings + invoice status, see §4).

### 3. Send-guard (critical fix)

In `api/core/routers/email.py` `send_invoice_email` (after the invoice is loaded,
before building/sending), add:

```python
from core.services.invoice_approval_policy import invoice_requires_approval

if invoice_requires_approval(db, invoice) and invoice.status in {
    "draft", "pending_approval", "rejected",
}:
    raise HTTPException(
        status_code=422,
        detail="This invoice requires approval before it can be sent.",
    )
```

Statuses `approved`, `sent`, `paid`, `partially_paid`, `overdue`, `cancelled`
pass through (already approved, already in-flight, or terminal). Re-sending an
approved invoice stays allowed.

**Other send paths:** `POST /invoices/{id}/send-email` (`pdf_email.py`) is a
deprecated stub that only returns a redirect — no guard needed. The UI client has
a `send: POST /invoices/{id}/send` method (`ui/src/lib/api/invoices.ts:429`); the
implementation must verify whether that route actually sends and, if so, guard it
the same way (the plan will check).

### 4. Surfaces (UI)

- **Settings** (`ui/src/components/settings/InvoiceSettingsTab.tsx`): a
  "Require approval before sending" toggle; when on, reveal a threshold amount
  input (mirrors the `payment_reminders` reveal pattern). New i18n keys. Wired
  through the existing `settingsApi.updateSettings` + `InvoiceSettings` type in
  `ui/src/lib/api/settings.ts`.
- **Send-block**: in the send action (`InvoiceForm.tsx` `sendInvoiceEmail` and the
  send button on `ViewInvoice.tsx`), disable/hide send with a tooltip
  ("Requires approval before sending") when the loaded invoice's status is
  `draft`/`pending_approval`/`rejected` and the tenant policy (from settings)
  applies to its amount. The backend 422 is surfaced as a clear error toast as a
  backstop.
- **Invoice list badges** (`ui/src/components/invoices/InvoiceCard.tsx`
  `getStatusConfig`): add `pending_approval` (amber, clock), `approved`
  (blue/emerald, check), `rejected` (destructive, x). Add the
  `invoices.status.{pending_approval,approved,rejected}` i18n keys if missing.

### 5. Typed invoice-approval API

Replace the `any[]` in `getPendingInvoiceApprovals()` with a
`PendingInvoiceApproval` interface (invoice id/number, client, amount,
submitted_at, approval id) in `ui/src/types` + `ui/src/lib/api/approvals.ts`.

### 6. Testing

**Backend (new `api/tests/test_invoice_approval_policy.py`):**
- `invoice_requires_approval`: false when approvals feature disabled (even with
  policy on); false when policy off; true when policy on + threshold 0; threshold
  boundary (amount just below → false, equal/above → true).
- Send-guard via the email route or a thin call into the guard: policy off →
  allowed; policy on + `draft`/`pending_approval`/`rejected` → 422; policy on +
  `approved` → allowed. (Stub the email service like
  `test_thank_you_email.py` / `test_invoice_dunning.py` do.)
- Settings persistence: new keys round-trip through GET/PUT `/settings`;
  negative threshold rejected.

**Frontend:** badge-mapping test for the three new statuses; a send-block test
asserting the send action is disabled for a `pending_approval` invoice under an
active policy.

## Files touched (summary)

**Backend:** `api/core/services/invoice_approval_policy.py` (new),
`api/core/routers/email.py`, `api/core/routers/settings.py`,
`api/core/schemas/settings.py`, `api/tests/test_invoice_approval_policy.py` (new).

**Frontend:** `ui/src/components/settings/InvoiceSettingsTab.tsx`,
`ui/src/lib/api/settings.ts`, `ui/src/components/invoices/InvoiceCard.tsx`,
`ui/src/lib/api/approvals.ts`, `ui/src/types/*`, send action in
`InvoiceForm.tsx` / `ViewInvoice.tsx`, `ui/src/i18n/locales/en.json`, plus the
relevant UI tests.

## Risks

- **Opt-in default avoids surprise**: existing tenants are unaffected until they
  turn the policy on.
- **Status-set coupling**: because send does not set `status = "sent"`, an approved
  invoice stays `approved` after sending — re-sends remain allowed (intended). We
  deliberately do not change this here.
- **Bypass surface**: share-link/portal distribution is not guarded in v1; noted as
  a follow-up so it isn't mistaken for covered.
