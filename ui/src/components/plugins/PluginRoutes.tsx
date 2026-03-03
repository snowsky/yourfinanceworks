import React from 'react';
import { Route } from 'react-router-dom';
import { PluginRouteConfig } from '@/types/plugin-routes';
import { RoleProtectedRoute } from '@/components/auth/RoleProtectedRoute';
import { PluginRouteGuard } from './PluginRouteGuard';
import { PluginRouteErrorBoundary } from './PluginRouteErrorBoundary';

/**
 * Build the guarded element for a single plugin route.
 *
 * Returns the page component wrapped with:
 *   1. PluginRouteGuard — required plugin-enabled check
 *   2. PluginRouteErrorBoundary — catches runtime errors (default on)
 *   3. RoleProtectedRoute — role check when requiresRole is set
 *
 * Usage in App.tsx (must produce <Route> as a direct <Routes> child):
 *   {allPluginRoutes.map(r => (
 *     <Route key={r.path} path={r.path} element={buildPluginElement(r)} />
 *   ))}
 */
export function buildPluginElement(route: PluginRouteConfig): React.ReactElement {
  const PageComponent = route.component;
  const useErrorBoundary = route.errorBoundary !== false;

  let inner: React.ReactElement = <PageComponent />;

  if (route.requiresRole) {
    inner = (
      <RoleProtectedRoute allowedRoles={route.requiresRole}>
        {inner}
      </RoleProtectedRoute>
    );
  }

  if (useErrorBoundary) {
    inner = (
      <PluginRouteErrorBoundary
        pluginId={route.pluginId}
        pluginName={route.pluginName}
        routePath={route.path}
      >
        {inner}
      </PluginRouteErrorBoundary>
    );
  }

  return (
    <PluginRouteGuard pluginId={route.pluginId} pluginName={route.pluginName}>
      {inner}
    </PluginRouteGuard>
  );
}

