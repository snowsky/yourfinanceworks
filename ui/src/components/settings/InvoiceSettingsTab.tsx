import React from "react";
import { useTranslation } from "react-i18next";
import { FileText, Percent } from "lucide-react";
import {
    ProfessionalCard,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
    ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";

interface InvoiceSettings {
    prefix: string;
    next_number: string;
    terms: string;
    notes: string;
    send_copy?: boolean;
    auto_reminders?: boolean;
    default_tax_rate?: number;
}

interface InvoiceSettingsTabProps {
    invoiceSettings: InvoiceSettings;
    saving: boolean;
    backendDefaultNotes: string;
    backendDefaultTerms: string;
    onInvoiceChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
    onSave: () => void;
}

export const InvoiceSettingsTab: React.FC<InvoiceSettingsTabProps> = ({
    invoiceSettings,
    saving,
    backendDefaultNotes,
    backendDefaultTerms,
    onInvoiceChange,
    onSave,
}) => {
    const { t } = useTranslation();

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
                        onChange={onInvoiceChange}
                    />
                    <ProfessionalInput
                        label={t('settings.next_invoice_number')}
                        id="next_number"
                        name="next_number"
                        type="number"
                        value={invoiceSettings.next_number}
                        onChange={onInvoiceChange}
                    />
                </div>

                <ProfessionalTextarea
                    label={t('settings.default_notes')}
                    id="default_notes"
                    name="notes"
                    rows={4}
                    value={invoiceSettings.notes}
                    onChange={onInvoiceChange}
                    placeholder={backendDefaultNotes}
                />

                <ProfessionalTextarea
                    label={t('settings.default_footer')}
                    id="default_footer"
                    name="terms"
                    rows={4}
                    value={invoiceSettings.terms}
                    onChange={onInvoiceChange}
                    placeholder={backendDefaultTerms}
                />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <ProfessionalInput
                        label={t('settings.default_tax_rate')}
                        id="default_tax_rate"
                        name="default_tax_rate"
                        type="number"
                        step="0.01"
                        value={invoiceSettings.default_tax_rate}
                        onChange={onInvoiceChange}
                        rightIcon={<Percent className="w-4 h-4" />}
                    />
                </div>

                <div className="flex justify-end pt-4">
                    <ProfessionalButton onClick={onSave} loading={saving} variant="gradient" size="lg">
                        {t('settings.save_changes')}
                    </ProfessionalButton>
                </div>
            </ProfessionalCardContent>
        </ProfessionalCard>
    );
};
