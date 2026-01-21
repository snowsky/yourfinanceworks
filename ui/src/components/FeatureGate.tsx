import React from 'react';
import { useTranslation } from 'react-i18next';
import { useFeatures } from '@/contexts/FeatureContext';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Lock, AlertCircle, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';

interface FeatureGateProps {
  feature: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  showUpgradePrompt?: boolean;
  upgradeMessage?: string;
  showExpiredContent?: boolean;  // If true, show content with renewal banner when expired
}

export const FeatureGate: React.FC<FeatureGateProps> = ({
  feature,
  children,
  fallback,
  showUpgradePrompt = false,
  upgradeMessage,
  showExpiredContent = true,  // Default to showing expired content with banner
}) => {
  const { t } = useTranslation();
  const { isFeatureEnabled, isFeatureExpired, loading, licenseStatus } = useFeatures();

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  // Check if this feature was previously licensed but has now expired
  const featureIsExpired = isFeatureExpired(feature);
  const featureIsEnabled = isFeatureEnabled(feature);

  // If feature is expired and we should show expired content, display with renewal banner
  if (featureIsExpired && showExpiredContent && !featureIsEnabled) {
    return (
      <>
        <Alert className="border-amber-300 bg-amber-50 mb-4">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertTitle className="text-amber-900">{t('settings.license.expired')}</AlertTitle>
          <AlertDescription className="text-amber-800">
            <p className="mb-3">
              {t('settings.license.expired_message')}
            </p>
            <div className="flex gap-2">
              <Button asChild size="sm" variant="default">
                <Link to="/settings?tab=license">{t('settings.license.renew')}</Link>
              </Button>
            </div>
          </AlertDescription>
        </Alert>
        {children}
      </>
    );
  }

  if (!featureIsEnabled) {
    if (showUpgradePrompt) {
      const defaultMessage = upgradeMessage || `This feature requires a license upgrade.`;
      const isTrialExpired = licenseStatus && licenseStatus.is_trial && (licenseStatus.trial_days_remaining || 0) <= 0;
      const isLicenseExpired = licenseStatus && licenseStatus.is_license_expired;

      return (
        <Alert className="border-amber-200 bg-amber-50">
          <Lock className="h-4 w-4 text-amber-600" />
          <AlertTitle className="text-amber-900">{t('settings.license.feature_locked')}</AlertTitle>
          <AlertDescription className="text-amber-800">
            <p className="mb-3">{defaultMessage}</p>
            {isTrialExpired && (
              <p className="mb-3 text-sm">{t('settings.license.trial_ended')}</p>
            )}
            {isLicenseExpired && (
              <p className="mb-3 text-sm">{t('settings.license.license_expired_feature')}</p>
            )}
            <div className="flex gap-2">
              <Button asChild size="sm" variant="default">
                <Link to="/settings?tab=license">{t('settings.license.manage')}</Link>
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      );
    }

    return fallback ? <>{fallback}</> : null;
  }

  return <>{children}</>;
};


interface FeatureAlertProps {
  feature: string;
  title?: string;
  message?: string;
}

export const FeatureAlert: React.FC<FeatureAlertProps> = ({
  feature,
  title = 'Feature Not Available',
  message,
}) => {
  const { t } = useTranslation();
  const { licenseStatus } = useFeatures();

  const defaultMessage = message || `The ${feature} feature is not available in your current plan.`;
  const isTrialExpired = licenseStatus && licenseStatus.is_trial && (licenseStatus.trial_days_remaining || 0) <= 0;
  const isLicenseExpired = licenseStatus && licenseStatus.is_license_expired;

  return (
    <Alert className="border-blue-200 bg-blue-50">
      <AlertCircle className="h-4 w-4 text-blue-600" />
      <AlertTitle className="text-blue-900">{title}</AlertTitle>
      <AlertDescription className="text-blue-800">
        <p className="mb-3">{defaultMessage}</p>
        {isTrialExpired && (
          <p className="mb-3 text-sm">{t('settings.license.trial_ended_access')}</p>
        )}
        {isLicenseExpired && (
          <p className="mb-3 text-sm">{t('settings.license.license_expired_access')}</p>
        )}
        <div className="flex gap-2">
          <Button asChild size="sm" variant="default">
            <Link to="/settings?tab=license">{t('settings.license.manage')}</Link>
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  );
};
