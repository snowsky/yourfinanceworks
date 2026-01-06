import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from "react-i18next";
import {
    ProfessionalCard,
    ProfessionalCardContent,
    ProfessionalCardHeader,
    ProfessionalCardTitle
} from "@/components/ui/professional-card";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
    Mail,
    Save,
    RefreshCw,
    CheckCircle2,
    AlertCircle,
    Loader2,
    Globe,
    User,
    Key,
    Hash,
    List,
    Clock,
    Server,
    Shield
} from "lucide-react";
import { toast } from "sonner";
import { api, getErrorMessage } from "@/lib/api";
import { FeatureGate } from "@/components/FeatureGate";

interface EmailConfig {
    imap_host: string;
    imap_port: number;
    username: string;
    password?: string;
    enabled: boolean;
    folders: string[];
    allowed_senders: string;
    lookback_days: number;
    max_emails_to_fetch: number;
}

const PROVIDERS = [
    { id: 'custom', name: 'Custom IMAP', host: '', port: 993 },
    { id: 'gmail', name: 'Gmail', host: 'imap.gmail.com', port: 993 },
];

export const EmailIntegrationSettingsTab: React.FC = () => {
    return (
        <FeatureGate
            feature="email_integration"
            fallback={
                <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
                    <ProfessionalCardContent className="p-12 text-center">
                        <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
                            <Mail className="w-8 h-8 text-blue-600 dark:text-blue-400" />
                        </div>
                        <h3 className="text-2xl font-bold text-foreground mb-3">Business License Required</h3>
                        <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
                            Email integration allows you to automatically ingest expenses from your inbox - a powerful automation feature.
                            Upgrade to a business license to enable email integration and save time on manual entry.
                        </p>
                        <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
                            <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                                <Shield className="h-4 w-4 text-primary" />
                                With Business License, you get:
                            </h4>
                            <ul className="text-left space-y-3 text-sm text-foreground/80">
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>Automatic expense ingestion from email</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>Support for Gmail, Outlook, and custom IMAP</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>AI-powered expense classification</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>Secure and encrypted connection</span>
                                </li>
                            </ul>
                        </div>
                        <div className="flex justify-center gap-4">
                            <ProfessionalButton
                                variant="gradient"
                                onClick={() => window.location.href = '/settings?tab=license'}
                                size="lg"
                            >
                                Activate Business License
                            </ProfessionalButton>
                            <ProfessionalButton
                                variant="outline"
                                onClick={() => window.open('https://docs.example.com/email-integration', '_blank')}
                                size="lg"
                            >
                                Learn More
                            </ProfessionalButton>
                        </div>
                    </ProfessionalCardContent>
                </ProfessionalCard>
            }
        >
            <EmailIntegrationSettingsContent />
        </FeatureGate>
    );
};

