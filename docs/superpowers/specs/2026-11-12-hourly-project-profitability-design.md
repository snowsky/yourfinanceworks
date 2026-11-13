# Hourly-first project profitability

Status: approved by the user on 2026-11-12 for implementation planning. Research baseline: local main at 2ec792dd. Implementation plan: `docs/superpowers/plans/2026-11-12-hourly-project-profitability.md`.

## Intent and agreed scope

Help freelancers and agencies understand the economics of client projects before all work is invoiced. The user primarily bills hourly, also wants fixed-price and retainer support eventually, and tracks their own work, employees, and subcontractors. They selected hourly-first profitability over implementing every billing model immediately.

Success means an authorized owner can explain a project's billable value, delivery costs, estimated contribution margin, budget usage, and collection status from linked records. Numbers must remain understandable when costs are missing or invoices differ from recorded time.

## Approaches considered

1. **Hourly-first profitability (selected):** individual cost rates, existing billing rates, expenses, margin, budget warnings, and separate billing/collection information. Builds on existing project workflows and delivers value sooner.
2. **All billing models together:** also implement fixed fees, retainer allowances, overages, and rollover. More comprehensive but introduces substantially more billing and recognition rules.
3. **Full agency finance:** add capacity planning, utilization, and forecasting. Broadest scope and highest maintenance burden.

## Current implementation evidence

- `api/plugins/time_tracking/models.py`: projects already have hourly/fixed_cost billing methods, hourly rates, fixed amounts, hour and amount budgets, and a currency. Time entries store their user, duration, billing rate, computed amount, billable flag, and invoice link. No internal labor cost field exists there.
- `api/plugins/time_tracking/router.py`: project summary aggregates time, expenses, and budgets; invoice generation links time and selected expenses to an invoice. Do not interpret existing summary totals as a cost-aware margin calculation.
- `ui/src/pages/projects/ProjectDetailInternal.tsx`: overview, tasks, Kanban, time entries, and unbilled workflows already exist. The overview presents time value and budget usage.
- `docs/todos/TIME_TRACKING_NEXT_FEATURES_TODO.md` already identifies profitability as the recommended next feature.
- The plugin advertises a profitability summary, but the reviewed summary schema contains no labor cost or margin fields.

These are source observations, not verification of the deployed application.

## Proposed first release

Add a protected project profitability view and a cost setup workflow. Show billable work value, known delivery cost, estimated contribution and margin percentage, billable/nonbillable hours, cost coverage, and existing budget usage. Include expandable breakdowns by contributor and task, linking back to time and expense records.

Show unbilled work, invoiced amounts, and collected amounts separately. They are different measures, not three numbers to add together. Label estimated work value distinctly from invoice revenue and cash receipts. Use localized labels and explanatory text, including incomplete-data states.

The first release covers individual projects. Cross-client rankings, CSV profitability exports, cost-to-finish forecasting, new billing-rate precedence rules, payroll integration, automated invoice changes, fixed-fee profitability, and retainer accounting are deferred. Existing fixed-cost projects remain usable; their new profitability view explicitly says hourly profitability is unavailable for that billing method.

## Contributor costs and historical behavior

Proposed defaults below are design choices, not additional user requirements:

- Use existing tenant user identities for tracked contributors. Optional labels distinguish owner, employee, and subcontractor; labels do not grant permissions. Contractors without application accounts can still be represented by project expenses.
- Define effective-dated hourly internal cost rates per contributor and currency. Owner time may have an explicit opportunity-cost rate. Employee rates are manually entered loaded-cost estimates, not payroll calculations.
- Resolve the rate using the entry's work date at manual creation/import or timer start. Snapshot rate, currency, source, and cost method onto each entry. Timer completion computes cost from that snapshot. All creation paths must use the same logic.
- A change to a default rate affects newly created entries only. Duration corrections recompute cost using the existing snapshot. Date changes retain the snapshot unless an authorized user explicitly reprices it. Existing billing-rate snapshots remain unchanged.
- Legacy entries begin with unknown cost. Provide an admin-only preview and apply operation to assign missing cost snapshots to selected entries. Show affected entries, dates, rates, and totals; audit every application. Never silently reprice history or overwrite existing snapshots in this operation.
- Zero is a valid explicitly entered cost; missing is not zero. When any eligible time lacks a cost, show known costs and missing hours, but withhold the headline complete margin and explain why.
- Use decimal monetary calculations and currency precision. Do not introduce new floating-point cost storage just because legacy billing fields use floats.

## Subcontractors and duplicate costs

Each costed time entry has one cost method: hourly rate or supplier expense. Supplier-expense mode requires explicit links to project expenses covering those entries; it contributes no hourly labor cost. Each expense contributes its amount once regardless of the number of linked entries. Mark hourly estimates as replaced by the linked expense when switching methods, retain the audit history, and prohibit simultaneous hourly and supplier-expense costing for an entry.

An expense can cover multiple entries in the same project. Cross-project allocation of one supplier bill is deferred: users must allocate it into separate project expense records without duplicating the source total. Contractor expense records may also stand alone when no time is tracked. Unlinked supplier-mode entries make coverage incomplete. Deleting/recycling a linked expense restores an incomplete state, rather than a zero-cost result. Arbitrary duplicate manual expense records remain subject to existing duplicate review; the feature cannot infer all duplicates reliably.

Keep all expense costs in a separate project-expenses bucket in contributor/task breakdowns, including supplier replacements. Show links from affected entries to that bucket, not duplicated or invented per-person allocations. Thus contributor/task hourly costs plus the expense bucket reconcile to project cost; do not show a fully allocated per-person margin in this release.

