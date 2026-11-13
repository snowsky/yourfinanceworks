# Task 7 — backend integration and delivery evidence

## Result and source identity

Implementation commit: `2958cb7078451a729543060726b26e893aa4f2a9`, based on `5db4b992`. No push, merge, release, or deployment. Documentation/screenshots/localized reason text: `a773f96b6fa1a20ebc018b16a599bd5548b7ba31`; final build documentation: `569dd866` (HEAD). Production/test source remains `2958cb70`.

Remote tests used the existing `yourfinanceworks-api:latest` image ID `sha256:f3e54079e8b0665a8da9419e2471b84c23043fa0640fb43897bea3d01d23f54e`. Candidate source was mounted readonly at `/candidate`; Python path explicitly prioritized `/candidate/api` and the copied pytest runner. No packages were installed. Importing the real router and authentication dependency succeeded with isolated nonproduction secrets. The shared API conftest was never loaded (`--noconftest`).

Full focused run: candidate `/tmp/yfw-profitability-xz3dwgya/task7-source`, **113 passed, 21 existing dependency/schema deprecation warnings in 138.31s**, cwd `/candidate/api`. Production API source in that directory matches the committed `2958cb70` archive. Final comparison showed only excluded tracked `.env` example files and the subsequently added query-scaling test differing; the strengthened concurrent-backfill test was copied and verified separately. Committed archive `git archive 2958cb70 api` SHA256 is `74ab635cccec593dc3a7510e2c6285d57668e9b3fc7d4aed2ac1aef07c0d4864`, extracted separately at `/tmp/yfw-profitability-xz3dwgya/2958cb70`. Its newly added query test passed in the remote image (1 passed, 1.74s).

## Implemented verification and small fixes

- New integration file imports actual FastAPI routers and uses actual JWT validation, actual `get_current_user`, actual tenant `get_db`, and real isolated master/two-tenant ORM databases. Only database factories are redirected; authentication is never overridden. It exercises two contributor rates, manual creation, CSV import, timer start/stop, supplier replacement, legacy preview/apply, invoice generation, canonical partial-payment records, and the final profitability read. It verifies unauthenticated/invalid tokens, ordinary-member cost denial, cross-tenant selection denial, foreign tenant absence, ordinary API responses, and CSV export without private cost fields. The fixture's tenant-context middleware substitutes for full application tenant middleware; this does not claim verification of the complete application middleware stack.
- Actual disposable PostgreSQL test invokes Alembic `env.py`, stamps 027, upgrades through 028/029/030, preserves legacy monetary rows/unknown costs, and checks additive table column/nullability parity with new-tenant metadata. Each run creates and drops a uniquely named disposable schema, never shared service schemas. Earlier tests separately create new-tenant ORM tables and compare the migration schema.
- PostgreSQL transaction races: synchronize two actual rate inserts after both pass existence checks; exactly one succeeds and the other returns 409. A savepoint now translates the unique-key race to the friendly conflict without masking unrelated integrity errors. A strengthened test simultaneously applies one two-entry preview twice; project/entry locking yields one application and one stale-preview 409, with both snapshots present exactly once. **Strengthened test: 1 passed in 4.55s**.
- HTTP multi-entry stale preview test changes one selected entry and proves neither receives a snapshot after 409.
- Source uniqueness now checks distinct invoice lines attempting to reuse one time/expense source. Plugin-absent subprocess exercises actual loader model import/router registration and metadata creation.
- Tests resolve repository sources from `__file__`, supporting the specified `cd api` command. Removed brittle creation-path spelling assertions now superseded by HTTP behavior.
- Billing reads batch invoices/items/provenance/payments, retaining the existing low-query empty-invoice path. Status reasons distinguish unsupported ordinary invoice states from credit/refund states. Query-scaling regression verifies a constant number of queries from 1 to 12 invoices.
- Controller browser checks found async time-entry links could need scrolling after rows loaded. Added a location-aware, tested hook selecting Time Entries and scrolling when the row exists. Existing row anchors are retained. Invoice links use canonical `/invoices/view/:id` (the older route also redirects correctly).
- Controller mobile check found header actions/tabstrip overflow. Project actions wrap; the tab strip scrolls inside its bounded width. No broad shared-layout redesign.

## Commands and results

