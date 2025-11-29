import React, { useState, useEffect } from 'react';
import { useTranslation } from "react-i18next";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
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
    Loader2
} from "lucide-react";
import { toast } from "sonner";
import { api, getErrorMessage } from "@/lib/api";

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

import { FeatureGate } from "@/components/FeatureGate";

const EmailIntegrationSettings: React.FC = () => {
    return (
        <FeatureGate
            feature="email_integration"
            fallback={
                <div className="bg-white dark:bg-gray-800 rounded-xl p-12 shadow-sm border border-gray-200 dark:border-gray-700">
                    <div className="text-center max-w-2xl mx-auto">
                        <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                            <Mail className="w-8 h-8 text-blue-600 dark:text-blue-400" />
                        </div>
                        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">Business License Required</h3>
                        <p className="text-gray-600 dark:text-gray-300 mb-6">
                            Email integration allows you to automatically ingest expenses from your inbox - a powerful automation feature.
                            Upgrade to a business license to enable email integration and save time on manual entry.
                        </p>
                        <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-6 mb-6">
                            <h4 className="font-semibold text-gray-900 dark:text-white mb-3">With Business License, you get:</h4>
                            <ul className="text-left space-y-2 text-gray-700 dark:text-gray-300">
                                <li className="flex items-start">
                                    <span className="text-blue-600 mr-2">✓</span>
                                    <span>Automatic expense ingestion from email</span>
                                </li>
                                <li className="flex items-start">
                                    <span className="text-blue-600 mr-2">✓</span>
                                    <span>Support for Gmail, Outlook, and custom IMAP</span>
                                </li>
                                <li className="flex items-start">
                                    <span className="text-blue-600 mr-2">✓</span>
                                    <span>AI-powered expense classification</span>
                                </li>
                                <li className="flex items-start">
                                    <span className="text-blue-600 mr-2">✓</span>
                                    <span>Secure and encrypted connection</span>
                                </li>
                            </ul>
                        </div>
                        <div className="flex justify-center space-x-4">
                            <Button
                                onClick={() => window.location.href = '/settings?tab=license'}
                                className="bg-blue-600 hover:bg-blue-700 text-white"
                            >
                                Activate Business License
                            </Button>
                            <Button
                                variant="outline"
                                onClick={() => window.open('https://docs.example.com/email-integration', '_blank')}
                            >
                                Learn More
                            </Button>
                        </div>
                    </div>
                </div>
            }
        >
            <EmailIntegrationSettingsContent />
        </FeatureGate>
    );
};

