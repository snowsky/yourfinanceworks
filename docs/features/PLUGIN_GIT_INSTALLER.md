# Plugin Git Installer

**Module**: Commercial (`plugin_management`)
**License tier**: `plugin_management`
**Added**: 2026-03-17

## Overview

Administrators can install third-party or custom plugins directly from a git repository through the Settings → Plugins UI. The installer clones the repository, validates the manifest, installs Python dependencies, copies files into the correct locations, and provides real-time progress feedback.

> **Restart required.** After installation (or uninstallation), the server must be restarted and the frontend rebuilt before the plugin becomes active. The UI communicates this at each step.

---

## User Flow

### Install a Plugin

1. Go to **Settings → Plugins** (requires admin role + `plugin_management` license).
2. Click **"Install from Git"** in the top-right of the Plugins tab.
3. Enter the repository URL and optionally a branch/tag (default: `main`).
4. Click **"Install Plugin"** and watch the step-by-step progress.
5. On success, restart the server:
   ```bash
   docker-compose restart
   ```
   If the plugin includes frontend UI, also rebuild:
   ```bash
   docker-compose exec ui npm run build
   ```

### Uninstall a Plugin

1. Go to **Settings → Plugins**.
2. Find the plugin card and click **"Uninstall"** (admin only).
3. Confirm the dialog.
4. Restart the server to complete removal.

> Plugin database tables and tenant data are **not** deleted on uninstall — only the plugin files are removed.

---

## Plugin Repository Structure

A plugin repository must have `plugin.json` at its root. The repository root is treated as the plugin folder.

```
my-plugin-repo/
├── plugin.json          # Required manifest
├── __init__.py          # register_plugin() entry point
├── router.py            # FastAPI routes
├── models.py            # SQLAlchemy models (optional)
├── schemas.py           # Pydantic schemas (optional)
├── requirements.txt     # Python dependencies (optional)
└── ui/                  # Frontend plugin (optional)
    └── index.ts         # Must export pluginRoutes + navItems
```

Alternatively, the repository may use a nested layout:

```
my-plugin-repo/
└── api/
    └── plugins/
        └── my_plugin/
            ├── plugin.json
            └── ...
```

See [PLUGIN_DEVELOPMENT.md](../developer/PLUGIN_DEVELOPMENT.md) for the full plugin authoring guide.

---

## Install Steps

The installer runs these steps sequentially in a background job:

| Step | Description |
|---|---|
| Cloning repository | `git clone --depth 1 --branch <ref> <url>` |
| Validating plugin manifest | Checks `plugin.json` exists and has `name`, `version`, `description` |
| Installing Python dependencies | `pip install -r requirements.txt` (skipped if no file) |
| Installing plugin files | Copies backend files to `api/plugins/<name>/` |
| Frontend files | Copies `ui/` to `ui/src/plugins/<name>/` if present |
| Registering plugin | Resets the plugin loader cache |

Progress is polled every 2 seconds and displayed live in the modal. On failure, partial files are cleaned up automatically.

---

## API Endpoints

All endpoints require admin role and `plugin_management` license.

### Start Installation

```
POST /api/v1/plugins/install
```

**Request body:**
```json
{
  "git_url": "https://github.com/org/my-plugin",
  "ref": "main"
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Installation started",
  "status_url": "/api/v1/plugins/install/status/550e8400-..."
}
```

### Poll Install Status

```
GET /api/v1/plugins/install/status/{job_id}
```

**Response:**
```json
{
  "job_id": "550e8400-...",
  "status": "done",
  "plugin_id": "my-plugin",
  "error": null,
  "restart_required": true,
  "steps": [
    { "label": "Cloning repository", "status": "done", "detail": "Cloned from https://... @main" },
    { "label": "Validating plugin manifest", "status": "done", "detail": "Plugin: My Plugin v1.0.0" },
    { "label": "Installing plugin files", "status": "done", "detail": "Backend installed to plugins/my_plugin/" },
    { "label": "Frontend files", "status": "done", "detail": "Frontend installed to ui/src/plugins/my_plugin/" },
    { "label": "Registering plugin", "status": "done", "detail": "Plugin loader cache reset — restart required" }
  ]
}
```

`status` values: `pending` | `running` | `done` | `failed`

### Uninstall Plugin

```
DELETE /api/v1/plugins/{plugin_id}/uninstall
```

**Response:**
```json
{
  "plugin_id": "my-plugin",
  "message": "Plugin 'my-plugin' uninstalled. A server restart is required.",
  "restart_required": true
}
```

---

## Implementation Files

### Backend

| File | Purpose |
|---|---|
| `api/commercial/plugin_management/services/git_installer.py` | Core installer: git clone, validation, file copy, cache reset |
| `api/commercial/plugin_management/router.py` | Endpoints: `/install`, `/install/status/{id}`, `/{id}/uninstall` |

### Frontend

| File | Purpose |
|---|---|
| `ui/src/components/settings/InstallPluginModal.tsx` | Install dialog with URL input and live progress |
| `ui/src/components/settings/PluginsTab.tsx` | "Install from Git" button + uninstall button per card |
| `ui/src/lib/api/plugins.ts` | `installFromGit`, `getInstallStatus`, `uninstallPlugin` |

---

## Security Considerations

- **Admin only**: All install/uninstall endpoints enforce admin role.
- **URL validation**: Only `https://`, `http://`, `git@`, and `ssh://` URLs are accepted. Shell metacharacters (`;`, `&&`, `|`, `` ` ``, `$`) are rejected.
- **No shell injection**: `git clone` and `pip install` are called via `subprocess` with list arguments — never `shell=True`.
- **Temp directory**: The repo is cloned into a system temp dir. On failure, partial backend files are removed automatically.
- **Trust**: Only install plugins from sources you control or trust. A plugin has full access to the Python process and database.

---

## Limitations

- **No hot-reload**: Both the backend (Python imports at startup) and frontend (Vite `import.meta.glob` at build time) require a restart/rebuild after install.
- **Single-process job store**: Install job status is stored in-memory. It is lost on server restart and not shared across multiple API workers.
- **No signature verification**: Plugin archives are not signed or checksum-verified. Planned for a future release.
- **Private repositories**: SSH-based git URLs are supported (`git@github.com:org/repo.git`) but require the server's SSH key to have access to the repository.
