import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Building2, Plus, Loader2 } from "lucide-react";
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
import { settingsApi, CompanyInfo, apiRequest } from "@/lib/api";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

interface CompanyInfoTabProps {
    isAdmin: boolean;
}

export const CompanyInfoTab: React.FC<CompanyInfoTabProps> = ({
    isAdmin,
}) => {
    const { t } = useTranslation();
    const queryClient = useQueryClient();

    const [companyInfo, setCompanyInfo] = useState<CompanyInfo>({
        name: "",
        email: "",
        phone: "",
        address: "",
        tax_id: "",
        logo: "",
    });
    const [timezone, setTimezone] = useState("UTC");
    const [logoFile, setLogoFile] = useState<File | null>(null);
    const [logoPreview, setLogoPreview] = useState<string>("");
    const [uploadingLogo, setUploadingLogo] = useState(false);

    const { data: settings, isLoading } = useQuery({
        queryKey: ['settings'],
        queryFn: () => settingsApi.getSettings(),
        enabled: isAdmin,
    });

    useEffect(() => {
        if (settings) {
            if (settings.company_info) {
                setCompanyInfo(settings.company_info);
            }
            if (settings.timezone) {
                setTimezone(settings.timezone);
            }
        }
    }, [settings]);

    const updateSettingsMutation = useMutation({
        mutationFn: (data: any) => settingsApi.updateSettings(data),
        onSuccess: () => {
            toast.success(t('settings.settings_saved_successfully'));
            queryClient.invalidateQueries({ queryKey: ['settings'] });
            setLogoFile(null);
            setLogoPreview("");
        },
        onError: (error) => {
            console.error("Failed to save company info:", error);
            toast.error(t('settings.failed_to_save_settings'));
        }
    });

    const handleCompanyChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        const { name, value } = e.target;
        if (name === 'email') return; // Email is usually non-editable here
        setCompanyInfo((prev) => ({ ...prev, [name]: value }));
    };

    const handleLogoFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setLogoFile(file);
            const reader = new FileReader();
            reader.onload = (e) => {
                setLogoPreview(e.target?.result as string);
            };
            reader.readAsDataURL(file);
        }
    };

    const uploadLogo = async (): Promise<string | null> => {
        if (!logoFile) return null;

        setUploadingLogo(true);
        try {
            const formData = new FormData();
            formData.append('file', logoFile);

            const result = await apiRequest<{ url: string }>('/settings/upload-logo', {
                method: 'POST',
                body: formData,
            });
            return result.url;
        } catch (error) {
            console.error('Failed to upload logo:', error);
            toast.error(t('settings.failed_to_upload_logo'));
            return null;
        } finally {
            setUploadingLogo(false);
        }
    };

    const handleSave = async () => {
        if (!isAdmin) return;

        try {
            let currentLogo = companyInfo.logo;

            if (logoFile) {
                const uploadedUrl = await uploadLogo();
                if (uploadedUrl) {
                    currentLogo = uploadedUrl;
                }
            }

            updateSettingsMutation.mutate({
                company_info: {
                    ...companyInfo,
                    logo: currentLogo
                },
                timezone: timezone
            });
        } catch (error) {
            console.error("Failed to save company info:", error);
            toast.error(t('settings.failed_to_save_settings'));
        }
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
                        onChange={handleCompanyChange}
                    />
                    <ProfessionalInput
                        label={t('settings.tax_id')}
                        id="tax_id"
                        name="tax_id"
                        value={companyInfo.tax_id}
                        onChange={handleCompanyChange}
                    />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <ProfessionalInput
                        label={t('settings.company_email')}
                        id="email"
                        name="email"
                        type="email"
                        value={companyInfo.email}
                        onChange={handleCompanyChange}
                        disabled
                        helperText={t('settings.email_readonly_hint', 'Company email cannot be changed here.')}
                    />
                    <ProfessionalInput
                        label={t('settings.company_phone')}
                        id="phone"
                        name="phone"
                        value={companyInfo.phone}
                        onChange={handleCompanyChange}
                    />
                </div>

                <ProfessionalTextarea
                    label={t('settings.company_address')}
                    id="address"
                    name="address"
                    rows={3}
                    value={companyInfo.address}
                    onChange={handleCompanyChange}
                />

                <div className="space-y-2">
                    <Label htmlFor="timezone" className="text-sm font-medium">{t('settings.timezone')}</Label>
                    <Select value={timezone} onValueChange={setTimezone}>
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
                                onChange={handleLogoFileChange}
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
                    <ProfessionalButton onClick={handleSave} loading={updateSettingsMutation.isPending} variant="gradient" size="lg">
                        {t('settings.save_changes')}
                    </ProfessionalButton>
                </div>
            </ProfessionalCardContent>
        </ProfessionalCard>
    );
};
