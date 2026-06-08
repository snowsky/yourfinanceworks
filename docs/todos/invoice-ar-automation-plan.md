# Invoice AR Automation — Reminder Cadences, Late Fees & Thank-You Emails

Competitor quick win #6 (`YourFinanceWORKS_competitor_features.xlsx`, Top
Opportunities #6): "customizable reminder cadences + auto late fees +
thank-yous" — cheap, high-ROI AR automation that speeds cash collection.

## Current state (researched 2026-06-08)

- **Client dunning: does NOT exist.** `core/services/reminder_*` is an *internal
  task* reminder system. `workflow_service` detects overdue invoices and creates
  internal tasks/notifications — it never emails the client about an unpaid
  invoice.
- **Scheduler:** an asyncio background loop (`reminder_background_service.py`)
  started in `main.py` lifespan, running every ~300s across all tenants. This is
  where a dunning pass hooks in.
- **Cadence config:** only `auto_reminders: bool` in `invoice_settings`. No
  schedule.
- **Thank-you email:** none. Clean hook at `sync_invoice_status()` (called from
  `payments.py` after a payment) where status flips to `paid`.
- **Email infra (solid):** `EmailService` (SES/Azure/Mailgun), Jinja2 templates
  in `notification_templates.py`, config in `Settings(key="email_config")`,
  client email via `invoice.client.email` (encrypted column). Existing
  `POST /email/send-invoice` is the reference flow.
- **Late fees:** no concept. Invoice money is `Numeric(15,4)` and **mid-migration
  to Decimal** (phase-2 commits just landed). Mutating invoice totals is the
  riskiest part of this work.

## Sequencing (lowest risk / highest ROI first)

### Slice 1 — Thank-you email on payment ✅ smallest, no money mutation
- Add a thank-you Jinja2 template (HTML + text) to `notification_templates.py`.
- In the payment flow, after `sync_invoice_status()`, detect the
  `… → paid` transition (full payment) and send the client a thank-you, using
  `invoice.client.email`. Best-effort (never fail the payment).
- Gate with an `invoice_settings.thank_you_email: bool` toggle (default on/off TBD).
- Idempotent: only on the *transition* into `paid`, not on every payment write.

### Slice 2 — Customizable reminder cadences (client dunning)
- **Settings:** extend `invoice_settings` with a `reminder_cadence` array, e.g.
  `[{ offset_days: -7 }, { offset_days: 0 }, { offset_days: 3 }, { offset_days: 7 }, { offset_days: 14 }]`
  (negative = before due, 0 = on due, positive = after due) + an `enabled` flag.
- **Invoice columns (new):** `last_reminder_sent_at`, `reminder_count`,
  `next_reminder_at` (+ db_init backfill, mirroring how other columns are added).
- **Dunning service:** a new service that, per tenant, finds invoices needing a
  reminder for the current cadence step (unpaid, not draft/paid/cancelled),
  renders a dunning email, sends it, and records the send (idempotent — one
  email per cadence step per invoice).
- **Scheduler:** call the dunning service from the existing background loop (or a
  daily-gated pass). Respect `auto_reminders` / new `enabled`.
- **UI:** a Settings → Invoices "Payment reminders" section to edit the cadence.

### Slice 3 — Auto late fees (most sensitive — touches money)
- **Settings:** `late_fee` policy in `invoice_settings`
  (`enabled`, `type: percent|flat`, `value`, `grace_days`, `max_amount`,
  `recurring: once|daily|monthly`).
- **Invoice column (new):** `late_fee` `Numeric(15,4)` (follow the Decimal
  migration pattern; do this AFTER phase-2 settles to avoid churn). Invoice total
  becomes `subtotal − discount + late_fee`.
- **Application:** a scheduled pass assesses fees on overdue invoices per policy;
  must reconcile with PDF totals, balance-due, and payment math.
- **Risk:** changes financial amounts → needs careful tests and coordination with
  the in-flight money→Decimal migration. Deliberately last.

## Open design decisions (confirm before building)

1. **Default on/off** for thank-you + dunning per tenant (opt-in vs opt-out).
2. **Cadence representation** — single global cadence in `invoice_settings`
   (proposed) vs per-invoice override.
3. **Late fees in this round?** Given the active Decimal migration, recommend
   deferring Slice 3 until that lands.
4. **Dunning email content/branding** — reuse the generic operation template vs a
   dedicated dunning template with pay link.

## References
- Email flow: `core/routers/email.py` (`/email/send-invoice`), `core/services/email_service.py`
- Templates: `core/services/notification_templates.py`
- Payment hook: `core/routers/payments.py` → `sync_invoice_status()` → `core/utils/payment_status.py`
- Scheduler: `core/services/reminder_background_service.py`, `main.py` lifespan
- Settings: `core/routers/settings.py` (`invoice_settings`)
