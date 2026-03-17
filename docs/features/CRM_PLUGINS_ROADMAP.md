# CRM Plugins Roadmap

**Status**: Planned
**Date**: 2026-03-17

## Context

The platform already includes a core CRM module with client management, encrypted notes, activity timeline, and label/tagging. This document describes the additional CRM capabilities planned as installable plugins, using the git-based plugin installer introduced in March 2026.

Each plugin is self-contained and can be installed independently. They build on the existing `clients` data model in core.

---

## Planned Plugins

---

### 1. `crm-pipeline` — Sales Pipeline & Deals

Track opportunities through a configurable sales pipeline.

**Key features:**
- Deals linked to existing clients
- Configurable pipeline stages (e.g. Prospecting → Qualified → Proposal → Negotiation → Closed Won/Lost)
- Kanban board view and list view
- Deal value, expected close date, probability
- Stage history and time-in-stage tracking
- Won/lost reporting with reason capture
- Weighted pipeline value calculation

**Backend models:**
| Table | Description |
|---|---|
| `crm_pipeline_stages` | Tenant-configurable stages with order and color |
| `crm_deals` | Deal record linked to client, stage, assigned user |
| `crm_deal_stage_history` | Audit trail of stage transitions |

**API routes:** `/api/v1/crm-pipeline/`
- `GET/POST /deals` — list and create deals
- `GET/PUT/DELETE /deals/{id}` — manage individual deals
- `PUT /deals/{id}/stage` — move deal to a new stage
- `GET/POST/PUT/DELETE /stages` — manage pipeline stages
- `GET /pipeline` — aggregated pipeline summary (counts, values by stage)

**Frontend pages:**
- Pipeline board (kanban)
- Deals list with filters (stage, assignee, close date range)
- Deal detail with stage history timeline
- Pipeline settings (stage configuration)

**Dependencies:** Core clients module

---

### 2. `crm-contacts` — Contact Management

Multiple contacts per client/company, with roles and communication preferences.

**Key features:**
- Multiple named contacts per client
- Contact roles (e.g. Decision Maker, Technical, Billing, Legal)
- Primary contact designation
- Contact-level notes
- Phone, email, LinkedIn per contact
- Communication preference flags (email, phone, do-not-contact)

**Backend models:**
| Table | Description |
|---|---|
| `crm_contacts` | Contact record linked to client |
| `crm_contact_notes` | Notes specific to a contact |

**API routes:** `/api/v1/crm-contacts/`
- `GET/POST /clients/{id}/contacts` — list and create contacts for a client
- `GET/PUT/DELETE /contacts/{id}` — manage contact
- `POST /contacts/{id}/notes` — add note to contact

**Frontend pages:**
- Contacts tab on the existing client edit page
- Contact card with role badge and communication links
- Quick-add contact modal

**Dependencies:** Core clients module

---

### 3. `crm-activities` — Tasks, Calls & Meetings

Schedule and log all client-facing activities. Replaces ad-hoc note-taking for structured follow-ups.

**Key features:**
- Activity types: Task, Call, Meeting, Email
- Due date and time, duration (for calls/meetings)
- Assigned user
- Linked to client and optionally to a deal (requires `crm-pipeline`)
- Completion tracking with outcome notes
- Overdue detection and notifications
- Calendar view (month/week)
- Reminders (email or in-app)

**Backend models:**
| Table | Description |
|---|---|
| `crm_activities` | Activity record with type, due date, assignee |
| `crm_activity_outcomes` | Logged outcome when activity is completed |

**API routes:** `/api/v1/crm-activities/`
- `GET/POST /activities` — list (with filters) and create
- `GET/PUT/DELETE /activities/{id}` — manage activity
- `POST /activities/{id}/complete` — mark done with outcome
- `GET /activities/calendar` — date-range query for calendar view
- `GET /clients/{id}/activities` — activities for a specific client

**Frontend pages:**
- Activity list with overdue/upcoming filters
- Calendar view
- Activity sidebar on client detail page
- Quick-log call/meeting modal

**Dependencies:** Core clients module. Optionally integrates with `crm-pipeline` to link activities to deals.

