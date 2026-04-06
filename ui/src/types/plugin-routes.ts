import React from 'react';

/**
 * PluginNavItem — self-declared sidebar navigation entry exported by each plugin.
 *
 * The icon field is a string key resolved through the central icon registry
 * (ui/src/plugins/plugin-icons.ts) so plugins don't need to import Lucide
 * components directly; the sidebar resolves them at render time.
 */
export interface PluginNavItem {
  /** Must match the pluginId used in pluginRoutes entries. */
  id: string;
  /** React Router path to navigate to. */
  path: string;
  /** Human-readable sidebar label. */
  label: string;
  /** Key in the icon registry, e.g. 'DollarSign', 'TrendingUp'. */
  icon: string;
  /** Lower number = higher in the list. Default: 999. */
  priority?: number;
  /** data-tour attribute for onboarding tours. */
  tourId?: string;
}

/**
 * PluginPublicPage — declares a plugin's public-facing portal page.
 *
 * Plugins that want a public URL at `/p/{pluginId}/` export one of these
 * as `publicPage` from their `plugin/ui/index.ts`.
 *
 * - In-process plugins set `component` (a lazy-loaded React component).
 * - Sidecar plugins set `uiEntry` (the iframe URL served by the sidecar service).
 *
 * Access is gated by the tenant's public-access settings for the plugin.
 * Default: disabled. Configurable in Settings → Plugins.
 */
export interface PluginPublicPage {
  /** Must match the plugin ID (e.g. 'surveys'). */
  pluginId: string;
  /** Human-readable name. */
  pluginName: string;
  /** Frontend path, e.g. '/p/surveys'. */
  path: string;
  /** In-process plugin: lazy React component. */
  component?: React.LazyExoticComponent<React.ComponentType<any>>;
  /** Sidecar plugin: iframe source URL. */
  uiEntry?: string;
}

/**
 * PluginRouteConfig — the contract between a plugin's index.ts and App.tsx.
 *
 * Each plugin declares an array of these in its `index.ts` and exports it
 * as `pluginRoutes`. The `PluginRoutes` renderer in `App.tsx` consumes the
 * combined array and renders each entry as a guarded `<Route>`.
 */
export interface PluginRouteConfig {
  /** React Router path (e.g. '/investments/portfolio/:id') */
  path: string;

  /** Lazy-loaded page component */
  component: React.LazyExoticComponent<React.ComponentType<any>>;

  /** ID matching the PluginContext plugin ID (e.g. 'investments') */
  pluginId: string;

  /** Human-readable name shown in the PluginRouteGuard fallback UI */
  pluginName: string;

  /** Human-readable label (for nav / breadcrumbs) */
  label: string;

  /**
   * Wraps the route in `<RoleProtectedRoute allowedRoles={...}>`.
   * Omit or leave undefined to allow any authenticated user.
   */
  requiresRole?: ('admin' | 'user' | 'superuser')[];

  /**
   * Wraps the route in `<PluginRouteErrorBoundary>`.
   * Defaults to true. Set to false for lightweight/redirect routes.
   */
  errorBoundary?: boolean;

  /**
   * If true, the route is accessible without authentication.
   * Public routes are rendered outside the main ProtectedRoute block in App.tsx.
   */
  isPublic?: boolean;
}
