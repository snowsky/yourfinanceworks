# Plugin Security Architecture — TODO

## Decision Pending

Evaluating two approaches for third-party plugin isolation:

### Option A: In-Process with Defense Layers (complex)
Designed 2026-04-04. Five layers:
1. PluginContext object (replace raw `app` pass)
2. DB restricted session + PostgreSQL role per plugin
3. Import audit/block hook (`sys.meta_path`)
4. Secret isolation (env namespace)
5. Subprocess isolation for external plugins

See full design in chat / `PROMPT_PLUGIN_CONVERSION.md`.

### Option B: Separate Docker Container per Plugin (preferred — investigate)
Each third-party plugin runs as its own Docker service (like yfw-socialhub standalone).
- Plugin has its own backend, DB, and optionally frontend container
- Main app proxies plugin API routes via reverse proxy / HTTP
- Auth via shared JWT secret or service token
- No shared memory, secrets, or DB access
- Naturally solves all isolation concerns with standard tooling

**yfw-socialhub already demonstrates this dual-mode pattern:**
- `standalone/` = runs as independent Docker service
- `plugin/` = embedded in-process plugin

## Next Steps
- [ ] Design the "sidecar plugin" Docker protocol
- [ ] Define how main app discovers and registers running plugin containers
- [ ] Define auth handshake (shared JWT secret vs. per-plugin service token)
- [ ] Define how plugin frontend UI is served/embedded (iframe vs. module federation)
- [ ] Decide: apply Option B only to third-party plugins, keep Option A for first-party?
