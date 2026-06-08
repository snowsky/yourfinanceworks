import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { FileText, Loader2, Mail } from "lucide-react";
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
import { settingsApi, InvoiceSettings } from "@/lib/api";
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

    const { data: settings, isLoading } = useQuery({
        queryKey: ['settings'],
        queryFn: () => settingsApi.getSettings(),
        enabled: isAdmin,
    });

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

        updateSettingsMutation.mutate({
            invoice_settings: invoiceSettings
        });
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
                        {t('settings.invoice_numbering', 'Numbering')}
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
                        {t('settings.default_content', 'Default Content')}
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
                        {t('settings.invoice_automation', 'Automation')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent>
                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="space-y-0.5 pr-4">
                            <Label htmlFor="thank_you_email" className="text-base font-semibold">
                                {t('settings.thank_you_email', 'Thank-you email on payment')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {t('settings.thank_you_email_description', 'Automatically email the client a thank-you when their invoice is paid in full. Requires email to be configured.')}
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
                                    {t('settings.payment_reminders', 'Payment reminders')}
                                </Label>
                                <p className="text-sm text-muted-foreground">
                                    {t('settings.payment_reminders_description', 'Automatically email clients about unpaid invoices on the schedule below. Requires email to be configured.')}
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
                                    {t('settings.reminder_schedule', 'Reminder schedule')}
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

            {/* Save */}
            <div className="flex justify-end">
                <ProfessionalButton onClick={handleSave} loading={updateSettingsMutation.isPending} variant="gradient" size="lg">
                    {t('settings.save_changes')}
                </ProfessionalButton>
            </div>
        </div>
    );
};
