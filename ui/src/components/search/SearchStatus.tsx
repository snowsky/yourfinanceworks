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
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: status, isLoading, isError, refetch } = useQuery({
    queryKey: ['searchStatus'],
    queryFn: () => apiClient.get<SearchStatusData>('/search/status'),
  });

  const reindexMutation = useMutation({
    mutationFn: () => apiClient.post('/search/reindex'),
    onSuccess: () => {
      toast.success(t('settings.search_settings.search_data_reindexed_successfully'));
      queryClient.invalidateQueries({ queryKey: ['searchStatus'] });
    },
    onError: () => {
      toast.error(t('settings.search_settings.failed_to_reindex_search_data'));
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
          <span className="text-muted-foreground font-medium">{t('settings.search_settings.loading_search_status')}</span>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  if (isError || !status) {
    return (
      <ProfessionalCard variant="elevated" className="border-destructive/30 bg-destructive/10">
        <ProfessionalCardContent className="flex flex-col items-center justify-center p-12 text-center">
          <div className="p-3 bg-destructive/10 rounded-full mb-3">
            <AlertCircle className="h-8 w-8 text-destructive" />
          </div>
          <h3 className="text-lg font-semibold text-destructive mb-2">{t('settings.search_settings.service_unavailable')}</h3>
          <p className="text-destructive mb-6">{t('settings.search_settings.failed_to_load_search_status')}</p>
          <ProfessionalButton onClick={handleRefresh} variant="outline" className="border-destructive/30 text-destructive hover:bg-destructive/10">
            <RefreshCw className="h-4 w-4 mr-2" />
            {t('settings.search_settings.retry_connection')}
          </ProfessionalButton>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  const getStatusBadge = () => {
    if (status.opensearch_enabled && status.opensearch_connected) {
      return (
        <Badge variant="default" className="bg-success/10 text-success hover:bg-success/20 border-success/30 py-1 px-3">
          <CheckCircle className="h-3.5 w-3.5 mr-1.5" />
          {t('settings.search_settings.opensearch_active')}
        </Badge>
      );
    } else if (status.fallback_available) {
      return (
        <Badge variant="secondary" className="bg-warning/10 text-warning hover:bg-warning/20 border-warning/30 py-1 px-3">
          <Database className="h-3.5 w-3.5 mr-1.5" />
          {t('settings.search_settings.database_fallback')}
        </Badge>
      );
    } else {
      return (
        <Badge variant="destructive" className="py-1 px-3">
          <AlertCircle className="h-3.5 w-3.5 mr-1.5" />
          {t('settings.search_settings.search_disabled')}
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
              <div className="p-3 bg-primary/10 rounded-xl shadow-sm">
                <Search className="h-6 w-6 text-primary" />
              </div>
              <div>
                <ProfessionalCardTitle className="text-xl">
                  {t('settings.search_settings.search_service_status')}
                </ProfessionalCardTitle>
                <ProfessionalCardDescription>
                  {t('settings.search_settings.search_service_description')}
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
                <Server className="h-4 w-4" /> {t('settings.search_settings.opensearch_configuration')}
              </h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">{t('settings.search_settings.status')}</span>
                  <Badge variant={status.opensearch_enabled ? "outline" : "secondary"}>
                    {status.opensearch_enabled ? t('settings.search_settings.enabled') : t('settings.search_settings.disabled')}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">{t('settings.search_settings.connection')}</span>
                  <span className={cn("flex items-center gap-1.5 font-medium", status.opensearch_connected ? "text-success" : "text-destructive")}>
                    <div className={cn("w-2 h-2 rounded-full", status.opensearch_connected ? "bg-success" : "bg-destructive")} />
                    {status.opensearch_connected ? t('settings.search_settings.connected') : t('settings.search_settings.disconnected')}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">{t('settings.search_settings.host')}</span>
                  <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">{status.host}:{status.port}</code>
                </div>
              </div>
            </div>

            <div className="p-4 bg-card rounded-xl border border-border/50 shadow-sm space-y-3">
              <h4 className="text-sm font-semibold flex items-center gap-2 text-muted-foreground pb-2 border-b border-border/50">
                <Activity className="h-4 w-4" /> {t('settings.search_settings.health_and_fallback')}
              </h4>
              <div className="space-y-2 text-sm">
                {status.opensearch_health && (
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">{t('settings.search_settings.cluster_health')}</span>
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
                    <span className="text-muted-foreground">{t('settings.search_settings.active_nodes')}</span>
                    <span className="font-mono">{status.opensearch_nodes}</span>
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">{t('settings.search_settings.database_fallback_status')}</span>
                  <span className={cn("flex items-center gap-1.5 font-medium", status.fallback_available ? "text-primary" : "text-muted-foreground")}>
                    {status.fallback_available && <ShieldCheck className="h-3.5 w-3.5" />}
                    {status.fallback_available ? t('settings.search_settings.available') : t('settings.search_settings.unavailable')}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {status.opensearch_error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <strong>{t('settings.search_settings.opensearch_error')}:</strong> {status.opensearch_error}
              </AlertDescription>
            </Alert>
          )}

          {status.error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <strong>{t('settings.search_settings.system_error')}:</strong> {status.error}
              </AlertDescription>
            </Alert>
          )}

          <div className="bg-muted/30 p-4 rounded-xl border border-border/50 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-background rounded-lg border shadow-sm mt-0.5">
                <Database className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <h4 className="text-sm font-medium">{t('settings.search_settings.search_index_management')}</h4>
                <p className="text-xs text-muted-foreground mt-0.5 max-w-sm">
                  {status.opensearch_enabled && status.opensearch_connected
                    ? t('settings.search_settings.search_powered_by_opensearch')
                    : status.fallback_available
                      ? t('settings.search_settings.search_using_database_fallback')
                      : t('settings.search_settings.search_unavailable')
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
                {t('settings.search_settings.refresh_status')}
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
                {reindexMutation.isPending ? t('settings.search_settings.reindexing') : t('settings.search_settings.reindex_data')}
              </ProfessionalButton>
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    </div>
  );
}