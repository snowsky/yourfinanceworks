import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { ConsentManager } from '@/components/cookie-consent/services/ConsentManager';
import { Shield, Eye, Target, Settings as SettingsIcon, RefreshCw, Save, Check } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

const CookieSettings: React.FC = () => {
  const { t } = useTranslation();
  const [consentManager] = useState(() => new ConsentManager());
  const [preferences, setPreferences] = useState({
    essential: true, // Always true, cannot be disabled
    analytics: false,
    marketing: false
  });
  const [originalPreferences, setOriginalPreferences] = useState({
    essential: true,
    analytics: false,
    marketing: false
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  useEffect(() => {
    // Load current preferences
    const loadPreferences = () => {
      const currentPrefs = {
        essential: true, // Always true
        analytics: consentManager.getCategoryConsent('analytics'),
        marketing: consentManager.getCategoryConsent('marketing')
      };
      setPreferences(currentPrefs);
      setOriginalPreferences(currentPrefs);
      setHasUnsavedChanges(false);
      setIsLoading(false);
    };

    loadPreferences();
  }, [consentManager]);

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

  const handleAcceptAll = async () => {
    const newPreferences = {
      essential: true,
      analytics: true,
      marketing: true
    };
    
    setPreferences(newPreferences);
    setHasUnsavedChanges(true);
  };

  const handleRejectAll = async () => {
    const newPreferences = {
      essential: true,
      analytics: false,
      marketing: false
    };
    
    setPreferences(newPreferences);
    setHasUnsavedChanges(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    
    try {
      // Update consent manager
      consentManager.setCategoryConsent('analytics', preferences.analytics);
      consentManager.setCategoryConsent('marketing', preferences.marketing);

      // Dispatch event for other components to react to changes
      window.dispatchEvent(new CustomEvent('cookieConsentChange', {
        detail: {
          preferences: {
            essential: true,
            analytics: preferences.analytics,
            marketing: preferences.marketing
          }
        }
      }));

      // Update original preferences to match current
      setOriginalPreferences(preferences);
      setHasUnsavedChanges(false);
      
      toast.success(t('cookieConsent.settings.messages.saveSuccess'));
    } catch (error) {
      console.error('Error saving cookie preferences:', error);
      toast.error(t('cookieConsent.settings.messages.saveError'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setPreferences(originalPreferences);
    setHasUnsavedChanges(false);
    toast.info(t('cookieConsent.settings.messages.resetInfo'));
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SettingsIcon className="w-5 h-5" />
            {t('cookieConsent.settings.title')}
          </CardTitle>
          <CardDescription>
            {t('cookieConsent.settings.loading')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SettingsIcon className="w-5 h-5" />
            {t('cookieConsent.settings.title')}
          </CardTitle>
          <CardDescription>
            {t('cookieConsent.settings.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Quick Actions */}
          <div className="flex gap-3">
            <Button onClick={handleAcceptAll} variant="outline" className="flex-1">
              {t('cookieConsent.settings.acceptAll')}
            </Button>
            <Button onClick={handleRejectAll} variant="outline" className="flex-1">
              {t('cookieConsent.settings.rejectOptional')}
            </Button>
          </div>

          <Separator />

          {/* Cookie Categories */}
          <div className="space-y-6">
            {/* Essential Cookies */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Shield className="w-5 h-5 text-green-600" />
                  <div>
                    <Label className="text-base font-medium">{t('cookieConsent.settings.categories.essential.title')}</Label>
                    <Badge variant="secondary" className="ml-2">{t('cookieConsent.settings.alwaysActive')}</Badge>
                  </div>
                </div>
                <Switch
                  checked={preferences.essential}
                  disabled={true}
                  aria-label={t('cookieConsent.settings.categories.essential.ariaLabel')}
                />
              </div>
              <p className="text-sm text-muted-foreground ml-8">
                {t('cookieConsent.settings.categories.essential.description')}
              </p>
            </div>

            {/* Analytics Cookies */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Eye className="w-5 h-5 text-blue-600" />
                  <div>
                    <Label className="text-base font-medium">{t('cookieConsent.settings.categories.analytics.title')}</Label>
                    {preferences.analytics && <Badge variant="default" className="ml-2">{t('cookieConsent.settings.enabled')}</Badge>}
                  </div>
                </div>
                <Switch
                  checked={preferences.analytics}
                  onCheckedChange={(checked) => handlePreferenceChange('analytics', checked)}
                  aria-label={t('cookieConsent.settings.categories.analytics.ariaLabel')}
                />
              </div>
              <p className="text-sm text-muted-foreground ml-8">
                {t('cookieConsent.settings.categories.analytics.description')}
              </p>
            </div>

            {/* Marketing Cookies */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Target className="w-5 h-5 text-purple-600" />
                  <div>
                    <Label className="text-base font-medium">{t('cookieConsent.settings.categories.marketing.title')}</Label>
                    {preferences.marketing && <Badge variant="default" className="ml-2">{t('cookieConsent.settings.enabled')}</Badge>}
                  </div>
                </div>
                <Switch
                  checked={preferences.marketing}
                  onCheckedChange={(checked) => handlePreferenceChange('marketing', checked)}
                  aria-label={t('cookieConsent.settings.categories.marketing.ariaLabel')}
                />
              </div>
              <p className="text-sm text-muted-foreground ml-8">
                {t('cookieConsent.settings.categories.marketing.description')}
              </p>
            </div>


          </div>

          <Separator />

          {/* Save Actions */}
          {hasUnsavedChanges && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
                  <span className="text-sm font-medium text-amber-800">
                    {t('cookieConsent.settings.unsavedChanges')}
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button 
                    onClick={handleReset} 
                    variant="ghost" 
                    size="sm"
                    className="text-amber-700 hover:text-amber-800 hover:bg-amber-100"
                  >
                    {t('cookieConsent.settings.reset')}
                  </Button>
                  <Button 
                    onClick={handleSave} 
                    size="sm"
                    disabled={isSaving}
                    className="bg-amber-600 hover:bg-amber-700 text-white"
                  >
                    {isSaving ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        {t('cookieConsent.settings.saving')}
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4 mr-2" />
                        {t('cookieConsent.settings.saveChanges')}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {!hasUnsavedChanges && !isLoading && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" />
                <span className="text-sm font-medium text-green-800">
                  {t('cookieConsent.settings.upToDate')}
                </span>
              </div>
            </div>
          )}

          <Separator />

          {/* Additional Information */}
          <div className="space-y-3">
            <h4 className="font-medium">{t('cookieConsent.settings.additionalInfo')}</h4>
            <div className="text-sm text-muted-foreground space-y-2">
              <p>
                • {t('cookieConsent.settings.infoPoints.stored')}
              </p>
              <p>
                • {t('cookieConsent.settings.infoPoints.changeable')}
              </p>
              <p>
                • {t('cookieConsent.settings.infoPoints.functionality')}
              </p>
              <p>
                • {t('cookieConsent.settings.infoPoints.compliance')}
              </p>
            </div>
          </div>


        </CardContent>
      </Card>
    </div>
  );
};

export default CookieSettings;