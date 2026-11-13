# Profitability screenshot regression repair

The reported screenshots showed raw `profitability.title`/`profitability.load_error` keys and Unbilled stuck loading. Read-only inspection of the running service at commit fb22043f confirmed both project41 endpoints returned500 because tenant1 lacked `expenses.project_id`. Schema inspection also confirmed `expenses.invoiced` was absent while all six profitability tables existed. Startup uses metadata.create_all and an explicit missing-column reconciler; the new expense mappings were missing from that reconciler.

Changes:
- Reconcile nullable expense project IDs, default-false invoice flags and their project index during the existing tenant startup path, preserving existing data. PostgreSQL column creation is idempotent across replicas.
- Register already-eager plugin locales before first render and resolve the runtime `time-tracking` ID to the `time_tracking` locale namespace for load/unload checks.
- Translate the project tabs and Unbilled view into English, French, Spanish and German. Failed Unbilled queries now show an error/retry action rather than an indefinite loading message.

Validation:
- Five new i18n tests and two Unbilled tests failed before the fixes. All31 selected frontend tests now pass, including existing profitability/cost/cache regressions.
- Legacy-schema startup regression failed before the fix; both startup tests pass afterward and preserve existing assignments/billed flags.
- Executed the actual startup reconciliation function in a disposable PostgreSQL schema twice. Both runs passed; existing amount125.5 remained unchanged and missing fields became NULL/false. Dropped only that disposable schema afterward.
- Clean-source production build passed in1.84s. New test files pass scoped ESLint. Unrelated optional local-plugin build issues remain outside this change.
- Chrome verified complete/incomplete/empty/unauthorized/mobile views, no page errors, no mobile overflow, Unbilled500→retry→success, and French fresh-page loading.

Browser fixtures use actual components and the application's side-effect i18n import with synthetic HTTP responses. Unlike the original browser harness, this harness does **not** manually add translation bundles. These are local preview checks, not a deployed application claim. The French screenshot demonstrates the changed views; unrelated older project-page labels remain English.

- [Unbilled error and retry](unbilled-error.png)
- [French profitability and project tabs](french.png)

The running service was inspected read-only. No production schema changes, restarts, or deployment were performed. Deploying the fixed API and running its normal startup initialization applies the additive expense-column repair; deploy the fixed UI for the translation changes.
