# Client Activity and Tasks TODO

This document tracks the next implementation tasks for the client activity feed and reminder-backed task record.

## Current State

Done:

- Client CRM metadata fields on the tenant `Client` model
- Client record aggregation endpoint
- Client record update endpoint
- Client-linked task list and task creation endpoints
- Reminder-backed client task convention
- Client `Overview`, `Activity`, and `Tasks` tabs
- Unified client activity feed
- `Mark Contacted` action
- Follow-up task shortcuts from selected activity items
- Activity entries for meaningful client record updates

## Immediate Next Tasks

- Add completed task history to the client record UI
- Add richer event actions from the activity feed
- Add clearer owner names in activity entries instead of raw IDs
- Show workflow-generated task origin more explicitly in the feed and task cards
- Add pagination or "load more" support for larger activity histories

## Activity Feed Backlog

- Add `workflow_triggered` entries when automations create client tasks
- Add `invoice_sent` entries if invoice delivery state is available
- Add `task_reassigned` entries when ownership changes
- Add `task_completed` visual treatment in the feed
- Add event grouping rules to reduce noise from rapid consecutive updates

For each new activity type:

- define when it should appear
- define whether it belongs in the client record or a broader audit surface
- define the actor/source shown in the UI
- define any related quick actions

## Activity Actions Backlog

- Add `send invoice reminder` from overdue invoice events
- Add `assign owner` from relevant activity items
- Add `schedule next follow-up` directly from the feed
- Add `convert to task` for more event types
- Add `open related invoice/payment` deep links where available

## Task Experience Backlog

- Add completed vs open task sections
- Add mark-complete support from the client record page
- Add due-soon and overdue visual states
- Add task reassignment from the client record page
- Add filters for manual vs workflow-generated tasks

## Workflow Integration

- Surface workflow-generated follow-up tasks more clearly in the client record
- Add workflow source metadata to task and activity cards
- Add workflow execution items to the activity feed when relevant
- Ensure the client page is the primary place to review automation-created follow-up work

## Product and UX Improvements

- Consider promoting the client record into its own dedicated route if the page grows further
- Add better empty states for accounts with no activity or no tasks
- Add relationship health badges with clearer visual cues
- Add summary widgets for last payment and overdue balance on the activity screen
- Add mobile-specific layout polish for the activity feed and task cards

## Task Model Decision

Open product and architecture question:

- keep tasks reminder-backed, or
- introduce a dedicated `Task` model

Short-term recommendation:

- continue using reminders while the workflow and client record behavior stabilizes

When a dedicated task model becomes worth it:

- tasks need comments or collaboration separate from reminders
- tasks need richer statuses or board views
- tasks need subtasks or dependencies
- task assignment and reporting outgrow the reminder model

## Testing Backlog

- Add backend tests for client record activity aggregation
- Add backend tests for client record update audit entries
- Add backend tests for client-linked task creation and retrieval
- Add frontend tests for activity feed quick actions
- Add frontend tests for immediate activity updates after record mutations

## Documentation Backlog

- Add a user guide for the new client record experience
- Add API reference docs for client record endpoints
- Add architecture notes for reminder-backed client tasks
- Update broader CRM feature docs as task and activity behavior expands
