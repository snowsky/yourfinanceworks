# Invoice "Send to Client" Button — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a working "Send to client" action on the invoice detail page (confirm dialog), transition a sent invoice's status `draft`/`approved` → `sent`, and make the `send_copy` setting BCC the tenant their own send.

**Architecture:** Two pure backend helpers (`status_after_send`, `resolve_send_bcc`) hold the rules; the `POST /email/send-invoice` endpoint calls them and threads a BCC list through `EmailService`. The frontend adds a self-contained `SendInvoiceDialog` (trigger + confirm) mounted in the `ViewInvoice` action bar, reusing the existing `isSendBlockedByApproval` guard. The dead `sendInvoiceEmail` in `InvoiceForm` is removed so there is one send path.

**Tech Stack:** FastAPI + SQLAlchemy, pytest (pure-helper tests), React/TS + Vitest, Radix `Dialog`/`Checkbox`.

**Spec:** `docs/superpowers/specs/2026-06-13-invoice-send-button-design.md`
**Branch:** `feat/invoice-send-button` (exists, spec committed). Do NOT create branches.

**Test invocation:** backend `docker compose exec api bash -c "cd /app && python -m pytest <path> -v"` (bare `docker compose exec api pytest` fails: `No module named 'core'`). UI: `cd ui && npx vitest run <path>` and `npx tsc --noEmit -p tsconfig.app.json`. Stack is up. Run touched test files individually (the suite has pre-existing cross-file IntegrityError pollution).

---

## File structure

**Backend**
- `api/core/services/invoice_send.py` *(new)* — `status_after_send`, `resolve_send_bcc` (pure).
- `api/core/services/email_service.py` *(modify)* — thread `bcc` into `send_invoice_email` + `_create_invoice_message`.
- `api/core/schemas/email.py` *(modify)* — `SendInvoiceEmailRequest.send_copy`.
- `api/core/routers/email.py` *(modify)* — resolve send_copy/BCC, pass BCC, set status on success.
- `api/tests/test_invoice_send.py` *(new)* — helper + bcc-threading tests.

**Frontend**
- `ui/src/components/invoices/SendInvoiceDialog.tsx` *(new)* + `.test.tsx` *(new)*.
- `ui/src/pages/ViewInvoice.tsx` *(modify)* — Send button + reload.
- `ui/src/components/invoices/InvoiceForm.tsx` *(modify)* — remove dead handler + now-unused imports.
- `ui/src/components/invoices/InvoiceCard.tsx` *(modify)* + `InvoiceCard.statusConfig.test.tsx` *(modify)* — `sent` badge.
- `ui/src/i18n/locales/en.json` *(modify)* — dialog + status keys.

---

## Task 1: Backend pure helpers

**Files:**
- Create: `api/core/services/invoice_send.py`
- Test: `api/tests/test_invoice_send.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_invoice_send.py`:

```python
"""Tests for invoice send helpers (status transition + copy-to-sender BCC)."""

import pytest

from core.services.invoice_send import resolve_send_bcc, status_after_send


@pytest.mark.parametrize("current", ["draft", "approved"])
def test_status_advances_pre_send_to_sent(current):
    assert status_after_send(current) == "sent"


@pytest.mark.parametrize(
    "current",
    ["sent", "paid", "partially_paid", "overdue", "cancelled", "pending_approval", "rejected"],
)
def test_status_unchanged_for_non_pre_send(current):
    assert status_after_send(current) == current


def test_resolve_send_bcc_on_with_address():
    assert resolve_send_bcc(True, "owner@acme.com") == ["owner@acme.com"]


def test_resolve_send_bcc_off():
    assert resolve_send_bcc(False, "owner@acme.com") == []


@pytest.mark.parametrize("addr", [None, "", "   "])
def test_resolve_send_bcc_no_address(addr):
    assert resolve_send_bcc(True, addr) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_send.py -v"`
Expected: import error (module missing).

- [ ] **Step 3: Create the module**

Create `api/core/services/invoice_send.py`:

