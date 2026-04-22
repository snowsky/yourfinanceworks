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
import { authApi, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { updateCurrentUser } from "@/utils/auth";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useFeatures } from "@/contexts/FeatureContext";

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

interface MFAChainSettings {
    enabled: boolean;
    mode: 'fixed' | 'random';
    factors: string[];
    enrolled_factors: string[];
    supported_factors: Array<{ id: string; label: string; type: string }>;
}

interface EnrollmentDraft {
    secret: string;
    otpauth_uri: string;
    qr_png_base64: string;
    verificationCode: string;
    verifying: boolean;
    verified: boolean;
}

export const UserProfileTab: React.FC = () => {
    const { t } = useTranslation();
    const queryClient = useQueryClient();
    const { isFeatureEnabled } = useFeatures();
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
    const [savingMFA, setSavingMFA] = useState(false);
    const [mfaSettings, setMfaSettings] = useState<MFAChainSettings>({
        enabled: false,
        mode: 'fixed',
        factors: [],
        enrolled_factors: [],
        supported_factors: [],
    });
    const [enrollmentData, setEnrollmentData] = useState<Record<string, EnrollmentDraft>>({});

    const { data: user, isLoading } = useQuery({
        queryKey: ['currentUser'],
        queryFn: () => authApi.getCurrentUser(),
    });

    const { data: fetchedMFASettings } = useQuery({
        queryKey: ['mfaChainSettings'],
        queryFn: () => authApi.getMFAChainSettings(),
        enabled: isFeatureEnabled('mfa_chain'),
    });

    const isSSOUser = user && (user.has_sso === true || user.sso_provider !== null);

    useEffect(() => {
        if (user) {
            setUserProfile(user);
        }
    }, [user]);

    useEffect(() => {
        if (fetchedMFASettings) {
            setMfaSettings(fetchedMFASettings);
        }
    }, [fetchedMFASettings]);

    useEffect(() => {
        setEnrollmentData((prev) => {
            const next = { ...prev };
            for (const factorId of fetchedMFASettings?.enrolled_factors || []) {
                if (next[factorId]) {
                    next[factorId] = { ...next[factorId], verified: true };
                }
            }
            return next;
        });
    }, [fetchedMFASettings?.enrolled_factors]);

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

    const toggleFactor = (factorId: string, checked: boolean) => {
        setMfaSettings((prev) => {
            const nextFactors = checked
                ? Array.from(new Set([...prev.factors, factorId]))
                : prev.factors.filter((f) => f !== factorId);
            return { ...prev, factors: nextFactors };
        });
    };

    const swapFactorOrder = () => {
        if (mfaSettings.factors.length !== 2) return;
        setMfaSettings((prev) => ({ ...prev, factors: [prev.factors[1], prev.factors[0]] }));
    };

    const saveMFASettings = async () => {
        if (mfaSettings.enabled && mfaSettings.factors.length === 0) {
            toast.error('Select at least one authenticator before enabling MFA chain.');
            return;
        }
        setSavingMFA(true);
        try {
            const saved = await authApi.updateMFAChainSettings({
                enabled: mfaSettings.enabled,
                mode: mfaSettings.mode,
                factors: mfaSettings.factors,
            });
            setMfaSettings(saved);
            queryClient.invalidateQueries({ queryKey: ['mfaChainSettings'] });
            toast.success('MFA chain settings saved');
        } catch (error) {
            console.error('Failed to save MFA settings:', error);
            toast.error(getErrorMessage(error, (key: string) => t(key)));
        } finally {
            setSavingMFA(false);
        }
    };

    const enrollFactor = async (factorId: string) => {
        try {
            const enrolled = await authApi.enrollMFAFactor(factorId);
            setMfaSettings((prev) => ({
                ...prev,
                factors: prev.factors.includes(factorId) ? prev.factors : [...prev.factors, factorId],
            }));
            setEnrollmentData((prev) => ({
                ...prev,
                [factorId]: {
                    secret: enrolled.secret,
                    otpauth_uri: enrolled.otpauth_uri,
                    qr_png_base64: enrolled.qr_png_base64,
                    verificationCode: '',
                    verifying: false,
                    verified: false,
                },
            }));
            toast.success(`${enrolled.factor_label} secret generated. Confirm with a 6-digit code.`);
        } catch (error) {
            console.error('Failed to enroll MFA factor:', error);
            toast.error('Failed to enroll factor');
        }
    };

    const updateEnrollmentCode = (factorId: string, value: string) => {
        setEnrollmentData((prev) => ({
            ...prev,
            [factorId]: {
                ...prev[factorId],
                verificationCode: value.replace(/\D/g, '').slice(0, 6),
            },
        }));
    };

    const verifyEnrollment = async (factorId: string) => {
        const draft = enrollmentData[factorId];
        if (!draft?.verificationCode || draft.verificationCode.length !== 6) {
            toast.error('Enter a valid 6-digit authenticator code.');
            return;
        }

        setEnrollmentData((prev) => ({
            ...prev,
            [factorId]: { ...prev[factorId], verifying: true },
        }));

        try {
            await authApi.verifyMFAFactorEnrollment(factorId, {
                user_input: draft.verificationCode,
                window: 1,
            });
            const refreshed = await authApi.getMFAChainSettings();
            setMfaSettings((prev) => ({
                ...prev,
                enrolled_factors: refreshed.enrolled_factors,
                supported_factors: refreshed.supported_factors,
            }));
            setEnrollmentData((prev) => ({
                ...prev,
                [factorId]: {
                    ...prev[factorId],
                    verifying: false,
                    verified: true,
                },
            }));
            toast.success(`${factorName(factorId)} enrollment verified`);
        } catch (error) {
            console.error('Failed to verify MFA enrollment:', error);
            setEnrollmentData((prev) => ({
                ...prev,
                [factorId]: { ...prev[factorId], verifying: false },
            }));
            toast.error(getErrorMessage(error, (key: string) => t(key)));
        }
    };

    const factorName = (factorId: string) => {
        return mfaSettings.supported_factors.find((f) => f.id === factorId)?.label || factorId;
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

                    {isFeatureEnabled('mfa_chain') && (
                    <div className="border-t border-border/50 pt-6 space-y-5">
                        <div className="flex items-center justify-between rounded-xl border border-border/50 p-4 bg-muted/20">
                            <div>
                                <Label className="text-base font-semibold">MFA Chain</Label>
                                <p className="text-sm text-muted-foreground">Require one or more authenticator apps after password or SSO.</p>
                            </div>
                            <Switch
                                checked={mfaSettings.enabled}
                                onCheckedChange={(checked) =>
                                    setMfaSettings((prev) => {
                                        if (!checked) {
                                            return { ...prev, enabled: false };
                                        }
                                        if (prev.factors.length > 0) {
                                            return { ...prev, enabled: true };
                                        }
                                        const firstFactor = prev.supported_factors[0]?.id;
                                        if (!firstFactor) {
                                            return { ...prev, enabled: true };
                                        }
                                        toast.info('Selected the first authenticator. Enroll it before saving.');
                                        return { ...prev, enabled: true, factors: [firstFactor] };
                                    })
                                }
                            />
                        </div>

                        <div className="space-y-3">
                            <Label className="text-sm font-semibold">Authenticators</Label>
                            {mfaSettings.supported_factors.map((factor) => {
                                const isSelected = mfaSettings.factors.includes(factor.id);
                                const isEnrolled = mfaSettings.enrolled_factors.includes(factor.id);
                                const enrollment = enrollmentData[factor.id];

                                return (
                                    <div key={factor.id} className="rounded-xl border border-border/50 p-4 space-y-3">
                                        <div className="flex items-center justify-between gap-4">
                                            <div>
                                                <p className="font-medium text-sm">{factor.label}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {isEnrolled ? 'Enrolled' : enrollment ? 'Pending verification' : 'Not enrolled'}
                                                </p>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Switch
                                                    checked={isSelected}
                                                    onCheckedChange={(checked) => toggleFactor(factor.id, checked)}
                                                />
                                                <ProfessionalButton
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => enrollFactor(factor.id)}
                                                >
                                                    {isEnrolled ? 'Re-enroll' : 'Enroll'}
                                                </ProfessionalButton>
                                            </div>
                                        </div>

                                        {enrollment && (
                                            <div className="rounded-lg bg-muted/30 border border-border/40 p-3 space-y-2">
                                                <p className="text-xs font-medium">Setup Secret: <span className="font-mono">{enrollment.secret}</span></p>
                                                <p className="text-xs break-all">{enrollment.otpauth_uri}</p>
                                                {enrollment.qr_png_base64 && (
                                                    <img
                                                        src={`data:image/png;base64,${enrollment.qr_png_base64}`}
                                                        alt={`${factor.label} QR`}
                                                        className="h-28 w-28 rounded border border-border/40"
                                                    />
                                                )}
                                                <div className="flex flex-col gap-2 pt-2 md:flex-row md:items-end">
                                                    <div className="flex-1">
                                                        <ProfessionalInput
                                                            id={`verify_${factor.id}`}
                                                            label="Verify Enrollment Code"
                                                            type="text"
                                                            placeholder="Enter 6-digit code"
                                                            value={enrollment.verificationCode}
                                                            onChange={(e) => updateEnrollmentCode(factor.id, e.target.value)}
                                                        />
                                                    </div>
                                                    <ProfessionalButton
                                                        size="sm"
                                                        variant={enrollment.verified ? "outline" : "default"}
                                                        onClick={() => verifyEnrollment(factor.id)}
                                                        loading={enrollment.verifying}
                                                    >
                                                        {enrollment.verified ? 'Verified' : 'Confirm'}
                                                    </ProfessionalButton>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label className="text-sm font-semibold">Chain Mode</Label>
                                <Select
                                    value={mfaSettings.mode}
                                    onValueChange={(value: 'fixed' | 'random') => setMfaSettings((prev) => ({ ...prev, mode: value }))}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select mode" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="fixed">Fixed sequence</SelectItem>
                                        <SelectItem value="random">Random sequence</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label className="text-sm font-semibold">Sequence</Label>
                                <div className="rounded-lg border border-border/50 px-3 py-2 text-sm text-muted-foreground min-h-10 flex items-center justify-between">
                                    <span>{mfaSettings.factors.length ? mfaSettings.factors.map(factorName).join(' -> ') : 'No factors selected'}</span>
                                    {mfaSettings.mode === 'fixed' && mfaSettings.factors.length === 2 && (
                                        <ProfessionalButton size="sm" variant="ghost" onClick={swapFactorOrder}>Swap</ProfessionalButton>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-end">
                            <ProfessionalButton variant="default" onClick={saveMFASettings} loading={savingMFA}>
                                Save MFA Security
                            </ProfessionalButton>
                        </div>
                    </div>
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
