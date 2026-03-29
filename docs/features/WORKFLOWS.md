# Workflows

This document describes the native workflow automation feature in YourFinanceWORKS, its current implementation, and the design direction for the next iterations.

## Goal

Workflows allow admins to define business automations using supported triggers and actions.

Current product intent:

- Keep automation native to this repo
- Reuse existing domain models where possible
- Expose only workflow options that the backend can actually execute
- Start with finance-adjacent automations that fit the current product

## Current MVP

The first workflow MVP is implemented around overdue invoice follow-up.

Implemented pieces:

- Workflow definitions stored in the tenant database
- Workflow execution log stored per tenant to prevent duplicate runs
- Background workflow execution integrated into the existing reminder background service
- Sidebar menu entry and `Workflows` page for admins
- Workflow builder that allows users to create workflows from predefined backend-supported triggers and actions

Key files:

- [api/core/models/models_per_tenant.py](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/api/core/models/models_per_tenant.py)
- [api/core/services/workflow_service.py](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/api/core/services/workflow_service.py)
- [api/core/routers/workflows.py](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/api/core/routers/workflows.py)
- [api/core/services/reminder_background_service.py](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/api/core/services/reminder_background_service.py)
- [ui/src/pages/Workflows.tsx](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/ui/src/pages/Workflows.tsx)

## Data Model

### `workflow_definitions`

Stores tenant-local workflow configuration.

Important fields:

- `name`
- `key`
- `description`
- `trigger_type`
- `conditions`
- `actions`
- `is_enabled`
- `is_system`
- `is_default`
- `last_run_at`

### `workflow_execution_logs`

Stores execution history and deduplication keys.

Important fields:

- `workflow_id`
- `event_key`
- `entity_type`
- `entity_id`
- `status`
- `details`

The unique constraint on `(workflow_id, event_key)` is what prevents the same workflow from running multiple times for the same event.

## Supported Trigger Catalog

The UI is intentionally driven by a backend catalog.

Currently supported trigger:

- `invoice_became_overdue`

Meaning:

- The workflow runs when an unpaid invoice has passed its due date
- Execution is deduplicated by invoice event key

## Supported Action Catalog

Currently supported actions:

- `send_internal_notification`
- `create_internal_task`

Important note:

- "Internal task" is currently implemented using the existing `Reminder` model
- This was a deliberate choice to avoid building a second task system before the workflow feature proves out

## Default Workflow

System-seeded default workflow:

- Name: `Overdue invoice follow-up`
- Key: `invoice-overdue-reminder-task`
- Trigger: `invoice_became_overdue`
- Default actions:
  - send internal reminder
  - create internal task

Behavior:

1. Background service scans for overdue invoices
2. Matching enabled workflows are evaluated
3. The responsible user is resolved
4. An internal notification is sent
5. A reminder-backed follow-up task is created
6. An execution log is written so the event is not reprocessed

## Responsible User Resolution

Current assignment logic:

1. Use `invoice.created_by_user_id` when available and active
2. Otherwise use the first active admin in the tenant
3. Otherwise fall back to the first active user

This is intentionally simple for the MVP.

## UI Design

The Workflows page currently provides:

- List of available workflows
- Toggle enable/disable
- Manual `Run now`
- Builder form for supported triggers and actions

Current UX principle:

- Do not expose fake flexibility
- Show only backend-supported trigger/action combinations

## Why Tasks Are Reminder-Backed Right Now

The repo already has strong reminder support:

- assignee
- due date
- priority
- status
- notifications
- background processing

Using reminders as the first task type lets us ship workflow automation now while deferring a full task domain until product needs are clearer.

## Current Limitations

- Only one real trigger is executable today
- Only two actions are executable today
- Workflow conditions are not user-editable beyond predefined trigger behavior
- No visual execution history page yet
- No per-workflow assignment rules yet
- No client-facing email action yet
- No standalone task module yet

## Next Design Direction

Recommended expansion order:

1. Add more supported triggers
2. Add more supported actions
3. Add workflow run history in the UI
4. Add assignment strategies
5. Decide whether to keep tasks reminder-backed or promote them into a first-class task system

Likely next triggers:

- `invoice_created`
- `payment_received`
- `client_created`
- `expense_submitted`

Likely next actions:

- `send_client_email`
- `assign_to_specific_user`
- `add_client_note`
- `create_timeline_event`
- `send_slack_notification`
