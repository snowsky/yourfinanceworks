# Prompt for Plugin Conversion (AI Agent Edition)

**Task**: Convert a standard project (typically with `backend/` and `frontend/` directories) into a **YourFinanceWORKS-compatible plugin structure** based on the official `yfw-plugin-template`.

## Context
YourFinanceWORKS (YFW) uses a unified plugin system where each plugin can run **standalone** (for development/testing) or as a **plugin** (integrated into the main YFW host app).

## Target Structure
- `shared/`: Logic shared between both modes.
  - `shared/api/`: Models, Schemas, CRUD, Services, Routers.
  - `shared/ui/`: Pages, Components, Hooks, API clients, Styles.
- `plugin/`: Registration logic for the host app.
  - `plugin/api/__init__.py`: Exports `register_plugin(app)` to mount routes.
  - `plugin/ui/index.ts`: Exports `pluginRoutes`, `navItems`, `pluginMetadata`.
- `standalone/`: Independent dev setup.
  - `standalone/api/main.py`: Entry point for local Uvicorn development.
  - `standalone/ui/`: Vite config, `index.html`, and `main.tsx` for local frontend development.
  - `standalone/api/Dockerfile`: Docker config for standalone deployment only.
- `plugin.json`: Metadata (name, version, database tables, API routes).
- `__init__.py` (root): Prepends the plugin directory to `sys.path`.

## Step-by-Step Instructions

### 1. Research & Metadata
- Identification of database tables from `backend/app/models.py`.
- Identification of API routes from `backend/app/main.py` or routers.
- Creation of `plugin.json` at the root.

### 2. Restructuring Backend
- Migration of core backend files to `shared/api/`.
- Fixing of imports (e.g., `from app.models` -> `from shared.api.models`).
- Ensuring `database.py` is generic enough for both modes.

### 3. Restructuring Frontend
- Migration of `frontend/src/` to `shared/ui/`.
- Decoupling of `App.tsx` logic so pages can be lazy-loaded in plugin mode.
- Fixing of asset paths and aliases.

### 4. Implementation of Plugin Layer
- Creation of `plugin/api/__init__.py`:
  - Usage of `app.include_router(...)`.
- Creation of `plugin/ui/index.ts`:
  - Export of `pluginRoutes` using lazy imports from `../../shared/ui/pages/...`.
  - Definition of `navItems` with appropriate icons.

### 5. Implementation of Standalone Layer
- Creation of `standalone/api/main.py` (copy of original `backend/main.py`, adjusted for `shared` imports).
- Movement of `Dockerfile` to `standalone/api/`.

### 6. Cleanup
- Removal of original `backend/` and `frontend/` directories.
- Removal of `alembic` (not needed for new plugins).
- Consolidation of `package.json` and `requirements.txt` at the root.

## Constraints
- **Reliability**: Always check if `sys.path` is updated in the root `__init__.py`.
- **Aesthetics**: Ensure the UI follows the host app's styling (Tailwind/CSS variables).
- **Isolation**: Plugins must not pollute the global namespace.
- **Docker**: Development Docker files stay in `standalone/`.
