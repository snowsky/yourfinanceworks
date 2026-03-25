import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { ConsentManager } from '@/components/cookie-consent/services/ConsentManager';
import { Shield, Eye, Target, Settings as SettingsIcon, RefreshCw, Save, Check, Cookie } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

export const CookieSettingsTab: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [consentManager] = useState(() => new ConsentManager());
  const [preferences, setPreferences] = useState({
    essential: true, // Always true, cannot be disabled
    analytics: false,
    marketing: false
  });
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Queries
  const { data: originalPreferences, isLoading } = useQuery({
    queryKey: ['cookie-preferences'],
    queryFn: () => {
      const prefs = {
        essential: true,
        analytics: consentManager.getCategoryConsent('analytics'),
        marketing: consentManager.getCategoryConsent('marketing')
      };
      return prefs;
    },
    staleTime: Infinity, // Preferences only change when updated
  });

  useEffect(() => {
    if (originalPreferences) {
      setPreferences(originalPreferences);
    }
  }, [originalPreferences]);

  // Mutations
  const saveMutation = useMutation({
    mutationFn: async (newPrefs: typeof preferences) => {
      consentManager.setCategoryConsent('analytics', newPrefs.analytics);
      consentManager.setCategoryConsent('marketing', newPrefs.marketing);

      // Dispatch event for other components to react to changes
      window.dispatchEvent(new CustomEvent('cookieConsentChange', {
        detail: {
          preferences: {
            essential: true,
            analytics: newPrefs.analytics,
            marketing: newPrefs.marketing
          }
        }
      }));
      return newPrefs;
    },
    onSuccess: (newPrefs) => {
      queryClient.setQueryData(['cookie-preferences'], newPrefs);
      setHasUnsavedChanges(false);
      toast.success(t('cookieConsent.settings.messages.saveSuccess'));
    },
    onError: (error) => {
      console.error('Error saving cookie preferences:', error);
      toast.error(t('cookieConsent.settings.messages.saveError'));
    }
  });

  const handlePreferenceChange = (category: string, enabled: boolean) => {
    if (category === 'essential') return; // Cannot disable essential cookies

    const newPreferences = {
      ...preferences,
      [category]: enabled
    };

    setPreferences(newPreferences);

    // Check if there are unsaved changes
    const hasChanges =
      newPreferences.analytics !== originalPreferences.analytics ||
      newPreferences.marketing !== originalPreferences.marketing;

    setHasUnsavedChanges(hasChanges);
  };

  const handleAcceptAll = () => {
    const newPreferences = {
      essential: true,
      analytics: true,
      marketing: true
    };

    setPreferences(newPreferences);

    const hasChanges =
      newPreferences.analytics !== originalPreferences.analytics ||
      newPreferences.marketing !== originalPreferences.marketing;
    setHasUnsavedChanges(hasChanges);
  };

  const handleRejectAll = () => {
    const newPreferences = {
      essential: true,
      analytics: false,
      marketing: false
    };

    setPreferences(newPreferences);

    const hasChanges =
      newPreferences.analytics !== originalPreferences.analytics ||
      newPreferences.marketing !== originalPreferences.marketing;
    setHasUnsavedChanges(hasChanges);
  };

  const handleSave = () => {
    saveMutation.mutate(preferences);
  };

  const handleReset = () => {
    setPreferences(originalPreferences);
    setHasUnsavedChanges(false);
    toast.info(t('cookieConsent.settings.messages.resetInfo'));
  };

  const isSaving = saveMutation.isPending;

  if (isLoading) {
    return (
      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center gap-2">
            <SettingsIcon className="w-5 h-5" />
            {t('cookieConsent.settings.title')}
          </ProfessionalCardTitle>
          <p className="text-muted-foreground ml-7 text-sm">
            {t('cookieConsent.settings.loading')}
          </p>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-primary" />
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  return (
    <div className="space-y-6">
      {/* Gradient Banner */}
      <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-6 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
            <Cookie className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">{t('cookieConsent.settings.title', 'Privacy & Cookies')}</h2>
            <p className="text-muted-foreground mt-0.5">{t('cookieConsent.settings.banner_description', 'Manage your cookie consent preferences')}</p>
          </div>
        </div>
      </div>

      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center gap-2">
            <Cookie className="w-5 h-5 text-primary" />
            {t('cookieConsent.settings.title')}
          </ProfessionalCardTitle>
          <p className="text-muted-foreground ml-7 text-sm">
            {t('cookieConsent.settings.description')}
          </p>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-8">
          {/* Quick Actions */}
          <div className="flex gap-4 p-4 bg-muted/20 rounded-xl border border-border/50">
            <ProfessionalButton
              onClick={handleAcceptAll}
              variant="outline"
              className="flex-1 border-primary/20 hover:border-primary/50 text-primary hover:bg-primary/5"
            >
              {t('cookieConsent.settings.acceptAll')}
            </ProfessionalButton>
            <ProfessionalButton
              onClick={handleRejectAll}
              variant="outline"
              className="flex-1"
            >
              {t('cookieConsent.settings.rejectOptional')}
            </ProfessionalButton>
          </div>

          <Separator className="bg-border/50" />

          {/* Cookie Categories */}
          <div className="space-y-6">
            {/* Essential Cookies */}
            <div className="flex flex-col gap-3 p-5 rounded-xl border border-border/50 bg-card/50 hover:bg-card transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-2.5 bg-green-50 text-green-600 rounded-lg">
                    <Shield className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <Label className="text-base font-semibold">{t('cookieConsent.settings.categories.essential.title')}</Label>
                      <Badge variant="secondary" className="bg-muted text-muted-foreground text-[10px] uppercase tracking-wider">{t('cookieConsent.settings.alwaysActive')}</Badge>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Switch
                    checked={preferences.essential}
                    disabled={true}
                    aria-label={t('cookieConsent.settings.categories.essential.ariaLabel')}
                    className="data-[state=checked]:bg-green-600 opacity-80"
                  />
                </div>
              </div>
              <p className="text-sm text-muted-foreground pl-[52px] leading-relaxed">
                {t('cookieConsent.settings.categories.essential.description')}
              </p>
            </div>

            {/* Analytics Cookies */}
            <div className={cn(
              "flex flex-col gap-3 p-5 rounded-xl border transition-all duration-200",
              preferences.analytics
                ? "border-blue-200 bg-blue-50/30"
                : "border-border/50 bg-card/50 hover:bg-card"
            )}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={cn("p-2.5 rounded-lg", preferences.analytics ? "bg-blue-100 text-blue-600" : "bg-muted text-muted-foreground")}>
                    <Eye className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <Label className="text-base font-semibold">{t('cookieConsent.settings.categories.analytics.title')}</Label>
                      {preferences.analytics && <Badge variant="default" className="bg-blue-600 text-[10px] uppercase tracking-wider">{t('cookieConsent.settings.enabled')}</Badge>}
                    </div>
                  </div>
                </div>
                <Switch
                  checked={preferences.analytics}
                  onCheckedChange={(checked) => handlePreferenceChange('analytics', checked)}
                  aria-label={t('cookieConsent.settings.categories.analytics.ariaLabel')}
                  className="data-[state=checked]:bg-blue-600"
                />
              </div>
              <p className="text-sm text-muted-foreground pl-[52px] leading-relaxed">
                {t('cookieConsent.settings.categories.analytics.description')}
              </p>
            </div>

            {/* Marketing Cookies */}
            <div className={cn(
              "flex flex-col gap-3 p-5 rounded-xl border transition-all duration-200",
              preferences.marketing
                ? "border-purple-200 bg-purple-50/30"
                : "border-border/50 bg-card/50 hover:bg-card"
            )}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={cn("p-2.5 rounded-lg", preferences.marketing ? "bg-purple-100 text-purple-600" : "bg-muted text-muted-foreground")}>
                    <Target className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <Label className="text-base font-semibold">{t('cookieConsent.settings.categories.marketing.title')}</Label>
                      {preferences.marketing && <Badge variant="default" className="bg-purple-600 text-[10px] uppercase tracking-wider">{t('cookieConsent.settings.enabled')}</Badge>}
                    </div>
                  </div>
                </div>
                <Switch
                  checked={preferences.marketing}
                  onCheckedChange={(checked) => handlePreferenceChange('marketing', checked)}
                  aria-label={t('cookieConsent.settings.categories.marketing.ariaLabel')}
                  className="data-[state=checked]:bg-purple-600"
                />
              </div>
              <p className="text-sm text-muted-foreground pl-[52px] leading-relaxed">
                {t('cookieConsent.settings.categories.marketing.description')}
              </p>
            </div>
          </div>

          <Separator className="bg-border/50" />

          {/* Save Actions */}
          {hasUnsavedChanges && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 animate-in slide-in-from-bottom-2 duration-300">
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-100 text-amber-600 rounded-full">
                    <RefreshCw className="w-4 h-4" />
                  </div>
                  <span className="font-medium text-amber-900">
                    {t('cookieConsent.settings.unsavedChanges')}
                  </span>
                </div>
                <div className="flex gap-2 w-full sm:w-auto">
                  <ProfessionalButton
                    onClick={handleReset}
                    variant="ghost"
                    size="sm"
                    className="flex-1 sm:flex-none text-amber-700 hover:text-amber-900 hover:bg-amber-100"
                  >
                    {t('cookieConsent.settings.reset')}
                  </ProfessionalButton>
                  <ProfessionalButton
                    onClick={handleSave}
                    size="sm"
                    disabled={isSaving}
                    loading={isSaving}
                    className="flex-1 sm:flex-none bg-amber-600 hover:bg-amber-700 text-white shadow-sm border-amber-700/20"
                  >
                    {!isSaving && <Save className="w-4 h-4 mr-2" />}
                    {t('cookieConsent.settings.saveChanges')}
                  </ProfessionalButton>
                </div>
              </div>
            </div>
          )}

          {!hasUnsavedChanges && !isLoading && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3 text-green-800 animate-in fade-in duration-300">
              <div className="p-1.5 bg-green-100 rounded-full">
                <Check className="w-4 h-4 text-green-600" />
              </div>
              <span className="font-medium">
                {t('cookieConsent.settings.upToDate')}
              </span>
            </div>
          )}

          <Separator className="bg-border/50" />

          {/* Additional Information */}
          <div className="space-y-4 pt-2">
            <h4 className="font-semibold text-sm flex items-center gap-2">
              <SettingsIcon className="h-4 w-4 text-primary" />
              {t('cookieConsent.settings.additionalInfo')}
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-muted-foreground">
              <div className="p-3 bg-muted/30 rounded-lg border border-border/30">
                • {t('cookieConsent.settings.infoPoints.stored')}
              </div>
              <div className="p-3 bg-muted/30 rounded-lg border border-border/30">
                • {t('cookieConsent.settings.infoPoints.changeable')}
              </div>
              <div className="p-3 bg-muted/30 rounded-lg border border-border/30">
                • {t('cookieConsent.settings.infoPoints.functionality')}
              </div>
              <div className="p-3 bg-muted/30 rounded-lg border border-border/30">
                • {t('cookieConsent.settings.infoPoints.compliance')}
              </div>
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    </div>
  );
};
