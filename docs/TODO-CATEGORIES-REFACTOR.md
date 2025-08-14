# TODO: Refactor and Unify Categories (Bank Transactions & Expenses)

Context
- Bank statement transactions (`BankStatementTransaction.category`) and Expenses (`Expense.category`) use loosely aligned category strings.
- The UI currently maps bank categories to expense categories ad-hoc (e.g., `BankStatements.tsx` has a local `categoryMap`).
- This leads to drift, hard-to-maintain mappings, and inconsistent reporting/i18n.

Goals
- Establish a single source of truth for categories with consistent keys, labels, and i18n.
- Normalize categories produced by bank extraction (LLM/regex) into supported expense categories.
- Ensure validation and guarded updates across API/UI.

Plan
1) Central taxonomy and constants
   - Backend: create a categories module (e.g., `api/constants/categories.py`) with canonical category keys and optional aliases.
   - Frontend: mirror categories in `ui/src/constants/expenses.ts` or fetch from API (preferred for single source).
   - i18n: add keys for canonical categories in UI locales.

2) Mapping layer for bank statements
   - Create a reusable mapping function (backend or frontend) that maps raw bank categories (LLM/regex outputs) to canonical categories.
   - Move current inline mapping in `BankStatements.tsx` to a shared helper.
   - Consider tenant-specific mappings in DB (optional future), with default fallback.

3) Validation & persistence
   - Backend: validate `Expense.category` against canonical list (reject/normalize unknowns). Return a clear error code.
   - Bank transactions: allow any raw category, but normalize at the time of creating an Expense from a transaction.
   - Add API endpoint to retrieve supported categories and their labels.

4) Data migration
   - Write a migration script to backfill existing `Expense.category` values to canonical categories.
   - Optional: scan `BankStatementTransaction.category` for analytics; no strict normalization required in-place.

5) UI updates
   - Replace hard-coded category lists with data from API (or centralized constants mirrored in UI).
   - Update selectors and ensure category badges/labels use i18n.
   - Ensure the “Create Expense from Transaction” uses the shared mapping helper.

6) Tests & telemetry
   - Unit tests for mapping function (raw -> canonical).
   - API tests for validation and error codes.
   - UI tests for category selector and mapped values.

Acceptance Criteria
- Expenses can only be saved with canonical categories; unknowns are normalized or rejected with a clear error.
- Creating an expense from a bank transaction uses the shared mapping and produces consistent categories.
- UI category lists and labels come from a single source and are i18n-friendly.
- Existing expenses are migrated to canonical categories.

Related Files
- Backend
  - `api/models/models_per_tenant.py` (Expense, BankStatementTransaction)
  - `api/routers/expenses.py`
  - `api/routers/bank_statements.py`
  - New: `api/constants/categories.py`, optional `api/routers/category.py`
- Frontend
  - `ui/src/pages/BankStatements.tsx` (remove inline mapping)
  - `ui/src/constants/expenses.ts` (or fetch from API)
  - `ui/src/pages/Expenses*.tsx` (selectors)
  - `ui/src/i18n/locales/*.json` (labels)

Notes
- If tenant-specific categories are required, add a `supported_categories` table and expose via API; cache on UI.
- Consider analytics impact when categories change; document in release notes.
