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
