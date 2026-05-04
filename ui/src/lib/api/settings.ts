import { API_BASE_URL, apiRequest } from './_base';

// Add settings types
export interface CompanyInfo {
  name: string;
  email: string;
  phone: string;
  address: string;
  tax_id: string;
  logo?: string;
}

export interface InvoiceSettings {
  prefix: string;
  next_number: string;
  terms: string;
  notes?: string;
  send_copy: boolean;
  auto_reminders: boolean;
}

export type ShareAccessType = 'public' | 'password' | 'question';

export interface SharingSettings {
  default_access_type: ShareAccessType;
  default_expiration_hours: number;
  allow_public_links: boolean;
  allow_password_links: boolean;
  allow_question_links: boolean;
  default_one_time: boolean;
  require_expiration: boolean;
}

export interface Settings {
  company_info: CompanyInfo;
  invoice_settings: InvoiceSettings;
  enable_ai_assistant?: boolean;
  timezone?: string;
  email_settings?: any;
  allow_join_lookup?: boolean;
  join_lookup_exact_match?: boolean;
  expense_mobile?: ExpenseMobileServiceSettings;
  sharing_settings?: SharingSettings;
}

export interface StripePaymentSettings {
  enabled: boolean;
  accountLabel?: string;
  publishableKey: string;
  secretKey: string;
  webhookSecret?: string;
}

export interface PaymentSettings {
  provider: 'stripe';
  stripe: StripePaymentSettings;
}

export interface ExpenseMobileServiceSettings {
  enabled: boolean;
  app_id: string;
  signup_enabled: boolean;
  default_role: 'user' | 'viewer';
  allowed_auth_methods: {
    password: boolean;
    google: boolean;
    microsoft: boolean;
  };
  branding: {
    title: string;
    subtitle: string;
    accent_color: string;
    logo_url?: string;
  };
}

// AI Configuration types
export interface AIConfig {
  id: number;
  tenant_id?: number;
  provider_name: string;
  provider_url?: string;
  api_key?: string;
  model_name: string;
  is_active: boolean;
  is_default: boolean;
  tested: boolean;
  ocr_enabled: boolean;
  max_tokens: number;
  temperature: number;
  usage_count: number;
  last_used_at?: string;
  created_at: string;
  updated_at: string;
}

export interface AIConfigCreate {
  provider_name: string;
  provider_url?: string;
  api_key?: string;
  model_name: string;
  is_active?: boolean;
  is_default?: boolean;
  tested?: boolean;
  ocr_enabled?: boolean;
  max_tokens?: number;
  temperature?: number;
}

export interface AIConfigUpdate {
  provider_name?: string;
  provider_url?: string;
  api_key?: string;
  model_name?: string;
  is_active?: boolean;
  is_default?: boolean;
  tested?: boolean;
  ocr_enabled?: boolean;
  max_tokens?: number;
  temperature?: number;
}

export interface AIConfigTestRequest {
  custom_prompt?: string;
  test_text?: string;
}

export interface AIConfigTestResponse {
  success: boolean;
  message: string;
  response_time_ms?: number;
  response?: string;
  error?: string;
}

export interface AIConfigTestWithOverrides {
  config_id?: number;
  provider_name?: string;
  provider_url?: string;
  api_key?: string;
  model_name?: string;
  max_tokens?: number;
  temperature?: number;
  custom_prompt?: string;
  test_text?: string;
}

export interface AIProviderInfo {
  name: string;
  display_name: string;
  description: string;
  website?: string;
  models: string[];
  supports_ocr: boolean;
  requires_api_key: boolean;
  default_model: string;
  default_max_tokens: number;
}

export interface SyncStatus {
  local_fingerprint: string;
  storage_identity: any;
  is_in_sync: boolean | null;
  remote_status: string;
  timestamp: string;
  remote_fingerprint?: string;
  remote_storage_identity?: any;
  suggest_skip_attachments?: string;
}

export interface TaxIntegrationStatus {
  enabled: boolean;
  configured: boolean;
  connection_tested: boolean;
  last_test_result?: string;
}

