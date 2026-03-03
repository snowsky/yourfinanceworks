import React from 'react';
import { Route } from 'react-router-dom';
import { PluginRouteConfig } from '@/types/plugin-routes';
import { RoleProtectedRoute } from '@/components/auth/RoleProtectedRoute';
import { PluginRouteGuard } from './PluginRouteGuard';
import { PluginRouteErrorBoundary } from './PluginRouteErrorBoundary';

interface PluginRoutesProps {
  routes: PluginRouteConfig[];
}

/**
 * Renders a list of plugin route configs as guarded React Router <Route> elements.
 *
 * Each route is automatically wrapped with:
 *   1. PluginRouteGuard — shows "plugin disabled" UI if the plugin is off
 *   2. PluginRouteErrorBoundary — catches runtime errors in plugin pages (optional, default on)
 *   3. RoleProtectedRoute — enforces role access when `requiresRole` is set
 *
 * Usage in App.tsx:
 *   import { PluginRoutes } from '@/components/plugins/PluginRoutes';
 *   import { allPluginRoutes } from '@/plugins';
 *   ...
 *   <PluginRoutes routes={allPluginRoutes} />
 */
export const PluginRoutes: React.FC<PluginRoutesProps> = ({ routes }) => {
  return (
    <>
      {routes.map((route) => {
        const PageComponent = route.component;
        const useErrorBoundary = route.errorBoundary !== false;

        // Build the inner element (page + optional role guard)
        let inner: React.ReactElement = <PageComponent />;

        if (route.requiresRole) {
          inner = (
            <RoleProtectedRoute allowedRoles={route.requiresRole}>
              {inner}
            </RoleProtectedRoute>
          );
        }

        // Optionally wrap in error boundary
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
          <Route
            key={route.path}
            path={route.path}
            element={
              <PluginRouteGuard
                pluginId={route.pluginId}
                pluginName={route.pluginName}
              >
                {inner}
              </PluginRouteGuard>
            }
          />
        );
      })}
    </>
  );
};
