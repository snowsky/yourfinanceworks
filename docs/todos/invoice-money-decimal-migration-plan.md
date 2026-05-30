# Invoice Money: float → Decimal / integer-cents migration plan

**Status:** Scoped, not started
**Owner:** TBD
**Created:** 2026-05-30
**Related:** prior bank-statements money fixes (commits `4f7c7213`, `fb678967`, `2d8a9ee2`, `39eed274`)

## Problem

Invoice money is stored and computed as floating point end-to-end, so the
amount the user sees, the amount persisted, and the amount on the PDF/email can
drift by sub-cent rounding. The bank-statements module already moved to
Decimal / integer-cents math; invoices did not.

Evidence:
- `api/core/schemas/invoice.py` — `quantity`, `price`, `amount`, `subtotal`,
  `discount_value`, `paid_amount` are all `float`.
- `api/core/models/models_per_tenant.py` — `Invoice.amount`, `Invoice.subtotal`,
  `Invoice.discount_value`, `Payment.amount`, `InvoiceItem.*` are `Column(Float)`.
- `api/core/routers/invoices/crud.py` — line-item totals, subtotal, discount and
  payment math use native float arithmetic.
- `ui/src/hooks/useInvoiceForm.ts`, `ui/src/components/invoices/InvoiceDiscountSection.tsx`,
  `ui/src/pages/ViewInvoice.tsx` — `quantity * price`, percentage discount, and
  `total` computed in JS floats; `.toFixed(2)` used only for display, while the
  raw float `calculateTotal()` is what gets POSTed as `amount`.

## Why this is a dedicated effort (not a quick fix)

This is database-per-tenant. Changing column types means a migration that must
run against **every** tenant DB plus the master, with backfill and rollback, and
the API + UI rounding rules must change in lockstep or the client/server totals
will mismatch during rollout.

## Proposed approach

Decide between two storage strategies first:

- **(A) `Numeric(precision=15, scale=2|4)` + `decimal.Decimal` in Python.**
  Lowest churn, matches how money is usually modeled in SQLAlchemy. Scale 4 for
  unit price/quantity intermediates, round to 2 at response time.
- **(B) Integer cents.** Matches the bank-statements module precedent; avoids any
  float/Decimal ambiguity but touches every read/write and all schemas.

Recommend **(A)** unless we want strict parity with bank-statements (then **(B)**).

### Work breakdown
1. **Schemas** (`schemas/invoice.py`): switch money fields to `Decimal` (or int
   cents), add validators (non-negative, max 2 dp on inputs).
2. **Models** (`models_per_tenant.py`): `Float` → `Numeric(15, 4)` (or `Integer`
   cents). Update relationships/defaults.
3. **Service/router math** (`routers/invoices/crud.py`, `payments.py`): all
   arithmetic in `Decimal`; centralize rounding (`ROUND_HALF_UP`, quantize to
   `0.01`) in one helper; round only at persistence/response boundaries.
4. **PDF / email** (`utils/pdf_generator.py`, `routers/email.py`): format from
   Decimal, never re-multiply floats.
5. **UI** (`useInvoiceForm.ts`, `InvoiceDiscountSection.tsx`, `ViewInvoice.tsx`):
   round every intermediate (`Math.round(x*100)/100`) or adopt a decimal lib;
   send the rounded `amount` at submit.
6. **Migration**: per-tenant Alembic/`db_init.py` migration with backfill;
   verify a sample of existing invoices' totals are unchanged after conversion.
7. **Tests**: golden cases that previously drifted (e.g. `19.99 × 3`,
   `0.1 + 0.2`, percentage discount on odd subtotals, multi-payment reversal to
   zero), asserting API == UI == PDF to the cent.

### Rollout
- Land schema/model/migration behind the same release; run migration per tenant.
- Add a reconciliation script that flags any invoice where
  `sum(items) - discount != stored amount` after migration.

## Out of scope here
Status-enum validation, RBAC, recurrence date math, email/PDF injection — these
are tracked separately from the money migration.
