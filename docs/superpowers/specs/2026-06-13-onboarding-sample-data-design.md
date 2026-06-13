# Onboarding: Sample-Data Seeding — Design Spec

**Date:** 2026-06-13
**Status:** Approved (design), pending spec review
**Competitor opportunity:** #10 "AI-guided onboarding + value-in-first-session"
(`YourFinanceWORKS_competitor_features.xlsx`) — this is **slice B** of three
(A = activation checklist, B = sample-data seeding, C = AI-guided layer). A and C
are separate future specs.

## Problem

A brand-new tenant lands on a **completely blank dashboard** — provisioning seeds
only currencies + prompt templates + the admin user, no clients/invoices/expenses
(`tenant_database_manager._init_tenant_schema`). There is no "load sample data" or
demo capability anywhere. The matrix calls "pre-fill a sample tenant; 'aha' in the
first 3 days" the highest-ROI onboarding move.

## Goals

- A brand-new tenant can one-click load a small, realistic set of sample
  clients/invoices/expenses so the first session shows populated dashboards, charts,
  AR-aging and forecast instead of empty states.
- Sample rows are clearly marked and removable in one click, never entangled with
  real data.
- Opt-in (a dashboard banner) — no surprise fake data, no signup-flow change.

## Non-goals (out of scope)

- No change to the signup flow (the banner is the only entry point).
- No auto-clear of sample data when the user creates real data (explicit Remove only).
- Banner lives on the Dashboard only (not every page).
- No AI involvement (slice C) and no activation checklist (slice A).
- `is_sample` only on the three primary entities (Client/Invoice/Expense); seeded
  payments are removed via their parent sample invoice.

## Design

### Backend

**1. `is_sample` flag.**
Add `is_sample = Column(Boolean, default=False, nullable=False, index=True)` to the
`Client`, `Invoice`, and `Expense` models (`api/core/models/models_per_tenant.py`).
Because `db_init` runs on every startup while Alembic does not, also add the column
to existing tenant DBs in `db_init.ensure_tenant_required_columns` using the
established inspector + `ALTER TABLE ... ADD COLUMN` pattern (mirrors how
`invoices.reminder_last_offset` etc. are added), for each of the three tables:

```python
if "clients" in inspector.get_table_names():
    existing = {c["name"] for c in inspector.get_columns("clients")}
    if "is_sample" not in existing:
        conn.execute(text("ALTER TABLE clients ADD COLUMN is_sample BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.commit()
# ...same for invoices and expenses
```

**2. `SampleDataService` (new, `api/core/services/sample_data.py`).**
Pure-ish service taking a tenant `Session`:

- `sample_data_status(db) -> dict` → `{"has_sample_data": bool, "has_any_data": bool}`.
  `has_sample_data` = any non-deleted `Invoice`/`Client`/`Expense` with
  `is_sample == True`. `has_any_data` = any non-deleted `Invoice` or `Client`
  (sample or real). (`is_deleted == False` filters apply.)
- `seed(db, user_id) -> dict` → `{"clients": n, "invoices": n, "expenses": n, "payments": n}`.
  **Guard:** raise `SampleDataError` (caught → 409) if the tenant already has any
  real (non-sample, non-deleted) `Invoice` or `Client`, or if sample data already
  exists. On a clean tenant, create, all with `is_sample=True`:
  - **~3 clients** (e.g. "Northwind Traders", "Acme Studio", "Riverside Cafe") with
    name/email.
  - **~6 invoices** across statuses using **relative dates** so dashboards look
    alive: one `draft`, two `sent` (one due in ~10 days, one due in ~3 days),
    one `overdue` (due ~20 days ago), one `partially_paid`, one `paid`. Each needs
    `number` (unique, e.g. `SAMPLE-0001`), `amount`, `subtotal`, `currency="USD"`,
    `due_date`, `status`, `client_id`.
  - **~2 payments** — one full payment against the `paid` invoice, one partial
    against the `partially_paid` invoice (so totals/AR reconcile). Payments carry no
    `is_sample` flag; they are removed via their parent invoice.
  - **~4 expenses** across categories ("Office Supplies", "Software", "Travel",
    "Meals"), each with `category`, `currency`, `expense_date` (recent), `amount`,
    `status="recorded"`, `is_sample=True`.
  Commit once. Numbers/labels chosen so the data is obviously illustrative.
