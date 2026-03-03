# Plugin Auto-Discovery — Phase 1

## Overview

Phase 1 replaces all hardcoded plugin registrations with an automatic discovery system. The backend now scans `api/plugins/*/plugin.json` at startup and registers every plugin it finds. The frontend fetches the plugin list from a new API endpoint instead of using a hardcoded list.

**Result:** To install a new plugin, drop a folder into `api/plugins/` — no other files need to change.

---

## Files Changed

### New: `api/plugins/loader.py`

A `PluginLoader` class (singleton `plugin_loader`) with:

- **`import_models()`** — imports each plugin's `models.py` before `init_db()` so tables are created correctly
- **`register_all(app)`** — dynamically imports each plugin and calls its `register_plugin(app)` function
- **`get_valid_plugin_ids()`** — returns the set of discovered plugin IDs (used by API validation)
- **`get_registry()`** — returns list of manifest dicts (used by the `/plugins/registry` endpoint)

Discovery convention (tried in order):

1. `register_plugin(app)` — preferred standard name
2. `register_<folder_name>_plugin(app)` — legacy fallback (supports existing plugins)

### Modified: `api/main.py`

Removed 39 lines of two hardcoded plugin registration blocks and replaced with:

```python
from plugins.loader import plugin_loader
plugin_loader.import_models()   # before init_db()
# ... app creation & middleware ...
plugin_loader.register_all(app) # registers all discovered plugins
```

### Modified: `api/commercial/plugin_management/router.py`

- Removed: `VALID_PLUGINS = {"investments", "time-tracking"}` hardcoded set
- Added: `_valid_plugins()` that calls `plugin_loader.get_valid_plugin_ids()` dynamically
- Added: `GET /api/v1/plugins/registry` endpoint (public, no auth) returning all plugin manifests

### Modified: `ui/src/contexts/PluginContext.tsx`

Implemented `discoverExternalPlugins()` to call `GET /api/v1/plugins/registry`. The hardcoded `getBuiltInPlugins()` list is kept as an **offline fallback** if the backend is unreachable.

### Bug fixes (pre-existing)

| File                                  | Bug                                                                                          | Fix                                                        |
| ------------------------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `api/plugins/time_tracking/router.py` | Missing `from core.routers.auth import get_current_user` import (masked by load order)       | Added the import                                           |
| `api/plugins/investments/__init__.py` | Function named `register_investment_plugin` (singular) didn't match loader's legacy fallback | Added `register_plugin = register_investment_plugin` alias |

---

## Tests

**File:** `api/tests/test_plugin_loader.py` — 12 unit tests

| Test                                      | What it checks                             |
| ----------------------------------------- | ------------------------------------------ |
| `test_discover_valid_plugin`              | A valid `plugin.json` is discovered        |
| `test_discover_no_manifest`               | Directory without `plugin.json` is skipped |
| `test_discover_invalid_json`              | Malformed JSON is skipped, no crash        |
| `test_discover_missing_required_fields`   | Incomplete manifest is rejected            |
| `test_discover_skips_private_dirs`        | `_*` directories are ignored               |
| `test_discover_multiple_plugins`          | All valid plugins are found                |
| `test_get_valid_plugin_ids`               | Returns correct ID set                     |
| `test_get_registry`                       | Returns manifest dicts                     |
| `test_import_models_no_models_file`       | No-op when `models.py` absent              |
| `test_register_all_calls_register_plugin` | Dispatch works for standard name           |
| `test_register_all_legacy_function_name`  | Legacy fallback name works                 |
| `test_discovery_is_cached`                | Filesystem scanned only once               |

Run in container:

```bash
docker compose exec api python -m pytest tests/test_plugin_loader.py -v
```

Result: **12 passed** ✅

---

## Startup Log (after changes)

```
INFO:plugins.loader:Plugin discovered: investments v1.0.0
INFO:plugins.loader:Plugin discovered: time_tracking v1.0.0
INFO:plugins.loader:Plugin discovery complete — found 2 plugin(s): ['investments', 'time_tracking']
INFO:plugins.loader:Plugin 'investments': models imported.
INFO:plugins.loader:Plugin 'time_tracking': models imported.
INFO:plugins.loader:Plugin 'investments' registered — routes: ['/api/v1/investments']
INFO:plugins.loader:Plugin 'time_tracking' registered — routes: ['/api/v1/projects', '/api/v1/time-entries']
INFO:     Application startup complete.
```

---

## How to Add a Third-Party Plugin

```
api/plugins/my-plugin/
├── plugin.json          # required: name, version, description
├── __init__.py          # required: def register_plugin(app, mcp_registry=None, feature_gate=None)
├── models.py            # optional: SQLAlchemy models (auto-imported before init_db)
├── router.py            # your FastAPI routes
└── schemas.py           # Pydantic schemas
```

**`plugin.json` minimum:**

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "What this plugin does"
}
```

**`__init__.py` minimum:**

```python
def register_plugin(app, mcp_registry=None, feature_gate=None):
    from .router import my_router
    app.include_router(my_router, prefix="/api/v1/my-plugin", tags=["my-plugin"])
    return {"name": "my-plugin", "version": "1.0.0", "routes": ["/api/v1/my-plugin"]}
```

Restart the API — the plugin is automatically discovered, registered, and appears in `/api/v1/plugins/registry`.
