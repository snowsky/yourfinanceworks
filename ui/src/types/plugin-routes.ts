import React from 'react';

/**
 * Configuration object for a single plugin page route.
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
