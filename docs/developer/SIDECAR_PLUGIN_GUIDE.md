# Sidecar Plugin Guide

This guide covers how to build, configure, and deploy a **sidecar plugin** for YourFinanceWORKS. Sidecar plugins run as isolated Docker containers (with their own database) and embed into the main app via an `<iframe>`.

See also: [PLUGIN_DEVELOPMENT.md](./PLUGIN_DEVELOPMENT.md) for built-in plugins.

---

## 1. Plugin Descriptor (`plugin.json`)

Place `plugin.json` at the root of the plugin repo. Key fields:

```json
{
  "id": "socialhub",
  "name": "Social Hub",
  "version": "0.1.0",
  "mode": "sidecar",
  "service_name": "plugin_socialhub",
  "api_prefix": "/api/v1/socialhub",
  "ui_entry": "/plugins/socialhub/",
  "nav_items": [
    { "id": "socialhub", "path": "/socialhub", "label": "Social Hub", "icon": "Share2", "priority": 40 }
  ]
}
```

- **`ui_entry`** — must match the nginx location block exactly (including trailing slash).
- **`nav_items[].path`** — path in the *main* app router (e.g. `/socialhub`), not inside the iframe.
- The main app reads `plugin.json` from `http://plugin_{id}:8000/plugin.json` at startup.

---

## 2. Backend (`backend/`)

- Expose a `GET /health` endpoint (used for Docker healthcheck and sidecar discovery).
- Expose a `GET /plugin.json` endpoint (or static file at root) so the main app can read metadata.
- Use absolute imports (not relative `..` imports) — the backend runs flat, not as a package.
- Validate JWTs using `YFW_SECRET_KEY` (shared with the main app via env var).

---

## 3. Frontend Vite Configuration

When served at `/plugins/socialhub/` by the main nginx, Vite must emit asset URLs with that prefix.

`frontend/vite.config.ts`:
```typescript
const isSidecar = process.env.VITE_MODE === 'sidecar';

export default defineConfig({
  base: isSidecar ? '/plugins/socialhub/' : '/',
  // ...
});
```

Build with `--build-arg VITE_MODE=sidecar` in the Dockerfile.

---

## 4. Frontend React Router

The plugin UI is loaded inside an iframe whose URL is `https://host/plugins/socialhub/`. The main app controls the *outer* URL (`/socialhub`). The plugin's React Router must use `basename` matching what the browser sees inside the iframe:

```tsx
// The iframe src is /plugins/socialhub/ → browser pathname is /plugins/socialhub/
<BrowserRouter>
  <Routes>
    <Route path="/" element={<Dashboard />} />
    <Route path="/posts" element={<PostList />} />
  </Routes>
</BrowserRouter>
```

Or, if React Router needs to match paths including the base:
```tsx
<BrowserRouter basename="/plugins/socialhub">
  <Routes>
    <Route path="/" element={<Dashboard />} />
  </Routes>
</BrowserRouter>
```

---

## 5. Frontend nginx (`frontend/nginx.conf`)

This is the nginx inside the plugin UI container. It receives requests **after** the main nginx strips the `/plugins/socialhub/` prefix.

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://${BACKEND_HOST}:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
    }

    # Hashed assets — cache indefinitely (filename changes on content change)
    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
        try_files $uri =404;
    }

    # index.html — never cache (prevents stale HTML with wrong asset hashes)
    location / {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        try_files $uri $uri/ /index.html;
    }
}
```

Use the nginx template mechanism (`/etc/nginx/templates/default.conf.template`) so `${BACKEND_HOST}` is substituted at container startup.

---

## 6. Main App nginx (`infra/docker/nginx-plugins/socialhub.conf`)

Copy `socialhub.conf.example` to `socialhub.conf` to activate. **Do not** check `socialhub.conf` into git (it's site-specific).

**Critical rules:**
- `set $upstream` must come **before** `rewrite` — `rewrite ... break` stops all subsequent rewrite-module directives (including `set`).
- Use `proxy_pass http://$var;` (no trailing URI) — with a variable, nginx does NOT strip the location prefix automatically; use an explicit `rewrite` instead.

