import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, XCircle, AlertCircle, Loader2, Settings, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useTranslation } from 'react-i18next';

interface IntegrationStatus {
  enabled: boolean;
  configured: boolean;
  connection_tested: boolean;
  last_test_result?: string;
}

export const TaxIntegrationStatus: React.FC = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isTestingConnection, setIsTestingConnection] = useState(false);

  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const response = await api.get<IntegrationStatus>('/tax-integration/status');
      setStatus(response);
    } catch (error: any) {
      console.error('Error fetching tax integration status:', error);
      toast.error(t('taxIntegration.errors.fetchStatusFailed'));
      setStatus({
        enabled: false,
        configured: false,
        connection_tested: false,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const testConnection = async () => {
    setIsTestingConnection(true);
    try {
      const response = await api.post<{ success: boolean; message: string }>(
        '/tax-integration/test-connection'
      );

      if (response.success) {
        toast.success(t('taxIntegration.success.connectionTestSuccessful'));
        await fetchStatus(); // Refresh status
      } else {
        toast.error(t('taxIntegration.errors.connectionTestFailed'));
      }
    } catch (error: any) {
      console.error('Error testing connection:', error);
      toast.error(
        error?.message || t('taxIntegration.errors.connectionTestFailed')
      );
    } finally {
      setIsTestingConnection(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const getStatusIcon = () => {
    if (!status) return <AlertCircle className="h-4 w-4 text-gray-500" />;

    if (!status.enabled) {
      return <XCircle className="h-4 w-4 text-red-500" />;
    }

    if (!status.configured) {
      return <AlertCircle className="h-4 w-4 text-yellow-500" />;
    }

    if (!status.connection_tested) {
      return <XCircle className="h-4 w-4 text-red-500" />;
    }

    return <CheckCircle className="h-4 w-4 text-green-500" />;
  };

  const getStatusText = () => {
    if (!status) return t('taxIntegration.status.unknown');

    if (!status.enabled) {
      return t('taxIntegration.status.disabled');
    }

    if (!status.configured) {
      return t('taxIntegration.status.notConfigured');
    }

    if (!status.connection_tested) {
      return t('taxIntegration.status.connectionFailed');
    }

    return t('taxIntegration.status.connected');
  };

  const getStatusBadgeVariant = () => {
    if (!status) return 'secondary';

    if (!status.enabled) return 'destructive';
    if (!status.configured) return 'secondary';
    if (!status.connection_tested) return 'destructive';

    return 'default';
  };

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Settings className="h-4 w-4" />
          {t('taxIntegration.title')}
        </CardTitle>
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Badge variant={getStatusBadgeVariant()}>
            {getStatusText()}
          </Badge>
        )}
      </CardHeader>
      <CardContent>
        {/* Development Notice */}
        <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-md">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <p className="text-sm text-amber-800">
              {t('taxIntegration.developmentNotice')}
            </p>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <span className="text-sm text-muted-foreground">
              {status?.last_test_result || t('taxIntegration.status.lastTestResult')}
            </span>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={testConnection}
              disabled={isTestingConnection || !status?.configured}
            >
              {isTestingConnection ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : null}
              {t('taxIntegration.testConnection')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchStatus}
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : null}
              {t('taxIntegration.refresh')}
            </Button>
          </div>
        </div>

        {!status?.enabled && (
          <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
            <p className="text-sm text-yellow-800">
              {t('taxIntegration.warnings.notEnabled')}
            </p>
          </div>
        )}

        {status?.enabled && !status?.configured && (
          <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <p className="text-sm text-blue-800">
              {t('taxIntegration.warnings.notConfigured')}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
