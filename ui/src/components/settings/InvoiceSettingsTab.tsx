import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { FileText, Loader2, Mail, Palette, Link2, Copy } from "lucide-react";
import {
    ProfessionalCard,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
    ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ReminderCadenceEditor } from "@/components/settings/ReminderCadenceEditor";
import { settingsApi, InvoiceSettings, InvoiceBranding } from "@/lib/api";
import { DEFAULT_BRANDING, isHexColor, readableTextColor } from "@/lib/invoice-branding";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

interface InvoiceSettingsTabProps {
    isAdmin: boolean;
}

export const InvoiceSettingsTab: React.FC<InvoiceSettingsTabProps> = ({
    isAdmin,
}) => {
    const { t } = useTranslation();
    const queryClient = useQueryClient();

    // Backend hardcoded English defaults used for detection/placeholders
    const BACKEND_DEFAULT_NOTES = t('settings.thank_you');
    const BACKEND_DEFAULT_TERMS = t('settings.payment_terms_net30');

    const [invoiceSettings, setInvoiceSettings] = useState<InvoiceSettings>({
        prefix: "INV-",
        next_number: "0001",
        terms: BACKEND_DEFAULT_TERMS,
        notes: BACKEND_DEFAULT_NOTES,
        send_copy: true,
        auto_reminders: true,
        thank_you_email: false,
        payment_reminders_enabled: false,
        reminder_cadence: [-7, -1, 3, 7, 14],
    });

    const [branding, setBranding] = useState<InvoiceBranding>(DEFAULT_BRANDING);

    const { data: settings, isLoading } = useQuery({
        queryKey: ['settings'],
        queryFn: () => settingsApi.getSettings(),
        enabled: isAdmin,
    });

    const companyName = settings?.company_info?.name || '';
    const companyLogo = settings?.company_info?.logo || '';

    const { data: portalLink } = useQuery({
        queryKey: ['client-portal-link'],
        queryFn: () => settingsApi.getClientPortalLink(),
        enabled: isAdmin,
    });

    const copyPortalLink = () => {
        if (portalLink?.portal_url) {
            navigator.clipboard.writeText(portalLink.portal_url);
            toast.success(t('settings.client_portal.copied'));
        }
    };

    useEffect(() => {
        if (settings && settings.invoice_settings) {
            setInvoiceSettings({
                ...settings.invoice_settings,
                terms: (settings.invoice_settings.terms && settings.invoice_settings.terms !== BACKEND_DEFAULT_TERMS)
                    ? settings.invoice_settings.terms
                    : BACKEND_DEFAULT_TERMS,
                notes: (settings.invoice_settings.notes && settings.invoice_settings.notes !== BACKEND_DEFAULT_NOTES)
                    ? settings.invoice_settings.notes
                    : BACKEND_DEFAULT_NOTES,
            });
        }
        if (settings && settings.invoice_branding) {
            setBranding({ ...DEFAULT_BRANDING, ...settings.invoice_branding });
        }
    }, [settings]);

    const updateSettingsMutation = useMutation({
        mutationFn: (data: any) => settingsApi.updateSettings(data),
        onSuccess: () => {
            toast.success(t('settings.settings_saved_successfully'));
            queryClient.invalidateQueries({ queryKey: ['settings'] });
        },
        onError: (error) => {
            console.error("Failed to save invoice settings:", error);
            toast.error(t('settings.failed_to_save_settings'));
        }
    });

    const handleInvoiceChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        const { name, value } = e.target;
        setInvoiceSettings((prev) => ({ ...prev, [name]: value }));
    };

    const handleSave = async () => {
        if (!isAdmin) return;

        if (!isHexColor(branding.brand_color) || !isHexColor(branding.accent_color)) {
            toast.error(t('settings.branding.invalid_color'));
            return;
        }

        updateSettingsMutation.mutate({
            invoice_settings: invoiceSettings,
            invoice_branding: branding,
        });
    };

    const setBrandColor = (key: 'brand_color' | 'accent_color', value: string) => {
        const next = value.startsWith('#') ? value : `#${value}`;
        setBranding((prev) => ({ ...prev, [key]: next }));
    };

    if (isLoading) {
        return (
            <div className="flex justify-center py-12">
                <Loader2 className="h-10 w-10 animate-spin text-primary" />
            </div>
        );
    }


    return (
        <div className="space-y-6">
            {/* Numbering Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <FileText className="w-4 h-4 text-primary" />
                        {t('settings.invoice_numbering')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <ProfessionalInput
                            label={t('settings.invoice_prefix')}
                            id="prefix"
                            name="prefix"
                            value={invoiceSettings.prefix}
                            onChange={handleInvoiceChange}
                        />
                        <ProfessionalInput
                            label={t('settings.next_invoice_number')}
                            id="next_number"
                            name="next_number"
                            type="number"
                            value={invoiceSettings.next_number}
                            onChange={handleInvoiceChange}
                        />
                    </div>
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Default Content Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <FileText className="w-4 h-4 text-primary" />
                        {t('settings.default_content')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-6">
                    <ProfessionalTextarea
                        label={t('settings.default_notes')}
                        id="default_notes"
                        name="notes"
                        rows={4}
                        value={invoiceSettings.notes || ''}
                        onChange={handleInvoiceChange}
                        placeholder={BACKEND_DEFAULT_NOTES}
                    />
                    <ProfessionalTextarea
                        label={t('settings.default_footer')}
                        id="default_footer"
                        name="terms"
                        rows={4}
                        value={invoiceSettings.terms}
                        onChange={handleInvoiceChange}
                        placeholder={BACKEND_DEFAULT_TERMS}
                    />
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Automation Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <Mail className="w-4 h-4 text-primary" />
                        {t('settings.invoice_automation')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent>
                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="space-y-0.5 pr-4">
                            <Label htmlFor="thank_you_email" className="text-base font-semibold">
                                {t('settings.thank_you_email')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {t('settings.thank_you_email_description')}
                            </p>
                        </div>
                        <Switch
                            id="thank_you_email"
                            checked={!!invoiceSettings.thank_you_email}
                            onCheckedChange={(checked) =>
                                setInvoiceSettings((prev) => ({ ...prev, thank_you_email: checked }))
                            }
                        />
                    </div>

                    <div className="p-4 bg-muted/30 rounded-xl space-y-4 mt-3">
                        <div className="flex items-center justify-between">
                            <div className="space-y-0.5 pr-4">
                                <Label htmlFor="payment_reminders_enabled" className="text-base font-semibold">
                                    {t('settings.payment_reminders')}
                                </Label>
                                <p className="text-sm text-muted-foreground">
                                    {t('settings.payment_reminders_description')}
                                </p>
                            </div>
                            <Switch
                                id="payment_reminders_enabled"
                                checked={!!invoiceSettings.payment_reminders_enabled}
                                onCheckedChange={(checked) =>
                                    setInvoiceSettings((prev) => ({ ...prev, payment_reminders_enabled: checked }))
                                }
                            />
                        </div>

                        {invoiceSettings.payment_reminders_enabled && (
                            <div className="pt-2 border-t">
                                <p className="text-sm font-medium mb-2">
                                    {t('settings.reminder_schedule')}
                                </p>
                                <ReminderCadenceEditor
                                    value={invoiceSettings.reminder_cadence ?? []}
                                    onChange={(next) =>
                                        setInvoiceSettings((prev) => ({ ...prev, reminder_cadence: next }))
                                    }
                                />
                            </div>
                        )}
                    </div>
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Branding Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <Palette className="w-4 h-4 text-primary" />
                        {t('settings.branding.title')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-6">
                    <p className="text-sm text-muted-foreground">
                        {t('settings.branding.description')}
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <Label htmlFor="brand_color">{t('settings.branding.brand_color')}</Label>
                            <div className="flex items-center gap-3">
                                <input
                                    type="color"
                                    aria-label={t('settings.branding.brand_color')}
                                    value={isHexColor(branding.brand_color) ? branding.brand_color : '#1e3a8a'}
                                    onChange={(e) => setBrandColor('brand_color', e.target.value)}
                                    className="h-10 w-14 cursor-pointer rounded-md border border-input bg-background p-1"
                                />
                                <ProfessionalInput
                                    id="brand_color"
                                    value={branding.brand_color}
                                    onChange={(e) => setBrandColor('brand_color', e.target.value)}
                                    className="font-mono"
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="accent_color">{t('settings.branding.accent_color')}</Label>
                            <div className="flex items-center gap-3">
                                <input
                                    type="color"
                                    aria-label={t('settings.branding.accent_color')}
                                    value={isHexColor(branding.accent_color) ? branding.accent_color : '#3b82f6'}
                                    onChange={(e) => setBrandColor('accent_color', e.target.value)}
                                    className="h-10 w-14 cursor-pointer rounded-md border border-input bg-background p-1"
                                />
                                <ProfessionalInput
                                    id="accent_color"
                                    value={branding.accent_color}
                                    onChange={(e) => setBrandColor('accent_color', e.target.value)}
                                    className="font-mono"
                                />
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="space-y-0.5 pr-4">
                            <Label htmlFor="show_logo" className="text-base font-semibold">
                                {t('settings.branding.show_logo')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {companyLogo
                                    ? t('settings.branding.show_logo_description')
                                    : t('settings.branding.no_logo_hint')}
                            </p>
                        </div>
                        <Switch
                            id="show_logo"
                            checked={!!branding.show_logo}
                            onCheckedChange={(checked) => setBranding((prev) => ({ ...prev, show_logo: checked }))}
                        />
                    </div>

                    <ProfessionalTextarea
                        label={t('settings.branding.footer_text')}
                        id="branding_footer"
                        name="branding_footer"
                        rows={2}
                        maxLength={500}
                        value={branding.footer_text || ''}
                        onChange={(e) => setBranding((prev) => ({ ...prev, footer_text: e.target.value }))}
                        placeholder={t('settings.branding.footer_placeholder')}
                    />

                    {/* Live preview */}
                    <div>
                        <p className="text-sm font-medium mb-2">{t('settings.branding.preview')}</p>
                        <div className="rounded-xl border overflow-hidden bg-white text-gray-900 shadow-sm">
                            <div
                                className="flex items-center justify-between gap-4 px-5 py-4"
                                style={{
                                    backgroundColor: isHexColor(branding.brand_color) ? branding.brand_color : '#1e3a8a',
                                    color: readableTextColor(branding.brand_color),
                                }}
                            >
                                <div className="flex items-center gap-3 min-w-0">
                                    {branding.show_logo && companyLogo && (
                                        <img src={companyLogo} alt="" className="h-8 w-8 rounded bg-white/90 object-contain p-0.5" />
                                    )}
                                    <span className="font-semibold truncate">{companyName || t('settings.branding.your_company')}</span>
                                </div>
                                <div className="text-right">
                                    <div className="text-xs uppercase tracking-wide opacity-80">{t('settings.branding.invoice_label')}</div>
                                    <div className="font-mono font-semibold">INV-0001</div>
                                </div>
                            </div>
                            <div className="px-5 py-4 space-y-3">
                                <div className="h-1 w-16 rounded" style={{ backgroundColor: isHexColor(branding.accent_color) ? branding.accent_color : '#3b82f6' }} />
                                <div className="flex justify-between text-sm">
                                    <span className="text-gray-500">{t('settings.branding.sample_item')}</span>
                                    <span className="font-medium">$1,200.00</span>
                                </div>
                                <div className="flex justify-between text-base font-bold" style={{ color: isHexColor(branding.brand_color) ? branding.brand_color : '#1e3a8a' }}>
                                    <span>{t('settings.branding.sample_total')}</span>
                                    <span>$1,200.00</span>
                                </div>
                                {branding.footer_text && (
                                    <p className="pt-2 border-t text-xs text-gray-500">{branding.footer_text}</p>
                                )}
                            </div>
                        </div>
                    </div>
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Client Portal Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <Link2 className="w-4 h-4 text-primary" />
                        {t('settings.client_portal.title')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-3">
                    <p className="text-sm text-muted-foreground">
                        {t('settings.client_portal.description')}
                    </p>
                    {portalLink?.enabled && portalLink.portal_url ? (
                        <div className="flex items-center gap-2">
                            <input
                                readOnly
                                value={portalLink.portal_url}
                                onFocus={(e) => e.currentTarget.select()}
                                className="flex-1 rounded-lg border border-input bg-muted/30 px-3 py-2 text-sm font-mono"
                            />
                            <ProfessionalButton variant="outline" size="sm" onClick={copyPortalLink}>
                                <Copy className="h-4 w-4" />
                                {t('settings.client_portal.copy')}
                            </ProfessionalButton>
                        </div>
                    ) : (
                        <p className="text-sm text-amber-600 dark:text-amber-500">
                            {t('settings.client_portal.requires_license')}
                        </p>
                    )}
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Save */}
            <div className="flex justify-end">
                <ProfessionalButton onClick={handleSave} loading={updateSettingsMutation.isPending} variant="gradient" size="lg">
                    {t('settings.save_changes')}
                </ProfessionalButton>
            </div>
        </div>
    );
};
