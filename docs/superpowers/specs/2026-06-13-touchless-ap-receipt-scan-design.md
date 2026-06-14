# Touchless AP — Receipt Scan & Confirm — Design Spec

**Date:** 2026-06-13
**Status:** Approved (design), pending spec review
**Competitor opportunity:** #3 "Touchless AP / OCR-extract vendor bills"
(`YourFinanceWORKS_competitor_features.xlsx`). Spans **two repos**: `invoice_app`
(FastAPI backend + React web) and `yfw-mobile` (Expo/React Native expenses app).

## Problem & current state (be honest: mostly built)

The expense-OCR capability is largely shipped on both platforms:

- **Backend:** `POST /expenses/{id}/upload-receipt` stores an attachment and runs AI
  Vision extraction (Kafka worker `api/workers/ocr/expense_handler.py`, or inline
  fallback `process_attachment_inline`). `apply_ocr_extraction_to_expense` writes
  vendor/amount/date/category onto the expense. A review/diff/accept flow exists
  (`review_status`, `/accept-review`, `/reject-review`, `/reprocess`).
- **Web:** `ExpensesNew` attaches files on create (`analysis_status="queued"`);
  `ExpensesView`/`ExpensesEdit` show `analysis_status`, per-attachment
  `extracted_amount`, errors, and reprocess.
- **Mobile (`yfw-mobile/apps/expenses`):** a `capture` tab snaps a photo → creates an
  expense → `uploadReceipt` → async OCR; an `inbox` tab lists review-needed expenses
  (amount/vendor/status) with **approve/reject** (`acceptReview`/`rejectReview`) and
  opens a detail screen `app/expense/[id].tsx`.

The one genuine gap on both platforms: you never **see what the AI read and confirm it
before committing** — the expense is created first and filled asynchronously, surfaced
only later (web review/diff, mobile inbox). This spec closes that gap with small,
targeted slices, not new infrastructure.

## Decomposition (3 sub-projects, built in order)

Each slice ships independently and gets its own implementation plan. Order: **1 → 2 → 3**
(web slice 2 depends on slice 1; mobile slice 3 is independent and gets its own
detailed brainstorm when started).

---

### Slice 1 — Backend: synchronous `scan-receipt` extraction (keystone)

**Goal:** extract a receipt's fields **without persisting anything**, so a client can
preview and confirm before creating the expense.

**Service `api/core/services/expense_scan.py` (new):**
- `scan_receipt_bytes(db, filename, content_type, contents) -> dict`:
  1. Validate exactly as `upload-receipt` does: extension in the allowed set,
     content-type in the allowed set, `validate_file_magic_bytes(contents, content_type)`
     (anti-spoof), size ≤ 10 MB. On failure raise `ScanError` (→ HTTP 400).
  2. Write `contents` to a `tempfile.NamedTemporaryFile` (suffix = original ext).
  3. Call the commercial extractor:
     `UnifiedOCRService(...).extract_structured_data(temp_path,
     DocumentType.EXPENSE_RECEIPT, db_session=db)`.
  4. Map the raw extraction to a stable field dict using the **same mapping logic**
     `apply_ocr_extraction_to_expense` uses (extract that mapping into a shared pure
     helper `map_extraction_to_fields(extracted) -> dict` in
     `commercial/ai/services/ocr_service/expense_extraction.py`, and call it from both
     `apply_ocr_extraction_to_expense` and the new service — DRY, no logic divergence).
  5. `finally:` delete the temp file.
  - Returns `{"available": True, "fields": {vendor, amount, currency, expense_date,
    category, tax_amount, total_amount, payment_method, reference_number, notes}}`
    (only keys the extractor produced; absent keys omitted).
- **Graceful degradation:** wrap the commercial import in `try/except ImportError`
  (and catch extractor runtime failures). On unavailable/failed extraction, return
  `{"available": False, "reason": "<short>"}` — never raise for "AI off".
- `ScanError(Exception)` lives in the same module (validation failures only).

**Endpoint (new submodule `api/core/routers/expenses/scan.py`, mounted on the expenses
router like the existing `attachments`/`crud` submodules — keeps `attachments.py`
focused):**
- `POST /api/v1/expenses/scan-receipt` (multipart `file`):
  `require_non_viewer(current_user, "scan receipts")`; read bytes; call
  `scan_receipt_bytes`; return its dict. `ScanError` → 400. The endpoint never writes
  to the DB and creates no attachment.

