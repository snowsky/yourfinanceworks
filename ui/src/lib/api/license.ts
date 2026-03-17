import { apiRequest } from './_base';

// ============================================================================
// License Management API
// ============================================================================

export interface LicenseStatus {
  installation_id: string;
  is_trial: boolean;
  trial_start_date?: string;
  trial_end_date?: string;
  trial_days_remaining?: number;
  is_licensed: boolean;
  license_key?: string;
  license_expires_at?: string;
  license_days_remaining?: number;
  in_grace_period: boolean;
  enabled_features: string[];
}

export interface LicenseFeatureInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  enabled: boolean;
}

export interface LicenseFeaturesResponse {
  features: Record<string, boolean>;
  feature_list: LicenseFeatureInfo[];
  license_status: {
    is_trial: boolean;
    trial_days_remaining?: number;
    is_licensed: boolean;
    license_expires_at?: string;
    license_days_remaining?: number;
    in_grace_period: boolean;
  };
}

export const licenseApi = {
  // Get license status
  getStatus: () =>
    apiRequest<LicenseStatus>('/license/status'),

  // Get enabled features
  getFeatures: () =>
    apiRequest<LicenseFeaturesResponse>('/license/features'),

  // Activate a license
  activateLicense: (licenseKey: string) =>
    apiRequest<{ success: boolean; message: string }>('/license/activate', {
      method: 'POST',
      body: JSON.stringify({ license_key: licenseKey }),
    }),

  // Deactivate current license
  deactivateLicense: () =>
    apiRequest<{ success: boolean; message: string }>('/license/deactivate', {
      method: 'POST',
    }),

  // Validate current license
  validateLicense: () =>
    apiRequest<{ valid: boolean; message: string }>('/license/validate', {
      method: 'POST',
    }),
};
