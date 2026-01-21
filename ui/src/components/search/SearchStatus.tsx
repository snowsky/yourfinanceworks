import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  ProfessionalCardDescription
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, Search, AlertCircle, CheckCircle, Database, Server, Activity, ShieldCheck } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

interface SearchStatusData {
  opensearch_enabled: boolean;
  opensearch_connected: boolean;
  opensearch_health?: string;
  opensearch_nodes?: number;
  opensearch_error?: string;
  host: string;
  port: number;
  fallback_available: boolean;
  error?: string;
}

export function SearchStatus() {
  const queryClient = useQueryClient();

  const { data: status, isLoading, isError, refetch } = useQuery({
    queryKey: ['searchStatus'],
    queryFn: () => apiClient.get<SearchStatusData>('/search/status'),
  });

  const reindexMutation = useMutation({
    mutationFn: () => apiClient.post('/search/reindex'),
    onSuccess: () => {
      toast.success('Search data reindexed successfully');
      queryClient.invalidateQueries({ queryKey: ['searchStatus'] });
    },
    onError: () => {
      toast.error('Failed to reindex search data');
    }
  });

  const handleRefresh = () => {
    refetch();
  };

  const handleReindex = () => {
    reindexMutation.mutate();
  };

  if (isLoading && !status) {
    return (
      <ProfessionalCard variant="elevated">
        <ProfessionalCardContent className="flex flex-col items-center justify-center p-12">
          <RefreshCw className="h-8 w-8 animate-spin text-primary mb-4" />
          <span className="text-muted-foreground font-medium">Loading search status...</span>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  if (isError || !status) {
    return (
      <ProfessionalCard variant="elevated" className="border-red-200 bg-red-50 dark:bg-red-900/10 dark:border-red-900/30">
        <ProfessionalCardContent className="flex flex-col items-center justify-center p-12 text-center">
          <div className="p-3 bg-red-100 rounded-full mb-3">
            <AlertCircle className="h-8 w-8 text-red-600" />
          </div>
          <h3 className="text-lg font-semibold text-red-900 dark:text-red-400 mb-2">Service Unavailable</h3>
          <p className="text-red-700 dark:text-red-300 mb-6">Failed to load search service status. Please check your connection.</p>
          <ProfessionalButton onClick={handleRefresh} variant="outline" className="border-red-300 text-red-700 hover:bg-red-100">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry Connection
          </ProfessionalButton>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  const getStatusBadge = () => {
    if (status.opensearch_enabled && status.opensearch_connected) {
      return (
        <Badge variant="default" className="bg-green-100 text-green-800 hover:bg-green-200 border-green-200 py-1 px-3">
          <CheckCircle className="h-3.5 w-3.5 mr-1.5" />
          OpenSearch Active
        </Badge>
      );
    } else if (status.fallback_available) {
      return (
        <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 hover:bg-yellow-200 border-yellow-200 py-1 px-3">
          <Database className="h-3.5 w-3.5 mr-1.5" />
          Database Fallback
        </Badge>
      );
    } else {
      return (
        <Badge variant="destructive" className="py-1 px-3">
          <AlertCircle className="h-3.5 w-3.5 mr-1.5" />
          Search Disabled
        </Badge>
      );
    }
  };

  return (
    <div className="space-y-6">
      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl shadow-sm">
                <Search className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <ProfessionalCardTitle className="text-xl">
                  Search Service Status
                </ProfessionalCardTitle>
                <ProfessionalCardDescription>
                  Monitor and manage the search indexing system
                </ProfessionalCardDescription>
              </div>
            </div>
            {getStatusBadge()}
          </div>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-card rounded-xl border border-border/50 shadow-sm space-y-3">
              <h4 className="text-sm font-semibold flex items-center gap-2 text-muted-foreground pb-2 border-b border-border/50">
                <Server className="h-4 w-4" /> OpenSearch Configuration
              </h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Status</span>
                  <Badge variant={status.opensearch_enabled ? "outline" : "secondary"}>
                    {status.opensearch_enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Connection</span>
                  <span className={cn("flex items-center gap-1.5 font-medium", status.opensearch_connected ? "text-green-600" : "text-red-600")}>
                    <div className={cn("w-2 h-2 rounded-full", status.opensearch_connected ? "bg-green-600" : "bg-red-600")} />
                    {status.opensearch_connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Host</span>
                  <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">{status.host}:{status.port}</code>
                </div>
              </div>
            </div>

            <div className="p-4 bg-card rounded-xl border border-border/50 shadow-sm space-y-3">
              <h4 className="text-sm font-semibold flex items-center gap-2 text-muted-foreground pb-2 border-b border-border/50">
                <Activity className="h-4 w-4" /> Health & Fallback
              </h4>
              <div className="space-y-2 text-sm">
                {status.opensearch_health && (
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Cluster Health</span>
                    <Badge
                      variant="outline"
                      className={cn(
                        status.opensearch_health === 'green' ? "border-green-200 text-green-700 bg-green-50" :
                          status.opensearch_health === 'yellow' ? "border-yellow-200 text-yellow-700 bg-yellow-50" :
                            "border-red-200 text-red-700 bg-red-50"
                      )}
                    >
                      {status.opensearch_health.toUpperCase()}
                    </Badge>
                  </div>
                )}
                {status.opensearch_nodes !== undefined && (
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Active Nodes</span>
                    <span className="font-mono">{status.opensearch_nodes}</span>
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Database Fallback</span>
                  <span className={cn("flex items-center gap-1.5 font-medium", status.fallback_available ? "text-blue-600" : "text-muted-foreground")}>
                    {status.fallback_available && <ShieldCheck className="h-3.5 w-3.5" />}
                    {status.fallback_available ? 'Available' : 'Unavailable'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {status.opensearch_error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <strong>OpenSearch Error:</strong> {status.opensearch_error}
              </AlertDescription>
            </Alert>
          )}

          {status.error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <strong>System Error:</strong> {status.error}
              </AlertDescription>
            </Alert>
          )}

          <div className="bg-muted/30 p-4 rounded-xl border border-border/50 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-background rounded-lg border shadow-sm mt-0.5">
                <Database className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <h4 className="text-sm font-medium">Search Index Management</h4>
                <p className="text-xs text-muted-foreground mt-0.5 max-w-sm">
                  {status.opensearch_enabled && status.opensearch_connected
                    ? 'Search is powered by OpenSearch with full-text search capabilities.'
                    : status.fallback_available
                      ? 'Search is using database fallback with basic text matching.'
                      : 'Search functionality is currently unavailable.'
                  }
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 w-full md:w-auto">
              <ProfessionalButton
                onClick={handleRefresh}
                variant="outline"
                size="sm"
                disabled={isLoading}
                className="w-full md:w-auto"
              >
                <RefreshCw className={cn("h-3.5 w-3.5 mr-2", isLoading && "animate-spin")} />
                Refresh Status
              </ProfessionalButton>

              <ProfessionalButton
                onClick={handleReindex}
                variant="gradient"
                size="sm"
                disabled={reindexMutation.isPending || isLoading || (!status.opensearch_enabled && !status.fallback_available)}
                loading={reindexMutation.isPending}
                className="w-full md:w-auto"
              >
                {!reindexMutation.isPending && <Database className="h-3.5 w-3.5 mr-2" />}
                {reindexMutation.isPending ? 'Reindexing...' : 'Reindex Data'}
              </ProfessionalButton>
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    </div>
  );
}