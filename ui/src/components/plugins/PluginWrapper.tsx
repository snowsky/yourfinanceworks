import React, { ReactNode } from 'react';
import { PluginErrorBoundary } from './PluginErrorBoundary';
import { usePlugins } from '@/contexts/PluginContext';
import { AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface PluginWrapperProps {
  pluginId: string;
  children: ReactNode;
  fallbackComponent?: ReactNode;
  requiresInitialization?: boolean;
}

/**
 * Wrapper component that provides error boundaries and initialization checks for plugins
 */
export const PluginWrapper: React.FC<PluginWrapperProps> = ({
  pluginId,
  children,
  fallbackComponent,
  requiresInitialization = true
}) => {
  const { getPlugin, getPluginInitializationStatus, isPluginEnabled } = usePlugins();

  const plugin = getPlugin(pluginId);
  const initStatus = getPluginInitializationStatus(pluginId);
  const isEnabled = isPluginEnabled(pluginId);

  // If plugin is not found
  if (!plugin) {
    return (
      <div className="min-h-[400px] flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-warning/10">
              <AlertTriangle className="h-6 w-6 text-warning" />
            </div>
            <CardTitle>Plugin Not Found</CardTitle>
            <CardDescription>
              The requested plugin "{pluginId}" is not available.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => window.location.href = '/'}
              variant="outline"
              className="w-full"
            >
              Go to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // If plugin is not enabled
  if (!isEnabled) {
    return (
      <div className="min-h-[400px] flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <AlertTriangle className="h-6 w-6 text-muted-foreground" />
            </div>
            <CardTitle>Plugin Disabled</CardTitle>
            <CardDescription>
              The {plugin.name} plugin is currently disabled.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button
              onClick={() => window.location.href = '/settings?tab=plugins'}
              variant="default"
              className="w-full"
            >
              Enable in Settings
            </Button>
            <Button
              onClick={() => window.location.href = '/'}
              variant="outline"
              className="w-full"
            >
              Go to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // If plugin requires initialization but failed to initialize
  if (requiresInitialization && !initStatus.isInitialized && initStatus.error) {
    return (
      <div className="min-h-[400px] flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
              <AlertTriangle className="h-6 w-6 text-destructive" />
            </div>
            <CardTitle>Plugin Initialization Failed</CardTitle>
            <CardDescription>
              The {plugin.name} plugin failed to initialize properly.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="text-sm text-muted-foreground bg-muted p-3 rounded">
              {initStatus.error}
            </div>
            <Button
              onClick={() => {
                window.dispatchEvent(new CustomEvent('plugin-retry-initialization', {
                  detail: { pluginId }
                }));
                window.location.reload();
              }}
              variant="default"
              className="w-full"
            >
              Retry Initialization
            </Button>
            <Button
              onClick={() => window.location.href = '/settings?tab=plugins'}
              variant="outline"
              className="w-full"
            >
              Plugin Settings
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Wrap with error boundary and render children
  return (
    <PluginErrorBoundary
      pluginId={pluginId}
      pluginName={plugin.name}
      fallbackComponent={fallbackComponent}
    >
      {children}
    </PluginErrorBoundary>
  );
};