Remote container environment: `PYTHONPATH=/candidate/api:/test-runner PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 LICENSE_PUBLIC_KEY_V2=test SECRET_KEY=profitability-isolated-test-secret-not-production JWT_SECRET_KEY=profitability-isolated-test-secret-not-production DATABASE_URL=postgresql://postgres:task1-disposable@127.0.0.1:5432/postgres UPLOAD_PATH=/tmp/attachments`. PostgreSQL tests additionally set the explicit `PROFITABILITY_TEST_DATABASE_URL` to that disposable URL and use `--network container:yfw-profitability-task1-pg`. HTTP-only/query tests use `--network none`; HTTP fixture databases are disposable SQLite files.

From `/candidate/api`:

```sh
python -m pytest --noconftest -o addopts= -o cache_dir=/tmp/pytest-cache \
  tests/test_project_profitability_migration.py tests/test_project_cost_permissions.py \
  tests/test_project_cost_lifecycle.py tests/test_project_profitability.py \
  tests/test_project_invoice_attribution.py tests/test_project_profitability_integration.py -q
```

**113 passed**. Separate final additions: concurrent rate/backfill test **1 passed**; committed query-scaling regression **1 passed**. All 114 current cases have passing evidence, though the final extra test was deliberately run focused rather than repeating the two-minute HTTP fixture suite. Initial actual HTTP/auth-only run: **4 passed in 120.34s**.

Local cwd `api`, copied venv, plugin autoload disabled, same first five files: **107 passed, 2 skipped in 5.36s** before the final extra query test (which passed independently). Skips require explicit disposable PostgreSQL configuration. Local environment lacks some production dependencies, so real HTTP imports use the production-dependency image instead. No dependency installs attempted.

Red/green: introduced batching initially exceeded the existing no-invoice query budget (11 versus at most 7); restored the no-invoice fast path and the focused suite passed. For the new scaling regression, temporarily restoring the pre-fix `5db4b992` attribution module produced **1 failed**, 41 queries for 12 invoices versus 8 for one. Restoring the committed batching implementation produced **1 passed** (0.65s). No claim of a pre-fix red run is made for the concurrency/HTTP tests.

Frontend: existing local binary `ui/node_modules/.bin/vitest run` over `ProjectProfitability.test.tsx`, `ProjectCostSetup.test.tsx`, `profitability-hooks.test.tsx`, and `useProjectEntryLink.test.tsx`: **4 files, 18 passed in 1.51s**. Scoped ESLint of the new hook/test and profitability component passes. ProjectDetail retains its pre-existing three `no-explicit-any` findings; no new ones were added. `git diff --check` passes.

Task 6 independently compared full lint baseline/current at **1,377 existing problems** and reproduced root build failures from unrelated untracked statement-tools imports against archived unchanged source. Its clean-source build passed. Controller final clean-source `npm run build` completed with exit 0 in 1.75s on the integration-stage source, with existing dynamic-import warnings. See Task 6 report for comparison commands/logs.

## Browser evidence and boundaries

Controller captured five actual Chrome screenshots using source components/hooks/translations/styles with synthetic HTTP fixtures: complete, incomplete, empty, ordinary-member unauthorized, and 390px mobile. After the scoped responsive fixes, all scenarios had zero page errors and the mobile document stayed within viewport width. Screenshots and their exact fixture boundary are in `docs/test-reports/project-profitability-2026-11-12/README.md`. This is real browser presentation and frontend authorization handling, not a deployed backend browser session.

Partial payment is registered via the canonical tenant Payment ORM model in the HTTP integration flow. The independently licensed/notification-bearing payment HTTP route is not mounted by that isolated app. Expenses are likewise seeded ORM records rather than exercising the separate expense-creation HTTP router. Ordinary time creation/import/timer and project invoice generation are actual HTTP routes. Generic monthly time export is actual HTTP. Client portal/MCP/notification runtime was not exercised by this task; source/schema exclusions and prior focused checks are narrower evidence. Full production middleware, live-service tenant migration, real provider integrations, and customer data were not touched.

Feature documentation describes operational cost basis, supplier expense reconciliation, missing-only historical backfill, authorization, unsupported fixed/retainer modes, and unallocated invoice/payment limitations. TODO records implemented branch scope without claiming deployment. This feature and migrations warrant a normal feature release/version assessment and release notes; no publishing is authorized here. Whole-branch review remains the controller's next gate.