- `clear(db) -> dict` → counts removed. Hard-delete in FK-safe order: payments whose
  `invoice_id` is in the set of sample-invoice ids, then sample invoices, sample
  expenses, sample clients (`is_sample == True`). Never touches non-sample rows.
  Commit once.

`SampleDataError(Exception)` lives in the same module.

**3. Endpoints (new `api/core/routers/onboarding.py`, registered in `main.py`).**
All require an authenticated non-viewer of the tenant (mirror the `require_non_viewer`
guard used by other write endpoints):

- `GET  /api/v1/onboarding/sample-data` → `sample_data_status(db)`.
- `POST /api/v1/onboarding/sample-data` → `seed(db, current_user.id)`; `SampleDataError`
  → HTTP 409 with its message.
- `DELETE /api/v1/onboarding/sample-data` → `clear(db)`.

### Frontend

**4. Dashboard banner (`ui/src/components/onboarding/SampleDataBanner.tsx`, new).**
Mounted near the top of the Dashboard page. On mount it calls
`GET /onboarding/sample-data`:
- If `!has_any_data` → show a prominent card: "👋 New here? Load example data to see
  how everything works." with a **Load example data** button → `POST` → on success
  toast + invalidate the dashboard/data queries (so the seeded data appears) and
  re-fetch status.
- Else if `has_sample_data` → show a slim inline notice: "You're viewing sample
  data." with a **Remove sample data** button → `DELETE` → toast + invalidate +
  re-fetch status.
- Else (real data, no sample) → render nothing.

New `onboardingApi` in `ui/src/lib/api/onboarding.ts`:
`getSampleDataStatus()`, `seedSampleData()`, `clearSampleData()`. i18n keys under a
new `onboarding.*` namespace in `en.json`.

### Testing

**Backend (`api/tests/test_sample_data.py`, new) — using the `db_session` fixture:**
- `seed` on an empty tenant creates the expected counts; every created
  client/invoice/expense has `is_sample == True`; invoices span the five statuses;
  payments reconcile the paid/partially_paid invoices.
- `seed` raises `SampleDataError` when a real (non-sample) invoice/client exists, and
  when sample data already exists (no double-seed).
- `clear` removes exactly the sample rows (and their payments) and leaves a
  pre-existing real client/invoice/expense untouched.
- `sample_data_status` reports the right flags across empty / sample-only /
  real-only / mixed states.

**Frontend (`SampleDataBanner.test.tsx`, new):** renders the Load CTA when
`has_any_data` is false and calls `seedSampleData` on click; renders the Remove
affordance when `has_sample_data` is true and calls `clearSampleData`; renders
nothing when there is real data and no sample data.

## Files touched

**Backend:** `api/core/services/sample_data.py` (new),
`api/core/models/models_per_tenant.py` (+`is_sample` ×3), `api/db_init.py`
(+3 ALTERs), `api/core/routers/onboarding.py` (new), `api/main.py` (register router),
`api/tests/test_sample_data.py` (new).

**Frontend:** `ui/src/lib/api/onboarding.ts` (new),
`ui/src/components/onboarding/SampleDataBanner.tsx` (new) + test,
`ui/src/pages/Dashboard.tsx` (mount the banner), `ui/src/i18n/locales/en.json`.

## Risks

- **No pollution of real accounts:** seeding is guarded to clean tenants only, and
  `clear` only deletes `is_sample` rows — real data is never at risk.
- **Encrypted columns:** `Client.name`/`email` are encrypted columns; the seeder
  writes through the ORM so encryption is transparent (same as the test fixtures).
- **Unique invoice numbers:** sample invoices use a `SAMPLE-####` prefix to avoid
  colliding with the tenant's real numbering sequence.
- **Multi-tenant column add:** the three `ALTER TABLE` statements run idempotently in
  `db_init` (guarded by the inspector check), consistent with existing column adds.
