import { toast } from 'sonner';
import { API_BASE_URL, apiRequest } from './_base';

// Report error handling types
export interface ReportError {
  error_code: string;
  message: string;
  details?: Record<string, any>;
  suggestions?: string[];
  field?: string;
  retryable?: boolean;
}

export interface ReportApiError extends Error {
  status?: number;
  error_code?: string;
  details?: Record<string, any>;
  suggestions?: string[];
  retryable?: boolean;
}

// Report types and interfaces
export interface ReportFilters {
  date_from?: string;
  date_to?: string;
  client_ids?: number[];
  currency?: string;
  status?: string[];
  amount_min?: number;
  amount_max?: number;
  categories?: string[];
  labels?: string[];
  payment_methods?: string[];
  include_items?: boolean;
  include_attachments?: boolean;
  include_unmatched?: boolean;
  include_reconciliation?: boolean;
  account_ids?: number[];
  transaction_types?: string[];
  vendor?: string;
  balance_min?: number;
  balance_max?: number;
  include_inactive?: boolean;
  is_recurring?: boolean;
  // Inventory-specific filters
  category_ids?: number[];
  item_type?: string[];
  date_filter_type?: string;
  value_min?: number;
  value_max?: number;
  low_stock_only?: boolean;
}

export interface ReportGenerateRequest {
  report_type: 'client' | 'invoice' | 'payment' | 'expense' | 'statement' | 'inventory';
  filters: ReportFilters;
  columns?: string[];
  export_format: 'pdf' | 'csv' | 'excel' | 'json';
  template_id?: number;
}

export interface ReportPreviewRequest {
  report_type: 'client' | 'invoice' | 'payment' | 'expense' | 'statement' | 'inventory';
  filters: ReportFilters;
  limit?: number;
}

export interface ReportTemplate {
  id: number;
  name: string;
  report_type: 'client' | 'invoice' | 'payment' | 'expense' | 'statement' | 'inventory';
  filters: ReportFilters;
  columns?: string[];
  formatting?: Record<string, any>;
  is_shared: boolean;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface ReportTemplateCreate {
  name: string;
  report_type: 'client' | 'invoice' | 'payment' | 'expense' | 'statement' | 'inventory';
  filters: ReportFilters;
  columns?: string[];
  formatting?: Record<string, any>;
  is_shared?: boolean;
}

export interface ReportData {
  report_type: string;
  summary: {
    total_records: number;
    total_amount?: number;
    currency?: string;
    date_range?: { date_from?: string; date_to?: string };
    key_metrics: Record<string, any>;
  };
  data: Record<string, any>[];
  metadata: {
    generated_at: string;
    generated_by: number;
    export_format: string;
    file_size?: number;
    generation_time?: number;
  };
  filters: ReportFilters;
}

export interface ReportResult {
  success: boolean;
  report_id?: number;
  data?: ReportData;
  file_path?: string;
  download_url?: string;

  // Enhanced error handling fields
  error_message?: string;
  error_code?: string;
  error_details?: Record<string, any>;
  suggestions?: string[];
  retryable?: boolean;

