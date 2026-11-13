# Hourly Project Profitability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give tenant admins reliable hourly project contribution estimates with historical cost snapshots and separate invoice/payment reporting.

**Architecture:** Extend the existing time-tracking plugin with private cost models, a shared snapshot service, a pure calculation layer, and a protected profitability API. Persist invoice-line provenance during project invoice creation; return explicit incomplete/unallocated states for data that cannot support reliable totals. Keep public time schemas and optional plugin behavior intact.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL/Alembic, Pydantic, Python Decimal, React/TypeScript, TanStack Query, pytest, Vitest/Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-12-hourly-project-profitability-design.md` (user approved).

## Global Constraints

- First-release cost configuration, profitability endpoints, and cost-bearing breakdowns are tenant-admin-only.
- Zero is a valid explicitly entered cost; missing is not zero.
- A change to a default rate affects newly created entries only.
- All totals are in project currency.
- Warn at 80% and at 100%; no outbound notifications in this release.
- Ordinary existing endpoints remain backward compatible.
- Cross-client comparisons, payroll, cost-to-finish estimates, fixed-fee profitability, retainer accounting, and automatic FX conversion are deferred.
- Preserve unrelated untracked files. Implementation starts on an isolated branch/worktree from current main after checking the approved spec commit is present.
- No production migrations or deployment as part of validation. Prior user guidance places the service at `hao@10.0.0.165:~/dev/yourfinanceworks/`; recheck that memory-derived location before remote checks and use disposable test resources with the exact candidate checkout.

## Review Focus

- Concurrent backfill/cost edits: stale previews must fail without partial updates (Task 2).
- Invoice edits after attribution: added/unmapped lines invalidate allocation rather than retain stale totals (Task 5).
- Contributor deleted or deactivated: snapshots survive and historical costs remain explainable (Tasks 1 and 2).
- Forged cost fields through ordinary time writes/imports: cannot set or reveal privileged values (Task 3).
- Tenant switching with cached UI results: no prior tenant cost data remains visible (Task 6).

## Repository findings and file boundaries

- `api/plugins/time_tracking/router.py` owns manual creation, CSV import, timer start/stop, updates, and project invoice generation. Extend these specific integration points; avoid a broad router rewrite.
- `api/plugins/time_tracking/models.py` stores time billing snapshots but no internal costs. Add private models in `cost_models.py`, imported during plugin model registration.
- `api/core/models/models_per_tenant.py` currently does not map expense `project_id`/`invoiced`, despite migration `007_add_project_fields_to_expenses.py` adding them. Task 1 must reconcile ORM and schema rather than relying on the router's swallowed exceptions.
- `api/core/services/tenant_database_manager.py:migrate_tenant_schema` uses `create_all`, which does not alter existing tables. Use Alembic's tenant mode (`ALEMBIC_DB_TYPE=tenant`, `TENANT_ID`) and `api/scripts/migrate_all_tenants.py` as the operational migration entry point, tested only against disposable tenants.
- Current numbered migration tip is `027_add_net_worth_tables`; verify actual Alembic heads before assigning the new revision parent.
- `api/core/utils/rbac.py:require_admin` checks role without a superuser bypass. Resolve the active tenant membership via existing authentication before invoking it; never trust an unadjusted master role.
- `api/core/routers/payments.py` sums Payment records; `api/core/utils/payment_status.py` derives statuses but is not a refund ledger. Task 5 must report unsupported refund/credit allocation as unavailable, not infer it from a status.
- New backend files: `cost_models.py`, `cost_schemas.py`, `cost_service.py`, `profitability_calculations.py`, `profitability_service.py`, `profitability_router.py`, and `invoice_attribution.py`, all under `api/plugins/time_tracking/`.
- New UI files: `profitability-api.ts`, `profitability-hooks.ts`, `components/ProjectProfitability.tsx`, and `components/ProjectCostSetup.tsx` under `ui/src/plugins/time_tracking/plugin/ui/`.

## Task 1: Persist private costs, expense links, and invoice provenance

**Files:** Create `api/plugins/time_tracking/cost_models.py`, `api/alembic/versions/028_add_project_profitability.py`, `api/tests/test_project_profitability_migration.py`; modify `api/plugins/time_tracking/models.py`, `api/core/models/models_per_tenant.py`, `api/alembic/env.py` and tenant model registration in `api/core/services/tenant_database_manager.py` only as necessary.

**Interfaces:** Produce `ContributorCostRate(user_id, currency, effective_from, hourly_cost, contributor_kind)`, `TimeEntryCost(time_entry_id, method, hourly_cost, currency, source_rate_id, version)`, `TimeEntryCostExpense(time_entry_id, expense_id)`, and `ProjectInvoiceSource(invoice_item_id, project_id, time_entry_id, expense_id)` ORM models. Costs/rates use Numeric(19,6); calculations round at currency precision. Method is `hourly` or `supplier_expense`; absence of a snapshot means unknown. Entry costs are one-to-one; links are unique; invoice source has exactly one source type. Effective rate dates use UTC entry start date with one rate per user/currency/date. Preserve historical rate rows and nullable source references when identities are removed.

- [ ] Write `test_old_tenant_upgrade_preserves_time_and_unknown_costs`, `test_new_tenant_has_same_schema`, and `test_snapshot_and_source_uniqueness`. Assert existing billing amounts remain unchanged, legacy cost count is zero, duplicate snapshots/source links fail, and expense project mapping is queryable.
- [ ] Run `cd api && python -m pytest tests/test_project_profitability_migration.py -q`; confirm failures concern missing models/schema, not unavailable dependencies.
- [ ] Implement the models, ORM expense mapping, registered metadata, and additive migration. Inspect Alembic heads and use the correct parent. Check existing columns before reconciling legacy expense fields. Do not add plugin table foreign keys to core metadata in a way that breaks plugin-disabled startup.
- [ ] Run the migration tests on disposable PostgreSQL databases, including upgrade from the previous revision, new tenant metadata initialization, and plugin-disabled import. Assert contributor deactivation leaves costs unchanged and optional-plugin loading works.
- [ ] Commit only Task 1 files with `feat(time-tracking): persist project cost snapshots`.

## Task 2: Admin cost configuration and audited historical backfill

**Files:** Create `cost_schemas.py`, `cost_service.py`, `profitability_router.py`, and `api/tests/test_project_cost_permissions.py`; modify `api/plugins/time_tracking/__init__.py` to register the new router behind the existing plugin guard.

**Interfaces:** `set_cost_rate(db: Session, actor: MasterUser, payload: CostRateWrite) -> CostRateResponse`; `snapshot_entry_cost(db: Session, entry: TimeEntry) -> TimeEntryCost | None`; `preview_cost_backfill(db: Session, project_id: int, entry_ids: list[int]) -> CostBackfillPreview`; `apply_cost_backfill(db: Session, actor: MasterUser, preview: CostBackfillPreview) -> CostBackfillResult`. Define these request/response types in `cost_schemas.py`; forbid extra request fields. Preview includes entry IDs, dates, duration/version fingerprint, selected effective rates, before/after totals, and a canonical fingerprint. Apply recomputes it under row locks and returns 409 for stale data. Apply fills missing snapshots only.

Protected routes under `/api/v1/projects`: `GET/POST /cost-rates`, `POST /{project_id}/cost-backfill/preview`, `POST /{project_id}/cost-backfill/apply`. Register fixed paths before generic project IDs where routes share a router. Rate listing filters currency and tenant contributor. Tenant admin authorization is required before private queries.

- [ ] Write tests asserting non-admin and global-superuser-with-nonadmin-tenant-role receive 403; foreign tenant/project IDs cannot be linked; negative/nonfinite rates fail; explicit zero succeeds; two effective dates resolve correctly; stale previews return 409 without writes.
- [ ] Run `cd api && python -m pytest tests/test_project_cost_permissions.py -q` and verify expected failures.
- [ ] Implement the interfaces, membership-aware authorization, admin route registration, and audit events. Audit access must not expose rates through ordinary audit responses: record affected IDs/reason in generic audit logs, keep sensitive before/after costs only in admin-accessible storage if needed. Apply backfill atomically; do not auto-commit inside snapshot helpers.
- [ ] Rerun tests, adding repeated apply and deactivated contributor cases: already costed entries remain unchanged and historic snapshots remain readable to admins.
- [ ] Commit scoped files with `feat(time-tracking): add protected contributor cost setup`.

## Task 3: Snapshot all time paths and replace subcontractor estimates safely

**Files:** Modify `router.py`, `cost_service.py`, `cost_schemas.py`, `profitability_router.py`; create `api/tests/test_project_cost_lifecycle.py`.

**Interfaces:** Consume `snapshot_entry_cost`; produce `replace_entry_cost_method(db: Session, actor: MasterUser, entry_id: int, method: str, expense_ids: list[int]) -> TimeEntryCost`. Protected `PUT /api/v1/projects/{project_id}/entry-costs/{entry_id}` accepts explicit replacement method and expense IDs. It validates entry and expenses against the same project and preserves the prior snapshot through an admin-only audit record.

- [ ] Write parametrized tests for manual/import/timer paths: 120 minutes at internal rate 40 gives 80 cost; later defaults do not alter that snapshot; changing duration to 180 gives 120; changing work date retains rate. Nonbillable time still receives costs. Manual zero rates work. Ordinary payloads carrying cost fields cannot change internal costs.
- [ ] Run `cd api && python -m pytest tests/test_project_cost_lifecycle.py -q` and confirm missing behavior fails.
- [ ] Integrate snapshot creation atomically at timer start, manual create, and import; calculate timer cost from the snapshot on stop. Reuse the original snapshot for duration/date corrections. Keep cost data absent from existing serializers, monthly exports, and MCP outputs.
- [ ] Implement replacement with same-project expense links; supplier mode has no hourly charge. Reject missing links at write time; handle subsequently recycled/deleted expenses as unresolved at read time. One expense may cover several entries but contributes only once. Reject cross-project links and conflicting cost modes.
- [ ] Rerun lifecycle tests, including a transaction failure after entry insert, multiple linked entries, cross-project expenses, expense recycling, and no cost leakage through ordinary API/export/MCP schemas.
- [ ] Commit with `feat(time-tracking): preserve labor costs across time workflows`.

## Task 4: Calculate contribution and expose complete/incomplete states

**Files:** Create `profitability_calculations.py`, `profitability_service.py`, `api/tests/test_project_profitability.py`; modify `cost_schemas.py`, `profitability_router.py`.

**Interfaces:** Define `ProjectProfitabilityInput` and `ProjectProfitabilityResponse` in `cost_schemas.py`. `calculate_profitability(data: ProjectProfitabilityInput) -> ProjectProfitabilityResponse` is pure. `get_project_profitability(db: Session, project_id: int) -> ProjectProfitabilityResponse` loads tenant records and calls it. Protected `GET /api/v1/projects/{project_id}/profitability` returns currency, work_value, known_cost, contribution/margin nullable, missing_hours, unresolved/excluded record lists with reason codes, contributor/task hourly-cost breakdowns, expense bucket, and budget percentages/warnings. Non-hourly projects return `unsupported_billing_method`, not hourly estimates.

- [ ] Write `test_hourly_contribution_example` with assertions `work_value == Decimal('1000')`, `known_cost == Decimal('580')`, `contribution == Decimal('420')`, `margin_percent == Decimal('42')` for the spec's ten billable/two nonbillable hours. Add missing/zero costs, zero revenue, negative contribution, active timers, exact 80%/100% thresholds, no budgets, non-hourly projects, and mixed currencies.
- [ ] Run `cd api && python -m pytest tests/test_project_profitability.py -q` and confirm failures.
- [ ] Implement Decimal calculations, currency rounding using the repository's existing money conventions, and data loading without N+1 queries. Use all completed hours for hour budgets, billable work value for amount budgets. Supplier expense links reconcile into one expense bucket, not fake contributor allocations.
- [ ] Implement expense eligibility using `Expense.status` and current approval cycle records in `ExpenseApproval`; inspect `api/commercial/workflows/approvals/services/approval_service.py` to align final outcomes. Recorded/no-required-approval and finalized approved records count; rejected/cancelled/deleted records are excluded visibly; pending/unknown/missing-amount/draft OCR costs prevent a complete margin. Use core stored approval state without making commercial imports mandatory.
- [ ] Run tests including resubmitted approval cycles, multiple approvers with one pending, an explicit zero expense, tax amount versus total amount, supplier-linked rejected expenses, and breakdown reconciliation. Every uncovered expense/state has a reason rather than a silent zero.
- [ ] Commit with `feat(time-tracking): calculate project contribution and cost coverage`.

## Task 5: Attribute invoice and cash totals conservatively

**Files:** Create `invoice_attribution.py`, `api/tests/test_project_invoice_attribution.py`; modify `router.py`, `profitability_service.py`, `cost_schemas.py`.

**Interfaces:** `record_project_invoice_sources(db: Session, project_id: int, sources: list[ProjectInvoiceSource]) -> None`; `get_project_billing_summary(db: Session, project_id: int) -> ProjectBillingSummary`. Define `ProjectBillingSummary` in `cost_schemas.py` with unbilled_work_value, invoiced_pre_tax, collected_cash, currency, attributed_invoice_ids, unresolved_invoice_ids/reasons, and completeness flags. Attach this object to the profitability response.

- [ ] Write tests asserting two entries on one 1,000 invoice count 1,000 once; a 300 partial payment produces collected_cash 300 regardless of status; expense-only invoices get provenance; mixed/unmapped invoices are unresolved; changed/deleted invoice lines invalidate full attribution.
- [ ] Run `cd api && python -m pytest tests/test_project_invoice_attribution.py -q` and confirm failures.
- [ ] Persist sources in the existing invoice-generation transaction after invoice item IDs exist. Do not change pricing. Validate selected source/project relationships; all source rows and invoice creation roll back together on failure.
- [ ] Implement unique-invoice aggregation and per-read provenance validation. Use invoice net subtotal/discount conventions from existing invoice schemas/calculation code and actual Payment rows, never time amounts as final invoice revenue or a status as cash. Recognize only fully attributed, eligible, single-project invoices with matching currency. Preserve time-value estimates independently.
- [ ] Leave legacy invoices unresolved unless every line has verifiable provenance; never parse descriptions as proof. For cancelled/refunded/credit-adjusted invoices without a supported ledger allocation, return explicit unavailable reasons and partial known totals. Do not invent a refund ledger. Payment removal updates cash on the next read.
- [ ] Rerun tests with discounts, tax-inclusive collected cash labels, negative payment/refund representations supported by the current API, mismatched payment currency, recycled invoices, source edits, and a source-insert transaction failure.
- [ ] Commit with `feat(time-tracking): attribute project invoices and collections`.

## Task 6: Protected profitability and cost setup interface

**Files:** Create the four UI files listed in File boundaries plus `components/ProjectProfitability.test.tsx` and `components/ProjectCostSetup.test.tsx`; modify `ui/src/pages/projects/ProjectDetailInternal.tsx` and plugin locale files `en.json`, `fr.json`, `de.json`, `es.json`.

**Interfaces:** `getProjectProfitability(projectId: number): Promise<ProjectProfitabilityResponse>` and typed rate/backfill/replacement API methods in `profitability-api.ts`; `useProjectProfitability(projectId: number)` and cost mutations in `profitability-hooks.ts`. `ProjectProfitability({projectId}: {projectId: number})` renders the protected tab; `ProjectCostSetup({projectId}: {projectId: number})` owns contributor rates, snapshot preview/apply, and supplier replacement controls. Types mirror backend nullable values and reason codes; never coerce null into zero.

- [ ] Write Testing Library tests for complete 1,000/580/420/42% display, incomplete margin, zero value, fixed-cost unsupported state, forbidden reads, and separate invoice/cash labels. Cost setup tests assert apply requires preview, stale preview needs refresh, and supplier replacements list their affected entries.
- [ ] Run from `ui`: `npx vitest run src/plugins/time_tracking/plugin/ui/components/ProjectProfitability.test.tsx src/plugins/time_tracking/plugin/ui/components/ProjectCostSetup.test.tsx`; confirm expected failures.
- [ ] Add the tab only for active-tenant admins; disable private queries without that authorization. Use existing query key conventions with explicit tenant identity plus project ID; never retain previous-tenant cost results during switching. Invalidate on rate, backfill, replacement, time, expense, invoice, and payment mutations affecting the view; refetch on focus to cover edits elsewhere.
- [ ] Implement cards, source-linked breakdowns, expense bucket, incomplete/excluded reason lists, rate forms, and preview/apply controls using existing components. Explain cost basis and owner opportunity cost. Expose historical corrections only via authorized cost setup. Display invoice and payment completeness independently from cost coverage.
- [ ] Add translations to all four plugin locales. Rerun tests including tenant-switch cache isolation and role revocation while the view is open; run `npm run build` and applicable lint.
- [ ] Commit with `feat(ui): add hourly project profitability and cost setup`.

## Task 7: Verify end-to-end invariants and document delivery

**Files:** Create `api/tests/test_project_profitability_integration.py`, `docs/features/PROJECT_PROFITABILITY.md`; update `docs/todos/TIME_TRACKING_NEXT_FEATURES_TODO.md` only for verified completed work.

**Interfaces:** Exercise the existing HTTP routes plus Tasks 2–5's new routes using real tenant database fixtures and mocked external services. No new production interface.

- [ ] Add an integration flow: configure two contributors, create/import/stop time, record expenses, replace subcontractor cost, preview/apply a legacy rate, generate invoice, register partial payment, then verify the profitability response. Assert tenant B and a normal contributor cannot read cost information.
- [ ] Run from `api`: `python -m pytest tests/test_project_profitability_migration.py tests/test_project_cost_permissions.py tests/test_project_cost_lifecycle.py tests/test_project_profitability.py tests/test_project_invoice_attribution.py tests/test_project_profitability_integration.py -q`. Require all focused tests to pass and distinguish environment setup failures from behavior failures.
- [ ] Run frontend tests from Task 6, `npm run build`, and `npm run lint` in `ui`; document pre-existing failures with comparison evidence rather than silently ignoring them.
- [ ] Exercise actual UI with complete, incomplete, empty, and unauthorized fixtures. Capture screenshots; verify ordinary time entry, invoice generation, exports, and client portal still function without costs leaking. Run migrations only on disposable old/new tenants; verify the candidate source SHA used for every remote test.
- [ ] Document cost basis, supplier expense bucket, legacy backfill, permissions, unsupported fixed/retainer mode, and unallocated payment limitations. Update the existing TODO accurately. Assess whether release/version changes are warranted; do not publish or deploy without authorization.
- [ ] Commit documentation and integration tests, request a whole-branch review, resolve findings, and report validation plus any untested live-service boundary. Do not merge or deploy as an incidental planning action.

## Plan self-review

Covered all approved design sections: costs/permissions (1–3), historical behavior (2–3), supplier replacement (3–4), contribution and budgets (4), invoice/cash attribution (5), interface and localization (6), migrations and delivery evidence (1,7). Each Review Focus condition has an owning test task. Fixed-price/retainer scope remains deferred. Known repository gaps are handled explicitly, rather than assuming a full refund ledger or working expense ORM mapping already exists.

Execution used the user-approved subagent-driven method. Tasks 1–7 are implemented and independently reviewed. The original checklists above retain the planned commands; actual commands, test coverage, justified substitutions, and unverified boundaries are recorded in [the validation report](../../test-reports/project-profitability-2026-11-12/VALIDATION.md). In particular, focused backend runs use `--noconftest`, and live client portal/provider/middleware behavior was not claimed. Whole-branch review and the scoped final-fix re-review are complete: all four findings addressed, no remaining blocking issues. Implementation is ready for integration; no push, merge, deployment, or production migration has occurred.
