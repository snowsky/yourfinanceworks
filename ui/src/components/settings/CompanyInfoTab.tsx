import React from "react";
import { useTranslation } from "react-i18next";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Building2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    ProfessionalCard,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
    ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";

interface CompanyInfo {
    name: string;
    email: string;
    phone: string;
    address: string;
    tax_id: string;
    logo: string;
}

interface CompanyInfoTabProps {
    companyInfo: CompanyInfo;
    timezone: string;
    logoFile: File | null;
    logoPreview: string;
    uploadingLogo: boolean;
    saving: boolean;
    onCompanyChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
    onTimezoneChange: (timezone: string) => void;
    onLogoFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onSave: () => void;
}

export const CompanyInfoTab: React.FC<CompanyInfoTabProps> = ({
    companyInfo,
    timezone,
    logoFile,
    logoPreview,
    uploadingLogo,
    saving,
    onCompanyChange,
    onTimezoneChange,
    onLogoFileChange,
    onSave,
}) => {
    const { t } = useTranslation();

    return (
        <ProfessionalCard variant="elevated">
            <ProfessionalCardHeader>
                <ProfessionalCardTitle className="flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-primary" />
                    {t('settings.company_info')}
                </ProfessionalCardTitle>
            </ProfessionalCardHeader>
            <ProfessionalCardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <ProfessionalInput
                        label={t('settings.company_name')}
                        id="name"
                        name="name"
                        value={companyInfo.name}
                        onChange={onCompanyChange}
                    />
                    <ProfessionalInput
                        label={t('settings.tax_id')}
                        id="tax_id"
                        name="tax_id"
                        value={companyInfo.tax_id}
                        onChange={onCompanyChange}
                    />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <ProfessionalInput
                        label={t('settings.company_email')}
                        id="email"
                        name="email"
                        type="email"
                        value={companyInfo.email}
                        onChange={onCompanyChange}
                        disabled
                        helperText="Company email cannot be changed here."
                    />
                    <ProfessionalInput
                        label={t('settings.company_phone')}
                        id="phone"
                        name="phone"
                        value={companyInfo.phone}
                        onChange={onCompanyChange}
                    />
                </div>

                <ProfessionalTextarea
                    label={t('settings.company_address')}
                    id="address"
                    name="address"
                    rows={3}
                    value={companyInfo.address}
                    onChange={onCompanyChange}
                />

                <div className="space-y-2">
                    <Label htmlFor="timezone" className="text-sm font-medium">{t('settings.timezone')}</Label>
                    <Select value={timezone} onValueChange={onTimezoneChange}>
                        <SelectTrigger id="timezone" className="rounded-lg">
                            <SelectValue placeholder="Select timezone" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="UTC">UTC (Coordinated Universal Time)</SelectItem>
                            <SelectItem value="America/New_York">Eastern Time (US & Canada)</SelectItem>
                            <SelectItem value="America/Chicago">Central Time (US & Canada)</SelectItem>
                            <SelectItem value="America/Denver">Mountain Time (US & Canada)</SelectItem>
                            <SelectItem value="America/Los_Angeles">Pacific Time (US & Canada)</SelectItem>
                            <SelectItem value="America/Phoenix">Arizona</SelectItem>
                            <SelectItem value="America/Anchorage">Alaska</SelectItem>
                            <SelectItem value="Pacific/Honolulu">Hawaii</SelectItem>
                            <SelectItem value="Europe/London">London</SelectItem>
                            <SelectItem value="Europe/Paris">Paris</SelectItem>
                            <SelectItem value="Europe/Berlin">Berlin</SelectItem>
                            <SelectItem value="Europe/Rome">Rome</SelectItem>
                            <SelectItem value="Europe/Madrid">Madrid</SelectItem>
                            <SelectItem value="Europe/Amsterdam">Amsterdam</SelectItem>
                            <SelectItem value="Europe/Stockholm">Stockholm</SelectItem>
                            <SelectItem value="Europe/Zurich">Zurich</SelectItem>
                            <SelectItem value="Asia/Tokyo">Tokyo</SelectItem>
                            <SelectItem value="Asia/Shanghai">Shanghai</SelectItem>
                            <SelectItem value="Asia/Hong_Kong">Hong Kong</SelectItem>
                            <SelectItem value="Asia/Singapore">Singapore</SelectItem>
                            <SelectItem value="Asia/Dubai">Dubai</SelectItem>
                            <SelectItem value="Asia/Kolkata">Mumbai, Kolkata, New Delhi</SelectItem>
                            <SelectItem value="Asia/Bangkok">Bangkok</SelectItem>
                            <SelectItem value="Australia/Sydney">Sydney</SelectItem>
                            <SelectItem value="Australia/Melbourne">Melbourne</SelectItem>
                            <SelectItem value="Australia/Brisbane">Brisbane</SelectItem>
                            <SelectItem value="Australia/Perth">Perth</SelectItem>
                            <SelectItem value="Pacific/Auckland">Auckland</SelectItem>
                            <SelectItem value="America/Toronto">Toronto</SelectItem>
                            <SelectItem value="America/Vancouver">Vancouver</SelectItem>
                            <SelectItem value="America/Mexico_City">Mexico City</SelectItem>
                            <SelectItem value="America/Sao_Paulo">Sao Paulo</SelectItem>
                            <SelectItem value="America/Buenos_Aires">Buenos Aires</SelectItem>
                            <SelectItem value="Africa/Johannesburg">Johannesburg</SelectItem>
                            <SelectItem value="Africa/Cairo">Cairo</SelectItem>
                        </SelectContent>
                    </Select>
                    <p className="text-sm text-muted-foreground">{t('settings.organization_timezone')}</p>
                </div>

                <div className="space-y-4 pt-2">
                    <Label className="text-sm font-medium">{t('settings.company_logo')}</Label>
                    <div className="flex flex-col sm:flex-row gap-6 items-start sm:items-center p-4 bg-muted/30 rounded-xl border border-border/50">
                        <div className="relative group">
                            <div className="w-24 h-24 rounded-xl overflow-hidden bg-background border-2 border-dashed border-border group-hover:border-primary transition-colors flex items-center justify-center">
                                {(logoPreview || companyInfo.logo) ? (
                                    <img
                                        src={logoPreview || `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${companyInfo.logo}`}
                                        alt="Company Logo"
                                        className="w-full h-full object-contain"
                                        onError={(e) => {
                                            e.currentTarget.style.display = 'none';
                                        }}
                                    />
                                ) : (
                                    <Building2 className="w-8 h-8 text-muted-foreground" />
                                )}
                            </div>
                            <input
                                id="logo-upload"
                                name="logo"
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={onLogoFileChange}
                                disabled={uploadingLogo}
                            />
                            <Button
                                type="button"
                                variant="secondary"
                                size="icon"
                                className="absolute -bottom-2 -right-2 rounded-full shadow-lg"
                                onClick={() => document.getElementById('logo-upload')?.click()}
                                disabled={uploadingLogo}
                            >
                                <Plus className="w-4 h-4" />
                            </Button>
                        </div>
                        <div className="space-y-1">
                            <p className="text-sm font-semibold">{t('settings.logo_preview')}</p>
                            <p className="text-xs text-muted-foreground max-w-[200px]">{t('settings.recommended_size')}</p>
                            <p className="text-xs font-medium text-primary mt-1">
                                {logoFile ? logoFile.name : t('settings.no_file_selected')}
                            </p>
                        </div>
                    </div>
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
