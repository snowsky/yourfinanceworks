# Plugin Development Guide

This guide explains how to build a plugin for YourFinanceWORKS. Plugins are self-contained directories that the system discovers and registers automatically — no changes to core application files are needed.

---

## Table of Contents

1. [How auto-discovery works](#how-auto-discovery-works)
2. [Plugin directory structure](#plugin-directory-structure)
3. [Backend: required files](#backend-required-files)
4. [Frontend: required files](#frontend-required-files)
5. [Using third-party services](#using-third-party-services)
6. [Database models and migrations](#database-models-and-migrations)
7. [Cross-Plugin Data Access](#cross-plugin-data-access)
8. [Installing a plugin](#installing-a-plugin)
9. [Sample plugin: currency-rates](#sample-plugin-currency-rates)

---

## How auto-discovery works

```
Application startup
      │
      ▼
PluginLoader.discover()
  └── scans api/plugins/*/plugin.json
  └── validates required fields (name, version, description)
  └── skips _private or malformed directories
      │
      ▼
PluginLoader.import_models()
  └── imports each plugin's models.py (if present)
  └── SQLAlchemy registers the tables before init_db() runs
      │
      ▼
PluginLoader.register_all(app)
  └── for each discovered plugin:
        1. imports __init__.py
        2. calls register_plugin(app) — or legacy register_<name>_plugin(app)
        3. logs registered routes
      │
      ▼
GET /api/v1/plugins/registry
  └── returns the list of discovered plugin manifests
  └── frontend PluginContext fetches this to know which plugins exist
```

Plugins are also validated against the enabled/disabled state stored per-tenant. A plugin can be installed but toggled off per user through **Settings → Plugins**.

---

## Plugin directory structure

```
api/plugins/my_plugin/          ← backend (snake_case folder name)
├── plugin.json                 ← REQUIRED: manifest
├── __init__.py                 ← REQUIRED: register_plugin()
├── router.py                   ← your FastAPI routes
├── models.py                   ← optional: SQLAlchemy models
└── schemas.py                  ← optional: Pydantic schemas

ui/src/plugins/my_plugin/       ← frontend (same snake_case name)
└── index.ts                    ← REQUIRED: pluginRoutes config

ui/src/pages/my_plugin/         ← your page components
└── MyPage.tsx
```

---

## Backend: required files

### `plugin.json` — manifest

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "What this plugin does",
  "license_tier": "agpl",
  "features": ["feature-a", "feature-b"]
}
```

Required fields: `name`, `version`, `description`.

### `__init__.py` — registration entry point

```python
def register_plugin(app, mcp_registry=None, feature_gate=None):
    from .router import router
    app.include_router(router, prefix="/api/v1", tags=["my-plugin"])
    return {
        "name": "my-plugin",
        "version": "1.0.0",
        "routes": ["/api/v1/my-plugin"],
    }
```

The loader calls `register_plugin(app)`. The returned dict is used for logging only.

### `router.py` — FastAPI routes

```python
from fastapi import APIRouter, Depends
from core.models.database import get_db
from core.routers.auth import get_current_user

router = APIRouter()

@router.get("/my-plugin")
def get_my_plugin(db=Depends(get_db), user=Depends(get_current_user)):
    return {"message": "hello from my-plugin"}
```

> [!NOTE]
> Always import `get_current_user` directly in your `router.py` — do not rely on it being imported transitively. This becomes important when the plugin is loaded dynamically.

---

## Frontend: required files

### `ui/src/plugins/my_plugin/index.ts`

```typescript
import React from "react";
import type { PluginRouteConfig } from "@/types/plugin-routes";

const MyPage = React.lazy(() => import("@/pages/my_plugin/MyPage"));

export const pluginMetadata = {
  name: "my-plugin",
  displayName: "My Plugin",
  version: "1.0.0",
  licenseTier: "agpl",
  description: "What this plugin does",
};

export const pluginRoutes: PluginRouteConfig[] = [
  {
    path: "/my-plugin",
    component: MyPage,
    pluginId: "my-plugin",
    pluginName: "My Plugin",
    label: "My Plugin",
    // requiresRole: ['admin', 'user'],  // optional role gate
    // errorBoundary: false,             // set false for lightweight routes
  },
];
```

Then in `App.tsx`, add one import and one spread:

```typescript
import { pluginRoutes as myPluginRoutes } from "./plugins/my_plugin";
const allPluginRoutes = [...existingRoutes, ...myPluginRoutes];
```

The `buildPluginElement()` renderer automatically wraps each route with:

- **`PluginRouteGuard`** — shows "plugin disabled" if toggled off
- **`PluginRouteErrorBoundary`** — catches runtime errors (on by default)
- **`RoleProtectedRoute`** — only when `requiresRole` is set

---

## Using third-party services

> [!IMPORTANT]
> Always proxy external API calls through your plugin's backend router. **Never call third-party APIs directly from the browser** in a plugin.

**Why proxy through the backend?**

| Concern          | Direct (browser)                  | Via plugin backend                |
| ---------------- | --------------------------------- | --------------------------------- |
| CORS             | Many APIs block browser origins   | Not an issue                      |
| API key security | Key exposed in source/network tab | Key stays server-side             |
| Rate limits      | Each user eats quota              | One server cache serves all users |
| Offline fallback | JS error, white screen            | Backend can return static data    |

**Pattern (see `currency_rates/router.py` for a full example):**

```python
import httpx, time

_cache = {}
CACHE_TTL = 3600   # seconds

@router.get("/my-plugin/external-data")
async def get_external_data():
    now = time.time()
    if "data" in _cache and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["data"]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.example.com/data")
            resp.raise_for_status()
            result = resp.json()
            _cache.update({"data": result, "fetched_at": now})
            return result
    except Exception as e:
        logger.warning("External fetch failed: %s", e)
        return STATIC_FALLBACK   # always provide a fallback
```

**On the frontend**, tell the user whether data is live or from a fallback. Include a `source` field in your response (`"live"` / `"fallback"`) and display an appropriate indicator.

---

## Database models and migrations

If your plugin needs its own tables:

**`models.py`** — define SQLAlchemy models using the per-tenant base:

```python
from core.models.models_per_tenant import Base
from sqlalchemy import Column, Integer, String

class MyPluginRecord(Base):
    __tablename__ = "my_plugin_records"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255))
```

The `PluginLoader` imports `models.py` automatically before `init_db()` runs, so tables are created at startup.

For production use, add a proper Alembic migration under `api/alembic/versions/`.

---

## Cross-Plugin Data Access

Plugin-to-plugin API calls are isolated by default.

- If `Plugin A` calls `Plugin B` with header `X-Plugin-Caller: plugin-a`, backend guard checks whether the current user approved that access.
- If not approved, backend returns `428` with `PLUGIN_ACCESS_APPROVAL_REQUIRED` and creates a pending request.
- UI listens for that event and shows an approval dialog. User can approve/deny directly.

### Backend: protect plugin routes

```python
from fastapi import Depends
from core.utils.plugin_access_guard import require_plugin_access

app.include_router(
    my_router,
    prefix="/api/v1/my-plugin",
    dependencies=[Depends(require_plugin_access("my-plugin"))],
)
```

### Frontend: call another plugin

Use `pluginToPluginRequest` to request access and include caller identity:

```ts
import { pluginToPluginRequest } from '@/lib/plugin-access';

const rates = await pluginToPluginRequest({
  sourcePlugin: 'time-tracking',
  targetPlugin: 'currency-rates',
  url: '/currency-rates?base=USD',
  options: { method: 'GET' },
  reason: 'Convert project totals to the selected currency',
});
```

If approval is missing, the helper raises `PLUGIN_ACCESS_APPROVAL_REQUIRED`; the UI dialog will handle the decision flow.

---

## Installing a plugin

1. Drop the plugin folder into `api/plugins/my_plugin/`
2. Drop the UI folder into `ui/src/plugins/my_plugin/`
3. Add the page component(s) to `ui/src/pages/my_plugin/`
4. Add the import + spread to `App.tsx` (two lines)
5. Restart the API container:
   ```bash
   docker compose restart api
   ```
6. The plugin appears in Settings → Plugins and can be enabled per-tenant.

> [!TIP]
> Check the API logs after restart to confirm discovery:
>
> ```
> INFO:plugins.loader:Plugin discovered: my-plugin v1.0.0
> INFO:plugins.loader:Plugin 'my-plugin' registered — routes: ['/api/v1/my-plugin']
> ```

---

## Sample plugin: currency-rates

The full working example lives at:

- **Backend:** [`api/plugins/currency_rates/`](file:///Users/hao/dev/github/machine_learning/hao_projects/invoice_app/api/plugins/currency_rates/)
- **Frontend:** [`ui/src/plugins/currency_rates/`](file:///Users/hao/dev/github/machine_learning/hao_projects/invoice_app/ui/src/plugins/currency_rates/) and [`ui/src/pages/currency_rates/`](file:///Users/hao/dev/github/machine_learning/hao_projects/invoice_app/ui/src/pages/currency_rates/)

It demonstrates:

- ✅ No database tables required
- ✅ Live data from a free public API (`open.er-api.com`)
- ✅ 1-hour server-side cache
- ✅ Static fallback when the API is unreachable
- ✅ `source` field in the response so the UI can show a live/fallback badge
- ✅ In-page explanation of how the third-party service integration works
