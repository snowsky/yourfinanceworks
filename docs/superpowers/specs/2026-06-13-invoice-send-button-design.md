# Invoice "Send to Client" Button — Design Spec

**Date:** 2026-06-13
**Status:** Approved (design), pending spec review
**Follow-up to:** `docs/todos/invoice-send-to-client-button-followup.md` (discovered while
shipping invoice approval-before-send, PR #398).

## Problem

The product has **no working "send invoice to client" action** in the UI. The backend
`POST /email/send-invoice` works (resolves client email, attaches PDF, adds a portal
link, sends via `EmailService`, and — since PR #398 — refuses unapproved invoices),
but nothing in the UI triggers it: `sendInvoiceEmail` in `InvoiceForm.tsx` is the only
caller and is dead code. Three more gaps compound it:

- **`status` is never set to `sent`.** "sent" is a recognised invoice status the rest
  of the system expects, but no code ever transitions an invoice into it.
- **`send_copy` invoice setting is dead config** — defined (default `True`), never read.
- `EmailService._create_invoice_message` never populates `message.bcc`, even though the
  `EmailMessage` dataclass and all three providers (SES/Azure/Mailgun) support BCC.

## Goals

- A "Send" button on the invoice detail page emails the invoice to the client, behind a
  confirmation dialog.
- A successful send transitions a pre-send invoice (`draft`/`approved`) to `sent`.
- The `send_copy` setting becomes real: when on, the tenant is BCC'd their own send.
- The approval-before-send guard (PR #398) is respected in the new UI path.

## Non-goals (out of scope)

- Full compose (recipient/subject/custom-message override). The backend schema already
  accepts these fields but `EmailService` ignores them; wiring them is a separate feature.
- A Send action in the invoice-list row menu or the edit form (detail page only for v1).
- Any change to overdue / payment-status logic beyond setting `status = "sent"`.
- CC support.

## Design

### Backend

**1. Status transition (`api/core/routers/email.py` `send_invoice_email`).**
After `email_service.send_invoice_email(...)` returns success, set the invoice to `sent`
and commit, using a pure helper so the rule is unit-testable:

```python
# api/core/services/invoice_send.py (new)
_PRE_SEND_STATUSES = frozenset({"draft", "approved"})

def status_after_send(current: str) -> str:
    """Status an invoice should hold after a successful send.

    Only the pre-send states advance to ``sent``; paid/partially_paid/overdue/
    sent/cancelled/pending_approval/rejected are left exactly as they are
    (already in-flight, terminal, or blocked).
    """
    return "sent" if current in _PRE_SEND_STATUSES else current
```

In the endpoint, after a successful send:

```python
new_status = status_after_send(invoice.status)
if new_status != invoice.status:
    invoice.status = new_status
    db.commit()
```

**2. `send_copy` → BCC.**
- Add `send_copy: Optional[bool]` to `SendInvoiceEmailRequest`
  (`api/core/schemas/email.py`).
- In the endpoint, resolve the effective value:
  `effective = request.send_copy if request.send_copy is not None else invoice_settings.send_copy`
  (read `invoice_settings` the same way the policy helper does; default `True`).
- When `effective` is true, BCC the tenant's own address — resolved **server-side** from
  the company/from email (`company_data['email']` / `email_service.config.from_email`),
  never from the client. Build `bcc = [that_address]` (skip if it is empty/None).
- Thread BCC through the send: add `bcc: Optional[List[str]] = None` to
  `EmailService.send_invoice_email` and `_create_invoice_message`, and set
  `message.bcc = bcc or []`. (Providers already honor `message.bcc`.)

A small helper keeps the address logic testable:

```python
# api/core/services/invoice_send.py
def resolve_send_bcc(send_copy: bool, sender_email: Optional[str]) -> List[str]:
    """BCC list for a copy-to-sender send: the sender's own address when
    send_copy is on and an address is available, else empty."""
    if send_copy and sender_email:
        return [sender_email]
    return []
```

### Frontend

**3. `SendInvoiceDialog` (new, `ui/src/components/invoices/SendInvoiceDialog.tsx`).**
A controlled confirm dialog (mirror the existing `AlertDialog`/`Dialog` pattern, e.g.
`ShareButton.tsx`):
- Body: "Send invoice {number} to {client email}?"
- "Send me a copy" checkbox, initial checked = `settings.invoice_settings.send_copy`.
- Disabled-send states with explanatory text:
  - client has no email → "This client has no email address."
  - `isSendBlockedByApproval({status, amount}, settings.invoice_settings)` →
    "This invoice must be approved before it can be sent."
- Confirm → `POST /email/send-invoice` with `{ invoice_id, include_pdf: true, send_copy }`,
  then success toast, `queryClient.invalidateQueries(['invoice', id])` (and the list) so
  the new `sent` status shows, and close. Errors surface `error?.message`.

**4. `ViewInvoice.tsx` action bar.** Add a "Send" button next to Share that opens the
dialog, passing the loaded `invoice` and `settings`.

**5. Cleanup.** Remove the dead `sendInvoiceEmail` + `sendingEmail` from
`InvoiceForm.tsx` (the dialog is the single live send path and reuses
`isSendBlockedByApproval`).

**6. `sent` badge.** Add a `sent` case to `getStatusConfig`
(`ui/src/components/invoices/InvoiceCard.tsx`) — `{variant:'secondary',
className:'status-sent', icon:'✉'}` — plus the `invoices.status.sent` i18n key if missing.

### Testing

**Backend (`api/tests/test_invoice_send.py`, new):**
- `status_after_send`: `draft`→`sent`, `approved`→`sent`; `paid`/`partially_paid`/
  `overdue`/`sent`/`cancelled`/`pending_approval`/`rejected` unchanged.
- `resolve_send_bcc`: on+address → `[address]`; off → `[]`; on+no-address → `[]`.

**Frontend:**
- `SendInvoiceDialog.test.tsx`: renders recipient; send disabled when no client email;
  send disabled (with approval message) when blocked; confirm calls the API with
  `send_copy` from the checkbox; success closes + toasts.
- Extend `InvoiceCard.statusConfig.test.tsx` with the `sent` case.

## Files touched

**Backend:** `api/core/services/invoice_send.py` (new), `api/core/routers/email.py`,
`api/core/services/email_service.py`, `api/core/schemas/email.py`,
`api/tests/test_invoice_send.py` (new).

**Frontend:** `ui/src/components/invoices/SendInvoiceDialog.tsx` (new) + test,
`ui/src/pages/ViewInvoice.tsx`, `ui/src/components/invoices/InvoiceForm.tsx`
(remove dead handler), `ui/src/components/invoices/InvoiceCard.tsx` (+ its test),
`ui/src/i18n/locales/en.json`.

## Risks

- **Status coupling:** transitioning to `sent` only from `draft`/`approved` avoids
  clobbering payment-driven or terminal statuses; re-sending a `sent`/`paid` invoice
  leaves status alone. A `pending_approval` invoice sent while the approval policy is OFF
  stays `pending_approval` (conservative — we only advance the two clean pre-send states).
- **BCC address source:** resolved server-side from the company/from email so a client
  can't redirect the copy.
- **Single send path:** removing the dead `InvoiceForm` handler ensures there are not two
  divergent send implementations.
