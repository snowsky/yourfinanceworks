# Time Tracking Next Features TODO

## Hourly Project Profitability — Implemented, Delivery Verification in Progress

See [feature documentation](../features/PROJECT_PROFITABILITY.md) for cost basis, rate snapshots/backfill, supplier replacements, permissions, and invoice/payment attribution limits.

Implemented in the feature branch:

- Tenant-admin profitability tab with time work value, known delivery costs, contribution, margin, coverage, budgets, contributor/task hourly costs, and a separate expense bucket.
- Effective-dated contributor costs, creation/import/timer snapshots, explicit legacy backfill preview/apply, and supplier expense replacement without double counting.
- Distinct unbilled work, pre-tax invoiced value, and actual attributed collections, with explicit incomplete/unallocated states.
- Hour/amount budget warnings at 80% and 100%; localized explanation and unsupported fixed-price state.

Do not mark deployed or end-to-end verified until the delivery report records the corresponding evidence. API HTTP/auth, migration, frontend, browser, and deployed-service checks are separate boundaries.

### Deferred Profitability Work

- Fixed-fee and retainer accounting.
- Profitability exports and cross-client rankings.
- Cost-to-finish forecasts, payroll integration, and cross-project supplier allocation.
- Fully allocated per-contributor margins and reliable historical/mixed-project payment allocation.
- Task burn warnings and outbound budget notifications.

## Other Strong Candidates

### Kanban Polish

- Editable Kanban columns
- Intra-column drag ordering
- Saved board filters
- Labels and quick filters for priority, due date, and custom fields

### Convert Kanban Tasks to Invoice Line Items

- Select completed task cards
- Generate invoice lines from logged time, estimated time, or fixed task amount
- Preserve links from invoice items back to project tasks

### Client Project Status Portal

- Share read-only project status through a secure link
- Show milestones, approved time, invoice status, and high-level progress
- Use existing share-token/security patterns before exposing project data

### AI Time Entry Cleanup

- Detect vague descriptions, unusual durations, missing tasks, or billing anomalies
- Suggest corrected task assignment and descriptions before invoicing
- Keep suggestions reviewable, not automatic