Controller reported independent Task 7 review approved with no Critical/Important findings; whole-branch review is in progress.


# Final review fixes

# Final review fixes

Base: `569dd866`, branch `feat/hourly-project-profitability-local`. One focused fix wave addresses the two Important and two Minor final-review findings. No push, deployment, production migration, dependency installation, or release.

## Changes

- **Important 1:** `TimeEntryCostExpense.expense_id` now preserves the historical expected expense ID independently of the live expense row. Migration031 removes only the cascading expense foreign key, retaining the entry FK and all existing link rows; new-tenant metadata matches. Existing protected replacement validation still requires active, same-project, matching-currency expenses. A missing expected ID keeps supplier time unresolved even when another linked expense survives. Explicit administrator replacement removes obsolete links and retains their IDs in private revision history.
- **Important 2:** private billing summaries now expose `expense_reimbursements_pre_tax` separately. Fully attributed expense-line amounts receive their proportional share of supported invoice discounts according to pre-discount line amounts. Each invoice's resulting reimbursement is rounded to project-currency precision. Unsupported/incompletely attributed invoices contribute no reimbursement; previously known invoices retain known totals with an incomplete indicator. Time work value and contribution are unchanged. The UI labels pre-tax/after-discount amounts and discloses the allocation basis in all four existing locales.
- **Minor 1:** rate save, preview, apply, supplier replacement, and hourly restoration each have localized action-specific failure guidance. Only an apply409 receives stale-preview refresh guidance. Multi-entry replacement errors acknowledge that not all selected entries may have succeeded.
- **Minor 2:** setup forms, action handlers, contributor/task breakdowns, and billing JSX are expanded for reviewability, with no redesign. Feature documentation records reimbursement rules and migrations028–031.

## Verification

Never loaded the shared destructive API conftest. Local backend environment prefix for all commands:

```sh
PYTHONPATH=api PYTHONDONTWRITEBYTECODE=1 LICENSE_PUBLIC_KEY_V2=test PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
/private/tmp/yfw-profitability-venv/bin/python -m pytest --noconftest -o addopts= -o cache_dir=/tmp/yfw-final-cache
```

1. Prefix plus `api/tests/test_project_cost_permissions.py api/tests/test_project_cost_lifecycle.py api/tests/test_project_profitability.py api/tests/test_project_invoice_attribution.py api/tests/test_project_profitability_migration.py -q`: **116 passed, 2 skipped in 5.89s**. The two skips require explicit disposable PostgreSQL configuration. This covered the new FK-enabled soft-delete→hard-delete of one of two supplier links, retained missing coverage, and explicit relink recovery with private history; six mixed/expense-only percentage/fixed/capped-discount cases; actual migrated expense deletion; and existing feature regressions.
2. After strengthening assertions to check unchanged time work value, partial known reimbursement totals, and metadata FK parity, prefix plus `api/tests/test_project_invoice_attribution.py api/tests/test_project_profitability_migration.py -q`: **49 passed, 1 skipped in 3.22s**. This adds one parameterized expense-only known-total case.
3. After further strengthening the migration regression to insert both links **before** migration031, prefix plus `api/tests/test_project_profitability_migration.py::test_migrated_supplier_evidence_survives_actual_expense_delete -q`: **1 passed in 0.51s**. Both pre-existing rows survive table migration and the subsequent actual delete.

Remote candidate source: `/tmp/yfw-profitability-xz3dwgya/final-source`, readonly `/candidate`. Existing API image `yourfinanceworks-api:latest` and existing copied pytest runner; no package installs. Disposable PostgreSQL container `yfw-profitability-task1-pg`, never application databases. Command wrapper:

```sh
ssh -o BatchMode=yes -o ConnectTimeout=10 hao@10.0.0.165 \
'docker run --rm --network container:yfw-profitability-task1-pg \
-v /tmp/yfw-profitability-xz3dwgya/final-source:/candidate:ro \
-v /tmp/yfw-profitability-xz3dwgya/runner:/test-runner:ro -w /candidate/api \
-e PYTHONPATH=/candidate/api:/test-runner -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
-e PYTHONDONTWRITEBYTECODE=1 -e LICENSE_PUBLIC_KEY_V2=test \
-e SECRET_KEY=profitability-isolated-test-secret-not-production \
-e JWT_SECRET_KEY=profitability-isolated-test-secret-not-production \
-e DATABASE_URL=postgresql://postgres:task1-disposable@127.0.0.1:5432/postgres \
-e PROFITABILITY_TEST_DATABASE_URL=postgresql://postgres:task1-disposable@127.0.0.1:5432/postgres \
-e UPLOAD_PATH=/tmp/attachments yourfinanceworks-api:latest \
python -m pytest --noconftest -o addopts= -o cache_dir=/tmp/pytest-cache TEST_FILES -q'
```

