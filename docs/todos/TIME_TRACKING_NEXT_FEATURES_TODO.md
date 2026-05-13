# Time Tracking Next Features TODO

## Recommended Next Feature: Project Profitability View

Build a project-level profitability dashboard that helps users understand whether a project is financially healthy before invoicing.

### Core Metrics

- Billed time amount
- Unbilled time amount
- Project expenses
- Budget hours used
- Budget amount used
- Effective hourly rate
- Gross margin estimate
- Remaining budget

### UI Placement

- Add as a new project detail tab: `Profitability`
- Reuse the existing project summary and unbilled data where possible
- Show compact metric cards first, then supporting breakdowns by task, time entry, and expense category

### Useful Follow-Ups

- Warn when a project is close to exceeding budget
- Highlight tasks with high time burn against estimates
- Show invoice readiness: completed billable work, unbilled entries, and expenses
- Add export support for profitability summaries

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
