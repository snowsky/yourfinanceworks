import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { User, Key, ShieldCheck, Loader2, Lock, Mail } from "lucide-react";
import { Label } from "@/components/ui/label";
import {
    ProfessionalCard,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
    ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { authApi } from "@/lib/api";
import { toast } from "sonner";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { updateCurrentUser } from "@/utils/auth";

interface UserProfile {
    id: number;
    first_name?: string;
    last_name?: string;
    show_analytics?: boolean;
    email: string;
    sso_provider?: 'google' | 'microsoft' | null;
    has_sso?: boolean;
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
    const [savingProfile, setSavingProfile] = useState(false);

    const { data: user, isLoading } = useQuery({
        queryKey: ['currentUser'],
        queryFn: () => authApi.getCurrentUser(),
    });

    const isSSOUser = user && (user.has_sso === true || user.sso_provider !== null);

    useEffect(() => {
        if (user) {
            setUserProfile(user);
        }
    }, [user]);

    const getInitials = () => {
        const first = userProfile.first_name?.charAt(0)?.toUpperCase() || '';
        const last = userProfile.last_name?.charAt(0)?.toUpperCase() || '';
        return first + last || userProfile.email?.charAt(0)?.toUpperCase() || '?';
    };

    const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setUserProfile(prev => ({ ...prev, [name]: value }));
    };

    const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setPasswordData(prev => ({ ...prev, [name]: value }));
    };

    const onProfileSave = async () => {
        setSavingProfile(true);
        try {
            await authApi.updateCurrentUser({
                first_name: userProfile.first_name,
                last_name: userProfile.last_name,
            });
            updateCurrentUser({
                first_name: userProfile.first_name,
                last_name: userProfile.last_name,
            });
            toast.success(t('settings.profile_updated_successfully'));
            queryClient.invalidateQueries({ queryKey: ['currentUser'] });
        } catch (error) {
            console.error("Failed to update profile:", error);
            toast.error(t('settings.failed_to_update_profile'));
        } finally {
            setSavingProfile(false);
        }
    };

    const onChangePassword = async () => {
        if (passwordData.new_password !== passwordData.confirm_password) {
            toast.error(t('settings.profile.passwords_not_match'));
            return;
        }
        try {
            await authApi.changePassword({
                current_password: passwordData.current_password,
                new_password: passwordData.new_password,
                confirm_password: passwordData.confirm_password
            });
            toast.success(t('settings.profile.password_changed_successfully'));
            setShowPasswordChange(false);
            setPasswordData({ current_password: "", new_password: "", confirm_password: "" });
        } catch (error) {
            console.error("Failed to change password:", error);
            toast.error(t('settings.profile.failed_to_change_password'));
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
        <div className="space-y-6">
            {/* Personal Details Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <User className="w-4 h-4 text-primary" />
                        {t('settings.profile.personal_details', 'Personal Details')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-6">
                    {/* Avatar */}
                    <div className="flex items-center gap-4">
                        <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 border-2 border-primary/20">
                            <span className="text-xl font-bold text-primary">{getInitials()}</span>
                        </div>
                        <div>
                            <p className="font-semibold text-foreground">
                                {[userProfile.first_name, userProfile.last_name].filter(Boolean).join(' ') || t('settings.profile.no_name_set', 'No name set')}
                            </p>
                            <p className="text-sm text-muted-foreground">{userProfile.email}</p>
                        </div>
                    </div>

                    {/* Name fields */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <ProfessionalInput
                            label={t('settings.profile.first_name')}
                            id="first_name"
                            name="first_name"
                            value={userProfile.first_name || ''}
                            onChange={handleProfileChange}
                            autoComplete="given-name"
                        />
                        <ProfessionalInput
                            label={t('settings.profile.last_name')}
                            id="last_name"
                            name="last_name"
                            value={userProfile.last_name || ''}
                            onChange={handleProfileChange}
                            autoComplete="family-name"
                        />
                    </div>

                    {/* Email (read-only) */}
                    <div className="flex items-center gap-3 p-4 bg-muted/30 rounded-xl border border-border/50">
                        <Mail className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                            <Label className="text-sm font-medium">{t('settings.profile.email', 'Email Address')}</Label>
                            <p className="text-sm text-foreground mt-0.5">{userProfile.email}</p>
                        </div>
                        <Lock className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    </div>
                    <p className="text-xs text-muted-foreground -mt-3 ml-1">
                        {t('settings.profile.email_readonly_hint', 'Contact your administrator to change your email address.')}
                    </p>

                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Security Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-primary" />
                        {t('settings.profile.security', 'Security')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-6">
                    {isSSOUser ? (
                        <div className="flex items-center gap-3 p-4 bg-muted/30 rounded-xl">
                            <div className="space-y-0.5">
                                <Label className="text-base font-semibold">{t('settings.profile.password_management')}</Label>
                                <p className="text-sm text-muted-foreground">
                                    {user.sso_provider === 'google' ? t('settings.profile.sso_password_message_google') :
                                     user.sso_provider === 'microsoft' ? t('settings.profile.sso_password_message_microsoft') :
                                     t('settings.profile.sso_password_message_general')}
                                </p>
                            </div>
                        </div>
                    ) : (
                        <>
                            {!showPasswordChange ? (
                                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                                    <div className="space-y-0.5">
                                        <Label className="text-base font-semibold">{t('settings.profile.password', 'Password')}</Label>
                                        <p className="text-sm text-muted-foreground">••••••••••••</p>
                                    </div>
                                    <ProfessionalButton
                                        variant="outline"
                                        onClick={() => setShowPasswordChange(true)}
                                        leftIcon={<Key className="w-4 h-4" />}
                                    >
                                        {t('settings.profile.change_password')}
                                    </ProfessionalButton>
                                </div>
                            ) : (
                                <div className="space-y-6 animate-fade-in-up">
                                    <ProfessionalInput
                                        label={t('settings.profile.current_password')}
                                        id="current_password"
                                        name="current_password"
                                        type="password"
                                        value={passwordData.current_password}
                                        onChange={handlePasswordChange}
                                        placeholder={t('settings.profile.current_password')}
                                    />
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <ProfessionalInput
                                            label={t('settings.profile.new_password')}
                                            id="new_password"
                                            name="new_password"
                                            type="password"
                                            value={passwordData.new_password}
                                            onChange={handlePasswordChange}
                                            placeholder={t('settings.profile.new_password')}
                                        />
                                        <ProfessionalInput
                                            label={t('settings.profile.confirm_password')}
                                            id="confirm_password"
                                            name="confirm_password"
                                            type="password"
                                            value={passwordData.confirm_password}
                                            onChange={handlePasswordChange}
                                            placeholder={t('settings.profile.confirm_password')}
                                        />
                                    </div>
                                    <div className="flex justify-end gap-3">
                                        <ProfessionalButton
                                            variant="ghost"
                                            onClick={() => setShowPasswordChange(false)}
                                        >
                                            {t('settings.profile.cancel')}
                                        </ProfessionalButton>
                                        <ProfessionalButton onClick={onChangePassword} variant="default">
                                            {t('settings.profile.change_password')}
                                        </ProfessionalButton>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Save */}
            <div className="flex justify-end">
                <ProfessionalButton onClick={onProfileSave} loading={savingProfile} variant="gradient" size="lg">
                    {t('settings.profile.save_profile')}
                </ProfessionalButton>
            </div>
        </div>
    );
};
