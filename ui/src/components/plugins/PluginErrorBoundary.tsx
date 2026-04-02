import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { cn } from '@/lib/utils';

interface Props {
  children: ReactNode;
  name?: string;
  className?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * PluginErrorBoundary — catches runtime errors within dynamic/internal plugins
 * to prevent the entire main application from crashing.
 */
export class PluginErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[PluginError:${this.props.name || 'Unknown'}]`, error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <ProfessionalCard
          variant="elevated"
          className={cn('p-6 border-l-4 border-l-destructive bg-destructive/5', this.props.className)}
        >
          <div className="flex items-start gap-4">
            <div className="p-2 rounded-full bg-destructive/10 text-destructive">
              <AlertCircle className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="font-bold text-foreground">
                {this.props.name ? `${this.props.name} Module` : 'Plugin Module'} Unavailable
              </h3>
              <p className="text-sm text-muted-foreground mt-1 mb-4">
                This component encountered an error and cannot be displayed. 
                The rest of the application is unaffected.
              </p>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={this.handleRetry}
                className="hover:bg-background"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-2" />
                Retry Loading
              </Button>
            </div>
          </div>
        </ProfessionalCard>
      );
    }

    return this.props.children;
  }
}