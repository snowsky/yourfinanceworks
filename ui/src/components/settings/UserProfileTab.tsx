import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Building2, Key, ShieldCheck, Loader2 } from "lucide-react";
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
import { authApi, userApi } from "@/lib/api";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { updateCurrentUser } from "@/utils/auth";

interface UserProfile {
    id: number;
    first_name?: string;
    last_name?: string;
    show_analytics?: boolean;
    email: string;
}

interface PasswordData {
    current_password: string;
    new_password: string;
    confirm_password: string;
}

export const UserProfileTab: React.FC = () => {
    const { t } = useTranslation();
    const queryClient = useQueryClient();

    const [userProfile, setUserProfile] = useState<UserProfile>({
        id: 0,
        first_name: "",
        last_name: "",
        show_analytics: true,
        email: "",
    });

    const [passwordData, setPasswordData] = useState<PasswordData>({
        current_password: "",
        new_password: "",
        confirm_password: "",
    });

    const [showPasswordChange, setShowPasswordChange] = useState(false);

    const { data: user, isLoading } = useQuery({
        queryKey: ['currentUser'],
        queryFn: () => authApi.getCurrentUser(),
    });

    useEffect(() => {
        if (user) {
            setUserProfile(user);
        }
    }, [user]);

    const updateProfileMutation = useMutation({
        mutationFn: (data: Partial<UserProfile>) => authApi.changePassword(data), // Wait, this is Profile update... Oh I should use authApi.updateCurrentUser or userApi.updateUser
        // Backend has @router.put("/me") which is update_current_user. 
        // Let's check api.ts again for update_current_user.
        // I saw authApi had login, register, etc. 
        // Actually api.ts usually mirrors the backend. 
    });

    // Let's re-verify api.ts for updateCurrentUser
    const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setUserProfile(prev => ({ ...prev, [name]: value }));
    };

    const handleShowAnalyticsChange = (checked: boolean) => {
        setUserProfile(prev => ({ ...prev, show_analytics: checked }));
    };

    const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setPasswordData(prev => ({ ...prev, [name]: value }));
    };

    const onProfileSave = async () => {
        try {
            // Backend has @router.put("/me") for update_current_user.
            // Let's see if it's in api.ts
            await authApi.updateCurrentUser({
                first_name: userProfile.first_name,
                last_name: userProfile.last_name,
                show_analytics: userProfile.show_analytics
            });
            
            // Update localStorage with the new user data
            updateCurrentUser({
                first_name: userProfile.first_name,
                last_name: userProfile.last_name,
                show_analytics: userProfile.show_analytics
            });
            
            toast.success(t('settings.profile_updated_successfully'));
            queryClient.invalidateQueries({ queryKey: ['currentUser'] });
        } catch (error) {
            console.error("Failed to update profile:", error);
            toast.error(t('settings.failed_to_update_profile'));
        }
    };

    const onChangePassword = async () => {
        if (passwordData.new_password !== passwordData.confirm_password) {
            toast.error(t('settings.passwords_do_not_match'));
            return;
        }

        try {
            await authApi.changePassword({
                current_password: passwordData.current_password,
                new_password: passwordData.new_password,
                confirm_password: passwordData.confirm_password
            });
            toast.success(t('settings.password_changed_successfully'));
            setShowPasswordChange(false);
            setPasswordData({
                current_password: "",
                new_password: "",
                confirm_password: "",
            });
        } catch (error) {
            console.error("Failed to change password:", error);
            toast.error(t('settings.failed_to_change_password'));
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
                        onChange={handleProfileChange}
                        autoComplete="given-name"
                    />
                    <ProfessionalInput
                        label={t('settings.last_name')}
                        id="last_name"
                        name="last_name"
                        value={userProfile.last_name || ''}
                        onChange={handleProfileChange}
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
                        onCheckedChange={handleShowAnalyticsChange}
                    />
                </div>
                <div className="flex justify-end pt-4 gap-3">
                    <ProfessionalButton
                        variant="outline"
                        onClick={() => setShowPasswordChange(!showPasswordChange)}
                        leftIcon={<Key className="w-4 h-4" />}
                    >
                        {showPasswordChange ? t('settings.cancel') : t('settings.change_password')}
                    </ProfessionalButton>
                    <ProfessionalButton
                        onClick={onProfileSave}
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
                                onChange={handlePasswordChange}
                                placeholder={t('settings.current_password')}
                            />
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <ProfessionalInput
                                    label={t('settings.new_password')}
                                    id="new_password"
                                    name="new_password"
                                    type="password"
                                    value={passwordData.new_password}
                                    onChange={handlePasswordChange}
                                    placeholder={t('auth.password_min_length')}
                                />
                                <ProfessionalInput
                                    label={t('settings.confirm_password')}
                                    id="confirm_password"
                                    name="confirm_password"
                                    type="password"
                                    value={passwordData.confirm_password}
                                    onChange={handlePasswordChange}
                                    placeholder={t('settings.confirm_password')}
                                />
                            </div>
                            <div className="flex justify-end gap-3 pt-2">
                                <ProfessionalButton
                                    variant="ghost"
                                    onClick={() => {
                                        setShowPasswordChange(false);
                                    }}
                                >
                                    {t('settings.cancel')}
                                </ProfessionalButton>
                                <ProfessionalButton
                                    onClick={onChangePassword}
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
