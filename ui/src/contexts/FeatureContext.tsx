import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface FeatureFlags {
  ai_invoice: boolean;
  ai_expense: boolean;
  ai_bank_statement: boolean;
  ai_chat: boolean;
  tax_integration: boolean;
  slack_integration: boolean;
  cloud_storage: boolean;
  sso: boolean;
  api_keys: boolean;
  batch_processing: boolean;
  reporting: boolean;
  inventory: boolean;
  approvals: boolean;
  advanced_search: boolean;
  email_integration: boolean;
  export_destinations: boolean;
  prompt_management: boolean;
  ai_configuration: boolean;
  crm: boolean;
  [key: string]: boolean;
}

interface LicenseStatus {
  is_trial: boolean;
  trial_days_remaining?: number;
  is_licensed: boolean;
  is_license_expired: boolean;  // True if license was active but now expired
  license_expires_at?: string;
  license_days_remaining?: number;
  in_grace_period: boolean;
  expired_features: string[];   // Features that were licensed but now expired
}

interface FeatureContextType {
  features: FeatureFlags;
  licenseStatus: LicenseStatus | null;
  isFeatureEnabled: (featureId: string) => boolean;
  isFeatureExpired: (featureId: string) => boolean;  // Check if feature was licensed but expired
  isFeatureReadOnly: (featureId: string) => boolean;  // Check if feature is available for read-only access
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

const FeatureContext = createContext<FeatureContextType | undefined>(undefined);

export const FeatureProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [features, setFeatures] = useState<FeatureFlags>({} as FeatureFlags);
  const [licenseStatus, setLicenseStatus] = useState<LicenseStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasAttemptedFetch, setHasAttemptedFetch] = useState(false);

  const fetchFeatures = async () => {
    try {
      setLoading(true);
      setError(null);

      // Check if user is authenticated before making the API call
      const token = localStorage.getItem('token');
      if (!token) {
        // User not authenticated - use safe defaults
        setFeatures({
          ai_invoice: false,
          ai_expense: false,
          ai_bank_statement: false,
          ai_chat: false,
          tax_integration: false,
          slack_integration: false,
          cloud_storage: false,
          sso: false,
          api_keys: false,
          batch_processing: false,
          reporting: false,
          inventory: false,
          approvals: false,
          advanced_search: false,
          email_integration: false,
          export_destinations: false,
          prompt_management: false,
          ai_configuration: false,
          crm: false,
        });
        setLicenseStatus(null);
        setLoading(false);
        setHasAttemptedFetch(true);
        return;
      }

      // Fetch actual license status with enabled features
      // This requires authentication and returns user's actual license
      const response = await api.get<{
        enabled_features: string[];
        expired_features: string[];  // Features that were licensed but now expired
        has_all_features: boolean;
        trial_info: any;
        license_info: any;
        is_licensed: boolean;
        is_trial: boolean;
        is_license_expired: boolean;  // True if license was active but now expired
        license_status: string;
      }>('/license/status');

      // Convert enabled_features array to FeatureFlags object
      const enabledFeatures = response.enabled_features || [];
      const hasAllFeatures = response.has_all_features || enabledFeatures.includes('all');

      // Build feature flags object
      const featureFlags: FeatureFlags = {
        ai_invoice: hasAllFeatures || enabledFeatures.includes('ai_invoice'),
        ai_expense: hasAllFeatures || enabledFeatures.includes('ai_expense'),
        ai_bank_statement: hasAllFeatures || enabledFeatures.includes('ai_bank_statement'),
        ai_chat: hasAllFeatures || enabledFeatures.includes('ai_chat'),
        tax_integration: hasAllFeatures || enabledFeatures.includes('tax_integration'),
        slack_integration: hasAllFeatures || enabledFeatures.includes('slack_integration'),
        cloud_storage: hasAllFeatures || enabledFeatures.includes('cloud_storage'),
        sso: hasAllFeatures || enabledFeatures.includes('sso'),
        api_keys: hasAllFeatures || enabledFeatures.includes('api_keys'),
        batch_processing: hasAllFeatures || enabledFeatures.includes('batch_processing'),
        reporting: hasAllFeatures || enabledFeatures.includes('reporting'),
        inventory: hasAllFeatures || enabledFeatures.includes('inventory'),
        approvals: hasAllFeatures || enabledFeatures.includes('approvals'),
        advanced_search: hasAllFeatures || enabledFeatures.includes('advanced_search'),
        email_integration: hasAllFeatures || enabledFeatures.includes('email_integration'),
        // Map undefined features to existing ones that are likely enabled together
        export_destinations: hasAllFeatures || enabledFeatures.includes('cloud_storage') || enabledFeatures.includes('batch_processing'),
        prompt_management: hasAllFeatures || enabledFeatures.includes('prompt_management'),
        ai_configuration: hasAllFeatures || enabledFeatures.includes('ai_chat') || enabledFeatures.includes('ai_invoice'),
        crm: false, // CRM removed from licensing
      };

      setFeatures(featureFlags);

      // Calculate license days remaining if we have an expiration date
      let licenseDaysRemaining: number | undefined = undefined;
      if (response.license_info?.expires_at) {
        try {
          const expiresAt = new Date(response.license_info.expires_at);
          const now = new Date();
          const daysRemaining = Math.ceil((expiresAt.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
          licenseDaysRemaining = Math.max(0, daysRemaining);
        } catch (e) {
          console.error('Failed to calculate license days remaining:', e);
        }
      }

      // Build license status from response
      const licenseStatusData: LicenseStatus = {
        is_trial: response.is_trial || false,
        trial_days_remaining: response.trial_info?.days_remaining,
        is_licensed: response.is_licensed || false,
        is_license_expired: response.is_license_expired || false,
        license_expires_at: response.license_info?.expires_at,
        license_days_remaining: licenseDaysRemaining,
        in_grace_period: response.trial_info?.in_grace_period || false,
        expired_features: response.expired_features || [],
      };

      // Debug logging
      console.log('FeatureContext: License status response:', {
        enabled_features: response.enabled_features,
        expired_features: response.expired_features,
        is_license_expired: response.is_license_expired,
        license_status: response.license_status
      });

      setLicenseStatus(licenseStatusData);
      setHasAttemptedFetch(true);
    } catch (err) {
      console.error('Failed to fetch feature flags:', err);

      // Don't set error state for auth errors - just use defaults
      // This prevents the UI from showing error messages on initial load
      if (!(err instanceof Error && err.message.includes('Authentication'))) {
        setError(err instanceof Error ? err.message : 'Failed to load features');
      }

      // Set all features to false on error (safe defaults)
      setFeatures({
        ai_invoice: false,
        ai_expense: false,
        ai_bank_statement: false,
        ai_chat: false,
        tax_integration: false,
        slack_integration: false,
        cloud_storage: false,
        sso: false,
        api_keys: false,
        batch_processing: false,
        reporting: false,
        inventory: false,
        approvals: false,
        advanced_search: false,
        email_integration: false,
        export_destinations: false,
        prompt_management: false,
        ai_configuration: false,
        crm: false,
      });
      setLicenseStatus(null);
      setHasAttemptedFetch(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Only fetch on initial mount if not already loaded
    if (!hasAttemptedFetch) {
      fetchFeatures();
    }

    // Listen for storage events (e.g., when token is set in another tab or after login)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'token') {
        fetchFeatures();
      }
    };

    window.addEventListener('storage', handleStorageChange);

    // Also listen for a custom event that we can dispatch after login
    const handleAuthChange = () => {
      fetchFeatures();
    };

    window.addEventListener('auth-changed', handleAuthChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('auth-changed', handleAuthChange);
    };
  }, [hasAttemptedFetch]);

  const isFeatureEnabled = (featureId: string): boolean => {
    return features[featureId] === true;
  };

  const isFeatureExpired = (featureId: string): boolean => {
    // Check if the feature was previously licensed but now expired
    if (!licenseStatus) return false;
    return licenseStatus.is_license_expired &&
      licenseStatus.expired_features.includes(featureId);
  };

  const isFeatureReadOnly = (featureId: string): boolean => {
    // Feature is available for read-only if it's currently enabled OR was previously licensed but expired
    return isFeatureEnabled(featureId) || isFeatureExpired(featureId);
  };

  const refetch = async () => {
    await fetchFeatures();
  };

  return (
    <FeatureContext.Provider value={{ features, licenseStatus, isFeatureEnabled, isFeatureExpired, isFeatureReadOnly, loading, error, refetch }}>
      {children}
    </FeatureContext.Provider>
  );
};

export const useFeatures = () => {
  const context = useContext(FeatureContext);
  if (!context) {
    throw new Error('useFeatures must be used within FeatureProvider');
  }
  return context;
};
