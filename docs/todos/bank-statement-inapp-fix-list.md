# Bank Statement (in-app API + UI) — tracked fix list

> Source: consolidated bank-statement review, 2026-05-30.
> `yfw-statement-tools` is tracked separately in `yfw-statement-tools-security-todo.md`.
>
> **Tags:** ✅ = verified against source by reviewer · ⚠️ = corrected/downgraded from
> the raw review · ◻︎ = relayed (plausible, NOT individually verified — confirm before fixing).
>
> Ordered by priority. No code changed yet.

---

## P0 — Verified, high impact

- [x] **EU-format money parsed ~1000× wrong** ✅ **DONE (2026-05-30)**
  `api/commercial/ai/services/ocr_service/_shared.py` — rewrote separator handling:
  decimal separator = whichever of `,`/`.` appears last; single-comma disambiguated by
  3-digit grouping; multi-dot treated as thousands. Fixed second latent bug (`1,234` → was
  `1.234`, now `1234`). Tests: `api/tests/test_parse_number_locale.py` (21 passing,
  run with `--noconftest`). Consumers (`ocr_service`, `extraction`) import clean.

- [x] **External-API rate limiting is a no-op** ✅ **DONE (2026-05-30, statement endpoint)**
  Confirmed stubbed in TWO places: `external_api_auth_service.py:379` AND middleware
  `external_api_auth_middleware.py:289` (both "allow all", fail open).
  **Fix applied:** rewired `ExternalAPIAuthService.check_rate_limits` (the only enforcement
  gate the statement-processing endpoint actually calls — `external_router.py:142`) to
  delegate to the existing **`RateLimiterService`** (`get_rate_limiter()`): Redis
  sliding-window INCR+EXPIRE per minute/hour/day, in-memory fallback, fail-open on limiter
  error. Reuses tested code; single-counted (middleware gate left as-is, so no double count).
  Tests: `api/tests/test_external_api_rate_limits.py` — enforcement verified locally (2
  pass); thin-delegation test runs in Docker/CI (skips locally: needs `stripe` + app env).
  **Scope note / FOLLOW-UP:** the *global* middleware `_check_rate_limits` is still a no-op
  and governs the OTHER external routes (`/api/v1/tools/*`, `/api/v1/external-transactions/*`).
  Wiring it to `RateLimiterService` is the broader change the original option described, but
  it's out of bank-statement scope and must avoid double-counting the statement endpoint
  (which already enforces at the service layer). Track as its own task.

---

## P1 — Cross-cutting (multiple sites, confirm each site then fix once)

- [x] **CSV formula injection** ✅ **DONE (2026-05-30)** — neutralize cells starting with `= + - @ \t \r`
  - API: new `api/core/utils/csv_safety.py` `escape_csv_formula()` (prefixes `'`, leaves
    plain numbers like `-45.67` intact); applied in `external_router.py` `_create_csv_response`.
    Tests `api/tests/test_csv_safety.py` (13 pass).
  - UI: new `ui/src/lib/csv.ts` (`neutralizeCsvFormula`/`csvField`/`csvRow`); `exportToCSV`
    now quotes+escapes ALL fields (was only description/notes). Tests `ui/src/lib/csv.test.ts`
    (15 pass); full `tsc` clean.
  - NOTE: `yfw-statement-tools` `_build_csv` has the same flaw but is the separate client →
    tracked in `yfw-statement-tools-security-todo.md`, not fixed here.

