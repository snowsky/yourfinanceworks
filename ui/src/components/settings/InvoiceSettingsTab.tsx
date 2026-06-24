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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ReminderCadenceEditor } from "@/components/settings/ReminderCadenceEditor";
import { settingsApi, InvoiceSettings, InvoiceBranding } from "@/lib/api";
import { DEFAULT_BRANDING, isHexColor, FONT_OPTIONS, LOGO_PLACEMENTS, LOGO_SIZES } from "@/lib/invoice-branding";
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
        thank_you_email: true,
        payment_reminders_enabled: false,
        reminder_cadence: [-7, -1, 3, 7, 14],
        require_approval_before_send: false,
        approval_threshold_amount: 0,
    });

    const [branding, setBranding] = useState<InvoiceBranding>(DEFAULT_BRANDING);

    const [previewHtml, setPreviewHtml] = useState<string>("");

    useEffect(() => {
        if (!isAdmin) return;
        const handle = setTimeout(() => {
            settingsApi
                .previewInvoiceTemplate(branding)
                .then(setPreviewHtml)
                .catch(() => { /* keep last good preview */ });
        }, 300);
        return () => clearTimeout(handle);
    }, [branding, isAdmin]);

    const { data: settings, isLoading } = useQuery({
        queryKey: ['settings'],
        queryFn: () => settingsApi.getSettings(),
        enabled: isAdmin,
    });

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

                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl mt-3">
                        <div className="space-y-0.5 pr-4">
                            <Label htmlFor="require_approval_before_send" className="text-base font-semibold">
                                {t('settings.require_approval_before_send')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {t('settings.require_approval_before_send_description')}
                            </p>
                        </div>
                        <Switch
                            id="require_approval_before_send"
                            checked={!!invoiceSettings.require_approval_before_send}
                            onCheckedChange={(checked) =>
                                setInvoiceSettings((prev) => ({ ...prev, require_approval_before_send: checked }))
                            }
                        />
                    </div>
                    {invoiceSettings.require_approval_before_send && (
                        <div className="pt-2 border-t">
                            <Label htmlFor="approval_threshold_amount" className="text-sm font-medium">
                                {t('settings.approval_threshold_amount')}
                            </Label>
                            <p className="text-sm text-muted-foreground mb-2">
                                {t('settings.approval_threshold_amount_description')}
                            </p>
                            <Input
                                id="approval_threshold_amount"
                                type="number"
                                min={0}
                                className="w-40"
                                value={invoiceSettings.approval_threshold_amount ?? 0}
                                onChange={(e) =>
                                    setInvoiceSettings((prev) => ({
                                        ...prev,
                                        approval_threshold_amount: Math.max(0, Number(e.target.value) || 0),
                                    }))
                                }
                            />
                        </div>
                    )}
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Branding / Template Editor Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <Palette className="w-4 h-4 text-primary" />
                        {t('settings.branding.title')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent>
                    <p className="text-sm text-muted-foreground mb-4">
                        {t('settings.branding.description')}
                    </p>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Left: controls */}
                        <div className="space-y-6">
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

                            {/* Font */}
                            <div className="space-y-2">
                                <Label htmlFor="font_family">{t('settings.branding.font')}</Label>
                                <div className="flex gap-2" role="group" aria-label={t('settings.branding.font')}>
                                    {FONT_OPTIONS.map((font) => (
                                        <button
                                            key={font}
                                            type="button"
                                            onClick={() => setBranding((prev) => ({ ...prev, font_family: font }))}
                                            className={`px-3 py-1.5 rounded-lg border text-sm capitalize ${branding.font_family === font ? 'border-primary bg-primary/10 font-semibold' : 'border-input'}`}
                                        >
                                            {t(`settings.branding.font_${font}`)}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Logo */}
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
                            {branding.show_logo && (
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>{t('settings.branding.logo_placement')}</Label>
                                        <div className="flex gap-2" role="group" aria-label={t('settings.branding.logo_placement')}>
                                            {LOGO_PLACEMENTS.map((p) => (
                                                <button
                                                    key={p}
                                                    type="button"
                                                    onClick={() => setBranding((prev) => ({ ...prev, logo_placement: p }))}
                                                    className={`px-3 py-1.5 rounded-lg border text-sm capitalize ${branding.logo_placement === p ? 'border-primary bg-primary/10 font-semibold' : 'border-input'}`}
                                                >
                                                    {t(`settings.branding.placement_${p}`)}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>{t('settings.branding.logo_size')}</Label>
                                        <div className="flex gap-2" role="group" aria-label={t('settings.branding.logo_size')}>
                                            {LOGO_SIZES.map((s) => (
                                                <button
                                                    key={s}
                                                    type="button"
                                                    onClick={() => setBranding((prev) => ({ ...prev, logo_size: s }))}
                                                    className={`px-3 py-1.5 rounded-lg border text-sm capitalize ${branding.logo_size === s ? 'border-primary bg-primary/10 font-semibold' : 'border-input'}`}
                                                >
                                                    {t(`settings.branding.size_${s}`)}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Section visibility */}
                            <div className="p-4 bg-muted/30 rounded-xl space-y-3">
                                <p className="text-sm font-semibold">{t('settings.branding.sections')}</p>
                                {([
                                    ['show_custom_fields', 'settings.branding.section_custom_fields'],
                                    ['show_notes', 'settings.branding.section_notes'],
                                    ['show_footer', 'settings.branding.section_footer'],
                                ] as const).map(([key, label]) => (
                                    <div key={key} className="flex items-center justify-between">
                                        <Label htmlFor={key}>{t(label)}</Label>
                                        <Switch
                                            id={key}
                                            checked={!!branding[key]}
                                            onCheckedChange={(checked) => setBranding((prev) => ({ ...prev, [key]: checked }))}
                                        />
                                    </div>
                                ))}
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
                        </div>

                        {/* Right: live preview */}
                        <div className="space-y-2">
                            <p className="text-sm font-medium">{t('settings.branding.preview')}</p>
                            <iframe
                                title="invoice-template-preview"
                                sandbox=""
                                srcDoc={previewHtml}
                                className="w-full h-[640px] rounded-xl border bg-white"
                            />
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
                        <p className="text-sm text-warning">
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