- `TEST_FILES=tests/test_project_profitability_migration.py tests/test_project_profitability.py tests/test_project_invoice_attribution.py`: **82 passed in 19.75s**. Actual Alembic env.py traversal027→031, PostgreSQL migrated delete, new-tenant metadata, and all new calculation/relink tests passed. Remote source includes all final production changes; the later test-only assertion strengthening and extra parameterized case above were verified locally.

Red/green proof: extracted `git archive 569dd866 api` to `/private/tmp/yfw-final-red-mjvaz7ov`, copied only the two new test files, and ran the supplier soft→hard-delete test and mixed fixed-discount reimbursement test with the same isolated local Python/environment. **2 failed in 0.84s**, respectively falsely complete supplier coverage and missing reimbursement field. Ran those exact node IDs against the final candidate: **2 passed in 0.76s**. No candidate source was temporarily reverted.

Frontend commands from `ui`:

```sh
node_modules/.bin/vitest run \
 src/plugins/time_tracking/plugin/ui/components/ProjectProfitability.test.tsx \
 src/plugins/time_tracking/plugin/ui/components/ProjectCostSetup.test.tsx \
 src/plugins/time_tracking/plugin/ui/profitability-hooks.test.tsx \
 src/plugins/time_tracking/plugin/ui/useProjectEntryLink.test.tsx
node_modules/.bin/eslint \
 src/plugins/time_tracking/plugin/ui/components/ProjectCostSetup.tsx \
 src/plugins/time_tracking/plugin/ui/components/ProjectCostSetup.test.tsx \
 src/plugins/time_tracking/plugin/ui/components/ProjectProfitability.tsx \
 src/plugins/time_tracking/plugin/ui/components/ProjectProfitability.test.tsx \
 src/plugins/time_tracking/plugin/ui/profitability-api.ts
```

**4 files, 26 tests passed in 1.60s**; scoped lint exit0 with no output. The error matrix covers apply409 refresh guidance, apply500/403, preview500/409, rate-save409, supplier-replacement409, and hourly-restore409. Reimbursement UI regression checks the separately labeled amount, basis explanation, and unchanged work-value headline. Existing Vite configuration warnings remain. `git diff --check` passes.

Controller independently reports final clean-source frontend build exit0 in 2.52s and all five Chrome fixture states with zero page errors/mobile overflow false. Controller inspected the mobile screenshot's separate reimbursement and allocation explanation and owns the refreshed screenshots/source README commit. These are frontend synthetic-HTTP presentation checks, not deployed-service verification. Existing Task7 integration boundaries still apply; no claim of full middleware, payment/expense-creation HTTP, MCP/portal/notification runtime, or deployed tenant migration coverage.

- Same remote wrapper with `TEST_FILES=tests/test_project_cost_permissions.py tests/test_project_cost_lifecycle.py tests/test_project_profitability_integration.py`: **40 passed, 21 existing dependency/schema deprecation warnings in 122.51s**. This includes actual authenticated HTTP profitability reads, source creation/import/timers/invoice workflow, tenant authorization, private-schema boundaries, and disposable PostgreSQL concurrency. All final production files were present.

All four final-review findings are addressed; no known blocking finding remains in this fix wave. Controller owns the single scoped rereview and integration decision. The feature and migrations warrant the normal feature-release/version assessment, without publishing authorization.

Controller verification of final UI72538ad1: clean-source production build exited0 in2.52s; all five Chrome scenarios had zero page errors and390px mobile had no horizontal overflow. Updated screenshots include the reimbursement amount and discount basis.

Final independent scoped review of569dd866..72538ad1: ready to merge; all four findings addressed, no new blocking issues. Migration031 downgrade deliberately fails if missing-expense evidence exists; rollback requires deliberate reconciliation. Reviewer inspected code/tests but did not rerun them.
