# Expense Feature Summary

## Overview
End-to-end expense management integrated with invoices:
- Backend: models, schemas, API (CRUD, filters, attachments, linking), migrations/self-heal.
- Frontend: list/new/edit pages, attachment upload/preview, delete confirmation, currency/category/date controls.
- Linking: one expense → one invoice (max); one invoice → many expenses. Link on invoice create or from invoice edit; unlink supported.

## Backend
- Models (`api/models/models_per_tenant.py`):
  - `Expense`: amount, currency, expense_date, category, vendor, tax_rate, tax_amount, total_amount, payment_method, reference_number, status, notes, user_id, invoice_id (nullable), timestamps.
  - `ExpenseAttachment`: expense_id, filename, content_type, size_bytes, file_path, uploaded_at, uploaded_by.
  - `Invoice.expenses` relationship; `Expense.invoice` backref.
- Schemas (`api/schemas/expense.py`):
  - `ExpenseBase`, `ExpenseCreate`, `ExpenseUpdate` (accepts `invoice_id`), `Expense` with `attachments_count`.
- API (`api/routers/expenses.py`):
  - CRUD with RBAC and audit logging.
  - Filters: `category`, `invoice_id`, `unlinked_only`.
  - Attachments: upload (<=5; PDF/JPG/PNG; 10MB max; UUID filenames), list, delete, download.
  - Delete cleans legacy `receipt_path` and all attachment files.
  - Linking validation: ensures invoice exists on create/update; `invoice_id: null` unlinks.
  - Uvicorn logs: linking/unlinking intent and persisted values.
- Migrations & Multi-tenancy:
  - Alembic `add_expense_invoice_link.py` adds `expenses.invoice_id` + FK.
  - `api/db_init.py` self-heals tenant DBs adding `expenses.invoice_id`/FK if missing.

## Frontend
- API client (`ui/src/lib/api.ts`):
  - `Expense`, `ExpenseAttachmentMeta`, `expenseApi` for CRUD/filters/attachments; `linkApi.getInvoicesBasic()` for linking selectors.
- Navigation: `Expenses` added to sidebar.
- Pages:
  - `ui/src/pages/Expenses.tsx`: list, category filter, delete confirm, upload + preview modal, `attachments_count`, Invoice column link.
  - `ui/src/pages/ExpensesNew.tsx`: full-page create with currency, category, date picker, multi-upload, "Link to Invoice".
  - `ui/src/pages/ExpensesEdit.tsx`: full-page edit; same controls; in-modal preview; deferred attachment deletion until save.
- Invoice integration:
  - `ui/src/components/invoices/InvoiceForm.tsx`: on create, optional "Link an Expense" (unlinked-only + client-side guard). After creation, updates selected expense with new invoice id.
  - `ui/src/pages/EditInvoice.tsx`: "Linked Expenses" section to link/unlink. Sends `invoice_id: null` to unlink; optimistic UI updates then refresh.

## Key Fixes/Improvements
- Select empty value fix; `useEffect` import fixes; 404 attachment download fix.
- Ensure link persistence: backend accepts `invoice_id` in update; UI sends `null` to unlink; logs added.
- UUID filenames for attachments to avoid collisions.
- Exclude linked expenses from create-invoice selector.

## Usage Notes
- Link on invoice creation via the "Link an Expense" dropdown.
- Manage links on the invoice edit page under "Linked Expenses".
- Up to 5 attachments per expense; images/PDF preview inline; others downloadable.

## Constraints
- One expense → one invoice; one invoice → many expenses.
- Attachment types: PDF, JPG, PNG; max size 10MB.

