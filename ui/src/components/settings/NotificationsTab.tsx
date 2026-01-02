import React from 'react';
import { useTranslation } from 'react-i18next';
import {
    Mail,
    Bell,
    User,
    Settings as SettingsIcon,
    Key,
    Globe,
    Activity,
    Send,
    Loader2
} from "lucide-react";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    ProfessionalCard,
    ProfessionalCardContent,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
} from "@/components/ui/professional-card";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalButton } from "@/components/ui/professional-button";

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
    emailSettings: EmailSettings;
    notificationSettings: NotificationSettings;
    saving: boolean;
    savingNotifications: boolean;
    loadingNotifications: boolean;
    isAdmin: boolean;
    onEmailChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
    onEmailToggleChange: (name: string, checked: boolean) => void;
    onEmailProviderChange: (provider: string) => void;
    onTestEmailConfiguration: () => void;
    onNotificationToggle: (setting: string, checked: boolean) => void;
    onNotificationEmailChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onSaveNotifications: () => void;
    onTestNotification: () => void;
    onSave: () => void;
    onSetEmailSettings: React.Dispatch<React.SetStateAction<EmailSettings>>;
}

const NotificationsTab: React.FC<NotificationsTabProps> = ({
    emailSettings,
    notificationSettings,
    saving,
    savingNotifications,
    loadingNotifications,
    isAdmin,
    onEmailChange,
    onEmailToggleChange,
    onEmailProviderChange,
    onTestEmailConfiguration,
    onNotificationToggle,
    onNotificationEmailChange,
    onSaveNotifications,
    onTestNotification,
    onSave,
    onSetEmailSettings
}) => {
    const { t } = useTranslation();

    return (
        <div className="space-y-6">
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="flex items-center gap-2">
                        <Mail className="w-5 h-5 text-primary" />
                        {t('settings.email_configuration')}
                    </ProfessionalCardTitle>
                    <p className="text-sm text-muted-foreground">
                        Configure your email service provider and settings
                    </p>
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
                            onCheckedChange={(checked) => onEmailToggleChange('enabled', checked)}
                        />
                    </div>

                    {emailSettings.enabled && (
                        <>
                            <div className="space-y-2">
                                <Label htmlFor="provider">{t('settings.email_provider')}</Label>
                                <Select value={emailSettings.provider} onValueChange={onEmailProviderChange}>
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
                                    id="from_name"
                                    name="from_name"
                                    label={t('settings.from_name')}
                                    value={emailSettings.from_name}
                                    onChange={onEmailChange}
                                    placeholder="e.g. Acme Corp"
                                    leftIcon={<User className="w-4 h-4 text-muted-foreground" />}
                                />

                                <ProfessionalInput
                                    id="from_email"
                                    name="from_email"
                                    type="email"
                                    label={t('settings.from_email')}
                                    value={emailSettings.from_email}
                                    onChange={onEmailChange}
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
                                        <ProfessionalInput
                                            id="aws_access_key_id"
                                            name="aws_access_key_id"
                                            type="password"
                                            label={t('settings.aws_access_key_id')}
                                            value={emailSettings.aws_access_key_id}
                                            onChange={onEmailChange}
                                            leftIcon={<Key className="w-4 h-4 text-muted-foreground" />}
                                        />
                                        <ProfessionalInput
                                            id="aws_secret_access_key"
                                            name="aws_secret_access_key"
                                            type="password"
                                            label={t('settings.aws_secret_access_key')}
                                            value={emailSettings.aws_secret_access_key}
                                            onChange={onEmailChange}
                                            leftIcon={<Key className="w-4 h-4 text-muted-foreground" />}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="aws_region">{t('settings.aws_region')}</Label>
                                        <Select
                                            value={emailSettings.aws_region}
                                            onValueChange={(value) => onSetEmailSettings(prev => ({ ...prev, aws_region: value }))}
                                        >
                                            <SelectTrigger className="h-10">
                                                <SelectValue />
                                            </SelectTrigger>
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
                                    <div className="space-y-2">
                                        <ProfessionalInput
                                            id="azure_connection_string"
                                            name="azure_connection_string"
                                            type="password"
                                            label={t('settings.azure_connection_string')}
                                            value={emailSettings.azure_connection_string}
                                            onChange={onEmailChange}
                                            leftIcon={<Globe className="w-4 h-4 text-muted-foreground" />}
                                        />
                                    </div>
                                </div>
                            )}

                            {emailSettings.provider === "mailgun" && (
                                <div className="space-y-4 p-6 border border-border/50 rounded-xl bg-card">
                                    <h4 className="font-semibold flex items-center gap-2">
                                        <SettingsIcon className="w-4 h-4" />
                                        {t('settings.mailgun_configuration')}
                                    </h4>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <ProfessionalInput
                                            id="mailgun_api_key"
                                            name="mailgun_api_key"
                                            type="password"
                                            label={t('settings.mailgun_api_key')}
                                            value={emailSettings.mailgun_api_key}
                                            onChange={onEmailChange}
                                            leftIcon={<Key className="w-4 h-4 text-muted-foreground" />}
                                        />
                                        <ProfessionalInput
                                            id="mailgun_domain"
                                            name="mailgun_domain"
                                            label={t('settings.mailgun_domain')}
                                            value={emailSettings.mailgun_domain}
                                            onChange={onEmailChange}
                                            leftIcon={<Globe className="w-4 h-4 text-muted-foreground" />}
                                        />
                                    </div>
                                </div>
                            )}

                            <div className="flex justify-between pt-4 border-t border-border/50">
                                <ProfessionalButton
                                    type="button"
                                    variant="outline"
                                    onClick={onTestEmailConfiguration}
                                    leftIcon={<Activity className="w-4 h-4" />}
                                >
                                    {t('settings.test_configuration')}
                                </ProfessionalButton>
                                <ProfessionalButton
                                    onClick={onSave}
                                    loading={saving}
                                    variant="gradient"
                                >
                                    {t('settings.save_email_settings')}
                                </ProfessionalButton>
                            </div>
                        </>
                    )}
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Notification Settings Section */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="flex items-center gap-2">
                        <Bell className="w-5 h-5 text-primary" />
                        {t('settings.notification_settings_title')}
                    </ProfessionalCardTitle>
                    <p className="text-sm text-muted-foreground">
                        {t('settings.notification_settings_description')}
                    </p>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-8">
                    {loadingNotifications ? (
                        <div className="flex items-center justify-center py-12">
                            <Loader2 className="h-8 w-8 animate-spin text-primary" />
                            <span className="sr-only">{t('settings.loading_notification_settings')}</span>
                        </div>
                    ) : (
                        <>
                            {/* Custom notification email */}
                            <div className="p-6 bg-muted/20 rounded-xl border border-border/50 space-y-4">
                                <ProfessionalInput
                                    id="notification_email"
                                    type="email"
                                    label="Notification Email (Optional)"
                                    value={notificationSettings.notification_email}
                                    onChange={onNotificationEmailChange}
                                    placeholder="Leave empty to use your account email"
                                    helperText="If specified, notifications will be sent to this email instead of your account email"
                                    leftIcon={<Mail className="w-4 h-4 text-muted-foreground" />}
                                />
                            </div>

                            {/* User Operations */}
                            <div className="space-y-4">
                                <h3 className="text-lg font-semibold">User Operations</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>User Created</Label>
                                            <p className="text-sm text-muted-foreground">When a new user is added</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.user_created}
                                            onCheckedChange={(checked) => onNotificationToggle('user_created', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>User Updated</Label>
                                            <p className="text-sm text-muted-foreground">When user info is modified</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.user_updated}
                                            onCheckedChange={(checked) => onNotificationToggle('user_updated', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>User Deleted</Label>
                                            <p className="text-sm text-muted-foreground">When a user is removed</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.user_deleted}
                                            onCheckedChange={(checked) => onNotificationToggle('user_deleted', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>User Login</Label>
                                            <p className="text-sm text-muted-foreground">When a user logs in</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.user_login}
                                            onCheckedChange={(checked) => onNotificationToggle('user_login', checked)}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Client Operations */}
                            <div className="space-y-4">
                                <h3 className="text-lg font-semibold">Client Operations</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Client Created</Label>
                                            <p className="text-sm text-muted-foreground">When a new client is added</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.client_created}
                                            onCheckedChange={(checked) => onNotificationToggle('client_created', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Client Updated</Label>
                                            <p className="text-sm text-muted-foreground">When client info is modified</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.client_updated}
                                            onCheckedChange={(checked) => onNotificationToggle('client_updated', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Client Deleted</Label>
                                            <p className="text-sm text-muted-foreground">When a client is removed</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.client_deleted}
                                            onCheckedChange={(checked) => onNotificationToggle('client_deleted', checked)}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Invoice Operations */}
                            <div className="space-y-4">
                                <h3 className="text-lg font-semibold">Invoice Operations</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Invoice Created</Label>
                                            <p className="text-sm text-muted-foreground">When a new invoice is created</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.invoice_created}
                                            onCheckedChange={(checked) => onNotificationToggle('invoice_created', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Invoice Updated</Label>
                                            <p className="text-sm text-muted-foreground">When invoice is modified</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.invoice_updated}
                                            onCheckedChange={(checked) => onNotificationToggle('invoice_updated', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Invoice Deleted</Label>
                                            <p className="text-sm text-muted-foreground">When an invoice is deleted</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.invoice_deleted}
                                            onCheckedChange={(checked) => onNotificationToggle('invoice_deleted', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Invoice Sent</Label>
                                            <p className="text-sm text-muted-foreground">When invoice is sent to client</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.invoice_sent}
                                            onCheckedChange={(checked) => onNotificationToggle('invoice_sent', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Invoice Paid</Label>
                                            <p className="text-sm text-muted-foreground">When invoice is marked as paid</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.invoice_paid}
                                            onCheckedChange={(checked) => onNotificationToggle('invoice_paid', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Invoice Overdue</Label>
                                            <p className="text-sm text-muted-foreground">When invoice becomes overdue</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.invoice_overdue}
                                            onCheckedChange={(checked) => onNotificationToggle('invoice_overdue', checked)}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Payment Operations */}
                            <div className="space-y-4">
                                <h3 className="text-lg font-semibold">Payment Operations</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Payment Created</Label>
                                            <p className="text-sm text-muted-foreground">When a payment is recorded</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.payment_created}
                                            onCheckedChange={(checked) => onNotificationToggle('payment_created', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Payment Updated</Label>
                                            <p className="text-sm text-muted-foreground">When payment is modified</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.payment_updated}
                                            onCheckedChange={(checked) => onNotificationToggle('payment_updated', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Payment Deleted</Label>
                                            <p className="text-sm text-muted-foreground">When a payment is removed</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.payment_deleted}
                                            onCheckedChange={(checked) => onNotificationToggle('payment_deleted', checked)}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Expense Operations */}
                            <div className="space-y-4">
                                <h3 className="text-lg font-semibold">{t('settings.expense_operations')}</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.expense_created')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.expense_created_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.expense_created}
                                            onCheckedChange={(checked) => onNotificationToggle('expense_created', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.expense_updated')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.expense_updated_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.expense_updated}
                                            onCheckedChange={(checked) => onNotificationToggle('expense_updated', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.expense_deleted')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.expense_deleted_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.expense_deleted}
                                            onCheckedChange={(checked) => onNotificationToggle('expense_deleted', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.expense_approved')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.expense_approved_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.expense_approved}
                                            onCheckedChange={(checked) => onNotificationToggle('expense_approved', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.expense_rejected')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.expense_rejected_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.expense_rejected}
                                            onCheckedChange={(checked) => onNotificationToggle('expense_rejected', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.expense_submitted')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.expense_submitted_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.expense_submitted}
                                            onCheckedChange={(checked) => onNotificationToggle('expense_submitted', checked)}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Inventory Operations */}
                            <div className="space-y-4">
                                <h3 className="text-lg font-semibold">{t('settings.inventory_operations')}</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.inventory_created')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.inventory_created_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.inventory_created}
                                            onCheckedChange={(checked) => onNotificationToggle('inventory_created', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.inventory_updated')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.inventory_updated_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.inventory_updated}
                                            onCheckedChange={(checked) => onNotificationToggle('inventory_updated', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.inventory_deleted')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.inventory_deleted_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.inventory_deleted}
                                            onCheckedChange={(checked) => onNotificationToggle('inventory_deleted', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.inventory_low_stock')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.inventory_low_stock_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.inventory_low_stock}
                                            onCheckedChange={(checked) => onNotificationToggle('inventory_low_stock', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.inventory_out_of_stock')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.inventory_out_of_stock_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.inventory_out_of_stock}
                                            onCheckedChange={(checked) => onNotificationToggle('inventory_out_of_stock', checked)}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Statement Operations */}
                            <div className="space-y-4">
                                <h3 className="text-lg font-semibold">{t('settings.statement_operations')}</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.statement_generated')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.statement_generated_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.statement_generated}
                                            onCheckedChange={(checked) => onNotificationToggle('statement_generated', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.statement_sent')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.statement_sent_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.statement_sent}
                                            onCheckedChange={(checked) => onNotificationToggle('statement_sent', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.statement_overdue')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.statement_overdue_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.statement_overdue}
                                            onCheckedChange={(checked) => onNotificationToggle('statement_overdue', checked)}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Reminder Operations */}
                            <div className="space-y-4">
                                <h3 className="text-lg font-semibold">{t('settings.reminder_operations')}</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.reminder_created')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.reminder_created_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.reminder_created}
                                            onCheckedChange={(checked) => onNotificationToggle('reminder_created', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.reminder_sent')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.reminder_sent_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.reminder_sent}
                                            onCheckedChange={(checked) => onNotificationToggle('reminder_sent', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.reminder_overdue')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.reminder_overdue_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.reminder_overdue}
                                            onCheckedChange={(checked) => onNotificationToggle('reminder_overdue', checked)}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Summary Notifications */}
                            <div className="space-y-4">
                                <h3 className="text-lg font-semibold">Summary Notifications</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.daily_summary')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.daily_summary_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.daily_summary}
                                            onCheckedChange={(checked) => onNotificationToggle('daily_summary', checked)}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>{t('settings.weekly_summary')}</Label>
                                            <p className="text-sm text-muted-foreground">{t('settings.weekly_summary_description')}</p>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.weekly_summary}
                                            onCheckedChange={(checked) => onNotificationToggle('weekly_summary', checked)}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Action buttons */}
                            <div className="flex justify-between pt-6 border-t border-border/50">
                                <ProfessionalButton
                                    type="button"
                                    variant="outline"
                                    onClick={onTestNotification}
                                    leftIcon={<Send className="w-4 h-4" />}
                                >
                                    {t('settings.send_test_notification')}
                                </ProfessionalButton>
                                <ProfessionalButton
                                    onClick={onSaveNotifications}
                                    loading={savingNotifications}
                                    variant="gradient"
                                >
                                    {t('settings.save_notification_settings')}
                                </ProfessionalButton>
                            </div>
                        </>
                    )}
                </ProfessionalCardContent>
            </ProfessionalCard>
        </div>
    );
};

export default NotificationsTab;