```nginx
location /api/v1/socialhub/ {
    set $upstream_socialhub plugin_socialhub:8000;
    proxy_pass http://$upstream_socialhub;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Authorization $http_authorization;
    proxy_read_timeout 120s;
}

location /plugins/socialhub/ {
    set $upstream_socialhub_ui plugin_socialhub_ui:80;          # ← set BEFORE rewrite
    rewrite ^/plugins/socialhub/(.*)$ /$1 break;                # ← strips prefix
    proxy_pass http://$upstream_socialhub_ui;                   # ← no trailing URI
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The main nginx includes all files in `infra/docker/nginx-plugins/*.conf` automatically.

---

## 7. Plugin Folder Location

The plugin repository folder (e.g. `yfw-socialhub/`) **must be placed in the root of the `yourfinanceworks` repository**:

```
yourfinanceworks/
├── api/
├── ui/
├── infra/
├── yfw-socialhub/        ← plugin folder here
│   ├── plugin.json
│   ├── backend/
│   ├── frontend/
│   └── docker-compose.plugin.yml
└── docker-compose.yml
```

This is required because:
- Docker Compose build context paths in `docker-compose.plugin.yml` are resolved relative to `yourfinanceworks/` (the directory of the first `-f` file).
- The `docker-compose.plugin.yml` references `./yfw-socialhub/backend` and `./yfw-socialhub/frontend` as build contexts.
- The main app's nginx volume mount (`./infra/docker/nginx-plugins/`) is also relative to `yourfinanceworks/`.

If the plugin folder is elsewhere, symlink it or adjust the context paths in `docker-compose.plugin.yml`.

---

## 8. Docker Compose (`docker-compose.plugin.yml`)

```yaml
services:
  plugin_socialhub:
    build:
      context: ./yfw-socialhub          # relative to yourfinanceworks/ (the -f base)
      dockerfile: backend/Dockerfile
    environment:
      YFW_SECRET_KEY: ${SECRET_KEY}
      SOCIALHUB_DATABASE_URL: postgresql://...
    networks:
      - yourfinanceworks_network

  plugin_socialhub_ui:
    build:
      context: ./yfw-socialhub/frontend
      dockerfile: Dockerfile
      args:
        VITE_MODE: sidecar
    environment:
      BACKEND_HOST: plugin_socialhub
    networks:
      - yourfinanceworks_network

networks:
  yourfinanceworks_network:
    driver: bridge   # Docker reuses the main app network when merged via -f
```

**Context paths** are relative to the **first** `-f` file's directory (yourfinanceworks/), not this file's location.

---

## 8. Deployment

```bash
# From yourfinanceworks/ directory:

# Build and start plugin services
docker compose -f docker-compose.yml -f yfw-socialhub/docker-compose.plugin.yml \
  up -d --build plugin_socialhub plugin_socialhub_ui

# Copy and activate nginx conf
cp infra/docker/nginx-plugins/socialhub.conf.example \
   infra/docker/nginx-plugins/socialhub.conf

# Reload nginx (no restart needed)
docker compose exec nginx nginx -s reload

# Set env var so the API discovers the sidecar on next restart
# Add to .env:  SIDECAR_PLUGINS=socialhub
docker compose restart api
```

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `using uninitialized "$upstream_socialhub_ui" variable` | `set` after `rewrite ... break` | Move `set` before `rewrite` |
| `invalid URL prefix in "http://"` | Same — variable was never set | Same fix |
| `text/html` MIME for JS asset (browser only) | Browser cached old broken response | Hard refresh (Ctrl+Shift+R) |
| `Failed to load module script: text/html` | Wrong nginx routing or cached bad response | Check `curl -I` on the asset URL; hard refresh |
| Plugin not in sidebar after `SIDECAR_PLUGINS=socialhub` | API started before plugin healthy | API has retry logic (10 × 5s); restart API if needed |
| `host not found: plugin_socialhub` in plugin UI nginx | Hardcoded hostname, not using template | Use `${BACKEND_HOST}` in nginx.conf template |
| `ImportError: attempted relative import` | Relative imports fail in flat-run backend | Convert all `..X` / `.X` imports to absolute |
| `FileNotFoundError: plugin.json` | Wrong path in main.py | Use `Path(__file__).parent / "plugin.json"` |
