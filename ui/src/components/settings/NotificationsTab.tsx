import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Mail, Bell, User, Settings as SettingsIcon, Key, Globe,
    Activity, Send, Loader2, FileText, CreditCard, ShoppingBag,
    Package, BookOpen, Clock, BarChart2
} from "lucide-react";
import { toast } from "sonner";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import {
    ProfessionalCard,
    ProfessionalCardContent,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
} from "@/components/ui/professional-card";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { settingsApi, getErrorMessage } from "@/lib/api";
import { getCurrentUser } from "@/utils/auth";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

interface EmailSettings {
    provider: string;
    from_name: string;
    from_email: string;
    enabled: boolean;
    aws_access_key_id: string;
    aws_secret_access_key: string;
    aws_region: string;
    azure_connection_string: string;
    mailgun_api_key: string;
    mailgun_domain: string;
}

interface NotificationSettings {
    user_created: boolean;
    user_updated: boolean;
    user_deleted: boolean;
    user_login: boolean;
    client_created: boolean;
    client_updated: boolean;
    client_deleted: boolean;
    invoice_created: boolean;
    invoice_updated: boolean;
    invoice_deleted: boolean;
    invoice_sent: boolean;
    invoice_paid: boolean;
    invoice_overdue: boolean;
    payment_created: boolean;
    payment_updated: boolean;
    payment_deleted: boolean;
    expense_created: boolean;
    expense_updated: boolean;
    expense_deleted: boolean;
    expense_approved: boolean;
    expense_rejected: boolean;
    expense_submitted: boolean;
    inventory_created: boolean;
    inventory_updated: boolean;
    inventory_deleted: boolean;
    inventory_low_stock: boolean;
    inventory_out_of_stock: boolean;
    statement_generated: boolean;
    statement_sent: boolean;
    statement_overdue: boolean;
    reminder_created: boolean;
    reminder_sent: boolean;
    reminder_overdue: boolean;
    settings_updated: boolean;
    notification_email: string;
    daily_summary: boolean;
    weekly_summary: boolean;
}

interface NotificationsTabProps {
    isAdmin: boolean;
}

interface ToggleOp {
    key: keyof NotificationSettings;
    label: string;
    desc: string;
}

interface NotificationGroupProps {
    value: string;
    icon: React.ReactNode;
    title: string;
    ops: ToggleOp[];
    settings: NotificationSettings;
    onToggle: (key: keyof NotificationSettings, checked: boolean) => void;
}

const NotificationGroup: React.FC<NotificationGroupProps> = ({ value, icon, title, ops, settings, onToggle }) => {
    const enabledCount = ops.filter(op => settings[op.key] as boolean).length;
    return (
        <AccordionItem value={value} className="border border-border/40 rounded-xl px-4 overflow-hidden">
            <AccordionTrigger className="py-4 hover:no-underline">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                        {icon}
                    </div>
                    <span className="text-sm font-semibold">{title}</span>
                    <Badge variant={enabledCount > 0 ? "default" : "secondary"} className="ml-auto mr-2 text-xs">
                        {enabledCount}/{ops.length}
                    </Badge>
                </div>
            </AccordionTrigger>
            <AccordionContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pb-4">
                    {ops.map((op) => (
                        <div key={op.key as string} className="flex items-center justify-between p-3 bg-muted/20 rounded-lg">
                            <div className="space-y-0.5 mr-3">
                                <Label className="text-sm font-medium">{op.label}</Label>
                                <p className="text-xs text-muted-foreground">{op.desc}</p>
                            </div>
                            <Switch
                                checked={settings[op.key] as boolean}
                                onCheckedChange={(checked) => onToggle(op.key, checked)}
                            />
                        </div>
                    ))}
                </div>
            </AccordionContent>
        </AccordionItem>
    );
};

