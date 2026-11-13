# Hourly project profitability

Tenant administrators can open **Profitability** on an hourly project's detail page. Configure effective-dated internal hourly costs for the owner, employees, or subcontractors, then review time value, delivery cost, contribution, budgets, invoicing, and collections. These operational estimates are not statutory net profit, payroll, or tax reporting.

## What the amounts mean

- **Work value** uses completed billable hours and each entry's stored billing rate. Nonbillable hours still incur cost. Active timers do not contribute until stopped.
- **Known delivery cost** combines completed hourly cost snapshots and eligible project expenses. Explicit zero costs are valid; missing costs are unknown. Missing rates, unresolved supplier links, expense approvals/OCR drafts, or currency mismatches make coverage incomplete and withhold complete contribution and margin.
- **Contribution** is time work value less delivery cost; margin divides contribution by work value. Zero work value has no margin percentage. Negative contribution is valid.
- **Project expenses** use the recorded `amount`, rather than `total_amount`. Approved expenses, or recorded expenses requiring no approval, contribute once. Rejected, cancelled, and deleted expenses are excluded with visible reasons; unresolved expenses prevent complete coverage. Matching project currency is required; historical currency conversion is not inferred.
- **Budgets** retain their existing meaning: all completed hours against the hours budget, and time work value against the amount budget. Warnings appear at 80% and 100%.

## Rates and historical entries

Rates are append-only and effective-dated per contributor/currency. Manual creation, CSV import, and timer start snapshot the applicable rate using the work date. A timer's eventual cost uses that snapshot. Changing a default rate does not reprice earlier entries. Correcting duration recomputes cost from its existing snapshot; changing the work date retains that snapshot.

Legacy entries start with unknown costs. An administrator selects entries, previews missing-only backfill, then applies it. The server recomputes and validates the preview; concurrent edits produce a conflict requiring a fresh preview. Existing snapshots are never overwritten by backfill. Generic audit records contain identifiers/reasons, while sensitive replacement history stays in protected cost storage.

## Supplier bills

Switch subcontractor time from hourly cost to **supplier expense** and explicitly link project expenses. An expense can cover multiple entries but contributes once. Hourly estimates are replaced, with private revision history retained. Missing, recycled, or ineligible linked expenses leave the affected time unresolved. Expected expense IDs survive permanent deletion, so deleting only one of several linked bills cannot falsely restore complete coverage. Only an explicit administrator replacement changes those expected links; the prior links remain in private revision history.

Contributor and task breakdowns show hourly labor costs. Supplier replacements and all other expenses remain in a separate project-expenses bucket; the feature does not invent per-person allocations. Allocate a bill spanning projects into separate project expense records without duplicating its total. Automatic detection of arbitrary duplicate manual expenses is outside this feature.

## Invoices and payments

Unbilled work value, pre-tax invoiced value, and collected cash are separate measures and must not be added together. New project invoices preserve explicit source-to-line attribution in their creation transaction without changing invoice pricing. Invoice edits or missing/unmapped lines can make attribution unresolved. Legacy invoices without reliable provenance remain unattributed.

A fully attributed single-project invoice can show actual valid partial payment records; cash may include tax, while invoiced value is pre-tax after supported discounts. Mixed-project/manual invoices, unsupported credits/refunds, and payment currency mismatches remain visibly unallocated. A status such as “paid” alone does not create cash. Attributed expense-line reimbursements appear separately as pre-tax amounts after discount. Supported invoice discounts are allocated proportionally by each line’s pre-discount amount, using invoice-line amounts rather than recorded expense costs. Only fully attributed invoices contribute; known reimbursements carry the same completeness indicator as invoiced value. Expense reimbursements are never added to time work value.

## Access and supported scope

Cost setup, profitability responses, and sensitive breakdowns require an active tenant administrator role. Global installation privileges do not replace tenant membership or role checks. Ordinary contributors retain time logging and existing ordinary response/export shapes; internal costs are not added to ordinary project/time responses, generic exports, MCP, notifications, or client portal schemas.

Hourly projects are supported. Existing fixed-price projects keep their workflows and display an unsupported profitability state. Fixed-fee/retainer accounting, cross-project bill allocation, cross-client rankings, profitability exports, payroll integration, and cost-to-finish forecasting remain future work.

## Validation and release boundary

Focused tests use disposable databases and `--noconftest`: the repository's default API test conftest drops its configured test database and must not run against shared or deployed data. See the [browser evidence](../test-reports/project-profitability-2026-11-12/README.md) for screenshots and its fixture boundary. Task 7 recorded 113 focused backend passes plus one final query regression, PostgreSQL migration/concurrency checks, 18 frontend passes, and a successful final clean-source frontend build; the delivery report distinguishes actual HTTP routes from ORM-seeded expenses/payments. Deployed service and client portal runtime remain unverified.

This introduces tenant migrations 028–031 and an administrator-facing feature, so it warrants a release note and the project's next feature version during the normal release process. No publication or deployment is included in the implementation.
