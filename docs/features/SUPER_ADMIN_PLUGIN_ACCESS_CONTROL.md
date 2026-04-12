# Super Admin Plugin Access Control

Centralized, platform-level control over which plugins are available to each organization. Only super administrators can install plugins on the server and decide which tenants are permitted to use them.

## Overview

Before this feature, any tenant admin could enable any installed plugin for their organization. This feature introduces a two-layer access model:

1. **Super admin** installs plugins on the server and grants access per organization
2. **Tenant admin** enables plugins within the set their super admin has granted

This allows operators of the platform to control plugin rollout, restrict commercial plugins to paying customers, and prevent unauthorized use of sensitive integrations.

---

## How It Works

### Layer 1 — Server-level (Super Admin)

Super admins manage plugins at the platform level:

- **Install / Uninstall / Reinstall** plugins from a git repository
- **Grant** a plugin to one or more organizations
- **Revoke** a plugin from an organization (automatically disables it for that tenant)

All of this is managed from the **Super Admin Dashboard → Plugins tab**, which shows a matrix of every installed plugin × every organization with a toggle per cell.

### Layer 2 — Tenant-level (Tenant Admin)

Tenant admins work within the set of plugins their super admin has granted:

- The Settings → Plugins page only shows enabled/disabled controls for plugins that have been granted to their organization
- Plugins not yet granted display a lock state with the message: *"This plugin has not been granted to your organization. Contact your super administrator."*
- Toggling, configuring, and cross-plugin access management work as before within the allowed set

---

## Super Admin UI

**Location:** Super Admin Dashboard → Plugins tab

The tab renders a matrix table:

| Plugin | Org A | Org B | Org C |
|---|---|---|---|
| Investments | ✅ | ✗ | ✅ |
| Time Tracking | ✅ | ✅ | ✗ |
| Currency Rates | ✅ | ✅ | ✅ |

Each cell has a toggle. Granting immediately allows the tenant admin to enable that plugin. Revoking immediately disables the plugin for that organization if it was active.

---

## API Reference

All endpoints under `/api/v1/plugins/admin/` require `is_superuser = true`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/plugins/admin/access` | List all grants across all tenants |
| `GET` | `/plugins/admin/tenants/{id}/access` | List granted plugins for a tenant |
| `POST` | `/plugins/admin/tenants/{id}/access` | Grant a plugin to a tenant |
| `DELETE` | `/plugins/admin/tenants/{id}/access/{plugin_id}` | Revoke a plugin from a tenant |
| `GET` | `/plugins/admin/plugins/{plugin_id}/tenants` | List tenants with access to a plugin |

**Grant payload:**
```json
{ "plugin_id": "investments" }
```

**Updated `/plugins/settings` response** now includes `available_plugins`:
```json
{
  "tenant_id": 1,
  "enabled_plugins": ["investments"],
  "available_plugins": ["investments", "time-tracking"],
  "updated_at": "2026-04-12T10:00:00Z"
}
```

**Install / Uninstall** endpoints (`/plugins/install`, `/plugins/{id}/uninstall`, `/plugins/{id}/reinstall`) now return **403** for non-superusers.

---

## Data Model

**`server_plugin_access`** (master database)

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | |
| `plugin_id` | String | Plugin identifier (e.g. `investments`) |
| `tenant_id` | Integer FK → tenants | Organization |
| `granted_by_id` | Integer FK → master_users | Super admin who granted access |
| `granted_at` | DateTime | When the grant was created |

Unique constraint on `(plugin_id, tenant_id)`.

---

## Behaviour on Revoke / Uninstall

- **Revoke** — removes the `server_plugin_access` row and immediately disables the plugin for that tenant's `TenantPluginSettings.enabled_plugins`
- **Uninstall** — removes the plugin files from disk, deletes all `server_plugin_access` rows for that plugin, and disables it for every tenant that had it enabled

---

## Implementation Notes

- Super admins bypass the allowlist check (they see all discovered plugins as available)
- The allowlist is enforced server-side on `POST /plugins/settings` (bulk) and `POST /plugins/settings/{id}/enable` — the UI restriction is a convenience layer only
- The `server_plugin_access` table is created automatically on server startup via `Base.metadata.create_all()`

---

## Related Features

- [Plugin Management](PLUGIN_MANAGEMENT.md) — core plugin enable/disable and configuration
- [Plugin Git Installer](PLUGIN_GIT_INSTALLER.md) — installing plugins from a git repository
- [Plugin Data Access Approvals](PLUGIN_DATA_ACCESS_APPROVALS.md) — cross-plugin data access control