```python
"""Pure helpers for sending an invoice to a client.

Kept free of DB/HTTP so the status-transition and copy-to-sender rules can be
unit-tested directly; the email router wires them to the request.
"""

from typing import List, Optional

# Only these advance to ``sent`` on a successful send; paid/partially_paid/
# overdue/sent/cancelled/pending_approval/rejected are already in-flight,
# terminal, or blocked and must be left untouched.
_PRE_SEND_STATUSES = frozenset({"draft", "approved"})


def status_after_send(current: str) -> str:
    """Status an invoice should hold after a successful send."""
    return "sent" if current in _PRE_SEND_STATUSES else current


def resolve_send_bcc(send_copy: bool, sender_email: Optional[str]) -> List[str]:
    """BCC list for a copy-to-sender send: the sender's own address when
    ``send_copy`` is on and a usable address exists, else empty."""
    if send_copy and sender_email and sender_email.strip():
        return [sender_email.strip()]
    return []
```

- [ ] **Step 4: Run to verify pass**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_send.py -v"`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_send.py api/tests/test_invoice_send.py
git commit -m "feat(send): invoice send-status + copy-to-sender bcc helpers"
```

(Commit attribution is disabled repo-wide — no Co-Authored-By.)

---

## Task 2: Thread BCC through EmailService

**Files:**
- Modify: `api/core/services/email_service.py` (`send_invoice_email` ~line 337, `_create_invoice_message` ~line 660)
- Test: `api/tests/test_invoice_send.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_invoice_send.py`:

```python
def _email_service(monkeypatch):
    from core.services.email_service import (
        EmailProvider,
        EmailProviderConfig,
        EmailService,
    )
    svc = EmailService(EmailProviderConfig(
        provider=EmailProvider.MAILGUN,
        from_email="owner@acme.com",
        from_name="Acme",
        mailgun_api_key="k",
        mailgun_domain="acme.com",
    ))
    # Trivial templates so rendering needs no template files.
    monkeypatch.setattr(svc, "_get_email_template", lambda t, fmt: "Invoice {{ invoice.number }}")
    return svc


def test_create_invoice_message_sets_bcc(monkeypatch):
    svc = _email_service(monkeypatch)
    msg = svc._create_invoice_message(
        invoice_data={"number": "INV-1"},
        client_data={"email": "client@x.com", "name": "Client"},
        company_data={"email": "owner@acme.com", "name": "Acme"},
        pdf_content=b"%PDF-1.4",
        template_type="invoice",
        portal_url=None,
        bcc=["owner@acme.com"],
    )
    assert msg.bcc == ["owner@acme.com"]


def test_create_invoice_message_bcc_defaults_empty(monkeypatch):
    svc = _email_service(monkeypatch)
    msg = svc._create_invoice_message(
        invoice_data={"number": "INV-1"},
        client_data={"email": "client@x.com", "name": "Client"},
        company_data={"email": "owner@acme.com", "name": "Acme"},
        pdf_content=b"%PDF-1.4",
        template_type="invoice",
        portal_url=None,
    )
    assert msg.bcc == []
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_send.py -k bcc_defaults_empty or create_invoice_message_sets_bcc -v"`
Expected: FAIL — `_create_invoice_message()` got an unexpected keyword `bcc`.

- [ ] **Step 3: Add the `bcc` param**

In `api/core/services/email_service.py`, change `send_invoice_email`'s signature to add `bcc` and forward it:

```python
    def send_invoice_email(
        self,
        invoice_data: Dict[str, Any],
        client_data: Dict[str, Any],
        company_data: Dict[str, Any],
        pdf_content: bytes,
        template_type: str = "invoice",
        portal_url: Optional[str] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """Send an invoice email with PDF attachment"""
        try:
            message = self._create_invoice_message(
                invoice_data, client_data, company_data, pdf_content, template_type, portal_url, bcc
            )
            return self.provider.send_email(message)
        except Exception as e:
            logger.error(f"Failed to send invoice email: {str(e)}")
            return False
```

