import React from 'react';
import { Navigate } from 'react-router-dom';
import { usePlugins } from '@/contexts/PluginContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface PluginRouteGuardProps {
  pluginId: string;
  pluginName: string;
  children: React.ReactNode;
}

/**
 * Route guard that checks if a plugin is enabled before rendering the route
 * If the plugin is disabled, shows a message and redirects to dashboard
 */
export const PluginRouteGuard: React.FC<PluginRouteGuardProps> = ({
  pluginId,
  pluginName,
  children
}) => {
  const { isPluginEnabled, loading, enabledPlugins } = usePlugins();

  // Show loading state while checking plugin status
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Check if plugin is enabled
  const pluginEnabled = isPluginEnabled(pluginId);

  console.log(`PluginRouteGuard: Checking plugin "${pluginId}" - Enabled: ${pluginEnabled}, EnabledPlugins: ${enabledPlugins.join(', ')}`);

  if (!pluginEnabled) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-warning/10">
              <AlertTriangle className="h-6 w-6 text-warning" />
            </div>
            <CardTitle className="text-lg">
              {pluginName} is Disabled
            </CardTitle>
            <CardDescription>
              The {pluginName} plugin is currently disabled and not available.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              To use this feature, please enable the {pluginName} plugin in Settings → Plugins.
            </p>

            <Button
              onClick={() => window.location.href = '/settings?tab=plugins'}
              className="w-full"
            >
              Go to Plugin Settings
            </Button>

            <Button
              onClick={() => window.location.href = '/'}
              variant="ghost"
              className="w-full"
            >
              <Home className="mr-2 h-4 w-4" />
              Go to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Plugin is enabled, render children
  return <>{children}</>;
};
