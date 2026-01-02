import React from "react";
import { useTranslation } from "react-i18next";
import { Building2, Key, ShieldCheck } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
    ProfessionalCard,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
    ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalInput } from "@/components/ui/professional-input";

interface UserProfile {
    first_name?: string;
    last_name?: string;
    show_analytics?: boolean;
}

interface PasswordData {
    current_password: string;
    new_password: string;
    confirm_password: string;
}

interface UserProfileTabProps {
    userProfile: UserProfile;
    passwordData: PasswordData;
    showPasswordChange: boolean;
    profileSaving: boolean;
    passwordChanging: boolean;
    onProfileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onPasswordChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onTogglePasswordChange: (show: boolean) => void;
    onProfileSave: () => Promise<void>;
    onChangePassword: () => Promise<void>;
    onShowAnalyticsChange: (checked: boolean) => void;
}

export const UserProfileTab: React.FC<UserProfileTabProps> = ({
    userProfile,
    passwordData,
    showPasswordChange,
    profileSaving,
    passwordChanging,
    onProfileChange,
    onPasswordChange,
    onTogglePasswordChange,
    onProfileSave,
    onChangePassword,
    onShowAnalyticsChange,
}) => {
    const { t } = useTranslation();

    return (
        <ProfessionalCard variant="elevated">
            <ProfessionalCardHeader>
                <ProfessionalCardTitle className="flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-primary" />
                    {t('settings.user_profile')}
                </ProfessionalCardTitle>
            </ProfessionalCardHeader>
            <ProfessionalCardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <ProfessionalInput
                        label={t('settings.first_name')}
                        id="first_name"
                        name="first_name"
                        value={userProfile.first_name || ''}
                        onChange={onProfileChange}
                        autoComplete="given-name"
                    />
                    <ProfessionalInput
                        label={t('settings.last_name')}
                        id="last_name"
                        name="last_name"
                        value={userProfile.last_name || ''}
                        onChange={onProfileChange}
                        autoComplete="family-name"
                    />
                </div>
                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                    <div className="space-y-0.5">
                        <Label htmlFor="show_analytics" className="text-base font-semibold">{t('settings.show_analytics_menu')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.show_analytics_menu_description')}</p>
                    </div>
                    <Switch
                        id="show_analytics"
                        checked={userProfile.show_analytics ?? true}
                        onCheckedChange={onShowAnalyticsChange}
                    />
                </div>
                <div className="flex justify-end pt-4 gap-3">
                    <ProfessionalButton
                        variant="outline"
                        onClick={() => onTogglePasswordChange(!showPasswordChange)}
                        leftIcon={<Key className="w-4 h-4" />}
                    >
                        {showPasswordChange ? t('settings.cancel') : t('settings.change_password')}
                    </ProfessionalButton>
                    <ProfessionalButton
                        onClick={onProfileSave}
                        loading={profileSaving}
                        variant="gradient"
                    >
                        {t('settings.save_profile')}
                    </ProfessionalButton>
                </div>

                {/* Password Change Section */}
                {showPasswordChange && (
                    <div className="mt-8 pt-8 border-t border-border/50 animate-fade-in-up">
                        <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
                            <ShieldCheck className="w-5 h-5 text-primary" />
                            {t('settings.change_password')}
                        </h3>
                        <div className="space-y-6">
                            <ProfessionalInput
                                label={t('settings.current_password')}
                                id="current_password"
                                name="current_password"
                                type="password"
                                value={passwordData.current_password}
                                onChange={onPasswordChange}
                                placeholder={t('settings.current_password')}
                            />
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <ProfessionalInput
                                    label={t('settings.new_password')}
                                    id="new_password"
                                    name="new_password"
                                    type="password"
                                    value={passwordData.new_password}
                                    onChange={onPasswordChange}
                                    placeholder={t('auth.password_min_length')}
                                />
                                <ProfessionalInput
                                    label={t('settings.confirm_password')}
                                    id="confirm_password"
                                    name="confirm_password"
                                    type="password"
                                    value={passwordData.confirm_password}
                                    onChange={onPasswordChange}
                                    placeholder={t('settings.confirm_password')}
                                />
                            </div>
                            <div className="flex justify-end gap-3 pt-2">
                                <ProfessionalButton
                                    variant="ghost"
                                    onClick={() => {
                                        onTogglePasswordChange(false);
                                    }}
                                >
                                    {t('settings.cancel')}
                                </ProfessionalButton>
                                <ProfessionalButton
                                    onClick={onChangePassword}
                                    loading={passwordChanging}
                                    variant="default"
                                >
                                    {t('settings.change_password')}
                                </ProfessionalButton>
                            </div>
                        </div>
                    </div>
                )}
            </ProfessionalCardContent>
        </ProfessionalCard>
    );
};
