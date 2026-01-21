import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, Eye, EyeOff, Settings, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useTranslation } from 'react-i18next';

interface IntegrationSettings {
  enabled: boolean;
  configured: boolean;
  base_url: string;
  api_key: string;
  timeout: number;
  retry_attempts: number;
}

export const TaxIntegrationSettings: React.FC = () => {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<IntegrationSettings | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  const fetchSettings = async () => {
    setIsLoading(true);
    try {
      const response = await api.get<IntegrationSettings>('/tax-integration/settings');
      setSettings(response);
    } catch (error: any) {
      console.error('Error fetching tax integration settings:', error);
      toast.error(t('taxIntegration.errors.fetchSettingsFailed'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const getStatusIcon = (enabled: boolean, configured: boolean) => {
    if (!enabled) return <XCircle className="h-4 w-4 text-red-500" />;
    if (!configured) return <XCircle className="h-4 w-4 text-yellow-500" />;
    return <CheckCircle className="h-4 w-4 text-green-500" />;
  };

  const maskApiKey = (apiKey: string) => {
    if (!apiKey || apiKey.length < 8) return apiKey;
    return `${apiKey.substring(0, 8)}...${apiKey.substring(apiKey.length - 4)}`;
  };

  if (isLoading && !settings) {
    return (
      <Card className="w-full">
        <CardContent className="flex items-center justify-center p-6">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="ml-2">{t('common.loading')}</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          {t('taxIntegration.settings.title')}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Development Notice */}
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <p className="text-sm text-amber-800">
              {t('taxIntegration.developmentNotice')}
            </p>
          </div>
        </div>
        {settings ? (
          <>
            {/* Status */}
            <div className="flex items-center gap-2">
              {getStatusIcon(settings.enabled, settings.configured)}
              <span className="text-sm font-medium">
                {settings.enabled
                  ? settings.configured
                    ? t('taxIntegration.settings.configured')
                    : t('taxIntegration.settings.notConfigured')
                  : t('taxIntegration.settings.disabled')
                }
              </span>
            </div>

            {/* Configuration Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="base_url">{t('taxIntegration.settings.baseUrl')}</Label>
                <Input
                  id="base_url"
                  value={settings.base_url}
                  readOnly
                  className="bg-gray-50"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="timeout">{t('taxIntegration.settings.timeout')}</Label>
                <Input
                  id="timeout"
                  value={`${settings.timeout}s`}
                  readOnly
                  className="bg-gray-50"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="retry_attempts">{t('taxIntegration.settings.retryAttempts')}</Label>
                <Input
                  id="retry_attempts"
                  value={settings.retry_attempts}
                  readOnly
                  className="bg-gray-50"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="api_key">{t('taxIntegration.settings.apiKey')}</Label>
                <div className="relative">
                  <Input
                    id="api_key"
                    type={showApiKey ? "text" : "password"}
                    value={showApiKey ? settings.api_key : maskApiKey(settings.api_key)}
                    readOnly
                    className="bg-gray-50 pr-10"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                    onClick={() => setShowApiKey(!showApiKey)}
                  >
                    {showApiKey ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>

            {/* Configuration Hints */}
            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
              <h4 className="text-sm font-medium text-blue-900 mb-2">
                {t('taxIntegration.settings.configurationHelp')}
              </h4>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• {t('taxIntegration.settings.help.apiKey')}</li>
                <li>• {t('taxIntegration.settings.help.baseUrl')}</li>
                <li>• {t('taxIntegration.settings.help.environment')}</li>
              </ul>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={fetchSettings}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                {t('common.refresh')}
              </Button>
            </div>
          </>
        ) : (
          <div className="text-center py-8">
            <Settings className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">{t('taxIntegration.settings.notAvailable')}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
