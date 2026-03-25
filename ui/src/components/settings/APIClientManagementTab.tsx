import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  ProfessionalCardFooter,
  MetricCard
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ProfessionalInput } from '@/components/ui/professional-input';
import { ProfessionalTextarea } from '@/components/ui/professional-textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Switch } from '@/components/ui/switch';
import { Copy, Key, Trash2, RotateCcw, Shield, Plus, Lock, Globe, Database, Activity, Calendar, Clock, LockKeyhole, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { FeatureGate } from '@/components/FeatureGate';
import { cn } from '@/lib/utils';

interface APIClient {
  id: number;
  client_id: string;
  client_name: string;
  client_description?: string;
  user_id: number;
  api_key_prefix: string;
  allowed_document_types: string[];
  max_transaction_amount?: number;
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  rate_limit_per_day: number;
  allowed_ip_addresses?: string[];
  webhook_url?: string;
  is_active: boolean;
  is_sandbox: boolean;
  total_requests: number;
  total_transactions_submitted: number;
  last_used_at?: string;
  created_at: string;
  updated_at: string;
  custom_quotas?: {
    allowed_domains?: string[];
    rate_limit_per_minute?: number;
    rate_limit_per_hour?: number;
    rate_limit_per_day?: number;
  };
}

interface APIKeyCreateRequest {
  client_name: string;
  client_description?: string;
  allowed_document_types: string[];
  max_transaction_amount?: number;
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  rate_limit_per_day: number;
  allowed_ip_addresses?: string[];
  webhook_url?: string;
  is_sandbox: boolean;
  expires_in_days?: number;
}

interface APIKeyResponse {
  client_id: string;
  api_key: string;
  api_key_prefix: string;
  client_name: string;
  allowed_document_types: string[];
  rate_limits: {
    per_minute: number;
    per_hour: number;
    per_day: number;
  };
  expires_at?: string;
  created_at: string;
}

interface OAuthClientCreateRequest {
  client_name: string;
  client_description?: string;
  redirect_uris: string[];
  scopes: string[];
  allowed_document_types: string[];
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  rate_limit_per_day: number;
}

const DOCUMENT_TYPES = [
  { value: 'invoice', label: 'Invoices' },
  { value: 'expense', label: 'Expenses' },
  { value: 'statement', label: 'Statements' },
  { value: 'portfolio', label: 'Portfolio' },
];

const getDocumentTypes = (t: any) => [
  { value: 'invoice', label: t('settings.api_keys.invoice') },
  { value: 'expense', label: t('settings.api_keys.expense') },
  { value: 'statement', label: t('settings.api_keys.statement') },
  { value: 'portfolio', label: 'Portfolio' },
];

const OAUTH_SCOPES = [
  { value: 'read', label: 'Read Access' },
  { value: 'write', label: 'Write Access' },
  { value: 'invoices:read', label: 'Read Invoices' },
  { value: 'invoices:write', label: 'Write Invoices' },
  { value: 'expenses:read', label: 'Read Expenses' },
  { value: 'expenses:write', label: 'Write Expenses' },
  { value: 'transactions:read', label: 'Read Transactions' },
  { value: 'transactions:write', label: 'Write Transactions' }
];

export const APIClientManagementTab: React.FC = () => {
  const { t } = useTranslation();
  return (
    <FeatureGate
      feature="external_api"
      fallback={
        <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
          <ProfessionalCardContent className="p-12 text-center">
            <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
              <Key className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-2xl font-bold text-foreground mb-3">{t('settings.api_keys.business_license_required')}</h3>
            <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
              {t('settings.api_keys.business_license_description')}
            </p>
            <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
              <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                {t('settings.api_keys.with_business_license_you_get')}
              </h4>
              <ul className="text-left space-y-3 text-sm text-foreground/80">
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>{t('settings.api_keys.create_up_to_2_api_keys')}</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>{t('settings.api_keys.configurable_rate_limits')}</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>{t('settings.api_keys.webhook_notifications')}</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>{t('settings.api_keys.ip_whitelisting')}</span>
                </li>
              </ul>
            </div>
            <div className="flex justify-center gap-4">
              <ProfessionalButton
                variant="gradient"
                onClick={() => window.location.href = '/settings?tab=license'}
                size="lg"
              >
                {t('settings.api_keys.activate_business_license')}
              </ProfessionalButton>
              <ProfessionalButton
                variant="outline"
                onClick={() => window.open('https://docs.example.com/api-keys', '_blank')}
                size="lg"
              >
                {t('settings.api_keys.learn_more')}
              </ProfessionalButton>
            </div>
          </ProfessionalCardContent>
        </ProfessionalCard>
      }
    >
      <APIClientManagementContent />
    </FeatureGate>
  );
};

const APIClientManagementContent: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showOAuthDialog, setShowOAuthDialog] = useState(false);
  const [showApiKey, setShowApiKey] = useState<APIKeyResponse | null>(null);
  const [showOAuthCredentials, setShowOAuthCredentials] = useState<any>(null);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState<{ clientId: string, clientName: string } | null>(null);
  const [showRegenerateConfirm, setShowRegenerateConfirm] = useState<{ clientId: string, clientName: string } | null>(null);

  // Create API key form state
  const [createForm, setCreateForm] = useState<APIKeyCreateRequest>({
    client_name: '',
    client_description: '',
    allowed_document_types: [],
    max_transaction_amount: undefined,
    rate_limit_per_minute: 60,
    rate_limit_per_hour: 1000,
    rate_limit_per_day: 10000,
    allowed_ip_addresses: [],
    webhook_url: '',
    is_sandbox: false,
    expires_in_days: undefined
  });

  // Create OAuth client form state
  const [oauthForm, setOAuthForm] = useState<OAuthClientCreateRequest>({
    client_name: '',
    client_description: '',
    redirect_uris: [''],
    scopes: [],
    allowed_document_types: [],
    rate_limit_per_minute: 100,
    rate_limit_per_hour: 2000,
    rate_limit_per_day: 20000
  });

  // Form helpers
  const [ipAddressInput, setIpAddressInput] = useState('');
  const [redirectUriInput, setRedirectUriInput] = useState('');

  // Fetch license features to determine tier
  const { data: licenseData } = useQuery<{ features: string[] }>({
    queryKey: ['license-status'],
    queryFn: () => api.get('/license/status'),
  });
  const licenseFeatures: string[] = licenseData?.features || [];

  // Fetch clients
  const { data: clientsData, isLoading: loading } = useQuery<APIClient[]>({
    queryKey: ['api-clients'],
    queryFn: () => api.get('/external-auth/api-keys'),
  });

  const clients = clientsData || [];

  // Mutations
  const createApiKeyMutation = useMutation({
    mutationFn: (data: APIKeyCreateRequest) => api.post('/external-auth/api-keys', data),
    onSuccess: (data: APIKeyResponse) => {
      setShowCreateDialog(false);
      setShowApiKey(data);
      setCreateForm({
        client_name: '',
        client_description: '',
        allowed_document_types: [],
        max_transaction_amount: undefined,
        rate_limit_per_minute: 60,
        rate_limit_per_hour: 1000,
        rate_limit_per_day: 10000,
        allowed_ip_addresses: [],
        webhook_url: '',
        is_sandbox: false,
        expires_in_days: undefined
      });
      queryClient.invalidateQueries({ queryKey: ['api-clients'] });
      toast.success('API key created successfully');
    },
    onError: (error) => {
      console.error('Failed to create API key:', error);
      toast.error('Failed to create API key');
    }
  });

  const createOAuthClientMutation = useMutation({
    mutationFn: (data: OAuthClientCreateRequest) => api.post('/external-auth/oauth/clients', data),
    onSuccess: (data: any) => {
      setShowOAuthDialog(false);
      setShowOAuthCredentials(data);
      setOAuthForm({
        client_name: '',
        client_description: '',
        redirect_uris: [''],
        scopes: [],
        allowed_document_types: [],
        rate_limit_per_minute: 100,
        rate_limit_per_hour: 2000,
        rate_limit_per_day: 20000
      });
      queryClient.invalidateQueries({ queryKey: ['api-clients'] });
      toast.success('OAuth client created successfully');
    },
    onError: (error) => {
      console.error('Failed to create OAuth client:', error);
      toast.error('Failed to create OAuth client');
    }
  });

  const revokeApiKeyMutation = useMutation({
    mutationFn: (clientId: string) => api.delete(`/external-auth/api-keys/${clientId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-clients'] });
      toast.success('API key revoked successfully');
      setShowRevokeConfirm(null);
    },
    onError: (error) => {
      console.error('Failed to revoke API key:', error);
      toast.error('Failed to revoke API key');
    }
  });

  const regenerateApiKeyMutation = useMutation({
    mutationFn: (clientId: string) => api.post(`/external-auth/api-keys/${clientId}/regenerate`),
    onSuccess: (data: APIKeyResponse) => {
      setShowApiKey(data);
      queryClient.invalidateQueries({ queryKey: ['api-clients'] });
      toast.success('API key regenerated successfully');
      setShowRegenerateConfirm(null);
    },
    onError: (error) => {
      console.error('Failed to regenerate API key:', error);
      toast.error('Failed to regenerate API key');
    }
  });

  const createApiKey = () => {
    if (clients.length >= 2) {
      toast.error('Maximum of 2 API keys allowed per user');
      return;
    }

    if (!createForm.client_name.trim()) {
      toast.error('Client name is required');
      return;
    }

    if (createForm.allowed_document_types.length === 0) {
      toast.error('At least one document type is required');
      return;
    }

    createApiKeyMutation.mutate(createForm);
  };

  const createOAuthClient = () => {
    if (!oauthForm.client_name.trim()) {
      toast.error('Client name is required');
      return;
    }

    if (oauthForm.allowed_document_types.length === 0) {
      toast.error('At least one document type is required');
      return;
    }

    if (oauthForm.redirect_uris.filter(uri => uri.trim()).length === 0) {
      toast.error('At least one redirect URI is required');
      return;
    }

    if (oauthForm.scopes.length === 0) {
      toast.error('At least one scope is required');
      return;
    }

    const cleanedForm = {
      ...oauthForm,
      redirect_uris: oauthForm.redirect_uris.filter(uri => uri.trim())
    };

    createOAuthClientMutation.mutate(cleanedForm);
  };

  const handleRevokeClick = (clientId: string, clientName: string) => {
    setShowRevokeConfirm({ clientId, clientName });
  };

  const confirmRevokeApiKey = () => {
    if (!showRevokeConfirm) return;
    revokeApiKeyMutation.mutate(showRevokeConfirm.clientId);
  };

  const handleRegenerateClick = (clientId: string, clientName: string) => {
    setShowRegenerateConfirm({ clientId, clientName });
  };

  const confirmRegenerateApiKey = () => {
    if (!showRegenerateConfirm) return;
    regenerateApiKeyMutation.mutate(showRegenerateConfirm.clientId);
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard');
    } catch (error) {
      toast.error('Failed to copy to clipboard');
    }
  };

  const addIpAddress = () => {
    if (ipAddressInput.trim() && !createForm.allowed_ip_addresses?.includes(ipAddressInput.trim())) {
      setCreateForm({
        ...createForm,
        allowed_ip_addresses: [...(createForm.allowed_ip_addresses || []), ipAddressInput.trim()]
      });
      setIpAddressInput('');
    }
  };

  const removeIpAddress = (ip: string) => {
    setCreateForm({
      ...createForm,
      allowed_ip_addresses: createForm.allowed_ip_addresses?.filter(addr => addr !== ip)
    });
  };

  const addRedirectUri = () => {
    if (redirectUriInput.trim()) {
      setOAuthForm({
        ...oauthForm,
        redirect_uris: [...oauthForm.redirect_uris, redirectUriInput.trim()]
      });
      setRedirectUriInput('');
    }
  };

  const removeRedirectUri = (index: number) => {
    setOAuthForm({
      ...oauthForm,
      redirect_uris: oauthForm.redirect_uris.filter((_, i) => i !== index)
    });
  };

  const handleDocumentTypeToggle = (type: string, checked: boolean) => {
    if (checked) {
      setCreateForm({
        ...createForm,
        allowed_document_types: [...createForm.allowed_document_types, type]
      });
    } else {
      setCreateForm({
        ...createForm,
        allowed_document_types: createForm.allowed_document_types.filter(t => t !== type)
      });
    }
  };

  const handleOAuthScopeToggle = (scope: string, checked: boolean) => {
    if (checked) {
      setOAuthForm({
        ...oauthForm,
        scopes: [...oauthForm.scopes, scope]
      });
    } else {
      setOAuthForm({
        ...oauthForm,
        scopes: oauthForm.scopes.filter(s => s !== scope)
      });
    }
  };

  const handleOAuthDocumentTypeToggle = (type: string, checked: boolean) => {
    if (checked) {
      setOAuthForm({
        ...oauthForm,
        allowed_document_types: [...oauthForm.allowed_document_types, type]
      });
    } else {
      setOAuthForm({
        ...oauthForm,
        allowed_document_types: oauthForm.allowed_document_types.filter(t => t !== type)
      });
    }
  };

  if (loading) {
    return (
      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle>{t('settings.api_keys.api_clients')}</ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          <div className="flex flex-col items-center justify-center p-12 text-muted-foreground">
            <RotateCcw className="h-6 w-6 animate-spin mb-4 text-primary" />
            <h3 className="text-lg font-semibold text-foreground mb-1">{t('settings.api_keys.loading_api_clients')}</h3>
            <p>{t('settings.api_keys.please_wait_load_api_clients')}</p>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-300">
      {/* Gradient Banner */}
      <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-6 backdrop-blur-sm">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
              <Key className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h2 className="text-2xl font-bold tracking-tight">{t('settings.api_keys.api_clients')}</h2>
              <div className="flex items-center gap-3 text-muted-foreground mt-0.5">
                <p>{t('settings.api_keys.manage_api_keys_oauth')}</p>
                <Badge variant={clients.length >= 2 ? "destructive" : clients.length > 0 ? "secondary" : "outline"}>
                  {clients.length}/2 {t('settings.api_keys.used')}
                </Badge>
              </div>
            </div>
          </div>

          <div className="flex space-x-3 w-full md:w-auto">
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <ProfessionalButton
                  variant="gradient"
                  disabled={clients.length >= 2}
                  className={cn("w-full md:w-auto", clients.length >= 2 && "opacity-50 cursor-not-allowed")}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  {t('settings.api_keys.create_api_key')}
                </ProfessionalButton>
              </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="text-xl">{t('settings.api_keys.create_new_api_key')}</DialogTitle>
                    <DialogDescription>
                      {t('settings.api_keys.create_api_key_description')}
                    </DialogDescription>
                  </DialogHeader>

                  {clients.length === 1 && (
                    <Alert className="bg-blue-50 border-blue-200">
                      <AlertDescription className="text-blue-800">
                        <strong>{t('settings.api_keys.note_can_create_1_more')}</strong>
                      </AlertDescription>
                    </Alert>
                  )}

                  <div className="space-y-6 py-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <ProfessionalInput
                        label={t('settings.api_keys.client_name')}
                        value={createForm.client_name}
                        onChange={(e) => setCreateForm({ ...createForm, client_name: e.target.value })}
                        placeholder="My Accounting System"
                      />

                      <div className="flex flex-col justify-end pb-2">
                        <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg border border-border/50">
                          <Switch
                            checked={createForm.is_sandbox}
                            onCheckedChange={(checked) => setCreateForm({ ...createForm, is_sandbox: checked })}
                          />
                          <Label className="text-base font-medium">{t('settings.api_keys.sandbox_mode')}</Label>
                        </div>
                      </div>
                    </div>

                    <ProfessionalTextarea
                      label={t('settings.api_keys.description')}
                      value={createForm.client_description}
                      onChange={(e) => setCreateForm({ ...createForm, client_description: e.target.value })}
                      placeholder="Integration with accounting software"
                      rows={2}
                    />

                    <div>
                      <Label className="text-sm font-medium mb-3 block">{t('settings.api_keys.allowed_document_types')}</Label>
                      <div className="flex flex-wrap gap-4">
                        {getDocumentTypes(t).map((type) => {
                          return (
                            <div key={type.value} className="flex items-center space-x-2 bg-card p-3 rounded-lg border border-border/50 shadow-sm">
                              <Switch
                                id={type.value}
                                checked={createForm.allowed_document_types.includes(type.value)}
                                onCheckedChange={(checked) => handleDocumentTypeToggle(type.value, checked)}
                              />
                              <Label htmlFor={type.value} className="text-sm cursor-pointer">
                                {type.label}
                              </Label>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                      <ProfessionalInput
                        label={t('settings.api_keys.rate_limit_per_minute')}
                        type="number"
                        value={createForm.rate_limit_per_minute}
                        onChange={(e) => setCreateForm({ ...createForm, rate_limit_per_minute: parseInt(e.target.value) })}
                      />
                      <ProfessionalInput
                        label={t('settings.api_keys.rate_limit_per_hour')}
                        type="number"
                        value={createForm.rate_limit_per_hour}
                        onChange={(e) => setCreateForm({ ...createForm, rate_limit_per_hour: parseInt(e.target.value) })}
                      />
                      <ProfessionalInput
                        label={t('settings.api_keys.rate_limit_per_day')}
                        type="number"
                        value={createForm.rate_limit_per_day}
                        onChange={(e) => setCreateForm({ ...createForm, rate_limit_per_day: parseInt(e.target.value) })}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <ProfessionalInput
                        label={t('settings.api_keys.max_transaction_amount')}
                        type="number"
                        step="0.01"
                        value={createForm.max_transaction_amount || ''}
                        onChange={(e) => setCreateForm({
                          ...createForm,
                          max_transaction_amount: e.target.value ? parseFloat(e.target.value) : undefined
                        })}
                        placeholder={t('settings.api_keys.no_limit')}
                        leftIcon={<span className="text-muted-foreground">$</span>}
                      />
                      <ProfessionalInput
                        label={t('settings.api_keys.expires_in_days')}
                        type="number"
                        value={createForm.expires_in_days || ''}
                        onChange={(e) => setCreateForm({
                          ...createForm,
                          expires_in_days: e.target.value ? parseInt(e.target.value) : undefined
                        })}
                        placeholder={t('settings.api_keys.never')}
                      />
                    </div>

                    <ProfessionalInput
                      label={t('settings.api_keys.webhook_url')}
                      value={createForm.webhook_url}
                      onChange={(e) => setCreateForm({ ...createForm, webhook_url: e.target.value })}
                      placeholder="https://your-app.com/webhooks/invoice-system"
                      leftIcon={<Globe className="w-4 h-4 text-muted-foreground" />}
                    />

                    <div>
                      <Label className="text-sm font-medium mb-2 block">{t('settings.api_keys.allowed_ip_addresses')}</Label>
                      <div className="flex gap-2">
                        <ProfessionalInput
                          value={ipAddressInput}
                          onChange={(e) => setIpAddressInput(e.target.value)}
                          placeholder="192.168.1.100 or 10.0.0.0/24"
                          className="flex-1"
                        />
                        <ProfessionalButton type="button" onClick={addIpAddress} variant="outline">
                          {t('settings.api_keys.add')}
                        </ProfessionalButton>
                      </div>
                      {createForm.allowed_ip_addresses && createForm.allowed_ip_addresses.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {createForm.allowed_ip_addresses.map((ip) => (
                            <Badge key={ip} variant="secondary" className="cursor-pointer hover:bg-destructive/10 hover:text-destructive transition-colors pr-1" onClick={() => removeIpAddress(ip)}>
                              {ip} <span className="ml-1 text-xs">✕</span>
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>

                    <DialogFooter>
                      <ProfessionalButton variant="ghost" onClick={() => setShowCreateDialog(false)}>
                        {t('settings.api_keys.cancel')}
                      </ProfessionalButton>
                      <ProfessionalButton variant="gradient" onClick={createApiKey}>
                        {t('settings.api_keys.create_api_key')}
                      </ProfessionalButton>
                    </DialogFooter>
                  </div>
                </DialogContent>
              </Dialog>

              <Dialog open={showOAuthDialog} onOpenChange={setShowOAuthDialog}>
                <DialogTrigger asChild>
                  <ProfessionalButton variant="outline" disabled className="w-full md:w-auto opacity-70">
                    <Shield className="w-4 h-4 mr-2" />
                    Create OAuth Client
                  </ProfessionalButton>
                </DialogTrigger>
                <DialogContent className="max-w-2xl">
                  <DialogHeader>
                    <DialogTitle>Create OAuth 2.0 Client</DialogTitle>
                    <DialogDescription>
                      Create an OAuth 2.0 client for secure third-party application access.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="p-8 text-center text-muted-foreground">
                    OAuth client creation is currently restricted to enterprise administrators.
                    <br />Please contact support to enable this feature.
                  </div>
                  <DialogFooter>
                    <ProfessionalButton onClick={() => setShowOAuthDialog(false)}>Close</ProfessionalButton>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </div>

      {/* API Key Display Dialog */}
      {showApiKey && (
        <Dialog open={!!showApiKey} onOpenChange={() => setShowApiKey(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-green-600">
                <CheckCircle2 className="h-6 w-6" />
                {t('settings.api_keys.api_key_generated_successfully')}
              </DialogTitle>
              <DialogDescription>
                {t('settings.api_keys.api_key_generated_description')}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-6 pt-4">
              <Alert className="bg-amber-50 border-amber-200">
                <LockKeyhole className="h-4 w-4 text-amber-600" />
                <AlertDescription className="text-amber-800 font-medium">
                  {t('settings.api_keys.copy_and_save_securely')}
                </AlertDescription>
              </Alert>

              <div className="space-y-4">
                <ProfessionalInput
                  label={t('settings.api_keys.client_id')}
                  value={showApiKey.client_id}
                  readOnly
                  rightIcon={
                    <ProfessionalButton
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8"
                      onClick={() => copyToClipboard(showApiKey.client_id)}
                    >
                      <Copy className="h-4 w-4" />
                    </ProfessionalButton>
                  }
                />

                <div className="space-y-2">
                  <Label>{t('settings.api_keys.api_key')}</Label>
                  <div className="flex gap-2">
                    <code className="flex-1 bg-muted p-3 rounded-lg border font-mono text-sm break-all">
                      {showApiKey.api_key}
                    </code>
                    <ProfessionalButton
                      size="icon"
                      variant="outline"
                      onClick={() => copyToClipboard(showApiKey.api_key)}
                    >
                      <Copy className="h-4 w-4" />
                    </ProfessionalButton>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 p-4 bg-muted/30 rounded-lg border border-border/50">
                  <div>
                    <span className="text-sm font-semibold block mb-2">{t('settings.api_keys.rate_limits')}</span>
                    <ul className="space-y-1.5 text-sm text-muted-foreground">
                      <li className="flex justify-between"><span>{t('settings.api_keys.per_minute')}</span> <span className="font-mono text-foreground">{showApiKey.rate_limits.per_minute}</span></li>
                      <li className="flex justify-between"><span>{t('settings.api_keys.per_hour')}</span> <span className="font-mono text-foreground">{showApiKey.rate_limits.per_hour}</span></li>
                      <li className="flex justify-between"><span>{t('settings.api_keys.per_day')}</span> <span className="font-mono text-foreground">{showApiKey.rate_limits.per_day}</span></li>
                    </ul>
                  </div>
                  <div>
                    <span className="text-sm font-semibold block mb-2">{t('settings.api_keys.document_types')}</span>
                    <div className="flex flex-wrap gap-1.5">
                      {showApiKey.allowed_document_types.map((type) => (
                        <Badge key={type} variant="secondary" className="text-xs">
                          {t(`settings.api_keys.${type}`)}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <DialogFooter>
                <ProfessionalButton onClick={() => setShowApiKey(null)} variant="gradient" className="w-full sm:w-auto">
                  {t('settings.api_keys.ive_saved_the_key')}
                </ProfessionalButton>
              </DialogFooter>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* OAuth Credentials Display Dialog - Simplified for now */}

      {/* Revoke API Key Confirmation Dialog */}
      {showRevokeConfirm && (
        <Dialog open={!!showRevokeConfirm} onOpenChange={() => setShowRevokeConfirm(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-destructive">
                <Trash2 className="w-5 h-5" />
                Revoke API Key
              </DialogTitle>
              <DialogDescription>
                This action cannot be undone. The API key will be immediately disabled and cannot be recovered.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <Alert variant="destructive">
                <AlertDescription>
                  <strong>Warning:</strong> This action cannot be undone. The API key will be permanently revoked and any applications using it will lose access immediately.
                </AlertDescription>
              </Alert>

              <div className="bg-muted p-4 rounded-lg border">
                <p className="text-sm text-muted-foreground mb-1">Revoking key for:</p>
                <p className="font-bold text-lg">{showRevokeConfirm.clientName}</p>
                <p className="text-xs font-mono text-muted-foreground mt-1">{showRevokeConfirm.clientId}</p>
              </div>

              <DialogFooter>
                <ProfessionalButton
                  variant="ghost"
                  onClick={() => setShowRevokeConfirm(null)}
                >
                  Cancel
                </ProfessionalButton>
                <ProfessionalButton
                  variant="destructive"
                  onClick={confirmRevokeApiKey}
                >
                  Revoke API Key
                </ProfessionalButton>
              </DialogFooter>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Regenerate API Key Confirmation Dialog */}
      {showRegenerateConfirm && (
        <Dialog open={!!showRegenerateConfirm} onOpenChange={() => setShowRegenerateConfirm(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-orange-600">
                <RotateCcw className="w-5 h-5" />
                Regenerate API Key
              </DialogTitle>
              <DialogDescription>
                This will create a new API key and invalidate the current one. Make sure to update any applications using the old key.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <Alert className="bg-orange-50 border-orange-200 text-orange-900">
                <AlertDescription>
                  <strong>Warning:</strong> This will generate a new API key and invalidate the current one. Any applications using the current key will lose access immediately.
                </AlertDescription>
              </Alert>

              <div className="bg-muted p-4 rounded-lg border">
                <p className="text-sm text-muted-foreground mb-1">Regenerating key for:</p>
                <p className="font-bold text-lg">{showRegenerateConfirm.clientName}</p>
                <p className="text-xs font-mono text-muted-foreground mt-1">{showRegenerateConfirm.clientId}</p>
              </div>

              <DialogFooter>
                <ProfessionalButton
                  variant="ghost"
                  onClick={() => setShowRegenerateConfirm(null)}
                >
                  Cancel
                </ProfessionalButton>
                <ProfessionalButton
                  className="bg-orange-600 hover:bg-orange-700 text-white"
                  onClick={confirmRegenerateApiKey}
                >
                  Regenerate Key
                </ProfessionalButton>
              </DialogFooter>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* API Key Limit Warning */}
      {clients.length >= 2 && (
        <Alert className="bg-amber-50 border-amber-200">
          <Shield className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-800">
            <strong>API Key Limit Reached:</strong> You have reached the maximum limit of 2 API keys per account. To create a new API key, you must first revoke an existing one.
          </AlertDescription>
        </Alert>
      )}

      {/* Professional API Clients List */}
      <div className="grid gap-6">
        {(!clients || clients.length === 0) ? (
          <ProfessionalCard variant="default" className="border-dashed">
            <ProfessionalCardContent className="flex flex-col items-center justify-center p-16 text-center">
              <div className="w-20 h-20 bg-muted rounded-full flex items-center justify-center mb-6">
                <Key className="w-10 h-10 text-muted-foreground/50" />
              </div>
              <h3 className="text-2xl font-bold text-foreground mb-3">{t('settings.api_keys.no_api_clients_found')}</h3>
              <p className="text-muted-foreground mb-8 max-w-md">
                {t('settings.api_keys.get_started_create_first_api_key')}
              </p>
              <ProfessionalButton
                onClick={() => setShowCreateDialog(true)}
                variant="gradient"
                size="lg"
                className="shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all"
              >
                <Key className="w-5 h-5 mr-2" />
                {t('settings.api_keys.create_your_first_api_key')}
              </ProfessionalButton>
            </ProfessionalCardContent>
          </ProfessionalCard>
        ) : (
          (clients || []).map((client) => (
            <ProfessionalCard key={client.client_id} variant="elevated" className="overflow-hidden bg-gradient-to-br from-card to-muted/20">
              <div className="p-6 border-b border-border/50 bg-card/50 backdrop-blur-sm">
                <div className="flex flex-col md:flex-row justify-between md:items-start gap-4">
                  <div className="flex items-start space-x-4">
                    <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-xl flex items-center justify-center shadow-sm flex-shrink-0">
                      <Key className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                    </div>
                    <div>
                      <div className="flex items-center flex-wrap gap-2 mb-1">
                        <h3 className="text-xl font-bold">{client.client_name}</h3>
                        {client.is_sandbox && (
                          <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 hover:bg-yellow-200 border-yellow-200">
                            Sandbox
                          </Badge>
                        )}
                        <Badge variant={client.is_active ? "default" : "destructive"} className={cn(client.is_active ? "bg-green-600 hover:bg-green-700" : "")}>
                          {client.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                      {client.client_description && (
                        <p className="text-muted-foreground mb-2 text-sm">{client.client_description}</p>
                      )}
                      <div className="flex items-center gap-2">
                        <code className="text-xs bg-muted px-2 py-1 rounded border font-mono text-muted-foreground">
                          ID: {client.client_id}
                        </code>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    {client.is_active && (
                      <ProfessionalButton
                        size="sm"
                        variant="outline"
                        onClick={() => handleRegenerateClick(client.client_id, client.client_name)}
                      >
                        <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                        Regenerate
                      </ProfessionalButton>
                    )}

                    <ProfessionalButton
                      size="sm"
                      variant="outline"
                      className="text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/20"
                      onClick={() => handleRevokeClick(client.client_id, client.client_name)}
                    >
                      <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                      Revoke
                    </ProfessionalButton>
                  </div>
                </div>
              </div>

              <ProfessionalCardContent className="p-6">
                {/* Client Statistics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                  <MetricCard
                    title="API Key Prefix"
                    value={client.api_key_prefix}
                    icon={Key}
                    variant="default"
                  />
                  <MetricCard
                    title="Total Requests"
                    value={client.total_requests.toLocaleString()}
                    icon={Activity}
                    variant="default"
                  />
                  <MetricCard
                    title="Last Used"
                    value={client.last_used_at ? new Date(client.last_used_at).toLocaleDateString() : 'Never'}
                    icon={Clock}
                    variant={client.last_used_at ? "success" : "default"}
                  />
                  <MetricCard
                    title="Created On"
                    value={new Date(client.created_at).toLocaleDateString()}
                    icon={Calendar}
                    variant="default"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
                  <div className="space-y-3">
                    <h4 className="font-semibold flex items-center gap-2 text-muted-foreground">
                      <Activity className="h-4 w-4" /> Rate Limits
                    </h4>
                    <div className="bg-muted/40 rounded-lg p-3 border border-border/50 space-y-2">
                      <div className="flex justify-between"><span>Per minute:</span> <span className="font-mono">{client.rate_limit_per_minute}</span></div>
                      <div className="flex justify-between"><span>Per hour:</span> <span className="font-mono">{client.rate_limit_per_hour}</span></div>
                      <div className="flex justify-between"><span>Per day:</span> <span className="font-mono">{client.rate_limit_per_day}</span></div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h4 className="font-semibold flex items-center gap-2 text-muted-foreground">
                      <Database className="h-4 w-4" /> Document Types
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {client.allowed_document_types.map((type) => (
                        <Badge key={type} variant="secondary" className="px-2.5 py-1">
                          {type}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h4 className="font-semibold flex items-center gap-2 text-muted-foreground">
                      <Shield className="h-4 w-4" /> Security Limits
                    </h4>
                    <div className="space-y-2">
                      {client.max_transaction_amount && (
                        <div className="flex items-center justify-between text-muted-foreground">
                          <span>Max Amount:</span>
                          <span className="font-medium text-foreground">${client.max_transaction_amount.toLocaleString()}</span>
                        </div>
                      )}
                      {client.allowed_ip_addresses && client.allowed_ip_addresses.length > 0 && (
                        <div>
                          <span className="text-muted-foreground mb-1 block">Allowed IPs:</span>
                          <div className="flex flex-wrap gap-1">
                            {client.allowed_ip_addresses.map((ip) => (
                              <Badge key={ip} variant="outline" className="text-[10px] font-mono">
                                {ip}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                      {client.webhook_url && (
                        <div>
                          <span className="text-muted-foreground mb-1 block">Webhook:</span>
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded break-all">{client.webhook_url}</code>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </ProfessionalCardContent>
            </ProfessionalCard>
          ))
        )}
      </div>
    </div>
  );
};
