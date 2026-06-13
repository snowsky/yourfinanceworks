# Follow-up: invoice "Send to client" button (UI send path)

Discovered 2026-06-12 while implementing enforced invoice-approval-before-send
(branch `feat/invoice-approval-before-send`, spec/plan under
`docs/superpowers/{specs,plans}/2026-06-12-invoice-approval-before-send.*`).

## Finding

**The product has no working "send invoice to client" button anywhere in the UI.**
- `sendInvoiceEmail` in `ui/src/components/invoices/InvoiceForm.tsx` is the ONLY
  caller of `POST /email/send-invoice`, and it has **0 callers** — confirmed dead
  on `origin/main` before this feature (`git grep -c 'sendInvoiceEmail(' origin/main`).
- `ViewInvoice.tsx` has no send button.
- `invoiceApi.send` (`ui/src/lib/api/invoices.ts`) points at `POST /invoices/{id}/send`,
  which has **no backend route** (would 404). Dead client method.
- `POST /invoices/{id}/send-email` (`api/core/routers/invoices/pdf_email.py`) is a
  deprecated stub that returns a redirect hint and sends nothing.

So invoices currently reach clients via the share-link / client portal / PDF
download — not a one-click "email this invoice" action.

## What the approval feature already did about this

The approval-before-send enforcement is **complete and server-side**:
`POST /email/send-invoice` returns 422 when an invoice requires approval and is
still draft/pending_approval/rejected (`api/core/services/invoice_approval_policy.py`
+ `api/core/routers/email.py`). That guarantee holds regardless of which UI calls it.

To be ready for a future send button, the dead `sendInvoiceEmail` was made
approval-aware (pre-checks `isSendBlockedByApproval` from
`ui/src/lib/invoiceSendPolicy.ts`, surfaces the backend error) — but it is still
unwired.

## The follow-up work (when a send-to-client button is wanted)

This is its own feature (build the send-to-client email UX), NOT part of
"approval before send". When picked up:
1. Add a "Send to client" button to `ViewInvoice.tsx` (and/or the `InvoiceForm`
   edit action bar) wired to `sendInvoiceEmail`.
2. Disable it when `isSendBlockedByApproval(invoice, settings.invoice_settings)` is
   true, with a tooltip. The helper + the approval-aware handler already exist.
3. Add the i18n key `invoices.send_blocked_pending_approval`
   ("This invoice must be approved before it can be sent.") and use `t(...)` in the
   handler's blocked-toast instead of the current hardcoded English string.
4. Decide product-wise whether "send" should also transition status draft→sent
   (currently it does not — deliberately left alone by the approval feature).
