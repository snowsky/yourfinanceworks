import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { FileText, Percent, Loader2 } from "lucide-react";
import {
    ProfessionalCard,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
    ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";
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
        <ProfessionalCard variant="elevated">
            <ProfessionalCardHeader>
                <ProfessionalCardTitle className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-primary" />
                    {t('settings.invoice_settings')}
                </ProfessionalCardTitle>
            </ProfessionalCardHeader>
            <ProfessionalCardContent className="space-y-6">
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

                {/* Optional settings like tax rate could be added here if defined in InvoiceSettings */}
                {/* 
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <ProfessionalInput
                        label={t('settings.default_tax_rate')}
                        id="default_tax_rate"
                        name="default_tax_rate"
                        type="number"
                        step="0.01"
                        value={invoiceSettings.default_tax_rate}
                        onChange={handleInvoiceChange}
                        rightIcon={<Percent className="w-4 h-4" />}
                    />
                </div>
                */}

                <div className="flex justify-end pt-4">
                    <ProfessionalButton onClick={handleSave} loading={updateSettingsMutation.isPending} variant="gradient" size="lg">
                        {t('settings.save_changes')}
                    </ProfessionalButton>
                </div>
            </ProfessionalCardContent>
        </ProfessionalCard>
    );
};
