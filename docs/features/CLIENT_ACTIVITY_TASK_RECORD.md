# Client Activity and Tasks

This document describes the native client activity feed and reminder-backed task experience that turns the client page into a more explicit CRM-style contact record.

## Goal

The product already had client notes, reminders, invoices, payments, and a timeline endpoint, but those pieces were spread across different surfaces.

This feature brings them together so users can work an account from one place:

- review recent client activity
- capture notes
- track follow-up tasks
- update relationship metadata
- move from an event to the next action quickly

## Current Product Shape

The client detail page now acts as a lightweight contact record with these tabs:

- `Overview`
- `Details`
- `Activity`
- `Tasks`
- `Contacts` when the CRM plugin is enabled

Key files:

- [api/core/services/client_record_service.py](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/api/core/services/client_record_service.py)
- [api/core/schemas/client_record.py](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/api/core/schemas/client_record.py)
- [api/core/routers/clients.py](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/api/core/routers/clients.py)
- [ui/src/pages/EditClient.tsx](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/ui/src/pages/EditClient.tsx)
- [ui/src/components/clients/ClientActivityFeed.tsx](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/ui/src/components/clients/ClientActivityFeed.tsx)
- [ui/src/lib/api/clients.ts](/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/ui/src/lib/api/clients.ts)

## Client Record Data

The client model now carries a small set of CRM-oriented fields:

- `owner_user_id`
- `stage`
- `relationship_status`
- `source`
- `last_contact_at`
- `next_follow_up_at`

These fields are intentionally small and operational. The goal is not to build a generic CRM abstraction first, but to support the account-management workflows this repo already fits well.

## Record API

Current record endpoints:

- `GET /api/v1/clients/{client_id}/record`
- `PATCH /api/v1/clients/{client_id}/record`
- `GET /api/v1/clients/{client_id}/tasks`
- `POST /api/v1/clients/{client_id}/tasks`

The record response includes:

- the client profile
- summary metrics
- normalized recent activity
- open client-linked tasks

## Activity Feed

The Activity tab is driven by the normalized `recent_activity` payload from the client record service instead of the older timeline-only view.

Current activity types:

- `note_created`
- `task_created`
- `task_completed`
- `invoice_created`
- `invoice_overdue`
- `payment_received`

The frontend presents these as one chronological feed with filters for:

- all
- notes
- tasks
- invoices
- payments

This gives the client page a single operational history instead of multiple partially-overlapping panels.

## Tasks

Tasks are currently implemented with the existing `Reminder` model.

This is a deliberate design choice because reminders already provide:

- assignee
- due date
- priority
- status
- background processing
- notification support

Client-linked tasks use the `Reminder.extra_metadata` convention:

- `client_id`
- `task_kind`
- `task_origin`
- `workflow_id` when applicable

This keeps the current implementation practical while leaving room to promote tasks into a dedicated model later if product needs grow.

## Quick Actions

The current Activity tab supports lightweight CRM actions:

- add note
- mark contacted
- create follow-up from notable events

`Mark Contacted` updates `last_contact_at` through the client record endpoint.

`Create Follow-Up` currently appears for key activity items such as:

- overdue invoices
- payments received
- notes

Rather than immediately creating a task with hidden defaults, the UI opens the Tasks tab with a prefilled task form so the user keeps control over assignee, due date, and priority.

## Relationship to Workflows

This feature pairs naturally with the workflow system.

Current workflow-created overdue follow-up tasks already fit the client record model because reminders can be linked back to a client through metadata. That means the client page can become the place where users see both:

- manual follow-up work
- automation-generated work

## Current Limitations

- tasks are still reminder-backed rather than first-class entities
- there is no dedicated activity endpoint separate from the record payload
- activity filters are frontend-only
- the feed does not yet support event-specific actions like send reminder
- the UI does not yet expose completed task history separately
- the current contact record is built into the existing client page rather than a dedicated route

## Recommended Next Steps

1. Add richer event actions such as invoice reminder and assign follow-up owner.
2. Show completed task history alongside open tasks.
3. Add workflow-triggered events more explicitly to the activity feed.
4. Decide whether reminders remain the long-term task system or become a temporary bridge.
5. Consider promoting the client record into its own page if the UI grows beyond the current edit-client shell.
