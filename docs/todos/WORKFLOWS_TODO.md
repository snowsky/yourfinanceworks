# Workflows TODO

This document tracks the next implementation tasks for the native workflow feature.

## Current State

Done:

- Workflow definition model
- Workflow execution log model
- Background runner hook
- Default overdue invoice workflow
- Admin Workflows page
- Workflow builder with backend-supported trigger/action catalog
- Reminder-backed internal task creation

## Immediate Next Tasks

- Add workflow execution history endpoint and UI
- Show recent workflow runs on the Workflows page
- Add richer error reporting for failed workflow executions
- Add deletion or archiving for user-created workflows
- Add edit support for user-created workflows

## Trigger Backlog

- Add `invoice_created`
- Add `payment_received`
- Add `client_created`
- Add `expense_created`
- Add `expense_submitted_for_approval`

For each new trigger:

- define event semantics clearly
- define deduplication key
- define matching conditions
- define expected actions
- add backend catalog entry
- add execution logic
- add tests

## Action Backlog

- Add `send_client_email`
- Add `assign_to_specific_user`
- Add `add_client_note`
- Add `create_client_timeline_event`
- Add `send_slack_notification`

For each new action:

- define required input fields
- define fallback behavior
- define idempotency expectations
- expose only after backend support exists

## Task System Decision

Open product/architecture question:

- keep internal tasks backed by `Reminder`, or
- introduce a dedicated `Task` model

Short-term recommendation:

- continue using reminders for workflow-generated tasks

When to introduce a dedicated task model:

- if tasks need subtasks
- if tasks need comments separate from reminders
- if tasks need richer workflow-specific ownership rules
- if tasks need boards, statuses, or team queues beyond the reminder UX

## Assignment Improvements

- Allow choosing assignment strategy in workflow creation
- Support:
  - invoice creator
  - client owner
  - first admin fallback
  - explicit selected user
- Add validation when a selected user becomes inactive

## Product UX Backlog

- Add workflow cards with richer summaries
- Add empty states and onboarding copy
- Add "duplicate workflow" action
- Add badges for system vs custom workflows
- Add clearer preview of what each workflow will do

## Observability

- Add audit log entries for workflow creation/update/toggle
- Add execution metrics
- Add failure counters
- Add retry guidance for failed actions

## Testing Backlog

- Unit tests for workflow catalog
- Unit tests for workflow creation validation
- Unit tests for execution deduplication
- Unit tests for responsible-user resolution
- Integration tests for overdue invoice processing
- UI tests for workflow builder form and toggles

## Documentation Backlog

- Add user guide for Workflows page
- Add API reference for workflow endpoints
- Add architecture note for reminder-backed internal tasks
- Update feature overview docs when more triggers/actions ship
