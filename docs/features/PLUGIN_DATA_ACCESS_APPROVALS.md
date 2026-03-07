# Plugin Data Access Approvals

Control and audit cross-plugin data access with explicit user approval.

## Overview

This feature isolates plugin data by default.
If one plugin tries to access another plugin's data, the app creates an approval request and prompts the user in the UI before access is granted.

## Why It Exists

- Prevent silent data sharing across plugins.
- Give users clear control over data boundaries.
- Provide an auditable approval trail per tenant and per user.

## Core Behavior

1. Plugin A attempts to call Plugin B with `X-Plugin-Caller`.
2. Backend checks whether the current user has an existing grant for that plugin pair and access type.
3. If no grant exists:
   - a pending request is stored,
   - backend returns `428 PRECONDITION_REQUIRED` with `PLUGIN_ACCESS_APPROVAL_REQUIRED`.
4. UI shows a modal prompt asking the user to approve or deny.
5. If approved, a grant is stored and future calls are allowed.
6. If denied, access remains blocked.

## Access Scope

- Scoped by:
  - tenant
  - user
  - source plugin
  - target plugin
  - access type (`read` or `write`)
- Same-plugin access is implicitly allowed.

## API Endpoints

All endpoints are under `/api/v1/plugins`.

- `POST /access/check`
  - Checks access and creates a pending request if needed.
- `GET /access-requests`
  - Lists requests (`mine_only=true` by default).
- `GET /access-grants`
  - Lists grants (`mine_only=true` by default).
- `POST /access-requests/{request_id}/approve`
  - Approves a pending request.
- `POST /access-requests/{request_id}/deny`
  - Denies a pending request.

## UI Experience

- On approval-required responses, the frontend emits a `plugin-access-approval-required` event.
- `PluginAccessApprovalPrompt` opens a modal with:
  - source plugin
  - target plugin
  - requested access type
  - reason (if provided)
- User can choose:
  - `Allow Access`
  - `Deny`

## Storage Model

Requests and grants are stored in:

- `tenant_plugin_settings.plugin_config.cross_plugin_access.requests`
- `tenant_plugin_settings.plugin_config.cross_plugin_access.grants`

This avoids extra schema migration while keeping data tenant-scoped.

## Security Notes

- Direct user requests without `X-Plugin-Caller` are unaffected.
- Unknown plugin IDs are rejected.
- Non-admin users can only resolve their own requests.
- Admin/superuser can resolve requests tenant-wide.

## Integration Pattern for Plugin Developers

Use the shared helper on the frontend:

```ts
pluginToPluginRequest({
  sourcePlugin: "time-tracking",
  targetPlugin: "investments",
  url: "/investments/portfolios",
  options: { method: "GET" },
  reason: "Show investment totals in project dashboard",
});
```

Protect backend plugin routes with:

```python
Depends(require_plugin_access("my-plugin"))
```

## Quick Validation Checklist

1. Trigger a cross-plugin call without prior grant.
2. Confirm HTTP `428` and pending request creation.
3. Confirm UI approval modal appears.
4. Approve request and retry call.
5. Confirm call succeeds without another prompt.
6. Deny request and confirm access stays blocked.