  // Retry and performance information
  retry_attempts?: number;
  generation_time?: number;
  circuit_breaker_triggered?: boolean;
}

export interface ReportHistory {
  id: number;
  report_type: string;
  parameters: Record<string, any>;
  status: 'pending' | 'generating' | 'completed' | 'failed';
  error_message?: string;
  template_id?: number;
  generated_by: number;
  file_path?: string;
  generated_at: string;
  expires_at?: string;
}

export interface ScheduleConfig {
  schedule_type: 'daily' | 'weekly' | 'monthly' | 'yearly';
  day_of_week?: number; // 0-6 for weekly
  day_of_month?: number; // 1-31 for monthly
  month?: number; // 1-12 for yearly
  hour?: number; // 0-23
  minute?: number; // 0-59
  timezone?: string;
}

export interface ScheduledReport {
  id: number;
  template_id: number;
  schedule_config: ScheduleConfig;
  recipients: string[];
  is_active: boolean;
  is_balanced: boolean;
  summary: string;
  last_run?: string;
  next_run?: string;
  created_at: string;
  updated_at: string;
  template?: ReportTemplate;
}

export interface ScheduledReportCreate {
  template_id: number;
  schedule_config: ScheduleConfig;
  recipients: string[];
  is_active?: boolean;
}

export interface ScheduledReportUpdate {
  schedule_config?: ScheduleConfig;
  recipients?: string[];
  is_active?: boolean;
}

export interface ReportType {
  type: string;
  name: string;
  description: string;
  available_filters: string[];
  available_columns: string[];
  default_columns: string[];
}

// Report error handling utilities
export const handleReportError = (error: any): ReportApiError => {
  const reportError = new Error() as ReportApiError;

  if (error.detail && typeof error.detail === 'object') {
    // Handle structured error response from backend
    reportError.message = error.detail.message || 'An error occurred';
    reportError.error_code = error.detail.error_code;
    reportError.details = error.detail.details;
    reportError.suggestions = error.detail.suggestions;
    reportError.retryable = error.detail.retryable;
  } else if (typeof error.detail === 'string') {
    // Handle simple string error
    reportError.message = error.detail;
  } else {
    // Handle generic error
    reportError.message = error.message || 'An unexpected error occurred';
  }

  reportError.status = error.status;
  return reportError;
};

export const getReportErrorMessage = (error: ReportApiError): string => {
  // Return user-friendly error messages based on error codes
  const errorMessages: Record<string, string> = {
    'REPORT_001': 'Invalid report type selected. Please choose a valid report type.',
    'VALIDATION_001': 'Invalid date range. Please check your start and end dates.',
    'VALIDATION_003': 'Invalid filters provided. Please check your filter values.',
    'VALIDATION_004': 'One or more selected clients could not be found.',
    'VALIDATION_005': 'Invalid amount range. Please check your minimum and maximum amounts.',
    'VALIDATION_006': 'Invalid currency selected. Please choose a valid currency.',
    'VALIDATION_007': 'Invalid export format selected.',
    'TEMPLATE_001': 'Report template not found.',
    'TEMPLATE_003': 'You do not have permission to access this template.',
    'TEMPLATE_004': 'A template with this name already exists.',
    'SCHEDULE_001': 'Invalid schedule configuration.',
    'SCHEDULE_004': 'Scheduled report not found.',
    'EXPORT_001': 'Export format not supported.',
    'REPORT_004': 'Report generation failed. Please try again.',
    'REPORT_007': 'Report generation timed out. Please try with smaller date range.',
  };

  if (error.error_code && errorMessages[error.error_code]) {
    return errorMessages[error.error_code];
  }

  return error.message || 'An unexpected error occurred';
};

export const showReportError = (error: ReportApiError) => {
  const message = getReportErrorMessage(error);

  // Show suggestions if available
  if (error.suggestions && error.suggestions.length > 0) {
    const suggestionText = error.suggestions.join(' ');
    toast.error(`${message} ${suggestionText}`);
  } else {
    toast.error(message);
  }

  // Log detailed error for debugging
  console.error('Report API Error:', {
    code: error.error_code,
    message: error.message,
    details: error.details,
    suggestions: error.suggestions,
    retryable: error.retryable
  });
};

// Report API methods
export const reportApi = {
  getReportTypes: async () => {
    try {
      return await apiRequest<{ report_types: ReportType[] }>("/reports/types");
    } catch (error) {
      const reportError = handleReportError(error);
      showReportError(reportError);
      throw reportError;
    }
  },

  generateReport: async (request: ReportGenerateRequest) => {
    try {
      return await apiRequest<ReportResult>("/reports/generate", {
        method: 'POST',
        body: JSON.stringify(request),
      });
    } catch (error) {
      const reportError = handleReportError(error);
      showReportError(reportError);
      throw reportError;
    }
  },

  previewReport: async (request: ReportPreviewRequest) => {
    try {
      return await apiRequest<ReportData>("/reports/preview", {
        method: 'POST',
        body: JSON.stringify(request),
      });
    } catch (error) {
      const reportError = handleReportError(error);
      showReportError(reportError);
      throw reportError;
    }
  },

  // Template management
  getTemplates: () => apiRequest<{ templates: ReportTemplate[]; total: number }>("/reports/templates"),

  getTemplate: (id: number) => apiRequest<ReportTemplate>(`/reports/templates/${id}`),

  createTemplate: (template: ReportTemplateCreate) =>
    apiRequest<ReportTemplate>("/reports/templates", {
      method: 'POST',
      body: JSON.stringify(template),
    }),

  updateTemplate: (id: number, template: Partial<ReportTemplateCreate>) =>
    apiRequest<ReportTemplate>(`/reports/templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(template),
    }),

  deleteTemplate: (id: number) =>
    apiRequest(`/reports/templates/${id}`, {
      method: 'DELETE',
    }),

  // Report history
  getHistory: (limit?: number, offset?: number, reportType?: string, status?: string) => {
    const params = new URLSearchParams();
    if (limit) params.set('limit', limit.toString());
    if (offset) params.set('offset', offset.toString());
    if (reportType) params.set('report_type', reportType);
    if (status) params.set('status', status);
    return apiRequest<{ reports: ReportHistory[]; total: number }>(`/reports/history${params.toString() ? `?${params.toString()}` : ''}`);
  },

  regenerateReport: (reportId: number, newParameters?: any) =>
    apiRequest<ReportResult>(`/reports/regenerate/${reportId}`, {
      method: 'POST',
      body: JSON.stringify(newParameters || {}),
    }),

  deleteReport: (reportId: number) =>
    apiRequest(`/reports/history/${reportId}`, {
      method: 'DELETE',
    }),

  shareReport: (reportId: number, shareSettings: any) =>
    apiRequest<{ shareUrl: string; shareId: string }>(`/reports/share/${reportId}`, {
      method: 'POST',
      body: JSON.stringify(shareSettings),
    }),

  downloadReport: async (reportId: number) => {
    try {
      const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
        try { const user = JSON.parse(localStorage.getItem('user') || '{}'); return user.tenant_id?.toString(); } catch { return undefined; }
      })();

      const headers: Record<string, string> = {};
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const downloadUrl = `${API_BASE_URL}/reports/download/${reportId}`;
      const response = await fetch(downloadUrl, { method: 'GET', headers, credentials: 'include' });

      if (response.status === 401) {
        localStorage.removeItem('user');
        localStorage.removeItem('selected_tenant_id');
        window.location.replace('/login');
        throw new Error('Authentication failed. Please log in again.');
      }

      if (!response.ok) {
        throw new Error(`Download failed: ${response.status} ${response.statusText}`);
      }

      return response;
    } catch (error) {
      console.error('Download report error:', error);
      throw error;
    }
  },

  // Scheduled reports
  getScheduledReports: (activeOnly?: boolean) => {
    const params = new URLSearchParams();
    if (activeOnly) params.set('active_only', 'true');
    return apiRequest<{ scheduled_reports: ScheduledReport[]; total: number }>(`/reports/scheduled${params.toString() ? `?${params.toString()}` : ''}`);
  },

  createScheduledReport: (scheduledReport: ScheduledReportCreate) =>
    apiRequest<ScheduledReport>("/reports/scheduled", {
      method: 'POST',
      body: JSON.stringify(scheduledReport),
    }),

  updateScheduledReport: (id: number, scheduledReport: ScheduledReportUpdate) =>
    apiRequest<ScheduledReport>(`/reports/scheduled/${id}`, {
      method: 'PUT',
      body: JSON.stringify(scheduledReport),
    }),

  deleteScheduledReport: (id: number) =>
    apiRequest(`/reports/scheduled/${id}`, {
      method: 'DELETE',
    }),
};
