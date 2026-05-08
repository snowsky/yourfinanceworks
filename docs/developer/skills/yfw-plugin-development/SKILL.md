---
name: yfw-plugin-development
description: Use when creating or updating a YourFinanceWORKS yfw-* plugin, especially when it must support both standalone Docker Compose mode and invoice_app plugin/promoted mode with the host tenant database.
---

# YFW Plugin Development

Use this workflow when building a new `yfw-*` plugin for `invoice_app`.

## First Decisions

Decide which modes the plugin needs:

- **Standalone app**: plugin runs by itself with its own `docker-compose.yml`, backend, frontend, and Postgres.
- **Dynamic plugin**: plugin remains a sibling symlink/folder and is mounted into `invoice_app` with `docker-compose.plugin.yml`.
- **Promoted plugin**: plugin files are copied into `invoice_app` using `api/scripts/promote_plugin.py`.

If the user wants the plugin to use the same database as `invoice_app`, use dynamic plugin mode or promoted plugin mode. Do not use standalone mode for shared tenant data.

## Recommended Folder Layout

Match the `yfw-socialhub` style:

```text
yfw-example/
  backend/
    __init__.py
    router.py
    models.py
    schemas.py
    main.py                 # standalone only
    database.py             # standalone fallback only
    Dockerfile
    requirements.txt
  frontend/
    src/
      plugin.tsx            # plugin entry
      App or page files
    Dockerfile
    package.json
    vite.config.ts
  plugin/ui/index.ts        # compatibility re-export for invoice_app discovery
  plugin.json
  docker-compose.yml        # standalone
  docker-compose.plugin.yml # invoice_app overlay
  docker-compose.promote.yml
  README.md
```

## Database Rule

Plugin/promoted mode should import host app database/session helpers:

```python
from core.models.database import get_db
from core.models.models_per_tenant import Base
```

Standalone mode can fall back to local database wiring:

```python
try:
    from core.models.database import get_db
    from core.models.models_per_tenant import Base
except ModuleNotFoundError:
    from .database import Base, get_db
```

This keeps standalone development isolated while allowing the same backend files to use the `invoice_app` tenant database after mounting or promotion.

## Compose Files

Standalone `docker-compose.yml` should be a real app stack:

```text
db -> backend -> frontend
```

Plugin overlay `docker-compose.plugin.yml` should mount the plugin into the main stack:

```yaml
services:
  api:
    volumes:
      - ./yfw-example:/app/plugins_dynamic/example:ro
  ui:
    volumes:
      - ./yfw-example:/app/src/plugins_dynamic/example:ro
```

Promotion helper `docker-compose.promote.yml` can run:

```bash
python -B api/scripts/promote_plugin.py /workspace/yfw-example --force
```

## Promotion

From `invoice_app`:

```bash
python -B api/scripts/promote_plugin.py yfw-example --force
```

Expected behavior:

- `backend/*` copies into `api/plugins/<plugin_folder>/`
- `frontend/src/*` copies into `ui/src/plugins/<plugin_folder>/plugin/ui/`
- `frontend/src/plugin.tsx` maps to `plugin/ui/index.tsx`
- backend copies remain ignored unless `--track-backend` is passed

After promotion, the plugin should run inside the host API process and share the host tenant database.

## Frontend Notes

For standalone frontend builds:

- Include Vite env typing with `src/env.d.ts`.
- Include or avoid host-only imports such as `@/types/plugin-routes`.
- If reusing host Tailwind classes, add `tailwind.config.ts`, `postcss.config.js`, and `@tailwind` directives.

For plugin mode:

- Export `pluginMetadata`, `pluginRoutes`, and `navItems` from `frontend/src/plugin.tsx`.
- Keep `plugin/ui/index.ts` as a compatibility re-export:

```ts
export * from '../../frontend/src/plugin';
```

## Manifest

Use `plugin.json` at the plugin root. Include:

- `name`, `version`, `description`
- `license_tier`
- `database_tables`
- `features`
- `metadata.standalone` when dual-mode

If the user sees a commercial license gate during local development, check `license_tier`. Use `agpl` for ungated local/plugin access, or `commercial` intentionally when the feature should be gated.

## Documentation Checklist

Update the plugin README with:

- standalone command and URL
- dynamic plugin command
- promotion command
- table explaining which mode uses which database
- database tables
- API highlights
- licensing behavior if relevant

Also update `docs/developer/PLUGIN_DEVELOPMENT.md` when a new general plugin rule emerges.

## Validation

Run the smallest checks that apply:

```bash
python -B api/scripts/promote_plugin.py yfw-example --dry-run --force
docker compose config --quiet
docker compose -f docker-compose.yml -f yfw-example/docker-compose.plugin.yml config --quiet
PYTHONPATH=yfw-example python -m compileall -q yfw-example/backend
```

Build Docker images when dependencies or frontend toolchain changes:

```bash
docker compose build backend frontend
```