**Tests (`api/tests/test_expense_scan.py`, new):**
- `map_extraction_to_fields` maps a representative raw extraction (vendor/amount/date/
  category/tax) to the stable dict; missing keys omitted; CSV-like/garbage vendor
  handled (reuse the existing guard).
- `scan_receipt_bytes` returns `available=False` when the commercial extractor import
  is unavailable (monkeypatch the import to raise `ImportError`).
- `scan_receipt_bytes` raises `ScanError` for a disallowed extension and for oversize
  content.
- The temp file is removed after a successful scan and after an extractor failure.
  (Extraction itself is mocked — these are unit tests, not a live vision-model call.)

---

### Slice 2 — Web: "Scan a bill" confirm modal (small)

**Goal:** drop a bill, see the extracted fields, confirm/edit, then it's created.

- `ui/src/lib/api/expenses.ts`: add `scanReceipt(file: File): Promise<ScanResult>`
  (multipart POST to `/expenses/scan-receipt`, mirroring `uploadReceipt`'s manual
  multipart). `ScanResult = { available: boolean; fields?: ExpenseScanFields; reason?: string }`.
- `ui/src/components/expenses/ScanBillDialog.tsx` (new): a modal with file drop/select.
  On file chosen → "Reading your bill…" spinner → `scanReceipt`:
  - `available && fields` → render an **editable form pre-filled** with the fields
    (amount, vendor, date, category, currency, tax). **Save** → existing
    `createExpense(prefilled)` then `uploadReceipt(created.id, file)` (the file attaches;
    `analysis_status` stays as the normal flow). **Cancel** → close, nothing persisted.
  - `available === false` → inline notice "Couldn't read it automatically — enter
    the details" and show the same editable form **empty** (with the file still queued
    to attach on Save). Never blocks the user.
- A **Scan a bill** button on `ui/src/pages/Expenses/index.tsx` opens the dialog.
- i18n under a new `expenses.scan_*` namespace in `en.json`.
- Reuses existing create + upload; introduces no new expense status and touches no
  reports/lists/totals.

**Tests (`ScanBillDialog.test.tsx`, new):** renders the prefilled form from a mocked
`scanReceipt` success; on `available:false` renders the empty-form fallback; Save calls
`createExpense` then `uploadReceipt`; Cancel persists nothing.

---

### Slice 3 — Mobile (`yfw-mobile`): enhanced inbox review (own brainstorm later)

**Goal:** make the existing async inbox a real confirm surface.

Design sketch (detailed brainstorm when we start this slice): keep snap→upload→async
OCR. Upgrade the inbox row and/or `app/expense/[id].tsx` detail to clearly surface the
OCR-extracted fields (vendor, amount, **date, category, tax** — currently only amount +
vendor show in the inbox) under a "Review what we read" framing, with one-tap
**Confirm** (reuse `acceptReview`) and inline **edit** (`updateExpense`) before confirm.
Likely needs only small mobile-API **schema** additions in `apps/expenses/src/lib/api.ts`
to expose any extracted fields not already returned — no new sync endpoint, since
mobile stays async (per the chosen UX). This slice is self-contained in `yfw-mobile`
and ships from its own branch/PR.

---

## Cross-cutting decisions

- **No new "draft" expense status.** Slice 2 persists nothing until confirm; slice 3
  uses the existing expense + review flow. Avoids excluding drafts from every
  report/list/total/dashboard/onboarding-checklist.
- **DRY extraction mapping.** The field-mapping logic is extracted into one pure helper
  used by both the async `apply_ocr_extraction_to_expense` and the new sync scan.
- **Commercial gating.** The OCR engine is `commercial/ai`; every new entry point
  degrades gracefully (`available:false`) when the module/license is absent.
- **Security.** `scan-receipt` reuses the magic-byte validation, extension/type allowlist,
  and 10 MB cap from `upload-receipt`; temp files are always cleaned up.

## Risks

- **Sync extraction latency** (slice 2): a vision-model call inside one HTTP request can
  take several seconds. Acceptable for an explicit "scan" action with a spinner; the
  endpoint inherits the platform's normal request timeout. Mobile avoids this entirely
  by staying async (slice 3).
- **Mapping divergence:** mitigated by the shared `map_extraction_to_fields` helper —
  both paths must produce identical field semantics.
- **Two repos:** slices 1+2 ship from `invoice_app`; slice 3 from `yfw-mobile` with its
  own toolchain (`npx tsc --noEmit` in `apps/expenses`; no test runner wired up).
