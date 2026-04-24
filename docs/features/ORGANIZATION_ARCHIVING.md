# Organization Archiving

Organization archiving lets super administrators retire an organization without deleting its data, tenant database, users, or audit history. Archived organizations are removed from normal access and license capacity while remaining available for super-admin review and audit.

## Overview

Before archiving, the super-admin delete action permanently removed tenant-related master records and dropped the tenant database. The archive flow replaces that destructive behavior with a reversible lifecycle state:

- Organization data is preserved.
- The tenant database is kept.
- Normal users cannot access the organization.
- The organization no longer counts against the licensed organization limit.
- Super admins can still see and audit the archived organization.
- Super admins can restore the organization if it should become active again.

## Archive State

Archiving updates the master `tenants` row:

| Field | Archived value | Purpose |
|---|---:|---|
| `is_active` | `false` | Shows the organization as inactive in admin views |
| `is_enabled` | `false` | Blocks normal tenant access through tenant context middleware |
| `count_against_license` | `false` | Frees license capacity for another organization |
| `archived_at` | Current timestamp | Records when the archive happened |
| `archived_by_id` | Current super admin ID | Records who archived it |
| `archive_reason` | `"Archived by super admin"` | Stores archive context |

No tenant data is deleted during archive.

## Super Admin UI

Location: **Super Admin Dashboard -> Organizations tab**

Available actions:

- **Archive**: Replaces the previous delete action for non-current organizations.
- **Restore**: Appears for archived organizations.
- **Enable / Disable**: Available only for non-archived organizations.

Archived organizations show an **Archived** status badge. The dashboard organization count includes archived organizations, and the summary text also shows how many are archived.

## License Capacity Behavior

Archived organizations do not count against the global organization limit because `count_against_license` is set to `false`.

When a super admin creates a new organization, the capacity check counts only tenants where:

```sql
count_against_license = true
```

This means archiving an organization immediately frees one organization slot for licensing purposes.

Restoring an organization sets `count_against_license` back to `true`. Operators should confirm license capacity before restoring in production environments where the tenant limit is already full.

## Audit Behavior

Archiving and restoring emit master audit events:

| Action | When emitted |
|---|---|
| `ARCHIVE_TENANT` | A super admin archives an organization |
| `RESTORE_TENANT` | A super admin restores an archived organization |

Archived organizations remain available in the audit organization selector and are labeled with `(Archived)`.

Super admins can audit archived organizations through:

- **Audit Log -> organization selector**
- Specific tenant audit log queries using `organization_id`
- Master audit log views for archive and restore events

## API Reference

All endpoints require a super admin.

### Archive Organization

```http
DELETE /api/v1/super-admin/tenants/{tenant_id}
```

Despite the `DELETE` method, this endpoint now performs a soft archive. It does not drop the tenant database and does not delete master or tenant data.

Success response:

```json
{
  "message": "Tenant Example Org archived successfully"
}
```

Guards:

- Returns `404` if the organization does not exist.
- Returns `400` when trying to archive the current super admin's own organization.
- Returns success with an "already archived" message if the organization is already archived.

### Restore Organization

```http
PATCH /api/v1/super-admin/tenants/{tenant_id}/restore
```

Restores access and license counting for an archived organization.

Success response:

```json
{
  "message": "Tenant Example Org restored successfully"
}
```

Restore sets:

- `is_active = true`
- `is_enabled = true`
- `count_against_license = true`
- `archived_at = null`
- `archived_by_id = null`
- `archive_reason = null`

### Toggle Status

```http
PATCH /api/v1/super-admin/tenants/{tenant_id}/toggle-status
```

This remains the enable/disable endpoint for active organizations. Archived organizations must be restored before their status can be toggled.

## Data Model

Archive metadata is stored on the existing master `tenants` table.

New columns:

| Column | Type | Nullable | Description |
|---|---|---:|---|
| `archived_at` | `DateTime(timezone=True)` | Yes | Archive timestamp |
| `archived_by_id` | `Integer` | Yes | Master user ID of the super admin who archived it |
| `archive_reason` | `Text` | Yes | Human-readable archive reason |

Migration:

```text
api/alembic/versions/019_add_tenant_archive_columns.py
```

Startup compatibility:

`api/db_init.py` also backfills these columns when they are missing, which keeps older local or demo databases compatible.

## Operational Notes

- Archive is reversible. Hard deletion is no longer the normal organization lifecycle path.
- Tenant databases for archived organizations remain on disk/Postgres and should continue to be included in backups.
- Background jobs that enumerate active tenants use `is_active = true`, so archived organizations are skipped by normal active-tenant processing.
- Normal tenant access is blocked through `is_enabled = false`.
- Archived data should still be treated as retained customer data for backup, export, and compliance policies.

## Verification

Check archive state:

```sql
SELECT
  id,
  name,
  is_active,
  is_enabled,
  count_against_license,
  archived_at IS NOT NULL AS is_archived
FROM tenants
ORDER BY id;
```

Check audit events:

```sql
SELECT action, resource_id, resource_name, status, created_at
FROM audit_logs
WHERE action IN ('ARCHIVE_TENANT', 'RESTORE_TENANT')
ORDER BY created_at DESC;
```

## Related Documentation

- [Super Admin Plugin Access Control](SUPER_ADMIN_PLUGIN_ACCESS_CONTROL.md)
- [Plugin Management](PLUGIN_MANAGEMENT.md)
- [License Administration Guide](../admin-guide/LICENSE_ADMINISTRATION_GUIDE.md)
- [Super Admin System Guide](../admin-guide/SUPER_ADMIN_SYSTEM.md)
