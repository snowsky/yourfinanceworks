# Plugin Data Access Approvals User Guide

## What This Is

Plugin data is isolated by default.

If one plugin needs data from another plugin, the app asks for your approval before sharing that data.

## What You Will See

When access is needed, a modal appears:

- **Title**: Plugin Data Access Request
- **Details**: Which plugin is requesting access, which plugin's data is being requested, and whether it is read/write intent.
- **Actions**:
  - **Allow Access**
  - **Deny**

## What Each Choice Means

- **Allow Access**
  - Grants access for that plugin pair in your tenant/user scope.
  - Future requests of the same scope will not prompt again unless policy changes.

- **Deny**
  - Blocks the current request.
  - The plugin action that needed that data will remain unavailable.

## Recommended User Action

Before clicking **Allow Access**, confirm:

1. You trust the requesting plugin and workflow.
2. The request reason matches what you were trying to do.
3. The requested data is necessary for that workflow.

If unclear, click **Deny** and contact your administrator.

## For Administrators

- Admins can review and resolve requests tenant-wide.
- Non-admin users can only resolve their own requests.

## Troubleshooting

### I denied by mistake

Trigger the same workflow again. You can approve when the prompt reappears, or ask an admin to approve from access requests.

### I approved, but action still fails

1. Refresh the page.
2. Retry the action.
3. If still failing, contact admin/support with:
   - source plugin
   - target plugin
   - approximate time of request

### I do not see a prompt

- Ensure you are logged in.
- Ensure the workflow actually requires cross-plugin data.
- Check with admin to verify plugin permissions and status.