- [x] **Silent bad-date → today substitution** ✅ **DONE (2026-05-30)**
  Shared pure helper `api/core/utils/date_parsing.py` `parse_transaction_date()` returns
  `None` (never fabricates). `BankStatementTransaction.date` is `NOT NULL`, so per site:
  - Worker `bank_statement_handler.py` `_save_transactions`: skips + logs rows with bad
    dates (was `datetime.utcnow()`); `extracted_count` now reflects rows actually saved.
  - Router `transactions.py` `replace_statement_transactions`: validates ALL dates BEFORE
    the destructive delete and returns HTTP 422 with the offending row index (so one bad
    row can't wipe existing data, and dates are never coerced to today). Normal UI flow
    always sends valid ISO (new rows/date-picker), so no UX regression.
  - UI `types.ts` `safeParseDateString` now returns `Date | null`; added `formatRowDate()`
    helper; `StatementDetailView` renders the fallback (`—` / "Pick a date") instead of today.
  Tests: `api/tests/test_transaction_date_parsing.py` (7), `ui/src/pages/Statements/types.test.ts` (5).

- [x] **Float money math** ✅ **DONE (2026-05-30)** — no more accumulation drift in persisted/displayed totals
  - API: new `api/core/utils/money.py` (`round_money`/`sum_money`, Decimal, half-up to cents);
    `statement_rollup_service.build_preview` now uses `sum_money` for the total that becomes
    `Expense.amount`. Tests: `api/tests/test_money.py` (8).
  - UI: new `ui/src/lib/money.ts` (`roundMoney`/`sumMoney` integer-cents/`formatMoney` locale);
    `StatementDetailView` summary cards use `sumMoney`/`roundMoney`; `RollupExpenseModal`
    `formatAmount` + per-debit display use `formatMoney` (fixes `toFixed` edge bug + adds
    thousands grouping). Tests: `ui/src/lib/money.test.ts` (6).

- [ ] **File size checked AFTER full read** ◻︎ — memory-exhaustion DoS
  `api/commercial/ai_bank_statement/external_router.py:119` (`await file.read()` then len check)
  **Fix:** enforce a body-size limit via middleware / streamed chunked read before buffering.

---

## P2 — Authz & input hardening (in-app, tenant-scoped)

- [x] **Recycle-bin authz inconsistency** ✅ **DONE (2026-05-30)**
  Added `require_component_permission` (component levels: viewer<user<admin):
  - `get_deleted_statements` → `viewer` (was no check)
  - `restore_statement` → `user` (matches soft-delete)
  - `permanently_delete_statement` → `admin` (irreversible)
  - `empty_statement_recycle_bin` → `admin` (replaced hand-rolled `role == "admin"`)
  Verified no tenant-admin lockout: `_effective(role, None)` returns the role itself, so a
  `role == "admin"` user resolves to `admin` level with no explicit grant.

- [ ] **Mass-assignment of `invoice_id` / `expense_id` without ownership check** ◻︎
  `routers/transactions.py` `replace_statement_transactions` (~194) and
  `patch_statement_transaction` (~140) accept these from payload unchecked.
  **Fix:** verify referenced invoice/expense belongs to this tenant before writing.

- [x] **Open-string fields that should be enums** ✅ **DONE (2026-05-30, in-app)**
  - `RestoreStatementRequest.new_status` → `Literal["pending","uploaded","processed","failed"]`
    (excludes `processing`/`merged`). Tests: `api/tests/test_restore_status_schema.py` (11).
  - `list_statements` `status` filter → 422 unless in `VALID_STATEMENT_STATUSES`.
  - upload `card_type` → 422 unless `debit`/`credit`/`auto`.
  - FOLLOW-UP: external `format`/`card_type` (`external_router.py`) — same treatment, but
    that's the external API surface; fold into the external-API hardening task.

- [ ] **`created_by_user_id` filter not scoped for non-admins** ◻︎ `crud.py:69-71`
  Mirror the expenses per-user-scope fix (commit `dc90e20b`): non-admin may only filter by
  own id.

- [ ] **Internal `file_path` leaked in responses** ◻︎ `upload.py:217-232`, plus get/list/
  recycle-bin payloads. Mirror commit `9bc753b6` (guarded internal OCR fields). Stop
  serializing `file_path`/`stored_filename`.

- [ ] **Pagination unbounded** ◻︎ `crud.py:47-51, 380-385` — add `Query(ge=0, le=500)`.

- [ ] **reprocess TOCTOU on processing lock** ◻︎ `routers/processing.py:43-108` — acquire
  lock atomically (DB unique constraint / `ON CONFLICT`) before statement reads; merge the
  two fetches.

---

## P2 — Worker / extraction robustness

- [ ] **Processing lock leaked on error path** ◻︎
  `core/services/statement_service/extraction.py:~821,1130` — lock released only on success.
  Move release into `finally`. (Also batch path: `bank_statement_handler.py:~93,194`.)

- [ ] **Greedy/non-greedy JSON array regex grabs wrong fragment** ◻︎
  `extraction.py:~530,1612` — `\[[\s\S]*?\]` non-greedy can match an inner/empty array and
  silently truncate transactions. Use `raw_decode` or greedy-longest-match.

- [ ] **No amount sanity validation on LLM output** ◻︎ `extraction.py:~541` — run parsed
  dicts through `TransactionModel` / bound amount to a plausible range.

- [ ] **`signal.SIGALRM` in async worker** ◻︎
  `commercial/ai_bank_statement/services/bank_statement_ocr_processor.py:55-78` — crashes
  off the main thread / on Windows. Use `asyncio.wait_for` or a thread-pool timeout.

- [ ] **DB session leak** ◻︎ `statement_service/processing.py:418-429` — `next(get_db())`
  without running generator cleanup. Use proper context management.

- [ ] **Cloud-download temp file never cleaned** ◻︎ `bank_statement_handler.py:466-476`
  (`delete=False`, no removal path). Add cleanup after save / on statement delete.

- [ ] **Dedup drops legitimate same-day/same-amount duplicates** ◻︎
  `statement_service/_shared.py:221-224` — include `balance` (or running index) in the key.

- [ ] **2-digit years unparsed** ◻︎ `_shared.py:183-198` `_normalize_date` — add `%y` formats.

---

## P3 — UI correctness & quality

- [ ] **`amount: Number(e.target.value)` → NaN saved to backend** ◻︎
  `StatementDetailView.tsx:673-675` (and balance `686`). Validate `isNaN`; block propagation.

- [ ] **Edit-in-progress overwritten by post-save refetch** ◻︎
  `index.tsx:449-456,487-495` — `saveRows`/`saveAll` end with `openStatement()` which
  `setRows()` over an open edit; the `onBlur` `saveMeta` can also race a running `saveAll`.
  Guard on `editingRow`/`detailLoading`; debounce the notes `onBlur`.

- [ ] **Object-URL leak on unmount mid-fetch** ◻︎ `index.tsx:173-192` — move `!active`
  check before `URL.createObjectURL`, or revoke in the inactive branch.

- [ ] **`window.startStatementPolling` global wiring** ⚠️ (NOT broken — registered at
  `App.tsx:215`; original "polling disconnected" claim was a false positive). Optional
  cleanup: replace the `window` global with context/props for robustness. Low priority.

- [ ] **`confirm()` for destructive actions** ◻︎ `StatementDetailView.tsx:845,895,991,1039`
  — suppressed in sandboxed iframes; use the existing `AlertDialog` pattern.

- [ ] **Sequential deletes, no partial-failure handling** ◻︎ `DuplicateStatementPanel.tsx:37-55`
  (and DuplicateTransactionPanel, bulk delete) — handle per-item errors + invalidate on
  partial completion.

- [ ] **Quality:** two recycle-bin implementations (`RecycleBinSection` vs
  `StatementRecycleBin` page) diverge; `index.tsx` is a 1184-line god component with heavy
  prop drilling; hardcoded i18n strings; index-as-key in transaction tables; fake 2s
  "deletion completed" timeout (`index.tsx:599-615`). Batch as a follow-up refactor.

---

## Dropped / corrected (do not action)
- UI "polling completely disconnected" → **false positive** (App.tsx:215 registers it).
- routers "reject-review cross-tenant IDOR / no permission check" → permission check
  exists (`processing.py:242`); only the `tenant_id` filter is missing, mitigated by
  DB-per-tenant → **LOW** defense-in-depth, not critical.
- routers "restore/permanent delete ANY statement" → tenant-scoped → see P2 MEDIUM above.
