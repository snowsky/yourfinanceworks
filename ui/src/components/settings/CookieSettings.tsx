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

const CookieSettings: React.FC = () => {
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
      
      toast.success('Cookie preferences saved successfully');
    } catch (error) {
      console.error('Error saving cookie preferences:', error);
      toast.error('Failed to save cookie preferences');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setPreferences(originalPreferences);
    setHasUnsavedChanges(false);
    toast.info('Changes reset to last saved preferences');
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SettingsIcon className="w-5 h-5" />
            Cookie Preferences
          </CardTitle>
          <CardDescription>
            Loading your cookie preferences...
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
            Cookie Preferences
          </CardTitle>
          <CardDescription>
            Manage your cookie and tracking preferences. These settings control how we collect and use data to improve your experience.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Quick Actions */}
          <div className="flex gap-3">
            <Button onClick={handleAcceptAll} variant="outline" className="flex-1">
              Accept All
            </Button>
            <Button onClick={handleRejectAll} variant="outline" className="flex-1">
              Reject Optional
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
                    <Label className="text-base font-medium">Essential Cookies</Label>
                    <Badge variant="secondary" className="ml-2">Always Active</Badge>
                  </div>
                </div>
                <Switch
                  checked={preferences.essential}
                  disabled={true}
                  aria-label="Essential cookies (always enabled)"
                />
              </div>
              <p className="text-sm text-muted-foreground ml-8">
                Essential cookies required for the website to function properly. These include authentication, 
                security, and basic functionality cookies that cannot be disabled.
              </p>
            </div>

            {/* Analytics Cookies */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Eye className="w-5 h-5 text-blue-600" />
                  <div>
                    <Label className="text-base font-medium">Analytics Cookies</Label>
                    {preferences.analytics && <Badge variant="default" className="ml-2">Enabled</Badge>}
                  </div>
                </div>
                <Switch
                  checked={preferences.analytics}
                  onCheckedChange={(checked) => handlePreferenceChange('analytics', checked)}
                  aria-label="Analytics cookies"
                />
              </div>
              <p className="text-sm text-muted-foreground ml-8">
                Help us understand how you use our website by collecting anonymous usage statistics. 
                This includes page views, user interactions, and performance metrics.
              </p>
            </div>

            {/* Marketing Cookies */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Target className="w-5 h-5 text-purple-600" />
                  <div>
                    <Label className="text-base font-medium">Marketing Cookies</Label>
                    {preferences.marketing && <Badge variant="default" className="ml-2">Enabled</Badge>}
                  </div>
                </div>
                <Switch
                  checked={preferences.marketing}
                  onCheckedChange={(checked) => handlePreferenceChange('marketing', checked)}
                  aria-label="Marketing cookies"
                />
              </div>
              <p className="text-sm text-muted-foreground ml-8">
                Used to track visitors across websites and show relevant advertisements. 
                This includes conversion tracking, remarketing, and personalized ad delivery.
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
                    You have unsaved changes
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button 
                    onClick={handleReset} 
                    variant="ghost" 
                    size="sm"
                    className="text-amber-700 hover:text-amber-800 hover:bg-amber-100"
                  >
                    Reset
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
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4 mr-2" />
                        Save Changes
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
                  Your preferences are saved and up to date
                </span>
              </div>
            </div>
          )}

          <Separator />

          {/* Additional Information */}
          <div className="space-y-3">
            <h4 className="font-medium">Additional Information</h4>
            <div className="text-sm text-muted-foreground space-y-2">
              <p>
                • Your preferences are stored locally and will be remembered for future visits
              </p>
              <p>
                • You can change these settings at any time
              </p>
              <p>
                • Some features may not work properly if certain cookies are disabled
              </p>
              <p>
                • We comply with GDPR and other privacy regulations
              </p>
            </div>
          </div>


        </CardContent>
      </Card>
    </div>
  );
};

export default CookieSettings;