---

### 4. `crm-leads` — Lead Capture & Qualification

Manage inbound leads before they become clients. Includes scoring, assignment, and conversion.

**Key features:**
- Lead capture with source tracking (web form, referral, cold outreach, import)
- Lead scoring (manual or rule-based)
- Assignment to sales users
- Qualification stages: New → Contacted → Qualified → Converted / Disqualified
- Disqualification reasons
- One-click conversion to client (creates a Client record)
- Lead import via CSV
- Source attribution reporting

**Backend models:**
| Table | Description |
|---|---|
| `crm_leads` | Lead record with source, score, stage, assignee |
| `crm_lead_notes` | Notes on the lead |
| `crm_lead_stage_history` | Stage transition audit trail |

**API routes:** `/api/v1/crm-leads/`
- `GET/POST /leads` — list and create leads
- `GET/PUT/DELETE /leads/{id}` — manage lead
- `PUT /leads/{id}/stage` — advance qualification stage
- `POST /leads/{id}/convert` — convert lead to client (returns new client ID)
- `POST /leads/import` — bulk import from CSV
- `GET /leads/sources` — lead source summary report

**Frontend pages:**
- Lead list with stage filter and score sorting
- Lead detail with notes and history
- Conversion modal (pre-fills client form from lead data)
- Lead source report

**Dependencies:** Core clients module (for conversion). Optionally links to `crm-pipeline` to create a deal on conversion.

---

## Integration Points Between Plugins

```
crm-leads
  └─ converts to → Core Client
                     ├─ crm-contacts (contacts)
                     ├─ crm-activities (follow-ups)
                     └─ crm-pipeline (deal)
                          └─ crm-activities (deal-linked tasks)
```

Each plugin declares its optional dependencies in `plugin.json` under `required_access`:

```json
{
  "required_access": [
    {
      "target_plugin": "crm-pipeline",
      "access_type": "write",
      "reason": "Create a deal when converting a lead",
      "allowed_paths": ["/api/v1/crm-pipeline/deals*"]
    }
  ]
}
```

---

## Shared Conventions

All CRM plugins should follow these conventions:

**Naming:**
- Backend folder: `crm_<name>/` (e.g. `crm_pipeline/`)
- Plugin ID in manifest: `crm-<name>` (e.g. `crm-pipeline`)
- Table prefix: `crm_<name>_` (e.g. `crm_pipeline_deals`)
- Frontend folder: `crm_<name>/`
- API prefix: `/api/v1/crm-<name>/`

**Models:**
- Inherit from `core.models.models_per_tenant.Base`
- Include `tenant_id` on every table
- Use `EncryptedColumn()` for personally identifiable fields (names, emails, notes)
- Include `created_at` / `updated_at` timestamps

**Security:**
- All routes require `get_current_user`
- Mutations restricted to admin or the assigned user
- Wrap with `require_plugin_access("crm-<name>")`

**Frontend:**
- Lazy-load page components with `React.lazy()`
- Use TanStack Query v5 (`useQuery` / `useMutation`) for data fetching
- Forms with React Hook Form + Zod validation
- ShadCN UI components with Tailwind styling

**License tier:** `agpl` (open source) — CRM is a core business need, not a premium upsell.

---

## Suggested Build Order

| Priority | Plugin | Reason |
|---|---|---|
| 1 | `crm-contacts` | Small, self-contained, high value immediately |
| 2 | `crm-activities` | Standalone, works without pipeline or leads |
| 3 | `crm-pipeline` | Core sales workflow, builds on contacts + activities |
| 4 | `crm-leads` | Depends on pipeline for full value |

---

## MCP Integration (AI Assistant)

Each plugin should provide an MCP provider so the AI assistant can answer questions like:
- "What deals are closing this month?"
- "Show overdue tasks for Acme Corp"
- "Convert lead #42 to a client"

Example provider registration in `__init__.py`:

```python
if mcp_registry:
    try:
        from .mcp.crm_pipeline_provider import CrmPipelineMCPProvider
        mcp_registry.register_provider("crm-pipeline", CrmPipelineMCPProvider())
    except ImportError:
        pass
```