const EmailIntegrationSettingsContent: React.FC = () => {
    const { t } = useTranslation();
    const queryClient = useQueryClient();

    const [config, setConfig] = useState<EmailConfig>({
        imap_host: '',
        imap_port: 993,
        username: '',
        password: '',
        enabled: false,
        folders: ['INBOX'],
        allowed_senders: '',
        lookback_days: 30,
        max_emails_to_fetch: 100,
    });

    const [testResult, setTestResult] = useState<{ success: boolean, message: string } | null>(null);
    const [hasExistingPassword, setHasExistingPassword] = useState(false);

    // Fetch config
    const { data: queryData, isLoading: queryLoading } = useQuery({
        queryKey: ['email-config'],
        queryFn: () => api.get<EmailConfig>('/email-integration/config'),
    });

    useEffect(() => {
        if (queryData) {
            setConfig(prev => ({ ...prev, ...queryData, password: '' }));
            setHasExistingPassword(!!queryData.username);
        }
    }, [queryData]);

    // Mutations
    const saveMutation = useMutation({
        mutationFn: (data: EmailConfig) => api.post('/email-integration/config', data),
        onSuccess: () => {
            toast.success(t('settings.save_success'));
            setHasExistingPassword(true);
            queryClient.invalidateQueries({ queryKey: ['email-config'] });
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, (k) => k));
        },
    });

    const testMutation = useMutation({
        mutationFn: (data: EmailConfig) => api.post('/email-integration/test', data),
        onSuccess: () => {
            setTestResult({ success: true, message: t('emailIntegration.connectionSuccessful') });
            toast.success(t('emailIntegration.connectionSuccessful'));
        },
        onError: (error) => {
            const msg = getErrorMessage(error, (k) => k);
            setTestResult({ success: false, message: msg });
            toast.error(t('emailIntegration.connectionFailed'));
        },
    });

    const syncMutation = useMutation({
        mutationFn: () => api.post('/email-integration/sync'),
        onSuccess: () => {
            toast.info(t('emailIntegration.syncStarted'));
            localStorage.setItem('email_sync_state', JSON.stringify({ timestamp: Date.now() }));
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, (k) => k));
        },
    });

    // Check sync status polling
    const { data: syncStatus, isLoading: isCheckingSync } = useQuery({
        queryKey: ['email-sync-status'],
        queryFn: () => api.get<{ status: string, message: string, downloaded: number, processed: number }>('/email-integration/sync/status'),
        enabled: !!localStorage.getItem('email_sync_state'),
        refetchInterval: (query) => {
            const data = query.state.data as any;
            if (data?.status === 'completed' || data?.status === 'failed') {
                return false;
            }
            return 2000;
        },
    });

    useEffect(() => {
        if (syncStatus?.status === 'completed') {
            toast.success(syncStatus.message || t('emailIntegration.syncComplete'));
            localStorage.removeItem('email_sync_state');
            queryClient.invalidateQueries({ queryKey: ['email-sync-status'] });
        } else if (syncStatus?.status === 'failed') {
            toast.error(syncStatus.message || t('emailIntegration.syncFailed'));
            localStorage.removeItem('email_sync_state');
            queryClient.invalidateQueries({ queryKey: ['email-sync-status'] });
        }
    }, [syncStatus, t, queryClient]);

    const loading = queryLoading || saveMutation.isPending;
    const testing = testMutation.isPending;
    const syncing = syncMutation.isPending || (syncStatus?.status === 'running' || syncStatus?.status === 'starting');

    const handleChange = (field: keyof EmailConfig, value: any) => {
        setConfig(prev => ({ ...prev, [field]: value }));
        if (field === 'password' && value) {
            setHasExistingPassword(true);
        }
    };

    const handleSave = () => {
        setTestResult(null);
        saveMutation.mutate(config);
    };

    const handleTestConnection = () => {
        setTestResult(null);
        testMutation.mutate(config);
    };

    const handleSync = () => {
        syncMutation.mutate();
    };

    return (
        <ProfessionalCard variant="elevated">
            <ProfessionalCardHeader>
                <ProfessionalCardTitle className="flex items-center gap-2">
                    <Mail className="h-5 w-5 text-primary" />
                    {t('emailIntegration.title')}
                </ProfessionalCardTitle>
                <p className="text-sm text-muted-foreground">
                    {t('emailIntegration.description')}
                </p>
            </ProfessionalCardHeader>
            <ProfessionalCardContent className="space-y-6">

                {testResult && (
                    <div className={`p-4 rounded-xl border flex items-start gap-3 ${testResult.success
                        ? 'bg-green-50/50 border-green-200/50 text-green-800'
                        : 'bg-red-50/50 border-red-200/50 text-red-800'
                        }`}>
                        {testResult.success ? (
                            <CheckCircle2 className="h-5 w-5 mt-0.5 shrink-0" />
                        ) : (
                            <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
                        )}
                        <div>
                            <h4 className="font-semibold text-sm">{testResult.success ? "Success" : "Error"}</h4>
                            <p className="text-sm font-medium leading-relaxed opacity-90">{testResult.message}</p>
                        </div>
                    </div>
                )}

                <div className="flex items-center justify-between p-4 bg-muted/20 rounded-xl border border-border/50">
                    <Label htmlFor="email-enabled" className="text-base font-medium flex-1 cursor-pointer">
                        {t('emailIntegration.enable')}
                    </Label>
                    <Switch
                        id="email-enabled"
                        checked={config.enabled}
                        onCheckedChange={(checked) => handleChange('enabled', checked)}
                    />
                </div>

                <div className="space-y-2">
                    <Label>{t('emailIntegration.serviceProvider')}</Label>
                    <Select
                        value={PROVIDERS.find(p => p.host === config.imap_host)?.id || 'custom'}
                        onValueChange={(value) => {
                            const provider = PROVIDERS.find(p => p.id === value);
                            if (provider) {
                                if (value === 'custom') {
                                    // Clear host when custom is selected so user can enter their own
                                    setConfig(prev => ({
                                        ...prev,
                                        imap_host: '',
                                        imap_port: 993
                                    }));
                                } else {
                                    // Set predefined provider settings
                                    setConfig(prev => ({
                                        ...prev,
                                        imap_host: provider.host,
                                        imap_port: provider.port
                                    }));
                                }
                            }
                        }}
                        disabled={loading}
                    >
                        <SelectTrigger className="h-10">
                            <SelectValue placeholder={t('emailIntegration.selectProvider')} />
                        </SelectTrigger>
                        <SelectContent>
                            {PROVIDERS.map(provider => (
                                <SelectItem key={provider.id} value={provider.id}>
                                    {provider.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {config.imap_host === 'imap.gmail.com' && (
                    <div className="p-4 bg-blue-50/50 border border-blue-200/50 rounded-xl text-blue-800 flex items-start gap-3">
                        <AlertCircle className="h-5 w-5 mt-0.5 shrink-0 text-blue-600" />
                        <div>
                            <h4 className="font-semibold text-sm mb-1">{t('emailIntegration.gmailAlert.title')}</h4>
                            <div className="text-sm opacity-90 space-y-1">
                                <p>{t('emailIntegration.gmailAlert.description')}</p>
                                <p>1. {t('emailIntegration.gmailAlert.step1')}</p>
                                <p>2. <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer" className="underline font-medium hover:text-blue-900">{t('emailIntegration.gmailAlert.step2')}</a></p>
                                <p>3. {t('emailIntegration.gmailAlert.step3')}</p>
                            </div>
                        </div>
                    </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <ProfessionalInput
                        id="imap_host"
                        label={t('emailIntegration.imapHost')}
                        placeholder="imap.gmail.com"
                        value={config.imap_host}
                        onChange={(e) => handleChange('imap_host', e.target.value)}
                        disabled={loading}
                        leftIcon={<Globe className="w-4 h-4 text-muted-foreground" />}
                    />

                    <ProfessionalInput
                        id="imap_port"
                        type="number"
                        label={t('emailIntegration.imapPort')}
                        value={config.imap_port}
                        onChange={(e) => handleChange('imap_port', parseInt(e.target.value))}
                        disabled={loading}
                        leftIcon={<Hash className="w-4 h-4 text-muted-foreground" />}
                    />

                    <ProfessionalInput
                        id="username"
                        label={t('emailIntegration.username')}
                        value={config.username}
                        onChange={(e) => handleChange('username', e.target.value)}
                        disabled={loading}
                        leftIcon={<User className="w-4 h-4 text-muted-foreground" />}
                    />

                    <ProfessionalInput
                        id="password"
                        type="password"
                        label={t('emailIntegration.password')}
                        value={config.password}
                        onChange={(e) => handleChange('password', e.target.value)}
                        placeholder={config.password ? "********" : t('emailIntegration.passwordPlaceholder')}
                        disabled={loading}
                        helperText={t('emailIntegration.passwordHint')}
                        leftIcon={<Key className="w-4 h-4 text-muted-foreground" />}
                    />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <ProfessionalInput
                        id="allowed_senders"
                        label={t('emailIntegration.allowedSenders')}
                        value={config.allowed_senders}
                        onChange={(e) => handleChange('allowed_senders', e.target.value)}
                        placeholder={t('emailIntegration.allowedSendersPlaceholder')}
                        disabled={loading}
                        helperText={t('emailIntegration.allowedSendersHint')}
                        leftIcon={<List className="w-4 h-4 text-muted-foreground" />}
                    />

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <ProfessionalInput
                            id="lookback_days"
                            type="number"
                            min={1}
                            max={365}
                            label={t('emailIntegration.lookbackDays')}
                            value={config.lookback_days}
                            onChange={(e) => handleChange('lookback_days', parseInt(e.target.value))}
                            disabled={loading}
                            helperText={t('emailIntegration.lookbackDaysHint')}
                            leftIcon={<Clock className="w-4 h-4 text-muted-foreground" />}
                        />

                        <ProfessionalInput
                            id="max_emails_to_fetch"
                            type="number"
                            min={1}
                            max={1000}
                            label="Max Emails per Sync"
                            value={config.max_emails_to_fetch}
                            onChange={(e) => handleChange('max_emails_to_fetch', parseInt(e.target.value))}
                            disabled={loading}
                            helperText="Limit per sync to avoid timeouts."
                            leftIcon={<Server className="w-4 h-4 text-muted-foreground" />}
                        />
                    </div>
                </div>

                <div className="flex flex-wrap gap-4 pt-6 border-t border-border/50">
                    <ProfessionalButton
                        onClick={handleSave}
                        loading={loading}
                        disabled={loading || testing}
                        leftIcon={<Save className="h-4 w-4" />}
                        variant="gradient"
                    >
                        {t('emailIntegration.saveSettings')}
                    </ProfessionalButton>

                    <ProfessionalButton
                        variant="outline"
                        onClick={handleTestConnection}
                        loading={testing}
                        disabled={loading || testing || !config.imap_host || !config.username}
                        leftIcon={<CheckCircle2 className="h-4 w-4" />}
                    >
                        {t('emailIntegration.testConnection')}
                    </ProfessionalButton>

                    <ProfessionalButton
                        variant="secondary"
                        onClick={handleSync}
                        loading={syncing}
                        disabled={loading || testing || syncing || !config.enabled}
                        leftIcon={<RefreshCw className="h-4 w-4" />}
                    >
                        {t('emailIntegration.syncNow')}
                    </ProfessionalButton>
                </div>
            </ProfessionalCardContent>
        </ProfessionalCard>
    );
};

export default EmailIntegrationSettingsTab;