## Calculation contract

- Include completed/logged/approved/invoiced entries; exclude active timers and deleted/ineligible records. Count nonbillable time as cost but never as billable work value.
- Billable work value = sum of completed billable entry durations multiplied by their stored billing rates. Handle explicit zero rates correctly.
- Known delivery cost = costed completed time plus eligible project expenses, applying the supplier-expense replacement rule above. Use the recorded project expense amount consistently and disclose that this is an operational contribution estimate, not statutory net profit or tax reporting.
- Eligible expenses are active project-linked recorded expenses that require no approval, or expenses whose required approval has completed successfully. Exclude rejected/cancelled/deleted expenses with visible counts. Pending approvals, OCR drafts, unknown statuses, missing amounts, and currency mismatches appear as unresolved costs and prevent a complete margin. An explicit zero amount is valid. Resolve actual status names through the existing workflow during planning; never infer approval from payment alone. Use `amount` as the first-release cost basis, matching the current project summary, and label the basis rather than inconsistently substituting `total_amount`.
- Estimated contribution = billable work value minus complete delivery cost. Margin percentage = contribution / billable work value; show unavailable when the denominator is zero. Negative contribution is valid.
- Expense reimbursements are not silently added to time value. Show them separately where reliably linked to invoice lines; label the primary margin as time value less project delivery costs. A later invoice-revenue margin can use explicit reimbursement attribution.
- All totals are in project currency. Do not sum mismatched currencies or use today's FX rate for historical costs. First release requires matching-currency records; mismatches produce visible exclusions and an incomplete margin state.
- Use all completed hours against `budget_hours`. Keep `budget_amount` as the existing work-value budget, not a newly invented cost budget. Warn at 80% and at 100%; no outbound notifications in this release. A missing/zero budget does not yield division errors.

## Invoice and payment attribution

Build a dedicated read model; do not sum whole invoices once per linked entry. A project invoice is counted once and only when attribution is reliable. Time links alone cannot attribute mixed-project or manual invoice lines safely.

For newly generated project invoices, persist explicit project/source line attribution atomically with invoice creation. Do not change invoice pricing behavior. For existing invoices, accept attribution only when every line is verifiably mapped; otherwise report the affected invoice as unattributed rather than guessing. Expense-only invoices need the same attribution.

Use existing canonical invoice/payment status rules, discounts, credits, refunds, soft deletion, and balance calculations. Present pre-tax invoiced value and collected cash as separately labeled measures. For a fully attributed single-project invoice, actual valid payment records can be shown, including partial payments. Mixed-project payments remain unallocated in this release; show the reason. Do not fabricate paid amounts from a status string. Changes to invoices and payments update billing/collection measures without rewriting historical time values.

## Permissions and architecture

First-release cost configuration, profitability endpoints, and cost-bearing breakdowns are tenant-admin-only, using the repository's tenant role enforcement. Ordinary contributors keep existing time entry access but cannot read or write internal cost fields. No cost fields are added to public/client portal responses, ordinary time APIs, MCP responses, generic exports, or notification payloads. Reject unauthorized writes server-side, including mass assignment; do not merely hide controls.

All queries and references use the tenant database session and validate that project, user, task, expense, and invoice relationships belong to the active tenant/project. An installation-level role is not a substitute for tenant authorization. Audit cost changes with access controls appropriate to sensitive cost information.

Keep calculation and snapshot logic in a dedicated time-tracking service, with protected schemas and endpoints. Reuse existing UI hooks/query invalidation patterns. Preserve optional plugin loading. Migrations must handle existing tenant databases as well as new tenants; do not rely solely on metadata creation. Ordinary existing endpoints remain backward compatible.

## Acceptance and validation

1. Ten billable hours at 100/hour, two nonbillable hours, internal cost 40/hour, and 100 in expenses produce 1,000 work value, 580 cost, 420 contribution, and 42% margin.
2. Missing cost, explicit zero cost, zero revenue, negative margin, active timers, and legacy entries have distinct correct states.
3. Changing a default rate does not rewrite old entries; creation, import, timers, correction, and explicit backfill follow the same snapshot contract.
4. A supplier expense replacing hourly cost is counted once, including when linked to multiple entries. Invalid links and missing/recycled expenses fail safely.
5. Partial payments, repeated time links, expense-only invoices, mixed invoices, discounts, credits/refunds, and deleted records never produce duplicated or invented project totals.
6. Cross-tenant requests, ordinary-user reads/writes, portal/MCP/export leakage, and currency mismatches have focused regressions.
7. Verify the interface with complete, incomplete, empty, and unauthorized fixtures; verify existing time logging and invoice generation still work. Capture UI evidence during implementation, not during this design-only task.
8. Run focused pytest and frontend Vitest coverage plus applicable lint/build checks. Validate migrations for new and existing tenants. State separately whether the deployed service has been exercised.

## Builder discretion and delivery

The builder selects table and endpoint names, component decomposition, and query/index details consistent with repository conventions. Exact canonical payment helper and tenant migration entry points must be traced during planning. If current invoice history cannot support reliable attribution, retain the explicit unavailable state rather than broadening into an accounting rewrite.

Implementation order: cost model and permissions; snapshots and coverage; calculation service and attribution; protected interface; regression and migration verification. After approval, create the detailed implementation plan. No release or deployment is authorized here; assess release/version needs when delivering implementation.

## Design review

A fresh builder review identified two missing decisions: expense eligibility and allocation of supplier expenses across contributor/task breakdowns. Both are resolved above with explicit eligibility/incomplete-data rules and a separate project-expenses bucket. These are proposed implementation defaults for user review.