// Prompt Improvement types
export interface PromptImprovementJob {
  job_id: number;
  status: string;
  prompt_name?: string;
  prompt_category?: string;
  current_iteration: number;
  max_iterations: number;
  iteration_log?: Array<{
    iteration: number;
    prompt_preview: string;
    evaluation: 'pass' | 'fail';
    reason: string;
  }>;
  result_summary?: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface StartImprovementRequest {
  message: string;
  document_id?: number;
  document_type?: 'invoice' | 'expense' | 'bank_statement' | 'portfolio';
}

export const promptImprovementApi = {
  startJob: (req: StartImprovementRequest) =>
    apiRequest<PromptImprovementJob>('/prompts/improve', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
  getJob: (id: number) =>
    apiRequest<PromptImprovementJob>(`/prompts/improve/${id}`),
  listJobs: (limit = 10) =>
    apiRequest<PromptImprovementJob[]>(`/prompts/improve?limit=${limit}`),
};

// Settings API methods
export const settingsApi = {
  getSettings: () => apiRequest<Settings>("/settings/"),
  getSharingSettings: () => apiRequest<SharingSettings>("/settings/sharing"),
  updateSettings: (settings: Partial<Settings>) =>
    apiRequest<Settings>("/settings/", {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  getSetting: (key: string) => apiRequest<{ key: string; value: any }>(`/settings/value/${key}`),
  updateSetting: (key: string, value: any) =>
    apiRequest<{ key: string; value: any }>(`/settings/value/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    }),
  getNotificationSettings: () => apiRequest<any>("/notifications/settings"),
  updateNotificationSettings: (settings: any) =>
    apiRequest<any>("/notifications/settings", {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  testNotification: () => apiRequest<any>("/notifications/test", { method: 'POST' }),
  sendExpenseDigest: (force = true) =>
    apiRequest<any>(`/notifications/expense-digest/send?force=${force}`, { method: 'POST' }),
  testEmailConfiguration: (testEmail: string, config?: any) =>
    apiRequest<any>("/email/test", {
      method: 'POST',
      body: JSON.stringify({
        test_email: testEmail,
        ...(config ? { config } : {}),
      }),
    }),
  exportData: async () => {
    const response = await fetch(`${API_BASE_URL}/settings/export-data`, {
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error('Failed to export data');
    }

    // Get filename from response headers or create a default one
    const contentDisposition = response.headers.get('content-disposition');
    let filename = `data_export_${new Date().toISOString().split('T')[0]}.sqlite`;

    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
      if (filenameMatch) {
        filename = filenameMatch[1];
      }
    }

    // Create blob and download
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },
  importData: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/settings/import-data`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to import data');
    }

    return await response.json();
  },
};

export const syncApi = {
  getStatus: (url?: string, apiKey?: string) => {
    const params = new URLSearchParams();
    if (url) params.set('remote_url', url);
    if (apiKey) params.set('remote_api_key', apiKey);
    const queryString = params.toString();
    return apiRequest<SyncStatus>(`/sync/status${queryString ? `?${queryString}` : ''}`);
  },
  push: (url: string, apiKey: string, includeAttachments: boolean = true) => {
    const params = new URLSearchParams({
      remote_url: url,
      remote_api_key: apiKey,
      include_attachments: includeAttachments.toString(),
    });
    return apiRequest<{ message: string; remote_response: any }>(`/sync/push?${params.toString()}`, {
      method: 'POST',
    });
  },
};

// AI Configuration API methods
export const aiConfigApi = {
  getAIConfigs: () => apiRequest<AIConfig[]>("/ai-config/"),
  getAIConfig: (id: number) => apiRequest<AIConfig>(`/ai-config/${id}`),
  createAIConfig: (config: AIConfigCreate) =>
    apiRequest<AIConfig>("/ai-config/", {
      method: 'POST',
      body: JSON.stringify(config),
    }),
  updateAIConfig: (id: number, config: AIConfigUpdate) =>
    apiRequest<AIConfig>(`/ai-config/${id}`, {
      method: 'PUT',
      body: JSON.stringify(config),
    }),
  deleteAIConfig: (id: number) =>
    apiRequest(`/ai-config/${id}`, {
      method: 'DELETE',
    }),
  testAIConfig: (id: number, testRequest?: AIConfigTestRequest) =>
    apiRequest<AIConfigTestResponse>(`/ai-config/${id}/test`, {
      method: 'POST',
      body: JSON.stringify(testRequest || {}),
    }),
  testAIConfigWithOverrides: (testRequest: AIConfigTestWithOverrides) =>
    apiRequest<AIConfigTestResponse>(`/ai-config/test-with-overrides`, {
      method: 'POST',
      body: JSON.stringify(testRequest),
    }),
  getSupportedProviders: () => apiRequest<{ providers: Record<string, AIProviderInfo>, count: number }>("/ai-config/providers"),
  getConfigUsage: (id: number) => apiRequest<{
    config_id: number,
    usage_count: number,
    last_used_at?: string,
    created_at: string,
    updated_at: string
  }>(`/ai-config/${id}/usage`),
  markAsTested: (id: number) =>
    apiRequest<{ message: string }>(`/ai-config/mark-tested/${id}`, {
      method: 'POST',
    }),
  triggerFullReview: () => apiRequest<{
    success: boolean;
    message: string;
    counts: { invoices: number; expenses: number; statements: number }
  }>(`/ai-config/trigger-full-review`, { method: 'POST' }),
  getReviewProgress: () => apiRequest<{
    invoices: { stats: Record<string, number>; total: number; completed: number; progress_percent: number };
    expenses: { stats: Record<string, number>; total: number; completed: number; progress_percent: number };
    statements: { stats: Record<string, number>; total: number; completed: number; progress_percent: number };
    overall_progress_percent: number;
  }>(`/ai-config/review-progress`, { method: 'GET' }),
  cancelFullReview: () => apiRequest<{
    success: boolean;
    message: string;
  }>(`/ai-config/cancel-full-review`, { method: 'POST' }),
};

// AI Assistant API methods
export const aiApi = {
  analyzePatterns: () => apiRequest<{ success: boolean, data: any }>("/ai/analyze-patterns"),
  suggestActions: () => apiRequest<{ success: boolean, data: any }>("/ai/suggest-actions"),
  chat: (message: string, configId: number) =>
    apiRequest<{ success: boolean, data: any }>("/ai/chat", {
      method: 'POST',
      body: JSON.stringify({ message, config_id: configId }),
    }),
};

// Tenant API methods
export const tenantApi = {
  getTenantInfo: () => apiRequest<{
    id: number;
    name: string;
    default_currency: string;
    email: string;
    phone?: string;
    address?: string;
    tax_id?: string;
    company_logo_url?: string;
    enable_ai_assistant: boolean;
    is_active: boolean;
    created_at: string;
    updated_at: string;
  }>("/tenants/me", { method: 'GET' }, { skipTenant: true }),
};

// Generic API client for direct calls
export const api = {
  get: <T>(url: string, config?: { isLogin?: boolean }) => apiRequest<T>(url, { method: 'GET' }, config),
  post: <T>(url: string, data?: any, config?: { isLogin?: boolean }) => apiRequest<T>(url, { method: 'POST', body: JSON.stringify(data) }, config),
  put: <T>(url: string, data?: any, config?: { isLogin?: boolean }) => apiRequest<T>(url, { method: 'PUT', body: JSON.stringify(data) }, config),
  patch: <T>(url: string, data?: any, config?: { isLogin?: boolean }) => apiRequest<T>(url, { method: 'PATCH', body: JSON.stringify(data) }, config),
  delete: <T>(url: string, config?: { isLogin?: boolean }) => apiRequest<T>(url, { method: 'DELETE' }, config),
};

// Export apiClient as alias for api for compatibility
export const apiClient = api;

export const superAdminApi = {
  demoteSuperAdmin: async (email: string) => {
    return apiRequest<{ message: string }>("/super-admin/demote", {
      method: "POST",
      body: JSON.stringify({ email }),
    }, { skipTenant: true });
  },
  toggleUserStatus: async (userId: number) => {
    return apiRequest<{ message: string }>(`/super-admin/users/${userId}/toggle-status`, {
      method: "PATCH",
    }, { skipTenant: true });
  },
  resetUserPassword: async (userId: number, newPassword: string, forceReset: boolean = false) => {
    return apiRequest<{ message: string }>(`/super-admin/users/${userId}/reset-password`, {
      method: "POST",
      body: JSON.stringify({
        new_password: newPassword,
        confirm_password: newPassword,
        force_reset_on_login: forceReset
      }),
    }, { skipTenant: true });
  },
  disableUserMFA: async (userId: number) => {
    return apiRequest<{ message: string }>(`/super-admin/users/${userId}/disable-mfa`, {
      method: "POST",
    }, { skipTenant: true });
  },

  // Licensing & Capacity Control
  getTenantLicenseMonitoring: async () => {
    return apiRequest<any[]>("/license/tenants", {
      method: "GET"
    }, { skipTenant: true });
  },
  getUserLicenseMonitoring: async () => {
    return apiRequest<any[]>("/license/monitoring/users", {
      method: "GET"
    }, { skipTenant: true });
  },
  updateUserCapacityControl: async (userId: number, counts: boolean) => {
    return apiRequest<{ success: boolean }>(`/license/monitoring/users/${userId}/update-capacity-control`, {
      method: "POST",
      body: JSON.stringify({ counts })
    }, { skipTenant: true });
  },
  updateTenantCapacityControl: async (tenantId: number, counts: boolean) => {
    return apiRequest<{ success: boolean }>(`/license/tenants/${tenantId}/update-capacity-control`, {
      method: "POST",
      body: JSON.stringify({ counts })
    }, { skipTenant: true });
  },
  activateGlobalLicense: async (licenseKey: string) => {
    return apiRequest<any>("/license/activate-global", {
      method: "POST",
      body: JSON.stringify({ license_key: licenseKey })
    }, { skipTenant: true });
  },
  deactivateGlobalLicense: async () => {
    return apiRequest<any>("/license/deactivate-global", {
      method: "POST"
    }, { skipTenant: true });
  },
  getGlobalSignupSettings: async () => {
    return apiRequest<{
      allow_password_signup: boolean;
      allow_sso_signup: boolean;
      max_tenants: number;
      current_tenants_count: number;
    }>("/super-admin/global-signup-settings", {
      method: "GET"
    }, { skipTenant: true });
  },
  updateGlobalSignupSettings: async (settings: { allow_password_signup?: boolean; allow_sso_signup?: boolean }) => {
    return apiRequest<{ message: string }>("/super-admin/global-signup-settings", {
      method: "PATCH",
      body: JSON.stringify(settings)
    }, { skipTenant: true });
  },
};