export const NotificationsTab: React.FC<NotificationsTabProps> = ({ isAdmin }) => {
    const { t } = useTranslation();
    const queryClient = useQueryClient();

    const [emailSettings, setEmailSettings] = useState<EmailSettings>({
        provider: 'aws_ses', from_name: '', from_email: '', enabled: false,
        aws_access_key_id: '', aws_secret_access_key: '', aws_region: 'us-east-1',
        azure_connection_string: '', mailgun_api_key: '', mailgun_domain: ''
    });

    const [notificationSettings, setNotificationSettings] = useState<NotificationSettings>({
        user_created: false, user_updated: false, user_deleted: false, user_login: false,
        client_created: false, client_updated: false, client_deleted: false,
        invoice_created: false, invoice_updated: false, invoice_deleted: false,
        invoice_sent: false, invoice_paid: false, invoice_overdue: false,
        payment_created: false, payment_updated: false, payment_deleted: false,
        expense_created: false, expense_updated: false, expense_deleted: false,
        expense_approved: false, expense_rejected: false, expense_submitted: false,
        inventory_created: false, inventory_updated: false, inventory_deleted: false,
        inventory_low_stock: false, inventory_out_of_stock: false,
        statement_generated: false, statement_sent: false, statement_overdue: false,
        reminder_created: false, reminder_sent: false, reminder_overdue: false,
        settings_updated: false, notification_email: '',
        daily_summary: false, weekly_summary: false
    });

    const { data: generalSettings, isLoading: isLoadingGeneral } = useQuery({
        queryKey: ['settings'],
        queryFn: () => settingsApi.getSettings(),
        enabled: isAdmin,
    });

    const { data: notificationsData, isLoading: isLoadingNotifications } = useQuery({
        queryKey: ['notificationSettings'],
        queryFn: () => settingsApi.getNotificationSettings(),
        enabled: isAdmin,
    });

    useEffect(() => {
        if (generalSettings?.email_settings) setEmailSettings(generalSettings.email_settings);
    }, [generalSettings]);

    useEffect(() => {
        if (notificationsData) setNotificationSettings(notificationsData);
    }, [notificationsData]);

    const updateEmailMutation = useMutation({
        mutationFn: (data: EmailSettings) => settingsApi.updateSettings({ email_settings: data }),
        onSuccess: () => {
            toast.success(t('settings.settings_saved_successfully'));
            queryClient.invalidateQueries({ queryKey: ['settings'] });
        },
        onError: (error) => toast.error(getErrorMessage(error, t))
    });

    const updateNotificationsMutation = useMutation({
        mutationFn: (data: NotificationSettings) => settingsApi.updateNotificationSettings(data),
        onSuccess: () => {
            toast.success(t('settings.notification_settings_updated_successfully', 'Notification settings updated successfully'));
            queryClient.invalidateQueries({ queryKey: ['notificationSettings'] });
        },
        onError: (error) => toast.error(getErrorMessage(error, t))
    });

    const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setEmailSettings(prev => ({ ...prev, [name]: value }));
    };
    const handleEmailToggleChange = (name: string, checked: boolean) => {
        setEmailSettings(prev => ({ ...prev, [name]: checked }));
    };
    const handleTestEmailConfiguration = async () => {
        try {
            const currentUser = getCurrentUser();
            const fallbackEmail =
                notificationSettings.notification_email?.trim() ||
                emailSettings.from_email?.trim() ||
                currentUser?.email?.trim() ||
                "";

            if (!fallbackEmail) {
                toast.error(t('settings.notification_email_required', 'Please provide an email address to send a test email.'));
                return;
            }

            await settingsApi.testEmailConfiguration(fallbackEmail);
            toast.success(t('settings.test_email_sent_successfully'));
        } catch (error) { toast.error(getErrorMessage(error, t)); }
    };
    const handleNotificationToggle = (setting: keyof NotificationSettings, checked: boolean) => {
        setNotificationSettings(prev => ({ ...prev, [setting]: checked }));
    };
    const handleNotificationEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setNotificationSettings(prev => ({ ...prev, notification_email: e.target.value }));
    };
    const handleTestNotification = async () => {
        try {
            await settingsApi.testNotification();
            toast.success(t('settings.test_notification_sent_successfully'));
        } catch (error) { toast.error(getErrorMessage(error, t)); }
    };

    if (isLoadingGeneral || isLoadingNotifications) {
        return <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
    }

    const notificationGroups = [
        {
            value: 'users',
            icon: <User className="w-4 h-4 text-primary" />,
            title: 'User Operations',
            ops: [
                { key: 'user_created' as keyof NotificationSettings, label: 'User Created', desc: 'When a new user is added' },
                { key: 'user_updated' as keyof NotificationSettings, label: 'User Updated', desc: 'When user info is modified' },
                { key: 'user_deleted' as keyof NotificationSettings, label: 'User Deleted', desc: 'When a user is removed' },
                { key: 'user_login' as keyof NotificationSettings, label: 'User Login', desc: 'When a user logs in' },
            ]
        },
        {
            value: 'clients',
            icon: <User className="w-4 h-4 text-primary" />,
            title: 'Client Operations',
            ops: [
                { key: 'client_created' as keyof NotificationSettings, label: 'Client Created', desc: 'When a new client is added' },
                { key: 'client_updated' as keyof NotificationSettings, label: 'Client Updated', desc: 'When client info is modified' },
                { key: 'client_deleted' as keyof NotificationSettings, label: 'Client Deleted', desc: 'When a client is removed' },
            ]
        },
        {
            value: 'invoices',
            icon: <FileText className="w-4 h-4 text-primary" />,
            title: 'Invoice Operations',
            ops: [
                { key: 'invoice_created' as keyof NotificationSettings, label: 'Invoice Created', desc: 'When a new invoice is created' },
                { key: 'invoice_updated' as keyof NotificationSettings, label: 'Invoice Updated', desc: 'When invoice is modified' },
                { key: 'invoice_deleted' as keyof NotificationSettings, label: 'Invoice Deleted', desc: 'When an invoice is deleted' },
                { key: 'invoice_sent' as keyof NotificationSettings, label: 'Invoice Sent', desc: 'When invoice is sent to client' },
                { key: 'invoice_paid' as keyof NotificationSettings, label: 'Invoice Paid', desc: 'When invoice is marked as paid' },
                { key: 'invoice_overdue' as keyof NotificationSettings, label: 'Invoice Overdue', desc: 'When invoice becomes overdue' },
            ]
        },
        {
            value: 'payments',
            icon: <CreditCard className="w-4 h-4 text-primary" />,
            title: 'Payment Operations',
            ops: [
                { key: 'payment_created' as keyof NotificationSettings, label: 'Payment Created', desc: 'When a payment is recorded' },
                { key: 'payment_updated' as keyof NotificationSettings, label: 'Payment Updated', desc: 'When payment is modified' },
                { key: 'payment_deleted' as keyof NotificationSettings, label: 'Payment Deleted', desc: 'When a payment is removed' },
            ]
        },
        {
            value: 'expenses',
            icon: <ShoppingBag className="w-4 h-4 text-primary" />,
            title: t('settings.expense_operations'),
            ops: [
                { key: 'expense_created' as keyof NotificationSettings, label: t('settings.expense_created'), desc: t('settings.expense_created_description') },
                { key: 'expense_updated' as keyof NotificationSettings, label: t('settings.expense_updated'), desc: t('settings.expense_updated_description') },
                { key: 'expense_deleted' as keyof NotificationSettings, label: t('settings.expense_deleted'), desc: t('settings.expense_deleted_description') },
                { key: 'expense_approved' as keyof NotificationSettings, label: t('settings.expense_approved'), desc: t('settings.expense_approved_description') },
                { key: 'expense_rejected' as keyof NotificationSettings, label: t('settings.expense_rejected'), desc: t('settings.expense_rejected_description') },
                { key: 'expense_submitted' as keyof NotificationSettings, label: t('settings.expense_submitted'), desc: t('settings.expense_submitted_description') },
            ]
        },
        {
            value: 'inventory',
            icon: <Package className="w-4 h-4 text-primary" />,
            title: t('settings.inventory_operations'),
            ops: [
                { key: 'inventory_created' as keyof NotificationSettings, label: t('settings.inventory_created'), desc: t('settings.inventory_created_description') },
                { key: 'inventory_updated' as keyof NotificationSettings, label: t('settings.inventory_updated'), desc: t('settings.inventory_updated_description') },
                { key: 'inventory_deleted' as keyof NotificationSettings, label: t('settings.inventory_deleted'), desc: t('settings.inventory_deleted_description') },
                { key: 'inventory_low_stock' as keyof NotificationSettings, label: t('settings.inventory_low_stock'), desc: t('settings.inventory_low_stock_description') },
                { key: 'inventory_out_of_stock' as keyof NotificationSettings, label: t('settings.inventory_out_of_stock'), desc: t('settings.inventory_out_of_stock_description') },
            ]
        },
        {
            value: 'statements',
            icon: <BookOpen className="w-4 h-4 text-primary" />,
            title: t('settings.statement_operations'),
            ops: [
                { key: 'statement_generated' as keyof NotificationSettings, label: t('settings.statement_generated'), desc: t('settings.statement_generated_description') },
                { key: 'statement_sent' as keyof NotificationSettings, label: t('settings.statement_sent'), desc: t('settings.statement_sent_description') },
                { key: 'statement_overdue' as keyof NotificationSettings, label: t('settings.statement_overdue'), desc: t('settings.statement_overdue_description') },
            ]
        },
        {
            value: 'reminders',
            icon: <Clock className="w-4 h-4 text-primary" />,
            title: t('settings.reminder_operations'),
            ops: [
                { key: 'reminder_created' as keyof NotificationSettings, label: t('settings.reminder_created'), desc: t('settings.reminder_created_description') },
                { key: 'reminder_sent' as keyof NotificationSettings, label: t('settings.reminder_sent'), desc: t('settings.reminder_sent_description') },
                { key: 'reminder_overdue' as keyof NotificationSettings, label: t('settings.reminder_overdue'), desc: t('settings.reminder_overdue_description') },
            ]
        },
    ];

    return (
        <div className="space-y-6">
            {/* Email Configuration Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="flex items-center gap-2">
                        <Mail className="w-5 h-5 text-primary" />
                        {t('settings.email_configuration')}
                    </ProfessionalCardTitle>
                    <p className="text-sm text-muted-foreground">Configure your email service provider and settings</p>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-6">
                    <div className="flex items-center justify-between p-4 bg-muted/20 rounded-xl border border-border/50">
                        <div className="space-y-0.5">
                            <Label htmlFor="email_enabled" className="text-base font-semibold">{t('settings.enable_email_service')}</Label>
                            <p className="text-sm text-muted-foreground">{t('settings.enable_email_service_description')}</p>
                        </div>
                        <Switch
                            id="email_enabled"
                            checked={emailSettings.enabled}
                            onCheckedChange={(checked) => handleEmailToggleChange('enabled', checked)}
                        />
                    </div>

                    {emailSettings.enabled && (
                        <>
                            <div className="space-y-2">
                                <Label htmlFor="provider">{t('settings.email_provider')}</Label>
                                <Select value={emailSettings.provider} onValueChange={(v) => setEmailSettings(prev => ({ ...prev, provider: v }))}>
                                    <SelectTrigger className="h-10">
                                        <SelectValue placeholder={t('settings.select_email_provider')} />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="aws_ses">{t('settings.aws_ses')}</SelectItem>
                                        <SelectItem value="azure_email">{t('settings.azure_email_services')}</SelectItem>
                                        <SelectItem value="mailgun">{t('settings.mailgun')}</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <ProfessionalInput
                                    id="from_name" name="from_name"
                                    label={t('settings.from_name')}
                                    value={emailSettings.from_name}
                                    onChange={handleEmailChange}
                                    placeholder="e.g. Acme Corp"
                                    leftIcon={<User className="w-4 h-4 text-muted-foreground" />}
                                />
                                <ProfessionalInput
                                    id="from_email" name="from_email" type="email"
                                    label={t('settings.from_email')}
                                    value={emailSettings.from_email}
                                    onChange={handleEmailChange}
                                    placeholder="noreply@example.com"
                                    leftIcon={<Mail className="w-4 h-4 text-muted-foreground" />}
                                />
                            </div>

                            {emailSettings.provider === "aws_ses" && (
                                <div className="space-y-4 p-6 border border-border/50 rounded-xl bg-card">
                                    <h4 className="font-semibold flex items-center gap-2">
                                        <SettingsIcon className="w-4 h-4" />
                                        {t('settings.aws_ses_configuration')}
                                    </h4>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <ProfessionalInput id="aws_access_key_id" name="aws_access_key_id" type="password"
                                            label={t('settings.aws_access_key_id')} value={emailSettings.aws_access_key_id}
                                            onChange={handleEmailChange} leftIcon={<Key className="w-4 h-4 text-muted-foreground" />} />
                                        <ProfessionalInput id="aws_secret_access_key" name="aws_secret_access_key" type="password"
                                            label={t('settings.aws_secret_access_key')} value={emailSettings.aws_secret_access_key}
                                            onChange={handleEmailChange} leftIcon={<Key className="w-4 h-4 text-muted-foreground" />} />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="aws_region">{t('settings.aws_region')}</Label>
                                        <Select value={emailSettings.aws_region} onValueChange={(v) => setEmailSettings(prev => ({ ...prev, aws_region: v }))}>
                                            <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="us-east-1">{t('settings.us_east_virginia')}</SelectItem>
                                                <SelectItem value="us-west-2">{t('settings.us_west_oregon')}</SelectItem>
                                                <SelectItem value="eu-west-1">{t('settings.eu_ireland')}</SelectItem>
                                                <SelectItem value="ap-southeast-1">{t('settings.asia_pacific_singapore')}</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                            )}

                            {emailSettings.provider === "azure_email" && (
                                <div className="space-y-4 p-6 border border-border/50 rounded-xl bg-card">
                                    <h4 className="font-semibold flex items-center gap-2">
                                        <SettingsIcon className="w-4 h-4" />
                                        {t('settings.azure_email_services_configuration')}
                                    </h4>
                                    <ProfessionalInput id="azure_connection_string" name="azure_connection_string" type="password"
                                        label={t('settings.azure_connection_string')} value={emailSettings.azure_connection_string}
                                        onChange={handleEmailChange} leftIcon={<Globe className="w-4 h-4 text-muted-foreground" />} />
                                </div>
                            )}

                            {emailSettings.provider === "mailgun" && (
                                <div className="space-y-4 p-6 border border-border/50 rounded-xl bg-card">
                                    <h4 className="font-semibold flex items-center gap-2">
                                        <SettingsIcon className="w-4 h-4" />
                                        {t('settings.mailgun_configuration')}
                                    </h4>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <ProfessionalInput id="mailgun_api_key" name="mailgun_api_key" type="password"
                                            label={t('settings.mailgun_api_key')} value={emailSettings.mailgun_api_key}
                                            onChange={handleEmailChange} leftIcon={<Key className="w-4 h-4 text-muted-foreground" />} />
                                        <ProfessionalInput id="mailgun_domain" name="mailgun_domain"
                                            label={t('settings.mailgun_domain')} value={emailSettings.mailgun_domain}
                                            onChange={handleEmailChange} leftIcon={<Globe className="w-4 h-4 text-muted-foreground" />} />
                                    </div>
                                </div>
                            )}

                            <div className="flex justify-between pt-4 border-t border-border/50">
                                <ProfessionalButton type="button" variant="outline" onClick={handleTestEmailConfiguration}
                                    leftIcon={<Activity className="w-4 h-4" />}>
                                    {t('settings.test_configuration')}
                                </ProfessionalButton>
                                <ProfessionalButton onClick={() => updateEmailMutation.mutate(emailSettings)}
                                    loading={updateEmailMutation.isPending} variant="gradient">
                                    {t('settings.save_email_settings')}
                                </ProfessionalButton>
                            </div>
                        </>
                    )}
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Notification Triggers Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="flex items-center gap-2">
                        <Bell className="w-5 h-5 text-primary" />
                        {t('settings.notification_settings_title')}
                    </ProfessionalCardTitle>
                    <p className="text-sm text-muted-foreground">{t('settings.notification_settings_description')}</p>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-6">
                    {/* Notification email override */}
                    <div className="p-4 bg-muted/20 rounded-xl border border-border/50">
                        <ProfessionalInput
                            id="notification_email" type="email"
                            label="Notification Email (Optional)"
                            value={notificationSettings.notification_email}
                            onChange={handleNotificationEmailChange}
                            placeholder="Leave empty to use your account email"
                            helperText="If specified, notifications will be sent to this email instead of your account email"
                            leftIcon={<Mail className="w-4 h-4 text-muted-foreground" />}
                        />
                    </div>

                    {/* Accordion Groups */}
                    <Accordion type="multiple" defaultValue={['users', 'invoices']} className="space-y-2">
                        {notificationGroups.map((group) => (
                            <NotificationGroup
                                key={group.value}
                                value={group.value}
                                icon={group.icon}
                                title={group.title}
                                ops={group.ops}
                                settings={notificationSettings}
                                onToggle={handleNotificationToggle}
                            />
                        ))}
                    </Accordion>

                    {/* Summary Notifications (always visible — only 2 items) */}
                    <div className="space-y-3 pt-2">
                        <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                            <BarChart2 className="w-4 h-4" />
                            Summary Notifications
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {[
                                { key: 'daily_summary' as keyof NotificationSettings, label: t('settings.daily_summary'), desc: t('settings.daily_summary_description') },
                                { key: 'weekly_summary' as keyof NotificationSettings, label: t('settings.weekly_summary'), desc: t('settings.weekly_summary_description') },
                            ].map((op) => (
                                <div key={op.key as string} className="flex items-center justify-between p-3 bg-muted/20 rounded-lg border border-border/30">
                                    <div className="space-y-0.5 mr-3">
                                        <Label className="text-sm font-medium">{op.label}</Label>
                                        <p className="text-xs text-muted-foreground">{op.desc}</p>
                                    </div>
                                    <Switch
                                        checked={notificationSettings[op.key] as boolean}
                                        onCheckedChange={(checked) => handleNotificationToggle(op.key, checked)}
                                    />
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="flex justify-between pt-6 border-t border-border/50">
                        <ProfessionalButton type="button" variant="outline" onClick={handleTestNotification}
                            leftIcon={<Send className="w-4 h-4" />}>
                            {t('settings.send_test_notification')}
                        </ProfessionalButton>
                        <ProfessionalButton onClick={() => updateNotificationsMutation.mutate(notificationSettings)}
                            loading={updateNotificationsMutation.isPending} variant="gradient">
                            {t('settings.save_notification_settings')}
                        </ProfessionalButton>
                    </div>
                </ProfessionalCardContent>
            </ProfessionalCard>
        </div>
    );
};
