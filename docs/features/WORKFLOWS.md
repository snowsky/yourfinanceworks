# Workflows

Workflows are user-configurable automation rules that react to events in YourFinanceWORKS (an invoice was created, a payment came in, a client was added, etc.) and run one or more actions (notify a teammate, create an internal task, append a note to the client, email the client, post to Slack, etc.).

This guide covers what admins see in the **Workflows** page, the supported triggers and actions, how to configure them, and how to debug a workflow that isn't firing the way you expect.

The Workflows feature is gated behind the `workflow_automation` feature flag. Tenants without the flag see an upgrade prompt instead of the Workflows page.

## When to use a workflow

A workflow is the right tool when **all** of the following hold:

- The reaction should happen automatically — not on demand.
- The reaction is the same every time the trigger fires (sometimes with per-event template variables, but the actions don't change).
- It's OK that the reaction may run on a short delay (the background runner polls every tick rather than running synchronously at the event source).

If you need a one-off action, use the relevant page directly (create a reminder, send an email). If you need a complex multi-step routing decision that branches on data, a workflow's per-trigger × per-action grid will feel cramped — talk to engineering about whether this is the right surface.

## Concepts

| Concept | What it is | Where it lives |
|---|---|---|
| **Workflow** | A user-defined rule with one trigger and N enabled actions. | `WorkflowDefinition` table, one row per workflow. |
| **Trigger** | A named event the platform knows how to detect — e.g. `invoice_became_overdue`. | `SUPPORTED_TRIGGERS` in `api/core/services/workflow_service.py`. |
| **Action** | A named side effect a workflow can produce — e.g. `send_internal_notification`. | `SUPPORTED_ACTIONS` in the same file. |
| **Execution log** | One row per (workflow, entity, event) pair. Records success/failure + details. | `WorkflowExecutionLog` table. Surfaced in the Workflows **History** tab. |
| **System workflow** | A built-in workflow the platform ships with (currently: the overdue-invoice follow-up). Can't be edited or deleted, but can be cloned. | `is_system=True` rows. |

The workflow runner is invoked by the background scheduler once per tenant per tick. The "Run now" button on a workflow card invokes the same processor synchronously for ad-hoc testing.

## Trigger × action grid

Triggers are the **events** that fire the workflow. Actions are the **side effects** it produces. Every action is available on every trigger; the per-trigger templates (notification subjects, task titles, client note bodies, client email subject/body, Slack message text) are defined per-(trigger, action) pair and have sensible server-side defaults.

### Triggers

| Trigger | Fires when... | Idempotency key |
|---|---|---|
| `invoice_became_overdue` | An unpaid invoice passes its due date for the first time. | `(workflow_id, invoice_id, "overdue")` |
| `invoice_created` | A new invoice is created on or after the workflow's own `created_at` (no retroactive backfill). | `(workflow_id, invoice_id, "created")` |
| `payment_received` | A payment is recorded against an invoice on or after the workflow's `created_at`. Orphan payments (no linked invoice) are skipped. | `(workflow_id, payment_id, "payment_received")` |
| `client_created` | A new client is added on or after the workflow's `created_at`. | `(workflow_id, client_id, "client_created")` |
| `expense_created` | A new expense is recorded on or after the workflow's `created_at`. | `(workflow_id, expense_id, "expense_created")` |
| `expense_submitted_for_approval` | An expense is submitted for approval (per `ExpenseApproval` row, so multi-level approvals fire once per level). | `(workflow_id, expense_approval_id, "submitted_for_approval")` |

All triggers use the same retroactive guard: only entities with `created_at >= workflow.created_at` are eligible, so deploying a new workflow doesn't fire for historical data.

### Actions

| Action | What it does | When it's skipped |
|---|---|---|
| `send_internal_notification` | Emits an in-app notification via `core.utils.notifications.send_notification`. | When the workflow's resolved owner is missing. |
| `create_internal_task` | Inserts a `Reminder` row tagged `workflow-task`, assigned to the resolved owner. Title and description are rendered from per-trigger templates. | Same — when no owner can be resolved. |
| `add_client_note` | Appends a `ClientNote` row prefixed `[Workflow {key}] ...`. The note automatically surfaces in the client activity timeline via the existing aggregator. | When the trigger has no client context (e.g. an expense without a `client_id`). |
| `assign_to_specific_user` | Overrides the auto-resolved owner with a specific user picked at workflow-edit time. | When the override user is missing or inactive at execution time — falls back to the default resolver with a WARN log. |
| `send_client_email` | Renders per-trigger subject and body templates and sends via the tenant's configured `EmailService`. | When the trigger has no client context, the client has no email address, or the tenant has not configured an email provider. |
| `send_slack_notification` | POSTs `{"text": message}` to the tenant's Slack incoming webhook with a 10s timeout. | When the tenant has no `slack_webhook_config` Settings row, no `webhook_url`, or the request errors out or returns non-2xx. |

## Configuring the prerequisites

Two actions read configuration from the per-tenant `Settings` table. Both are silently no-ops (with a WARN log) until configured.

### Email — `email_provider_config`

Already used by the rest of the platform (invoice emails, password reset, etc.), so if you've sent any other emails from your tenant, this is already set. The `send_client_email` action picks it up via the same Settings row:

```json
{
  "provider": "aws_ses",
  "from_email": "noreply@your-tenant.example",
  "from_name": "Your Tenant",
  "aws_access_key_id": "AKIA...",
  "aws_secret_access_key": "...",
  "aws_region": "us-east-1"
}
```

Other providers (`azure_email`, `mailgun`) follow the same shape with their own credentials — see `api/core/services/email_service.py`.

### Slack — `slack_webhook_config`

```json
{
  "webhook_url": "https://hooks.slack.com/services/T.../B.../..."
}
```

The webhook URL controls which channel the message lands in (Slack's per-webhook setting). No OAuth, no Slack app required — the integration is plain Incoming Webhooks.

## Walkthrough: configure your first workflow

1. **Navigate to Workflows.** Admin role required.
2. On the **Active Workflows** tab, fill out the form:
   - **Workflow name** — surfaces in notifications and the executions log.
   - **Trigger** — pick from the grid above.
   - **Description** — optional, but reads back to you next time you edit.
   - **Actions** — check one or more. Action descriptions are pulled from `SUPPORTED_ACTIONS`.
   - **Assigned teammate** — only shown when `Assign to a specific teammate` is checked. Required when that action is on.
3. **Create workflow.** The new row appears below; it's enabled by default.
4. **Toggle the switch** to disable temporarily; the workflow stays in the list but won't fire.
5. **Run now** processes every event matching the trigger right now (subject to the per-event execution log, so already-handled events are silently skipped).

## Cloning an existing workflow

Use **Duplicate** on any workflow card — including the built-in system workflows. The clone:

- Becomes user-owned (`is_system=False`, `is_default=False`)
- Is always created enabled regardless of source state
- Carries every condition and action flag from the source (deep-copied, so editing the clone doesn't affect the source)
- Gets the name `"{source name} (copy)"` with a slug suffix appended on collision

This is the primary way to take the built-in overdue follow-up and adapt it to your tenant's specifics.

## Observability: the History tab

The **History** tab lists every execution log row across all workflows (or a specific one via the workflow filter).

- **Status filter** — All / Success / Failed.
- **Workflow filter** — narrow to a specific workflow.
- Each row's badge is `Success` or `Failed`. Failed rows show a truncated error preview inline so they're scannable without expanding.
- Expanding a row reveals the execution metadata (workflow ID, event key, entity, assigned user) and the full `details` JSON.
- Expanded **failed** rows include a **Rerun workflow** button. It calls `run now` on the source workflow; the per-event execution log keeps already-successful events idempotent, so only this and any other still-pending events refire.

## Idempotency model

Every per-event run writes a row to `WorkflowExecutionLog` with a deterministic `event_key`:

- Invoice-overdue: `invoice:<id>:overdue`
- Invoice-created: `invoice:<id>:created`
- Payment-received: `payment:<id>:payment_received`
- Client-created: `client:<id>:client_created`
- Expense-created: `expense:<id>:expense_created`
- Expense-submitted-for-approval: `expense_approval:<id>:submitted_for_approval`

Before processing, the runner checks for an existing row with the same `(workflow_id, event_key)`. If one exists, the event is silently skipped. This means:

- Rerunning a workflow doesn't fire duplicate notifications/tasks/notes/emails/Slack messages for already-successful events.
- A failed execution writes a `status="failed"` row with the same event key — so the next run *does* retry it, because the runner only skips when a `status="success"` row is present.

## Audit log

Every mutating workflow endpoint writes to the per-tenant `AuditLog` table via `core.utils.audit.log_audit_event`:

| Action | Logged on | `details` includes |
|---|---|---|
| `CREATE` | Successful workflow creation (and failed attempts with the validation error) | `trigger_type`, `is_enabled`, `is_system`, `actions` |
| `UPDATE` | Successful update (and failed attempts) | Same as create |
| `TOGGLE` | Every enable/disable | `previous_enabled`, `new_enabled`, `trigger_type` |
| `DELETE` | Successful delete + failed attempts (e.g. trying to delete a system workflow) | `trigger_type` captured before the row is removed |
| `DUPLICATE` | Successful clone | `source_workflow_id` + the clone's payload |
| `RUN_NOW` | Every manual run | Per-tick stats (`processed_count`, `created_task_count`, `notification_count`, `skipped_count`, `error_count`) |

The audit rows show up in the existing Admin → Audit Logs view.

## Troubleshooting

| Symptom | Likely cause | What to check |
|---|---|---|
| Workflow is enabled but nothing fires. | The trigger entity was created **before** the workflow itself (`entity.created_at < workflow.created_at`). | Look at execution log: there will be no log rows at all. Workflows don't backfill historical data — this is intentional. |
| Workflow fires once but not again for the same entity. | The first run wrote a `status="success"` execution log row. Subsequent ticks see it and skip. | This is the idempotency guard, not a bug. To rerun, delete the matching log row (rare — usually you want to leave it in place). |
| `send_client_email` does nothing. | No `email_provider_config` Settings row, missing client email, or no client linked to the trigger entity. | Check the execution log row's `client_email_sent` field. Skips also produce a WARN log on the server with the reason. |
| `send_slack_notification` does nothing. | No `slack_webhook_config` Settings row, or the webhook URL returned non-2xx. | Same — check `slack_notification_sent` on the execution log. Server WARN log includes the response code on non-2xx. |
| `assign_to_specific_user` task lands on someone unexpected. | The configured target user is inactive at execution time, so the default resolver chain ran. | Server WARN log explains the fallback. Re-pick the user via Edit and ensure they're active. |
| A workflow you cloned silently dropped its actions on save. | Pre-March 2026 bug — fixed in #305. Make sure the UI is up to date; if you see this on the current build, file an issue. | Reopen Edit; the checkboxes should reflect all active flags. |

## Architecture note

- **Service** — `api/core/services/workflow_service.py`. Owns the trigger registry, action registry, per-trigger processors, dispatch table, and helpers (`_create_internal_task`, `_add_client_note`, `_send_client_email`, `_send_slack_notification`, `_apply_assignment_override`, `_resolve_assigned_user` / `_resolve_user_for_client` / `_resolve_user_for_expense` / `_resolve_user_for_expense_approval` / `_fallback_admin_user`).
- **Router** — `api/core/routers/workflows.py`. CRUD + run-now + duplicate + execution-log endpoints, all gated on the `workflow_automation` feature and `require_admin`.
- **Scheduler** — Background runner per tenant calls `WorkflowService.process_all_workflows()`, which dispatches through `_trigger_processors`.
- **UI** — `ui/src/pages/Workflows.tsx`. Active workflows tab (cards) + History tab (executions). Both tabs share the catalog query (`workflowsApi.catalog()`) and the workflows list query.

### Why tasks are reminder-backed

The codebase already has strong reminder support (assignee, due date, priority, status, notifications, background processing). Using `Reminder` as the workflow task type lets workflows ship without first building a parallel task domain. Promoting to a dedicated `Task` model is the right call once any of these become true:

- Tasks need subtasks.
- Tasks need comments separate from reminders.
- Tasks need richer workflow-specific ownership rules.
- Tasks need boards, statuses, or team queues beyond the reminder UX.

### Why the timeline is an aggregator

`get_client_timeline()` synthesizes events on the fly from Invoice / Payment / Expense / BankStatementTransaction / ClientNote rather than maintaining a dedicated `client_timeline_event` table. The `add_client_note` workflow action therefore automatically surfaces in the timeline via the existing notes bucket — a separate `create_client_timeline_event` action would be redundant unless and until workflow events need to render distinctly from manual notes in the UI.

## API reference

| Method | Path | Notes |
|---|---|---|
| `GET` | `/workflows/` | List workflows. |
| `GET` | `/workflows/catalog` | Discoverable triggers + actions for the form. |
| `POST` | `/workflows/` | Create. Body: `{name, description, trigger_type, action_ids, assigned_user_id}`. Returns 400 if `assign_to_specific_user` is set without a user. |
| `PUT` | `/workflows/{id}` | Update. Same shape as create. |
| `POST` | `/workflows/{id}/toggle` | Enable/disable. Body: `{is_enabled}`. |
| `POST` | `/workflows/{id}/run` | Run-now. Returns per-tick stats including `errors[]`. |
| `POST` | `/workflows/{id}/duplicate` | Clone. Returns the new workflow. |
| `DELETE` | `/workflows/{id}` | Delete a user-created workflow. 400 if the workflow is system-owned. |
| `GET` | `/workflows/executions` | Cross-workflow execution log list with `?status=`, `?limit=`, `?offset=`. |
| `GET` | `/workflows/{id}/executions` | Same, narrowed to one workflow. |

All endpoints require admin role.
