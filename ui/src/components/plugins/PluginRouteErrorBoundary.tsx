import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, ArrowLeft, RefreshCw, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface Props {
  children: ReactNode;
  pluginId: string;
  pluginName: string;
  routePath?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * Error boundary specifically for plugin routes
 * Provides a full-page fallback when plugin pages fail to load
 */
export class PluginRouteErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Plugin Route Error Boundary caught an error:', error, errorInfo);

    this.setState({
      error,
      errorInfo
    });

    // Dispatch global event for error tracking
    window.dispatchEvent(new CustomEvent('plugin-route-error', {
      detail: {
        pluginId: this.props.pluginId,
        pluginName: this.props.pluginName,
        routePath: this.props.routePath,
        error: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack
      }
    }));

    // Try to disable the plugin if it's causing route errors
    window.dispatchEvent(new CustomEvent('plugin-error-disable', {
      detail: {
        pluginId: this.props.pluginId,
        reason: `Route error at ${this.props.routePath}: ${error.message}`
      }
    }));
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  handleGoBack = () => {
    window.history.back();
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  handleGoToSettings = () => {
    window.location.href = '/settings?tab=plugins';
  };

  render() {
    if (this.state.hasError) {
      const { pluginName, pluginId, routePath } = this.props;
      const { error } = this.state;

      return (
        <div className="min-h-screen bg-background flex items-center justify-center p-4">
          <div className="w-full max-w-2xl">
            <Card>
              <CardHeader className="text-center pb-6">
                <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
                  <AlertTriangle className="h-8 w-8 text-destructive" />
                </div>
                <CardTitle className="text-2xl">
                  {pluginName} Plugin Error
                </CardTitle>
                <CardDescription className="text-base">
                  The {pluginName} plugin encountered an error while loading this page.
                  {routePath && (
                    <div className="mt-2 text-sm font-mono bg-muted px-2 py-1 rounded">
                      Route: {routePath}
                    </div>
                  )}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-6">
                {/* Error details */}
                {error && (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      <div className="font-semibold mb-1">Error Details:</div>
                      <div className="font-mono text-sm">{error.message}</div>
                    </AlertDescription>
                  </Alert>
                )}

                {/* What happened section */}
                <div className="space-y-3">
                  <h3 className="font-semibold">What happened?</h3>
                  <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                    <li>The {pluginName} plugin failed to load properly</li>
                    <li>This could be due to a plugin update, configuration issue, or compatibility problem</li>
                    <li>The plugin has been temporarily disabled to prevent further issues</li>
                  </ul>
                </div>

                {/* What you can do section */}
                <div className="space-y-3">
                  <h3 className="font-semibold">What you can do:</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <Button
                      onClick={this.handleRetry}
                      variant="default"
                      className="w-full"
                    >
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Try Again
                    </Button>

                    <Button
                      onClick={this.handleGoBack}
                      variant="outline"
                      className="w-full"
                    >
                      <ArrowLeft className="mr-2 h-4 w-4" />
                      Go Back
                    </Button>

                    <Button
                      onClick={this.handleGoToSettings}
                      variant="outline"
                      className="w-full"
                    >
                      <Settings className="mr-2 h-4 w-4" />
                      Plugin Settings
                    </Button>

                    <Button
                      onClick={this.handleGoHome}
                      variant="ghost"
                      className="w-full"
                    >
                      Dashboard
                    </Button>
                  </div>
                </div>

                {/* Technical details */}
                <details className="text-sm">
                  <summary className="cursor-pointer font-medium text-muted-foreground hover:text-foreground">
                    Technical Details
                  </summary>
                  <div className="mt-3 p-3 bg-muted rounded-md font-mono text-xs space-y-2">
                    <div><strong>Plugin ID:</strong> {pluginId}</div>
                    <div><strong>Route:</strong> {routePath || 'Unknown'}</div>
                    <div><strong>Error:</strong> {error?.name || 'Unknown'}</div>
                    <div><strong>Message:</strong> {error?.message || 'No message'}</div>
                    {error?.stack && (
                      <div>
                        <strong>Stack Trace:</strong>
                        <pre className="mt-1 whitespace-pre-wrap text-xs">
                          {error.stack}
                        </pre>
                      </div>
                    )}
                  </div>
                </details>

                {/* Help text */}
                <div className="text-xs text-muted-foreground text-center pt-4 border-t">
                  If this problem persists, try disabling and re-enabling the plugin in settings,
                  or contact your administrator for assistance.
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}