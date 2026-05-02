import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';

interface FeatureFlags {
  ai_invoice: boolean;
  ai_expense: boolean;
  ai_bank_statement: boolean;
  ai_chat: boolean;
  // tax_integration: boolean;
  slack_integration: boolean;
  cloud_storage: boolean;
  sso: boolean;
  mfa_chain: boolean;
  external_api: boolean;
  external_transactions: boolean;
  advanced_export: boolean;
  approval_analytics: boolean;
  batch_processing: boolean;
  reporting: boolean;
  cash_flow: boolean;
  approvals: boolean;
  advanced_search: boolean;
  email_integration: boolean;
  workflow_automation: boolean;
  prompt_management: boolean;
  anomaly_detection: boolean;
  plugin_management: boolean;
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
  apiAvailable: boolean;  // False when API is unreachable (restarting, network down)
  refetch: () => Promise<void>;
}

const FeatureContext = createContext<FeatureContextType | undefined>(undefined);

export const FeatureProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [features, setFeatures] = useState<FeatureFlags>({} as FeatureFlags);
  const [licenseStatus, setLicenseStatus] = useState<LicenseStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasAttemptedFetch, setHasAttemptedFetch] = useState(false);
  const [apiAvailable, setApiAvailable] = useState(true);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchFeatures = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch actual license status with enabled features
      // Auth is via httpOnly cookie — do not gate on localStorage, which may be absent
      // in sandboxed browser contexts (PWA, WebView, app mode). The API returns 401 if
      // the user is not authenticated, and the catch block handles that gracefully.
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
        // tax_integration: hasAllFeatures || enabledFeatures.includes('tax_integration'),
        slack_integration: hasAllFeatures || enabledFeatures.includes('slack_integration'),
        cloud_storage: hasAllFeatures || enabledFeatures.includes('cloud_storage'),
        sso: hasAllFeatures || enabledFeatures.includes('sso'),
        mfa_chain: hasAllFeatures || enabledFeatures.includes('mfa_chain'),
        external_api: hasAllFeatures || enabledFeatures.includes('external_api'),
        external_transactions: hasAllFeatures || enabledFeatures.includes('external_transactions'),
        advanced_export: hasAllFeatures || enabledFeatures.includes('advanced_export'),
        approval_analytics: hasAllFeatures || enabledFeatures.includes('approval_analytics'),
        batch_processing: hasAllFeatures || enabledFeatures.includes('batch_processing'),
        reporting: hasAllFeatures || enabledFeatures.includes('reporting'),
        cash_flow: hasAllFeatures || enabledFeatures.includes('cash_flow'),
        approvals: hasAllFeatures || enabledFeatures.includes('approvals'),
        advanced_search: hasAllFeatures || enabledFeatures.includes('advanced_search'),
        email_integration: hasAllFeatures || enabledFeatures.includes('email_integration'),
        workflow_automation: hasAllFeatures || enabledFeatures.includes('workflow_automation'),
        prompt_management: hasAllFeatures || enabledFeatures.includes('prompt_management'),
        anomaly_detection: hasAllFeatures || enabledFeatures.includes('anomaly_detection'),
        plugin_management: hasAllFeatures || enabledFeatures.includes('plugin_management'),
        
        // Core features (client-side only for now)
        inventory: true,
        crm: true,
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
      setApiAvailable(true);

      // Clear any pending retry now that API is reachable
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }

      // Emit event to notify other components that features have been updated
      window.dispatchEvent(new CustomEvent('feature-context-updated', {
        detail: { features: featureFlags, licenseStatus: licenseStatusData }
      }));
    } catch (err) {
      console.error('Failed to fetch feature flags:', err);

      // Detect network-level failures (API restarting, unreachable).
      // Note: when the 502/503/504 body is non-JSON (nginx HTML error page),
      // _base.ts throws a plain Error("Error: 502 Bad Gateway") without a
      // .status property, so we must also check the message string.
      const errStatus = (err as any)?.status;
      const errMsg = err instanceof Error ? err.message : '';
      const isNetworkError =
        (err instanceof TypeError && errMsg.toLowerCase().includes('fetch')) ||
        errStatus === 502 || errStatus === 503 || errStatus === 504 ||
        /Error:\s*(502|503|504)\b/.test(errMsg);

      if (isNetworkError) {
        // API is temporarily unavailable — keep existing features, just flag it
        setApiAvailable(false);
        setHasAttemptedFetch(true);
        // Schedule a retry every 5 seconds until the API comes back
        if (!retryTimerRef.current) {
          retryTimerRef.current = setTimeout(() => {
            retryTimerRef.current = null;
            fetchFeatures();
          }, 5000);
        }
      } else {
        // API responded but with an error (auth, license, etc.) — treat as normal
        setApiAvailable(true);

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
          // tax_integration: false,
          slack_integration: false,
          cloud_storage: false,
          sso: false,
          mfa_chain: false,
          external_api: false,
          external_transactions: false,
          advanced_export: false,
          approval_analytics: false,
          batch_processing: false,
          reporting: false,
          cash_flow: false,
          inventory: true,
          approvals: false,
          advanced_search: false,
          email_integration: false,
          workflow_automation: false,
          prompt_management: false,
          anomaly_detection: false,
          plugin_management: false,
          crm: true,
        });
        setLicenseStatus(null);
        setHasAttemptedFetch(true);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Only fetch on initial mount if not already loaded
    if (!hasAttemptedFetch) {
      fetchFeatures();
    }

    // Listen for storage events (e.g., when user is set in another tab or after login)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'user') {
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
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
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
    <FeatureContext.Provider value={{ features, licenseStatus, isFeatureEnabled, isFeatureExpired, isFeatureReadOnly, loading, error, apiAvailable, refetch }}>
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