Change `_create_invoice_message`'s signature to accept `bcc` and set it on the returned message. Add the param:

```python
    def _create_invoice_message(
        self,
        invoice_data: Dict[str, Any],
        client_data: Dict[str, Any],
        company_data: Dict[str, Any],
        pdf_content: bytes,
        template_type: str,
        portal_url: Optional[str] = None,
        bcc: Optional[List[str]] = None,
    ) -> EmailMessage:
```

And in that method's final `return EmailMessage(...)`, add `bcc=bcc or []` to the constructor call (alongside the existing `attachments=[attachment]`):

```python
        return EmailMessage(
            to_email=client_data['email'],
            to_name=client_data['name'],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=company_data.get('email', 'noreply@company.com'),
            from_name=company_data.get('name', 'Your Company'),
            attachments=[attachment],
            bcc=bcc or [],
        )
```

Confirm `List` is imported in `email_service.py` (it uses `List[str]` already in the `EmailMessage` dataclass; if the typing import is missing `List`, add it).

- [ ] **Step 4: Run to verify pass**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_send.py -v"`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add api/core/services/email_service.py api/tests/test_invoice_send.py
git commit -m "feat(send): support BCC on invoice emails"
```

---

## Task 3: Endpoint wiring (send_copy resolve + BCC + status)

**Files:**
- Modify: `api/core/schemas/email.py` (`SendInvoiceEmailRequest`)
- Modify: `api/core/routers/email.py` (`send_invoice_email`)

- [ ] **Step 1: Add `send_copy` to the request schema**

In `api/core/schemas/email.py`, add to `SendInvoiceEmailRequest` (after `custom_message`):

```python
    send_copy: Optional[bool] = Field(
        None,
        description="BCC the sender a copy. None = use the tenant's send_copy invoice setting.",
    )
```

- [ ] **Step 2: Import the helpers in the router**

In `api/core/routers/email.py`, add near the other `core.services` imports:

```python
from core.services.invoice_send import resolve_send_bcc, status_after_send
```

- [ ] **Step 3: Resolve send_copy + BCC and pass it to the send**

In `send_invoice_email`, just before the `success = email_service.send_invoice_email(` call, compute the BCC list:

```python
        settings_row = db.query(Settings).filter(Settings.key == "invoice_settings").first()
        default_send_copy = bool((settings_row.value or {}).get("send_copy", True)) if settings_row else True
        effective_send_copy = request.send_copy if request.send_copy is not None else default_send_copy
        bcc = resolve_send_bcc(effective_send_copy, company_data.get("email"))
```

`Settings` is already imported in this router (it is used by `get_email_service`); if not, add `from core.models.models_per_tenant import Settings`.

Then add `bcc=bcc` to the existing send call:

```python
        success = email_service.send_invoice_email(
            invoice_data=invoice_data,
            client_data=client_data,
            company_data=company_data,
            pdf_content=pdf_content,
            portal_url=portal_url,
            bcc=bcc,
        )
```

- [ ] **Step 4: Transition status on success**

Inside the existing `if success:` block (before building the `EmailResponse(success=True, ...)`), add:

```python
            new_status = status_after_send(invoice.status)
            if new_status != invoice.status:
                invoice.status = new_status
                db.commit()
```

- [ ] **Step 5: Verify the routers import cleanly**

Run: `docker compose exec api bash -c "cd /app && python -c 'import core.routers.email, core.schemas.email'"`
Expected: no output (clean import).

- [ ] **Step 6: Re-run the helper tests (logic covered there)**

Run: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_send.py -v"`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add api/core/schemas/email.py api/core/routers/email.py
git commit -m "feat(send): BCC copy-to-sender + mark invoice sent on send"
```

---

## Task 4: SendInvoiceDialog component

**Files:**
- Create: `ui/src/components/invoices/SendInvoiceDialog.tsx`
- Create: `ui/src/components/invoices/SendInvoiceDialog.test.tsx`

The dialog is self-contained (renders its own "Send" trigger + dialog), mirroring `ShareButton`. It reuses `isSendBlockedByApproval` and posts to `/email/send-invoice`.

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/invoices/SendInvoiceDialog.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SendInvoiceDialog } from './SendInvoiceDialog';

const apiRequest = vi.fn();
vi.mock('@/lib/api', () => ({ apiRequest: (...a: any[]) => apiRequest(...a) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const baseInvoice = { id: 7, number: 'INV-7', status: 'draft', amount: 100, client_name: 'Acme', client_email: 'a@x.com' };

function open() {
  fireEvent.click(screen.getByRole('button', { name: /send/i }));
}

describe('SendInvoiceDialog', () => {
  beforeEach(() => { apiRequest.mockReset(); apiRequest.mockResolvedValue({}); });

  it('shows the recipient and sends with send_copy', async () => {
    const onSent = vi.fn();
    render(<SendInvoiceDialog invoice={baseInvoice} settings={{ invoice_settings: { send_copy: true } }} onSent={onSent} />);
    open();
    expect(screen.getByText(/a@x.com/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^send invoice$/i }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith('/email/send-invoice', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ invoice_id: 7, include_pdf: true, send_copy: true }),
    })));
    await waitFor(() => expect(onSent).toHaveBeenCalled());
  });

  it('blocks the send when approval is required', () => {
    render(<SendInvoiceDialog
      invoice={{ ...baseInvoice, status: 'pending_approval' }}
      settings={{ invoice_settings: { require_approval_before_send: true, approval_threshold_amount: 0 } }}
      onSent={vi.fn()} />);
    open();
    expect(screen.getByText(/must be approved/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^send invoice$/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ui && npx vitest run src/components/invoices/SendInvoiceDialog.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `ui/src/components/invoices/SendInvoiceDialog.tsx`:

```tsx
import { useState } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Mail } from 'lucide-react';
import { apiRequest } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from '@/components/ui/dialog';
import { isSendBlockedByApproval } from '@/lib/invoiceSendPolicy';
import type { InvoiceSettings } from '@/lib/api/settings';

