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
}
