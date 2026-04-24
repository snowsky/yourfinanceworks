# Finance Agent Plan

## Goal

Build a finance-focused agent platform on top of the current repo that can serve both small businesses and larger enterprises without forking the architecture.

The correct approach in this codebase is to evolve the existing assistant into a governed planner/executor, not to build a second AI subsystem in parallel.

## Repo Reality

This repository already contains most of the platform primitives needed for a finance agent:

- Multi-tenant data isolation with database-per-tenant architecture
- AI chat entrypoint in `api/commercial/ai/routers/chat.py`
- AI provider abstraction via LiteLLM and tenant AI configs
- MCP server and tool modules in `api/MCP/`
- Agent-oriented Tools API in `api/commercial/tools_api/`
- OCR and document ingestion pipelines
- Approval workflows and workflow execution logs
- Reporting, analytics, audit logs, notifications, reminders, and search
- Encryption and tenant-context-aware data access

What is missing is a real agent runtime:

- Structured planning
- Safe tool orchestration
- Long-term memory
- Policy enforcement
- Approval gating for risky actions
- Execution logs with replayable steps

## Recommended Product Shape

Do not build separate codebases for SMB and enterprise.

Build one finance agent platform with role- and policy-driven operating modes:

1. Collections Agent
   Handles overdue invoices, payment follow-up, collections prioritization, and reminder drafting.
2. AP and Expense Agent
   Reviews expenses, flags policy violations, recommends categorization, and prepares approval packets.
3. Controller and CFO Agent
   Produces summaries, cash flow insights, variance explanations, and recommended next actions.
4. Audit and Compliance Agent
   Detects anomalies, duplicate invoices, suspicious edits, missing attachments, and policy exceptions.

For small businesses, the agent should act as a copilot with optional low-risk execution.

For larger enterprises, the same platform should become approval-heavy, policy-driven, and fully auditable.

## Architecture Direction

### Current Best Entry Point

Use the existing `/ai/chat` capability as the main user-facing entrypoint, but change the backend behavior from simple intent routing into a staged agent pipeline.

### Target Runtime Flow

1. Interpret the user request and classify the finance job to perform.
2. Build a structured execution plan instead of answering in one pass.
3. Select tools from the existing MCP tools and Tools API.
4. Run policy checks before each write-capable action.
5. Execute step-by-step with structured results and idempotency protection.
6. Persist memory, approvals, and execution logs.
7. Return both the answer and the evidence trail.

### Core Layers To Add

#### 1. Planner Layer

Responsible for:

- Task decomposition
- Tool selection
- Deciding when clarification is required
- Deciding when approval is required
- Choosing the right finance playbook

#### 2. Policy Layer

Responsible for:

- RBAC checks
- Feature and license checks
- Domain allowlists
- Tenant policy enforcement
- Spend or action thresholds
- Segregation of duties rules

#### 3. Execution Layer

Responsible for:

- Calling existing finance tools safely
- Enforcing read-only vs write mode
- Step-level retries
- Idempotency keys
- Partial failure handling

#### 4. Memory Layer

Responsible for:

- Tenant finance preferences
- Prior approved actions
- Vendor/category heuristics
- Recurring reporting patterns
- Known exception rules

#### 5. Audit Layer

Responsible for:

- Full execution traces
- Inputs, outputs, and tool calls
- Approval decisions
- User-visible evidence for enterprise review

## Existing Repo Components To Reuse

### Reuse As-Is or With Light Extension

- `api/commercial/ai/routers/chat.py`
- `api/commercial/ai/services/ai_config_service.py`
- `api/commercial/tools_api/`
- `api/MCP/tools/`
- `api/core/services/workflow_service.py`
- `api/core/models/models_per_tenant.py`
- `api/core/services/search_indexer.py`
- `api/core/services/report_*`
- approval, notification, and reminder infrastructure

### Why These Matter

The repo already exposes finance-domain operations in a form close to agent-consumable interfaces. That reduces the amount of new infrastructure needed. The main effort is orchestration and governance, not CRUD coverage.

## New Backend Components To Add

Recommended new modules:

- `api/commercial/ai/services/agent_runtime.py`
- `api/commercial/ai/services/agent_policy_service.py`
- `api/commercial/ai/services/agent_memory_service.py`
- `api/commercial/ai/services/agent_registry.py`
- `api/commercial/ai/services/agent_approval_service.py`
- `api/commercial/ai/services/agent_playbooks/`

Recommended playbook modules:

- `collections_playbook.py`
- `expense_review_playbook.py`
- `cash_flow_playbook.py`
- `month_end_playbook.py`
- `audit_anomaly_playbook.py`

## Data Model Additions

Add tenant-level models for agent execution and governance.

Suggested tables:

- `agent_runs`
- `agent_run_steps`
- `agent_action_approvals`
- `agent_memory`
- `agent_saved_views` or `agent_saved_queries`
- `agent_policy_overrides`

Suggested fields:

### `agent_runs`