interface SendInvoiceDialogProps {
  invoice: { id: number; number: string; status: string; amount: number; client_name?: string; client_email?: string };
  settings?: { invoice_settings?: InvoiceSettings } | null;
  onSent?: () => void;
}

export function SendInvoiceDialog({ invoice, settings, onSent }: SendInvoiceDialogProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendCopy, setSendCopy] = useState<boolean>(settings?.invoice_settings?.send_copy ?? true);

  const blocked = isSendBlockedByApproval(
    { status: invoice.status, amount: Number(invoice.amount) },
    settings?.invoice_settings,
  );
  const recipient = invoice.client_email || invoice.client_name || '';

  const handleSend = async () => {
    setSending(true);
    try {
      await apiRequest('/email/send-invoice', {
        method: 'POST',
        body: JSON.stringify({ invoice_id: invoice.id, include_pdf: true, send_copy: sendCopy }),
      });
      toast.success(t('viewInvoice.send_success', { defaultValue: 'Invoice sent.' }));
      setOpen(false);
      onSent?.();
    } catch (error: any) {
      toast.error(error?.message || t('viewInvoice.send_failed', { defaultValue: 'Failed to send invoice.' }));
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2">
          <Mail className="h-4 w-4" />
          {t('viewInvoice.send', { defaultValue: 'Send' })}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('viewInvoice.send_title', { defaultValue: 'Send invoice' })}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <p>
            {t('viewInvoice.send_body', {
              defaultValue: 'Email invoice {{number}} to {{recipient}}?',
              number: invoice.number,
              recipient,
            })}
          </p>
          {blocked && (
            <p className="text-warning">
              {t('invoices.send_blocked_pending_approval', {
                defaultValue: 'This invoice must be approved before it can be sent.',
              })}
            </p>
          )}
          <label className="flex items-center gap-2">
            <Checkbox checked={sendCopy} onCheckedChange={(v) => setSendCopy(!!v)} />
            {t('viewInvoice.send_copy', { defaultValue: 'Send me a copy' })}
          </label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={sending}>
            {t('common.cancel', { defaultValue: 'Cancel' })}
          </Button>
          <Button onClick={handleSend} disabled={blocked || sending}>
            {t('viewInvoice.send_confirm', { defaultValue: 'Send invoice' })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

Verify `@/components/ui/dialog` exports `DialogFooter` and `DialogTrigger` (it does — check the file; if `DialogFooter` is missing, compose the footer with a `<div className="flex justify-end gap-2">` instead).

- [ ] **Step 4: Run to verify pass**

Run: `cd ui && npx vitest run src/components/invoices/SendInvoiceDialog.test.tsx`
Expected: PASS (both tests).

- [ ] **Step 5: Type-check**

Run: `cd ui && npx tsc --noEmit -p tsconfig.app.json 2>&1 | grep SendInvoiceDialog`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/invoices/SendInvoiceDialog.tsx ui/src/components/invoices/SendInvoiceDialog.test.tsx
git commit -m "feat(send): SendInvoiceDialog (confirm + copy + approval guard)"
```

---

## Task 5: Mount the dialog in ViewInvoice

**Files:**
- Modify: `ui/src/pages/ViewInvoice.tsx`

- [ ] **Step 1: Add a reload function**

In `ui/src/pages/ViewInvoice.tsx`, the page loads the invoice in a `useEffect`. Add a reusable reload near the component's other handlers (it re-fetches the single invoice so the new `sent` status shows):

```tsx
  const reloadInvoice = async () => {
    if (!id) return;
    try {
      const inv = await invoiceApi.getInvoice(Number(id));
      setInvoice(inv);
    } catch (e) {
      console.error('Error reloading invoice:', e);
    }
  };
```

(`id`, `invoiceApi`, and `setInvoice` are already in scope.)

- [ ] **Step 2: Import and mount the dialog**

Add the import near the other component imports:

```tsx
import { SendInvoiceDialog } from '@/components/invoices/SendInvoiceDialog';
```

In the `actions` block of `PageHeader`, add the dialog right after `<ShareButton ... />`:

```tsx
              <ShareButton recordType="invoice" recordId={invoice.id} />
              <SendInvoiceDialog invoice={invoice} settings={settings} onSent={reloadInvoice} />
```

The `invoice` object (type `Invoice`) has `id`, `number`, `status`, `amount`, `client_name`, `client_email` — matching the dialog's prop shape.

- [ ] **Step 3: Type-check**

Run: `cd ui && npx tsc --noEmit -p tsconfig.app.json 2>&1 | grep ViewInvoice`
Expected: no output (or only pre-existing baseline unrelated to this change — confirm none mention SendInvoiceDialog/reloadInvoice).

- [ ] **Step 4: Commit**

```bash
git add ui/src/pages/ViewInvoice.tsx
git commit -m "feat(send): Send button in the invoice detail action bar"
```

---

## Task 6: `sent` status badge

**Files:**
- Modify: `ui/src/components/invoices/InvoiceCard.tsx` (`getStatusConfig`)
- Modify: `ui/src/components/invoices/InvoiceCard.statusConfig.test.tsx`
- Modify: `ui/src/i18n/locales/en.json`

- [ ] **Step 1: Add the failing test case**

In `ui/src/components/invoices/InvoiceCard.statusConfig.test.tsx`, add inside the existing `describe`:

```tsx
  it('maps sent', () => {
    expect(getStatusConfig('sent')).toEqual({
      variant: 'secondary',
      className: 'status-sent',
      icon: '✉',
    });
  });
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ui && npx vitest run src/components/invoices/InvoiceCard.statusConfig.test.tsx`
Expected: FAIL — `sent` falls through to the generic default (`📄`).

- [ ] **Step 3: Add the case**

In `ui/src/components/invoices/InvoiceCard.tsx` `getStatusConfig`, add before `default:`:

```tsx
    case 'sent':
      return {
        variant: 'secondary' as const,
        className: 'status-sent',
        icon: '✉'
      };
```

- [ ] **Step 4: Add the i18n key if missing**

Check `ui/src/i18n/locales/en.json` for `invoices.status.sent`. If the `invoices.status` object lacks `sent`, add `"sent": "Sent",` to it. (If it already exists, skip.) Verify valid JSON:
`cd ui && node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/en.json','utf8')); console.log('JSON_OK')"`

- [ ] **Step 5: Run to verify pass**

Run: `cd ui && npx vitest run src/components/invoices/InvoiceCard.statusConfig.test.tsx`
Expected: PASS (all cases).

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/invoices/InvoiceCard.tsx ui/src/components/invoices/InvoiceCard.statusConfig.test.tsx ui/src/i18n/locales/en.json
git commit -m "feat(send): sent-status badge in the invoice list"
```

---

## Task 7: Remove the dead send handler

**Files:**
- Modify: `ui/src/components/invoices/InvoiceForm.tsx`

- [ ] **Step 1: Remove the dead handler + state**

In `ui/src/components/invoices/InvoiceForm.tsx`:
- Delete the `sendInvoiceEmail` function (the whole `const sendInvoiceEmail = async () => { ... };` block).
- Delete the `const [sendingEmail, setSendingEmail] = useState(false);` line.
- Remove the now-unused imports: `isSendBlockedByApproval` (from `@/lib/invoiceSendPolicy`) and `settingsApi` from the `@/lib/api` import (leave the other names in that import intact).

- [ ] **Step 2: Type-check — confirm no new errors and no unused-symbol errors from the removed code**

Run: `cd ui && npx tsc --noEmit -p tsconfig.app.json 2>&1 | grep 'InvoiceForm.tsx'`
Expected: the only remaining lines are PRE-EXISTING baseline unused-vars (`openNewClientOnInit`, `onFormSubmit`, `setSelectedTemplate`) — and NONE mention `sendInvoiceEmail`, `sendingEmail`, `settingsApi`, or `isSendBlockedByApproval` (those are gone). If `sending`/`setSendingEmail` were referenced by a button you did not expect, stop and report (the audit says there is none).

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/invoices/InvoiceForm.tsx
git commit -m "refactor(send): remove dead sendInvoiceEmail handler (superseded by dialog)"
```

---

## Final verification (after all tasks)

- [ ] Backend: `docker compose exec api bash -c "cd /app && python -m pytest tests/test_invoice_send.py tests/test_invoice_approval_policy.py -v"` — all pass.
- [ ] Backend imports: `docker compose exec api bash -c "cd /app && python -c 'import core.routers.email, core.schemas.email, core.services.email_service, core.services.invoice_send'"` — clean.
- [ ] UI: `cd ui && npx vitest run src/components/invoices/SendInvoiceDialog.test.tsx src/components/invoices/InvoiceCard.statusConfig.test.tsx src/lib/invoiceSendPolicy.test.ts` — pass.
- [ ] UI: `cd ui && npx tsc --noEmit -p tsconfig.app.json` — no NEW errors vs baseline; nothing referencing the new/removed symbols.
- [ ] Manual (optional): open an invoice, click Send, confirm the dialog shows the recipient + copy checkbox, send, and the status badge flips to `sent`; toggle the copy checkbox and confirm the BCC behaviour.

## Notes for the implementer

- Backend tests MUST run as `docker compose exec api bash -c "cd /app && python -m pytest ..."`.
- The endpoint (Task 3) is heavy (auth/email-service deps); its logic is fully covered by the Task 1/2 pure-helper + message tests, so no endpoint integration test is required.
- Don't add a no-client-email *disable* in the dialog — `invoice.client_email` is often empty from the API even when the client has an email; the backend returns a clear error for the genuinely-missing case (surfaced by the dialog's catch).
- Don't build compose (recipient/subject/message override) or a list-row Send — out of scope per the spec.
