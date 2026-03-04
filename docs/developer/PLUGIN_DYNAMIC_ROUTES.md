# Plugin Dynamic UI Routes — Phase 2

## Overview

Plugin pages are now registered via each plugin's own `index.ts` rather than being hardcoded in `App.tsx`. A generic `PluginRoutes` renderer component wraps each page with the appropriate guards automatically.

**Result:** To add a new plugin's pages, define them in the plugin's `index.ts` and add the routes to `allPluginRoutes` in `App.tsx`. No other files need to change.

---

## Files Changed

### New: `ui/src/types/plugin-routes.ts`

Defines `PluginRouteConfig` — the typed contract between plugin route declarations and the renderer:

```ts
interface PluginRouteConfig {
  path: string;
  component: React.LazyExoticComponent<React.ComponentType<any>>;
  pluginId: string;
  pluginName: string;
  label: string;
  requiresRole?: ("admin" | "user" | "superuser")[];
  errorBoundary?: boolean; // default true
}
```

### New: `ui/src/components/plugins/PluginRoutes.tsx`

Generic renderer that takes `PluginRouteConfig[]` and for each entry renders:

```
<Route path={r.path}>
  <PluginRouteGuard>           ← always: shows "plugin disabled" if plugin is off
    <PluginRouteErrorBoundary> ← optional (default on): catches runtime errors
      <RoleProtectedRoute>     ← optional: when requiresRole is set
        <PageComponent />
```

### Modified: `ui/src/plugins/investments/index.ts`

Replaced 3 string stubs with **8 typed `PluginRouteConfig` objects** with real `React.lazy` imports:

| Route                                    | Role-gated?      |
| ---------------------------------------- | ---------------- |
| `/investments`                           | No               |
| `/investments/portfolio/new`             | Yes (admin/user) |
| `/investments/portfolio/:id`             | No               |
| `/investments/portfolio/:id/performance` | No               |
| `/investments/portfolio/:id/rebalance`   | No               |
| `/investments/analytics`                 | No               |
| `/investments/tax-export`                | No               |
| `/investments/cross-portfolio`           | No               |

### Modified: `ui/src/plugins/time_tracking/index.ts`

Added **2 typed `PluginRouteConfig` objects** with real lazy refs:

| Route            | Role-gated?      |
| ---------------- | ---------------- |
| `/time-tracking` | No               |
| `/projects/:id`  | Yes (admin/user) |

### Modified: `ui/src/App.tsx`

- Removed 10 individual lazy imports for investment/time-tracking pages
- Removed ~110 lines of hardcoded plugin route JSX
- Added 6 lines:

```tsx
import { PluginRoutes } from "./components/plugins/PluginRoutes";
import { pluginRoutes as investmentRoutes } from "./plugins/investments";
import { pluginRoutes as timeTrackingRoutes } from "./plugins/time_tracking";
const allPluginRoutes = [...investmentRoutes, ...timeTrackingRoutes];

// Inside <Routes>:
<PluginRoutes routes={allPluginRoutes} />;
```

Kept `<Navigate>` redirects for `/projects` and `/time` (app-level concerns, not plugin-specific).

---

## Verification

```
docker compose exec ui npx tsc --noEmit  →  0 errors ✅
```

---

## How to Add a New Plugin's Pages

**`ui/src/plugins/my-plugin/index.ts`:**

```ts
import React from "react";
import type { PluginRouteConfig } from "@/types/plugin-routes";

const MyPage = React.lazy(() => import("@/pages/my-plugin/MyPage"));

export const pluginRoutes: PluginRouteConfig[] = [
  {
    path: "/my-plugin",
    component: MyPage,
    pluginId: "my-plugin",
    pluginName: "My Plugin",
    label: "My Plugin",
  },
];
```

**`ui/src/App.tsx`** — one line change:

```ts
import { pluginRoutes as myPluginRoutes } from "./plugins/my_plugin";
const allPluginRoutes = [
  ...investmentRoutes,
  ...timeTrackingRoutes,
  ...myPluginRoutes,
];
```

All guards (`PluginRouteGuard`, `PluginRouteErrorBoundary`, `RoleProtectedRoute`) are applied automatically by the renderer.