- `id`
- `agent_type`
- `requested_by_user_id`
- `status`
- `input_payload`
- `final_response`
- `risk_level`
- `requires_approval`
- `created_at`
- `completed_at`

### `agent_run_steps`

- `id`
- `agent_run_id`
- `step_order`
- `step_type`
- `tool_name`
- `tool_input`
- `tool_output`
- `status`
- `error_message`
- `started_at`
- `finished_at`

### `agent_action_approvals`

- `id`
- `agent_run_id`
- `step_id`
- `approval_type`
- `status`
- `requested_from_user_id`
- `decided_by_user_id`
- `decision_reason`
- `created_at`
- `decided_at`

### `agent_memory`

- `id`
- `memory_scope`
- `memory_key`
- `memory_value`
- `confidence`
- `source`
- `created_at`
- `updated_at`

## Action Safety Model

Finance agents should not treat all tool calls equally.

Define three action classes:

### Low Risk

- List invoices
- Summarize cash flow
- Find overdue items
- Draft recommendations

These can run automatically.

### Medium Risk

- Create draft invoice
- Update reminder/task state
- Propose recategorization
- Change non-destructive metadata

These can run automatically for SMB tenants, but should usually require confirmation in enterprise tenants.

### High Risk

- Delete finance records
- Mark invoices paid
- Change approval outcomes
- Modify accounting exports
- Restore or remove statements
- Trigger sensitive external integrations

These should require explicit approval and a persisted audit trail.

## SMB to Enterprise Maturity Path

### Phase 1: Finance Copilot

Goal: fast value for small businesses.

Scope:

- Natural-language Q&A over invoices, expenses, payments, and statements
- Low-risk action execution only
- Basic run logs
- Playbooks for:
  - overdue invoice follow-up
  - weekly finance summary
  - expense anomaly surfacing

Expected outcome:

The assistant becomes materially useful without introducing governance risk.

### Phase 2: Operational Agent

Goal: support day-to-day finance operations.

Scope:

- Structured plans with step-by-step execution
- Approval prompts for medium-risk writes
- Tenant memory for recurring actions and preferences
- Better evidence and result summaries
- Workflow-triggered agent runs

Expected outcome:

The system shifts from chat assistant to finance operations copilot.

### Phase 3: Enterprise Governance

Goal: make the agent safe for larger organizations.

Scope:

- Policy packs by tenant
- Dual approval for sensitive actions
- Segregation of duties enforcement
- Per-role action allowlists
- Full execution and approval audit history
- Model routing by data sensitivity

Expected outcome:

The same agent can be trusted in more regulated or distributed finance teams.

### Phase 4: Specialized Multi-Agent Operation

Goal: scale by specialization without fragmenting the platform.

Scope:

- Planner agent plus domain executors
- Shared policy and memory backbone
- Specialized agents for collections, AP, reporting, and audit
- Optional plugin-based vertical packs by industry

Expected outcome:

The platform supports more complex finance automation while keeping one control plane.

## UI and Product Surface

The frontend should not present this as a generic chatbot.

Recommended UI changes:

- Finance agent workspace instead of simple chat bubble only
- Plan preview before write actions
- Approval cards for risky actions
- Run history with step trace
- Saved finance tasks and recurring jobs
- Role-aware views for admin, controller, approver, and operator

Good initial surfaces:

- AI assistant panel for ad hoc asks
- dashboard finance summary card
- overdue collections workspace
- month-end checklist workspace

## Recommended First Deliverable

The best first deliverable for this repo is:

`Finance Operations Agent v1`

Capabilities:

- Answers finance questions from live tenant data
- Produces structured action plans
- Executes only low-risk actions automatically
- Routes medium- and high-risk actions into approval flow
- Persists execution logs for traceability

This is a realistic first release because it builds directly on the repo's current architecture.

## Implementation Notes For This Repo

### Current Strengths

- The repo already has tenant isolation, tool surfaces, and workflow foundations.
- The Tools API is already shaped for agent access.
- Existing finance modules cover invoices, expenses, payments, and bank statements.
- OCR and reporting pipelines provide strong supporting context.

### Current Gaps

- Chat flow is still mostly intent routing, not true planning.
- No durable agent memory layer exists yet.
- No unified policy engine for agent actions exists yet.
- Existing workflows are relatively narrow and not yet agent-native.
- Execution traces for agent actions are not first-class models yet.

### Shortest Viable Build Strategy

1. Add agent run models and execution logging.
2. Introduce a planner/executor service behind the current AI chat entrypoint.
3. Wrap Tools API calls with policy checks and risk classification.
4. Add the first two playbooks:
   - collections follow-up
   - finance summary and risk review
5. Add approval prompts and step previews for write actions.
6. Expand into memory, enterprise policies, and specialized sub-agents only after v1 proves useful.

## Summary

This repo does not need a brand-new finance agent platform.

It already has most of the expensive infrastructure: tenant isolation, finance data models, OCR, workflows, tool access, reporting, and AI provider support.

The right plan is to add a governed agent runtime on top of those systems so the product can start as a high-leverage finance copilot for small businesses and mature into an enterprise-safe finance operations platform.