const EmailIntegrationSettingsContent: React.FC = () => {
    const { t } = useTranslation();
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
    const [loading, setLoading] = useState(false);
    const [testing, setTesting] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [testResult, setTestResult] = useState<{ success: boolean, message: string } | null>(null);
    const [hasExistingPassword, setHasExistingPassword] = useState(false);

    useEffect(() => {
        // Check if there's an ongoing sync from localStorage
        const syncState = localStorage.getItem('email_sync_state');
        if (syncState) {
            const { timestamp } = JSON.parse(syncState);
            // If sync was started less than 5 minutes ago, assume it might still be running
            if (Date.now() - timestamp < 5 * 60 * 1000) {
                setSyncing(true);
                // Poll to check if sync is complete
                // checkSyncStatus(); // Handled by useEffect now
            } else {
                // Clear stale sync state
                localStorage.removeItem('email_sync_state');
            }
        }
        fetchConfig();
    }, []);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (syncing) {
            interval = setInterval(async () => {
                try {
                    const data = await api.get<{ status: string, message: string, downloaded: number, processed: number }>('/email-integration/sync/status');

                    if (data.status === 'completed') {
                        setSyncing(false);
                        toast.success(data.message || t('emailIntegration.syncComplete'));
                        localStorage.removeItem('email_sync_state');
                    } else if (data.status === 'failed') {
                        setSyncing(false);
                        toast.error(data.message || t('emailIntegration.syncFailed'));
                        localStorage.removeItem('email_sync_state');
                    }
                    // If running or starting, just keep polling
                } catch (error) {
                    console.error('Error checking sync status:', error);
                }
            }, 2000);
        }
        return () => clearInterval(interval);
    }, [syncing]);

    const fetchConfig = async () => {
        setLoading(true);
        try {
            const data = await api.get<EmailConfig>('/email-integration/config');
            setConfig(prev => ({ ...prev, ...data, password: '' })); // Don't show password
            // Check if password exists in the saved config
            setHasExistingPassword(!!data.username); // If username exists, assume password exists too
        } catch (error) {
            console.error('Failed to fetch config', error);
            // toast.error("Failed to load email settings");
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (field: keyof EmailConfig, value: any) => {
        setConfig(prev => ({ ...prev, [field]: value }));
        // If password is being changed, mark that we have a new password
        if (field === 'password' && value) {
            setHasExistingPassword(true);
        }
    };

    const handleSave = async () => {
        setLoading(true);
        setTestResult(null);
        try {
            await api.post('/email-integration/config', config);
            toast.success(t('settings.save_success'));
            // After save, mark that password exists
            setHasExistingPassword(true);
        } catch (error) {
            toast.error(getErrorMessage(error, (k) => k));
        } finally {
            setLoading(false);
        }
    };

    const handleTestConnection = async () => {
        setTesting(true);
        setTestResult(null);
        try {
            // If password field is empty but we have an existing password, 
            // the backend will use the saved one
            await api.post('/email-integration/test', config);
            setTestResult({ success: true, message: t('emailIntegration.connectionSuccessful') });
            toast.success(t('emailIntegration.connectionSuccessful'));
        } catch (error) {
            const msg = getErrorMessage(error, (k) => k);
            setTestResult({ success: false, message: msg });
            toast.error(t('emailIntegration.connectionFailed'));
        } finally {
            setTesting(false);
        }
    };

    const handleSync = async () => {
        setSyncing(true);
        // Store sync state in localStorage
        localStorage.setItem('email_sync_state', JSON.stringify({ timestamp: Date.now() }));

        try {
            await api.post('/email-integration/sync');
            toast.info(t('emailIntegration.syncStarted'));
        } catch (error) {
            setSyncing(false);
            localStorage.removeItem('email_sync_state');
            toast.error(getErrorMessage(error, (k) => k));
        }
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center gap-2">
                    <Mail className="h-5 w-5 text-primary" />
                    <CardTitle>{t('emailIntegration.title')}</CardTitle>
                </div>
                <CardDescription>
                    {t('emailIntegration.description')}
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">

                {testResult && (
                    <Alert variant={testResult.success ? "default" : "destructive"}>
                        {testResult.success ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                        <AlertTitle>{testResult.success ? "Success" : "Error"}</AlertTitle>
                        <AlertDescription>{testResult.message}</AlertDescription>
                    </Alert>
                )}

                <div className="flex items-center space-x-2">
                    <Switch
                        id="email-enabled"
                        checked={config.enabled}
                        onCheckedChange={(checked) => handleChange('enabled', checked)}
                    />
                    <Label htmlFor="email-enabled">{t('emailIntegration.enable')}</Label>
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
                        <SelectTrigger>
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
                    <Alert className="bg-blue-50 border-blue-200 text-blue-800">
                        <AlertCircle className="h-4 w-4 text-blue-800" />
                        <AlertTitle>{t('emailIntegration.gmailAlert.title')}</AlertTitle>
                        <AlertDescription>
                            {t('emailIntegration.gmailAlert.description')}
                            <br />
                            {t('emailIntegration.gmailAlert.step1')}
                            <br />
                            <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer" className="underline font-medium">{t('emailIntegration.gmailAlert.step2')}</a>
                            <br />
                            {t('emailIntegration.gmailAlert.step3')}
                        </AlertDescription>
                    </Alert>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <Label htmlFor="imap_host">{t('emailIntegration.imapHost')}</Label>
                        <Input
                            id="imap_host"
                            placeholder="imap.gmail.com"
                            value={config.imap_host}
                            onChange={(e) => handleChange('imap_host', e.target.value)}
                            disabled={loading}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="imap_port">{t('emailIntegration.imapPort')}</Label>
                        <Input
                            id="imap_port"
                            type="number"
                            value={config.imap_port}
                            onChange={(e) => handleChange('imap_port', parseInt(e.target.value))}
                            disabled={loading}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="username">{t('emailIntegration.username')}</Label>
                        <Input
                            id="username"
                            value={config.username}
                            onChange={(e) => handleChange('username', e.target.value)}
                            disabled={loading}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="password">{t('emailIntegration.password')}</Label>
                        <Input
                            id="password"
                            type="password"
                            value={config.password}
                            onChange={(e) => handleChange('password', e.target.value)}
                            placeholder={config.password ? "********" : t('emailIntegration.passwordPlaceholder')}
                            disabled={loading}
                        />
                        <p className="text-xs text-muted-foreground">{t('emailIntegration.passwordHint')}</p>
                    </div>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="allowed_senders">{t('emailIntegration.allowedSenders')}</Label>
                    <Input
                        id="allowed_senders"
                        value={config.allowed_senders}
                        onChange={(e) => handleChange('allowed_senders', e.target.value)}
                        placeholder={t('emailIntegration.allowedSendersPlaceholder')}
                        disabled={loading}
                    />
                    <p className="text-xs text-muted-foreground">{t('emailIntegration.allowedSendersHint')}</p>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="lookback_days">{t('emailIntegration.lookbackDays')}</Label>
                    <Input
                        id="lookback_days"
                        type="number"
                        min={1}
                        max={365}
                        value={config.lookback_days}
                        onChange={(e) => handleChange('lookback_days', parseInt(e.target.value))}
                        disabled={loading}
                    />
                    <p className="text-xs text-muted-foreground">{t('emailIntegration.lookbackDaysHint')}</p>
                </div>

                {/* TODO: Add i18n keys for max_emails_to_fetch */}
                <div className="space-y-2">
                    <Label htmlFor="max_emails_to_fetch">Max Emails to Fetch per Sync</Label>
                    <Input
                        id="max_emails_to_fetch"
                        type="number"
                        min={1}
                        max={1000}
                        value={config.max_emails_to_fetch}
                        onChange={(e) => handleChange('max_emails_to_fetch', parseInt(e.target.value))}
                        disabled={loading}
                    />
                    <p className="text-xs text-muted-foreground">
                        Limit the number of emails to process in a single sync. A lower number can prevent timeouts on slow servers.
                    </p>
                </div>

                <div className="flex flex-wrap gap-4 pt-4">
                    <Button
                        onClick={handleSave}
                        disabled={loading || testing}
                        className="gap-2"
                    >
                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                        {t('emailIntegration.saveSettings')}
                    </Button>

                    <Button
                        variant="outline"
                        onClick={handleTestConnection}
                        disabled={loading || testing || !config.imap_host || !config.username}
                        className="gap-2"
                    >
                        {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                        {t('emailIntegration.testConnection')}
                    </Button>

                    <Button
                        variant="secondary"
                        onClick={handleSync}
                        disabled={loading || testing || syncing || !config.enabled}
                        className="gap-2"
                    >
                        {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                        {t('emailIntegration.syncNow')}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
};

export default EmailIntegrationSettings;
