import { toast } from 'sonner';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';

// API base URL comes from env var. Set VITE_API_URL in your environment.
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Type definitions
export interface Client {
  id: number;
  name: string;
  email: string;
  phone: string;
  address: string;
  balance: number;
  paid_amount: number;
  outstanding_balance?: number;
  preferred_currency?: string;
  created_at: string;
  updated_at: string;
}

export interface ClientNote {
  id: number;
  note: string;
  user_id: number;
  client_id: number;
  created_at: string;
  updated_at: string;
}

export interface InvoiceItem {
  id?: number;
  description: string;
  quantity: number;
  price: number;
  amount: number;
  invoice_id?: number;
}

export type InvoiceStatus = "draft" | "pending" | "paid" | "overdue" | "partially_paid";

export interface Invoice {
  id: number;
  number: string;
  client_id: number;
  client_name: string;
  client_email: string;
  date: string;
  due_date: string;
  amount: number;
  currency?: string;
  paid_amount: number;
  status: InvoiceStatus;
  notes?: string;
  items: InvoiceItem[];
  created_at: string;
  updated_at: string;
  is_recurring?: boolean;
  recurring_frequency?: string;
  discount_type?: string;
  discount_value?: number;
  subtotal?: number;
  custom_fields?: Record<string, any>;
  show_discount_in_pdf?: boolean; // New property added
  has_attachment?: boolean;
  attachment_filename?: string;
}

export const linkApi = {
  // Simple invoice list for selectors
  getInvoicesBasic: async () => {
    const list = await invoiceApi.getInvoicesWithParams({ limit: 1000 });
    // Map to minimal data
    return list.map(inv => ({ id: inv.id, number: inv.number, client_name: inv.client_name, amount: inv.amount, status: inv.status }));
  },
};

export interface Payment {
  id: number;
  invoice_id: number;
  invoice_number: string;
  client_name: string;
  amount: number;
  currency?: string;
  payment_date: string;
  payment_method: string;
  reference_number?: string;
  notes?: string;
  status: 'completed' | 'pending' | 'failed';
  tenant_id: number;
  created_at: string;
  updated_at: string;
}

export interface Expense {
  id: number;
  amount: number;
  currency?: string;
  expense_date: string;
  category: string;
  vendor?: string;
  labels?: string[];
  tax_rate?: number;
  tax_amount?: number;
  total_amount?: number;
  payment_method?: string;
  reference_number?: string;
  status: string;
  notes?: string;
  receipt_filename?: string;
  attachments_count?: number;
  invoice_id?: number | null;
  created_at: string;
  updated_at: string;
  imported_from_attachment?: boolean;
  analysis_status?: 'not_started' | 'queued' | 'processing' | 'done' | 'failed' | 'cancelled';
  manual_override?: boolean;
}

export interface ExpenseAttachmentMeta {
  id: number;
  filename: string;
  content_type?: string;
  size_bytes?: number;
  uploaded_at?: string;
}

export interface BankTransactionEntry {
  id?: number;
  date: string;
  description: string;
  amount: number;
  transaction_type: 'debit' | 'credit';
  balance?: number | null;
  category?: string | null;
  invoice_id?: number | null;
  expense_id?: number | null;
}

export interface BankStatementSummary {
  id: number;
  original_filename: string;
  stored_filename: string;
  file_path: string;
  status: string;
  extracted_count: number;
  labels?: string[] | null;
  notes?: string | null;
  created_at?: string;
}

export interface BankStatementDetail extends BankStatementSummary {
  transactions: BankTransactionEntry[];
}

export const bankStatementApi = {
  uploadAndExtract: async (
    files: File[]
  ): Promise<{ success: boolean; statements: BankStatementSummary[] }> => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
      try { const user = JSON.parse(localStorage.getItem('user') || '{}'); return user.tenant_id?.toString(); } catch { return undefined; }
    })();

    const formData = new FormData();
    files.slice(0, 12).forEach((f) => formData.append('files', f));

    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const url = `${API_BASE_URL}/bank-statements/upload`;
    const resp = await fetch(url, { method: 'POST', headers, body: formData });
    const text = await resp.text();
    if (!resp.ok) {
      try { throw new Error(JSON.parse(text).detail || 'Failed to process bank statements'); }
      catch { throw new Error(text || 'Failed to process bank statements'); }
    }
    return JSON.parse(text);
  },

  list: async (): Promise<BankStatementSummary[]> => {
    const data = await apiRequest<{ success: boolean; statements: BankStatementSummary[] }>(
      '/bank-statements',
      { method: 'GET' }
    );
    return data.statements;
  },

  get: async (statementId: number): Promise<BankStatementDetail> => {
    const data = await apiRequest<{ success: boolean; statement: BankStatementDetail }>(
      `/bank-statements/${statementId}`,
      { method: 'GET' }
    );
    return data.statement;
  },

  updateMeta: async (
    statementId: number,
    updates: { labels?: string[] | null; notes?: string | null }
  ): Promise<{ success: boolean; statement: BankStatementSummary }> => {
    return apiRequest<{ success: boolean; statement: BankStatementSummary }>(
      `/bank-statements/${statementId}`,
      { method: 'PUT', body: JSON.stringify(updates) }
    );
  },

  replaceTransactions: async (
    statementId: number,
    transactions: BankTransactionEntry[]
  ): Promise<{ success: boolean; updated_count: number }> => {
    return apiRequest<{ success: boolean; updated_count: number }>(
      `/bank-statements/${statementId}/transactions`,
      { method: 'PUT', body: JSON.stringify({ transactions }) }
    );
  },

  reprocess: async (statementId: number): Promise<{ success: boolean; message: string }> => {
    return apiRequest<{ success: boolean; message: string }>(
      `/bank-statements/${statementId}/reprocess`,
      { method: 'POST' }
    );
  },

  // Build URLs for preview/download (relative if API_BASE_URL is relative)
  fileUrl: (statementId: number, inline = true): string => {
    const base = API_BASE_URL.replace(/\/$/, '');
    return `${base}/bank-statements/${statementId}/file${inline ? '?inline=true' : ''}`;
  },

  fetchFileBlob: async (
    statementId: number,
    inline = true
  ): Promise<{ blob: Blob; filename: string }> => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
      try { const user = JSON.parse(localStorage.getItem('user') || '{}'); return user.tenant_id?.toString(); } catch { return undefined; }
    })();
    const base = API_BASE_URL.replace(/\/$/, '');
    const url = `${base}/bank-statements/${statementId}/file${inline ? '?inline=true' : ''}`;
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (tenantId) headers['X-Tenant-ID'] = tenantId;
    const resp = await fetch(url, { method: 'GET', headers });
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      throw new Error(text || `Failed to fetch file (${resp.status})`);
    }
    const cd = resp.headers.get('content-disposition') || '';
    const ct = resp.headers.get('content-type') || '';
    let filename = `statement-${statementId}.pdf`;
    try {
      const m = cd.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
      const raw = decodeURIComponent((m?.[1] || m?.[2] || '').trim());
      if (raw) filename = raw;
    } catch { /* noop */ }
    const blob = await resp.blob();
    const type = ct || blob.type || 'application/pdf';
    const pdfBlob = blob.type === type ? blob : new Blob([blob], { type });
    return { blob: pdfBlob, filename };
  },

  delete: async (statementId: number): Promise<void> => {
    await apiRequest<{ success: boolean }>(
      `/bank-statements/${statementId}`,
      { method: 'DELETE' }
    );
  },
};

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

export interface Settings {
  company_info: CompanyInfo;
  invoice_settings: InvoiceSettings;
  enable_ai_assistant?: boolean;
}

// AI Configuration types
export interface AIConfig {
  id: number;
  provider_name: string;
  provider_url?: string;
  api_key?: string;
  model_name: string;
  is_active: boolean;
  is_default: boolean;
  tested: boolean;
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
}

export interface AIConfigUpdate {
  provider_name?: string;
  provider_url?: string;
  api_key?: string;
  model_name?: string;
  is_active?: boolean;
  is_default?: boolean;
  tested?: boolean;
}

// Discount rule types
export interface DiscountRule {
  id: number;
  name: string;
  min_amount: number;
  discount_type: 'percentage' | 'fixed';
  discount_value: number;
  is_active: boolean;
  priority: number;
  created_at: string;
  updated_at: string;
  currency: string;
}

export interface DiscountRuleCreate {
  name: string;
  min_amount: number;
  discount_type: 'percentage' | 'fixed';
  discount_value: number;
  is_active?: boolean;
  priority?: number;
  currency: string;
}

export interface DiscountRuleUpdate {
  name?: string;
  min_amount?: number;
  discount_type?: 'percentage' | 'fixed';
  discount_value?: number;
  is_active?: boolean;
  priority?: number;
  currency?: string;
}

export interface DiscountCalculation {
  discount_type: 'percentage' | 'fixed' | 'none';
  discount_value: number;
  discount_amount: number;
  applied_rule?: {
    id: number;
    name: string;
    min_amount: number;
  };
}

export interface InvoiceHistory {
  id: number;
  invoice_id: number;
  tenant_id: number;
  user_id: number;
  action: string;
  details?: string;
  previous_values?: Record<string, any>;
  current_values?: Record<string, any>;
  created_at: string;
  user_name?: string;
}

export interface InvoiceHistoryCreate {
  invoice_id: number;
  tenant_id: number;
  user_id: number;
  action: string;
  details?: string;
  previous_values?: Record<string, any>;
  current_values?: Record<string, any>;
}

// Generic API request function with error handling
export async function apiRequest<T>(
  url: string,
  options: RequestInit = {},
  config: { isLogin?: boolean; skipTenant?: boolean } = {}
): Promise<T> {
  try {
    // Get JWT token from localStorage
    const token = localStorage.getItem('token');
    // Get tenantId from localStorage - check for selected tenant first, then fallback to user's default
    let tenantId: string | undefined = undefined;
    try {
      // First check if user has selected a specific tenant
      const selectedTenantId = localStorage.getItem('selected_tenant_id');
      if (selectedTenantId) {
        tenantId = selectedTenantId;
        console.log(`🔍 API Request: Using selected tenant ID: ${tenantId} for ${url}`);
      } else {
        // Fallback to user's default tenant
        const userStr = localStorage.getItem('user');
        if (userStr) {
          const user = JSON.parse(userStr);
          if (user && user.tenant_id) {
            tenantId = String(user.tenant_id);
            console.log(`🔍 API Request: Using user's default tenant ID: ${tenantId} for ${url}`);
          }
        }
      }
    } catch (e) {
      console.error('Error parsing user for tenantId:', e);
    }
    
    const requestUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    let extraHeaders: Record<string, string> = {};
    if (options.headers) {
      if (options.headers instanceof Headers) {
        // Convert Headers instance to plain object
        options.headers.forEach((value, key) => {
          extraHeaders[key] = value;
        });
      } else if (typeof options.headers === 'object' && !Array.isArray(options.headers)) {
        extraHeaders = options.headers as Record<string, string>;
      }
    }
    const headers: Record<string, string> = {
      ...(token && { 'Authorization': `Bearer ${token}` }),
      ...extraHeaders,
    };
    
    // Only set Content-Type for non-FormData requests
    // FormData requests need the browser to set Content-Type with boundary
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }
    if (!config.skipTenant && tenantId) {
      headers['X-Tenant-ID'] = tenantId;
      console.log(`🔄 API Request: ${requestUrl} with X-Tenant-ID: ${tenantId}`);
    } else if (!config.skipTenant) {
      console.warn(`⚠️ No tenant ID available for request to ${requestUrl}`);
      console.log('Debug info:', { 
        selectedTenantId: localStorage.getItem('selected_tenant_id'),
        userTenantId: (() => {
          try {
            const user = JSON.parse(localStorage.getItem('user') || '{}');
            return user.tenant_id;
          } catch { return 'parse error'; }
        })()
      });
    }
    const response = await fetch(requestUrl, {
      ...options,
      headers,
    });

    console.log('API Response status:', response.status);
    console.log('API Response headers:', Object.fromEntries(response.headers.entries()));
    
    // Log the raw response text for debugging
    const responseText = await response.text();
    // console.log('API Raw response text:', responseText);
    
    if (!response.ok) {
      // Try to parse error response
      let errorData;
      try {
        errorData = JSON.parse(responseText);
        console.log('API Error response:', errorData);
      } catch (e) {
        // If JSON parsing fails, use status text
        console.log('API Error - could not parse JSON:', e);
        throw new Error(`Error: ${response.status} ${response.statusText}`);
      }

      // Handle authentication errors
      if (!config.isLogin && response.status === 401) {
        // Only log out on 401 (unauthorized) - token is invalid/expired
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        localStorage.removeItem('selected_tenant_id');
        // Show toast and redirect to login
        toast.error('Session expired. Please log in again.');
        // Use window.location.replace for reliability
        window.location.replace('/login');
        throw new Error('Authentication failed. Please log in again.');
      }
      
      // Handle 403 (forbidden) errors - could be permission or tenant context issues
      if (response.status === 403) {
        // Check if it's a tenant context error
        if (errorData.detail && errorData.detail.includes('Tenant context required')) {
          // This is a session/tenant context issue - log out the user
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          localStorage.removeItem('selected_tenant_id');
          toast.error('Session expired. Please log in again.');
          window.location.replace('/login');
          throw new Error('Session expired. Please log in again.');
        } else {
          // User is authenticated but lacks permissions - don't log out
          console.log('403 Forbidden - User lacks permissions for this resource');
          throw new Error(errorData.detail || 'Access denied. You do not have permission to access this resource.');
        }
      }

      // Handle 400 errors that might be tenant context issues
      if (response.status === 400 && errorData.detail && errorData.detail.includes('Tenant context required')) {
        // This is a session/tenant context issue - log out the user
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        localStorage.removeItem('selected_tenant_id');
        toast.error('Session expired. Please log in again.');
        window.location.replace('/login');
        throw new Error('Session expired. Please log in again.');
      }

      // Better handle validation errors (422)
      if (response.status === 422 && errorData.detail) {
        // Format validation errors nicely
        if (Array.isArray(errorData.detail)) {
          // Format validation errors from FastAPI
          const errorMessages = errorData.detail.map((err: any) => {
            const field = err.loc.slice(1).join('.');
            return `${field}: ${err.msg}`;
          }).join('; ');
          
          console.error('Validation error:', errorMessages);
          throw new Error(`Validation error: ${errorMessages}`);
        } else {
          // Handle other error detail formats
          console.error('API error:', errorData.detail);
          throw new Error(String(errorData.detail));
        }
      }

      // Handle other errors
      const errorMessage = errorData.detail || `Error: ${response.status} ${response.statusText}`;
      throw new Error(errorMessage);
    }

    // For DELETE requests with 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    // Parse the response text as JSON
    let responseData;
    try {
      responseData = JSON.parse(responseText) as T;
    } catch (e) {
      console.log('API Success response is not valid JSON:', e);
      throw new Error('Invalid JSON response from server');
    }
    
    console.log('API Success response:', responseData);
    console.log('API Response type:', typeof responseData);
    console.log('API Response keys:', Object.keys(responseData || {}));
    return responseData;
  } catch (error) {
    console.error('API request failed:', error);
    // const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    // toast.error(`Request failed: ${errorMessage}`);
    throw error;
  }
}

// Helper to get i18n error message from backend error code
export function getErrorMessage(error: any, t: (key: string) => string): string {
  // Check if the error message is a known error code
  if (error?.message) {
    const code = error.message;
    // Try to map to i18n error code
    const i18nMsg = t(`errors.${code}`);
    if (i18nMsg && i18nMsg !== `errors.${code}`) {
      return i18nMsg;
    }
    // Fallback to the original error message if no translation is found
    return code;
  }
  // Fallback to generic error
  return t('errors.unknown_error');
}

// Client API methods
export const clientApi = {
  getClients: () => apiRequest<Client[]>("/clients/"),
  getClient: (id: number) => apiRequest<Client>(`/clients/${id}`),
  createClient: (client: Omit<Client, 'id' | 'created_at' | 'updated_at'>) => 
    apiRequest<Client>("/clients/", {
      method: 'POST',
      body: JSON.stringify(client),
    }),
  updateClient: (id: number, client: Partial<Client>) => 
    apiRequest<Client>(`/clients/${id}`, {
      method: 'PUT',
      body: JSON.stringify(client),
    }),
  deleteClient: (id: number) => 
    apiRequest(`/clients/${id}`, {
      method: 'DELETE',
    }),
};

// CRM API methods
export const crmApi = {
    getNotesForClient: (clientId: number) =>
        apiRequest<ClientNote[]>(`/crm/clients/${clientId}/notes`),
    createNoteForClient: (clientId: number, note: { note: string }) =>
        apiRequest<ClientNote>(`/crm/clients/${clientId}/notes`, {
            method: 'POST',
            body: JSON.stringify(note),
        }),
    updateNoteForClient: (clientId: number, noteId: number, note: { note: string }) =>
        apiRequest<ClientNote>(`/crm/clients/${clientId}/notes/${noteId}`, {
            method: 'PUT',
            body: JSON.stringify(note),
        }),
    deleteNoteForClient: (clientId: number, noteId: number) =>
        apiRequest(`/crm/clients/${clientId}/notes/${noteId}`, {
            method: 'DELETE',
        }),
};

// Currency API methods
export const currencyApi = {
    getSupportedCurrencies: () => apiRequest<any>("/currency/supported?active_only=false"),
    createCustomCurrency: (data: any) => apiRequest<any>("/currency/custom", {
        method: 'POST',
        body: JSON.stringify(data),
    }),
    updateCustomCurrency: (id: number, data: any) => apiRequest<any>(`/currency/custom/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }),
    deleteCustomCurrency: (id: number) => apiRequest<any>(`/currency/custom/${id}`, {
        method: 'DELETE',
    }),
};

// Auth API methods
export const authApi = {
  login: (email: string, password: string) =>
    apiRequest<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }, { isLogin: true }),
  register: (userData: any) =>
    apiRequest<any>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    }, { isLogin: true }),
  checkOrganizationNameAvailability: (name: string) =>
    apiRequest<{ available: boolean; name: string }>(`/tenants/check-name-availability?name=${encodeURIComponent(name)}`, {
      method: 'GET',
    }),
  checkEmailAvailability: (email: string) =>
    apiRequest<{ available: boolean; email: string }>(`/auth/check-email-availability?email=${encodeURIComponent(email)}`, {
      method: 'GET',
    }),
  requestPasswordReset: (email: string) =>
    apiRequest<{ message: string; success: boolean }>(`/auth/request-password-reset`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, newPassword: string) =>
    apiRequest<{ message: string; success: boolean }>(`/auth/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),
  activateUser: (inviteId: number, activationData: { password?: string; first_name?: string; last_name?: string }) =>
    apiRequest<any>(`/auth/invites/${inviteId}/activate`, {
      method: 'POST',
      body: JSON.stringify(activationData),
    }),
};

// Invoice API methods
export const invoiceApi = {
  getInvoicesWithParams: async (opts: { status?: string; skip?: number; limit?: number } = {}): Promise<Invoice[]> => {
    try {
      const params = new URLSearchParams();
      if (opts.status) params.set('status_filter', opts.status);
      if (typeof opts.skip === 'number') params.set('skip', String(opts.skip));
      if (typeof opts.limit === 'number') params.set('limit', String(opts.limit));
      const response = await apiRequest<any[]>(`/invoices/${params.toString() ? `?${params.toString()}` : ''}`);
      const mappedInvoices: Invoice[] = response.map(apiInvoice => ({
        id: apiInvoice.id,
        number: apiInvoice.number || '',
        client_id: apiInvoice.client_id,
        client_name: apiInvoice.client_name || '',
        client_email: '',
        date: apiInvoice.created_at || apiInvoice.date || '',
        due_date: apiInvoice.due_date || '',
        amount: apiInvoice.amount || 0,
        currency: apiInvoice.currency || 'USD',
        paid_amount: apiInvoice.total_paid || 0,
        status: apiInvoice.status || 'pending',
        notes: apiInvoice.notes || '',
        items: [],
        created_at: apiInvoice.created_at,
        updated_at: apiInvoice.updated_at,
        is_recurring: apiInvoice.is_recurring,
        recurring_frequency: apiInvoice.recurring_frequency,
        has_attachment: apiInvoice.has_attachment || false,
        attachment_filename: apiInvoice.attachment_filename || undefined,
      }));
      return mappedInvoices;
    } catch (error) {
      console.error('Failed to fetch invoices with params:', error);
      throw error;
    }
  },
  getInvoices: async (status?: string): Promise<Invoice[]> => {
    try {
      const response = await apiRequest<any[]>(`/invoices/${status ? `?status_filter=${status}` : ''}`);
      
      // Map API response to frontend Invoice interface
      const mappedInvoices: Invoice[] = response.map(apiInvoice => ({
        id: apiInvoice.id,
        number: apiInvoice.number || '',
        client_id: apiInvoice.client_id,
        client_name: apiInvoice.client_name || '',
        client_email: '', // API doesn't return this
        date: apiInvoice.created_at || apiInvoice.date || '',
        due_date: apiInvoice.due_date || '',
        amount: apiInvoice.amount || 0,
        currency: apiInvoice.currency || 'USD', // Map currency from API response
        paid_amount: apiInvoice.total_paid || 0, // Map total_paid to paid_amount
        status: apiInvoice.status || 'pending',
        notes: apiInvoice.notes || '',
        items: [], // API doesn't return items for list view
        created_at: apiInvoice.created_at,
        updated_at: apiInvoice.updated_at,
        is_recurring: apiInvoice.is_recurring,
        recurring_frequency: apiInvoice.recurring_frequency,
        has_attachment: apiInvoice.has_attachment || false,
        attachment_filename: apiInvoice.attachment_filename || undefined,
      }));
      
      console.log("Mapped invoices with paid amounts:", mappedInvoices);
      return mappedInvoices;
    } catch (error) {
      console.error('Failed to fetch invoices:', error);
      throw error;
    }
  },
  getInvoice: async (id: number) => {
    try {
      // Get invoice data from API
      const apiResponse = await apiRequest<any>(`/invoices/${id}`);
      
      console.log("API response for invoice:", apiResponse);
      
      // Map API response to frontend Invoice interface
      const invoice: Invoice = {
        id: apiResponse.id,
        number: apiResponse.number || '',
        client_id: apiResponse.client_id,
        client_name: apiResponse.client_name || '',
        client_email: '', // API doesn't return this, we'll need to fetch it separately or leave empty
        date: apiResponse.created_at || apiResponse.date || '', // Use created_at as fallback for date
        due_date: apiResponse.due_date || '',
        amount: apiResponse.amount || 0,
        currency: apiResponse.currency || 'USD', // Map currency from API response
        paid_amount: apiResponse.total_paid || 0, // API returns total_paid, not paid_amount
        status: apiResponse.status || 'pending',
        notes: apiResponse.notes || '',
        items: apiResponse.items && Array.isArray(apiResponse.items) ? apiResponse.items.map((item: any) => ({
          id: item.id,
          description: item.description || '',
          quantity: item.quantity || 1,
          price: item.price || 0,
          amount: item.amount || (item.quantity || 1) * (item.price || 0)
        })) : [],
        created_at: apiResponse.created_at || '',
        updated_at: apiResponse.updated_at || '',
        is_recurring: apiResponse.is_recurring,
        recurring_frequency: apiResponse.recurring_frequency,
        discount_type: apiResponse.discount_type,
        discount_value: apiResponse.discount_value,
        subtotal: apiResponse.subtotal,
        custom_fields: apiResponse.custom_fields,
        show_discount_in_pdf: apiResponse.show_discount_in_pdf || false, // Map show_discount_in_pdf from API response
        has_attachment: apiResponse.has_attachment || false,
        attachment_filename: apiResponse.attachment_filename || undefined,
      };
      
      console.log("🔍 API CLIENT - Raw apiResponse keys:", Object.keys(apiResponse));
      console.log("🔍 API CLIENT - Raw apiResponse:", JSON.stringify(apiResponse, null, 2));
      console.log("🔍 API RESPONSE ATTACHMENT DEBUG:", {
        'raw apiResponse.has_attachment': apiResponse.has_attachment,
        'raw apiResponse.attachment_filename': apiResponse.attachment_filename,
        'typeof has_attachment': typeof apiResponse.has_attachment,
        'typeof attachment_filename': typeof apiResponse.attachment_filename,
        'mapped has_attachment': invoice.has_attachment,
        'mapped attachment_filename': invoice.attachment_filename
      });
      console.log("Mapped invoice object:", invoice);
      
      return invoice;
    } catch (error) {
      console.error("Error fetching invoice:", error);
      throw error;
    }
  },
  createInvoice: (invoiceData: Omit<Invoice, 'id' | 'created_at' | 'updated_at'>) => 
    apiRequest<Invoice>('/invoices/', {
      method: 'POST',
      body: JSON.stringify(invoiceData),
    }),
  updateInvoice: (id: number, invoiceData: Partial<Invoice>) =>
    apiRequest<Invoice>(`/invoices/${id}`, {
      method: 'PUT',
      body: JSON.stringify(invoiceData),
    }),
  cloneInvoice: (id: number) =>
    apiRequest<Invoice>(`/invoices/${id}/clone`, { method: 'POST' }),
  deleteInvoice: (id: number) => 
    apiRequest(`/invoices/${id}`, { method: 'DELETE' }),
  
  // Recycle bin methods
  getDeletedInvoices: () => 
    apiRequest<any[]>('/invoices/recycle-bin'),
  restoreInvoice: (id: number, newStatus: string = 'draft') => 
    apiRequest(`/invoices/${id}/restore`, {
      method: 'POST',
      body: JSON.stringify({ new_status: newStatus }),
    }),
  permanentlyDeleteInvoice: (id: number) => 
    apiRequest(`/invoices/${id}/permanent`, { method: 'DELETE' }),
  emptyRecycleBin: () => 
    apiRequest('/invoices/recycle-bin/empty', { method: 'POST' }),
  
  // Attachment methods
  uploadAttachment: async (invoiceId: number, file: File) => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') || 
      (() => {
        try {
          const user = JSON.parse(localStorage.getItem('user') || '{}');
          return user.tenant_id?.toString();
        } catch { return undefined; }
      })();
    
    const formData = new FormData();
    formData.append('file', file);
    
    const headers: Record<string, string> = {
      'Authorization': `Bearer ${token}`,
    };
    if (tenantId) {
      headers['X-Tenant-ID'] = tenantId;
    }
    
    const uploadUrl = `${API_BASE_URL}/invoices/${invoiceId}/upload-attachment`;
    console.log("🔍 UPLOAD API DEBUG - API_BASE_URL:", API_BASE_URL);
    console.log("🔍 UPLOAD API DEBUG - Calling URL:", uploadUrl);
    console.log("🔍 UPLOAD API DEBUG - Full URL:", uploadUrl);
    console.log("🔍 UPLOAD API DEBUG - Headers:", headers);
    console.log("🔍 UPLOAD API DEBUG - FormData keys:", Array.from(formData.keys()));
    
    const response = await fetch(uploadUrl, {
      method: 'POST',
      headers,
      body: formData,
    });
    
    console.log("🔍 UPLOAD API DEBUG - Response status:", response.status);
    console.log("🔍 UPLOAD API DEBUG - Response ok:", response.ok);
    
    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = 'Failed to upload attachment';
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || errorMessage;
      } catch {
        errorMessage = errorText || errorMessage;
      }
      throw new Error(errorMessage);
    }
    
    const responseText = await response.text();
    try {
      return JSON.parse(responseText);
    } catch (e) {
      console.error('Failed to parse upload response as JSON:', responseText);
      throw new Error('Invalid response from server');
    }
  },
  downloadAttachment: (invoiceId: number) => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') || 
      (() => {
        try {
          const user = JSON.parse(localStorage.getItem('user') || '{}');
          return user.tenant_id?.toString();
        } catch { return undefined; }
      })();
    
    // Create a form to submit with proper headers
    const form = document.createElement('form');
    form.method = 'GET';
    form.action = `${API_BASE_URL}/invoices/${invoiceId}/download-attachment`;
    form.target = '_blank';
    
    // Add token as query parameter since we can't set headers on form submission
    const url = new URL(form.action);
    url.searchParams.set('token', token || '');
    if (tenantId) {
      url.searchParams.set('tenant_id', tenantId);
    }
    form.action = url.toString();
    
    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
  },
  getAttachmentInfo: (invoiceId: number) =>
    apiRequest<{ has_attachment: boolean; filename?: string; content_type?: string; size_bytes?: number }>(`/invoices/${invoiceId}/attachment-info`),
  previewAttachmentBlob: async (invoiceId: number): Promise<Blob> => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
      try {
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        return user.tenant_id?.toString();
      } catch { return undefined; }
    })();

    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const url = `${API_BASE_URL}/invoices/${invoiceId}/preview-attachment`;
    const resp = await fetch(url, { headers });
    if (!resp.ok) {
      const text = await resp.text();
      try { throw new Error(JSON.parse(text).detail || 'Failed to preview'); }
      catch { throw new Error(text || 'Failed to preview'); }
    }
    return await resp.blob();
  },
  
  // Invoice history methods
  getInvoiceHistory: (invoiceId: number) => 
    apiRequest<InvoiceHistory[]>(`/invoices/${invoiceId}/history`),
  
  createInvoiceHistoryEntry: (invoiceId: number, historyEntry: InvoiceHistoryCreate) => 
    apiRequest<InvoiceHistory>(`/invoices/${invoiceId}/history`, {
      method: 'POST',
      body: JSON.stringify(historyEntry),
    }),
};

// Payment API methods
export const paymentApi = {
  getPayments: async () => {
    const response = await apiRequest<{ success: boolean; data: Payment[]; count: number; chart_data: any }>("/payments/");
    return response.data || [];
  },
  getPayment: (id: number) => apiRequest<Payment>(`/payments/${id}`),
  createPayment: (payment: {
    invoice_id: number;
    amount: number;
    payment_date: string;
    payment_method: string;
    reference_number?: string;
    notes?: string;
  }) => 
    apiRequest<Payment>("/payments/", {
      method: 'POST',
      body: JSON.stringify(payment),
    }),
  updatePayment: (id: number, payment: Partial<Payment>) => 
    apiRequest<Payment>(`/payments/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payment),
    }),
  deletePayment: (id: number) => 
    apiRequest(`/payments/${id}`, {
      method: 'DELETE',
    }),
};

// Expense API methods
export const expenseApi = {
  getExpenses: async (category?: string, label?: string) => {
    const params = new URLSearchParams();
    if (category && category !== 'all') params.set('category', category);
    if (label) params.set('label', label);
    const query = params.toString() ? `?${params.toString()}` : '';
    const list = await apiRequest<Expense[]>(`/expenses/${query}`);
    // Normalize category to a known option; fallback to 'General'
    const validCategories = EXPENSE_CATEGORY_OPTIONS;
    return list.map(e => ({
      ...e,
      category: validCategories.includes(e.category) ? e.category : 'General'
    }));
  },
  getExpensesFiltered: async (opts: { category?: string; label?: string; invoiceId?: number; unlinkedOnly?: boolean; skip?: number; limit?: number } = {}) => {
    const params = new URLSearchParams();
    if (opts.category && opts.category !== 'all') params.set('category', opts.category);
    if (opts.label) params.set('label', opts.label);
    if (typeof opts.invoiceId === 'number') params.set('invoice_id', String(opts.invoiceId));
    if (opts.unlinkedOnly) params.set('unlinked_only', 'true');
    if (typeof opts.skip === 'number') params.set('skip', String(opts.skip));
    if (typeof opts.limit === 'number') params.set('limit', String(opts.limit));
    const qs = params.toString();
    const url = `/expenses/${qs ? `?${qs}` : ''}`;
    return apiRequest<Expense[]>(url);
  },
  getExpense: async (id: number) => {
    const e = await apiRequest<Expense>(`/expenses/${id}`);
    const validCategories = EXPENSE_CATEGORY_OPTIONS;
    return {
      ...e,
      category: validCategories.includes(e.category) ? e.category : 'General'
    };
  },
  createExpense: (expense: Omit<Expense, 'id' | 'created_at' | 'updated_at' | 'receipt_filename'>) =>
    apiRequest<Expense>(`/expenses/`, {
      method: 'POST',
      body: JSON.stringify(expense),
    }),
  updateExpense: (id: number, expense: Partial<Expense>) =>
    apiRequest<Expense>(`/expenses/${id}`, {
      method: 'PUT',
      body: JSON.stringify(expense),
    }),
  bulkLabels: (expenseIds: number[], operation: 'add' | 'remove', label: string) =>
    apiRequest<{ updated: number }>(`/expenses/bulk-labels`, {
      method: 'POST',
      body: JSON.stringify({ expense_ids: expenseIds, operation, label }),
    }),
  deleteExpense: (id: number) => apiRequest(`/expenses/${id}`, { method: 'DELETE' }),
  uploadReceipt: async (expenseId: number, file: File) => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
      try {
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        return user.tenant_id?.toString();
      } catch { return undefined; }
    })();

    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {
      'Authorization': `Bearer ${token}`,
    };
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const uploadUrl = `${API_BASE_URL}/expenses/${expenseId}/upload-receipt`;
    const response = await fetch(uploadUrl, { method: 'POST', headers, body: formData });
    if (!response.ok) {
      const errorText = await response.text();
      try { throw new Error(JSON.parse(errorText).detail || 'Failed to upload receipt'); }
      catch { throw new Error(errorText || 'Failed to upload receipt'); }
    }
    return response.json();
  },
  listAttachments: async (expenseId: number) => {
    return apiRequest<ExpenseAttachmentMeta[]>(`/expenses/${expenseId}/attachments`);
  },
  deleteAttachment: async (expenseId: number, attachmentId: number) => {
    return apiRequest(`/expenses/${expenseId}/attachments/${attachmentId}`, { method: 'DELETE' });
  },
  downloadAttachmentBlob: async (expenseId: number, attachmentId: number): Promise<Blob> => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
      try {
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        return user.tenant_id?.toString();
      } catch { return undefined; }
    })();

    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const url = `${API_BASE_URL}/expenses/${expenseId}/attachments/${attachmentId}/download`;
    const resp = await fetch(url, { headers });
    if (!resp.ok) {
      const text = await resp.text();
      try { throw new Error(JSON.parse(text).detail || 'Failed to download'); }
      catch { throw new Error(text || 'Failed to download'); }
    }
    return await resp.blob();
  },
};

// Dashboard API
export const dashboardApi = {
  getStats: async () => {
    try {
      const [clients, invoices, payments] = await Promise.all([
        clientApi.getClients(),
        invoiceApi.getInvoices(),
        paymentApi.getPayments(),
      ]);
      
      const totalClients = clients.length;
      // Group totals by currency
      const totalIncome: Record<string, number> = {};
      const pendingInvoices: Record<string, number> = {};
      
      console.log('Dashboard API - Processing invoices:', invoices.length);
      invoices.forEach(invoice => {
        const currency = invoice.currency || 'USD';
        console.log(`Invoice ${invoice.number}: status=${invoice.status}, amount=${invoice.amount}, paid_amount=${invoice.paid_amount}, currency=${currency}`);
        
        if (invoice.status === 'paid' || invoice.status === 'partially_paid') {
          totalIncome[currency] = (totalIncome[currency] || 0) + invoice.paid_amount;
          console.log(`Added to totalIncome[${currency}]: ${invoice.paid_amount}`);
        }
        // Calculate pending amounts for invoices that are not fully paid
        if (invoice.status === 'pending' || invoice.status === 'overdue' || invoice.status === 'partially_paid') {
          const outstandingAmount = invoice.amount - (invoice.paid_amount || 0);
          console.log(`Outstanding amount for ${invoice.number}: ${outstandingAmount}`);
          if (outstandingAmount > 0) {
            pendingInvoices[currency] = (pendingInvoices[currency] || 0) + outstandingAmount;
            console.log(`Added to pendingInvoices[${currency}]: ${outstandingAmount}`);
          }
        }
      });
      
      console.log('Final dashboard stats:', { totalIncome, pendingInvoices });
      
      const invoicesPaid = (invoices || []).filter(invoice => invoice.status === 'paid').length;
      const invoicesPending = (invoices || []).filter(invoice => invoice.status === 'pending').length;
      const invoicesOverdue = (invoices || []).filter(invoice => invoice.status === 'overdue').length;
      
      // Calculate trends by comparing current month vs previous month
      const now = new Date();
      const currentMonth = now.getMonth();
      const currentYear = now.getFullYear();
      const previousMonth = currentMonth === 0 ? 11 : currentMonth - 1;
      const previousYear = currentMonth === 0 ? currentYear - 1 : currentYear;
      
      // Helper function to calculate total for a specific month
      const calculateMonthlyTotal = (targetMonth: number, targetYear: number) => {
        return (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth && 
                   invoiceDate.getFullYear() === targetYear &&
                   (invoice.status === 'paid' || invoice.status === 'partially_paid');
          })
          .reduce((sum, invoice) => sum + (invoice.paid_amount || 0), 0);
      };
      
      // Helper function to calculate pending for a specific month
      const calculateMonthlyPending = (targetMonth: number, targetYear: number) => {
        return (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth && 
                   invoiceDate.getFullYear() === targetYear &&
                   (invoice.status === 'pending' || invoice.status === 'overdue' || invoice.status === 'partially_paid');
          })
          .reduce((sum, invoice) => {
            const outstandingAmount = invoice.amount - (invoice.paid_amount || 0);
            return sum + (outstandingAmount > 0 ? outstandingAmount : 0);
          }, 0);
      };
      
      // Helper function to calculate client count for a specific month
      const calculateMonthlyClients = (targetMonth: number, targetYear: number) => {
        const clientIds = new Set();
        (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth && 
                   invoiceDate.getFullYear() === targetYear;
          })
          .forEach(invoice => clientIds.add(invoice.client_id));
        return clientIds.size;
      };
      
      // Helper function to calculate overdue count for a specific month
      const calculateMonthlyOverdue = (targetMonth: number, targetYear: number) => {
        return (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth && 
                   invoiceDate.getFullYear() === targetYear &&
                   invoice.status === 'overdue';
          }).length;
      };
      
      // Calculate current and previous month totals
      const currentMonthIncome = calculateMonthlyTotal(currentMonth, currentYear);
      const previousMonthIncome = calculateMonthlyTotal(previousMonth, previousYear);
      const currentMonthPending = calculateMonthlyPending(currentMonth, currentYear);
      const previousMonthPending = calculateMonthlyPending(previousMonth, previousYear);
      const currentMonthClients = calculateMonthlyClients(currentMonth, currentYear);
      const previousMonthClients = calculateMonthlyClients(previousMonth, previousYear);
      const currentMonthOverdue = calculateMonthlyOverdue(currentMonth, currentYear);
      const previousMonthOverdue = calculateMonthlyOverdue(previousMonth, previousYear);
      
      // Calculate percentage changes
      const calculatePercentageChange = (current: number, previous: number) => {
        if (previous === 0) return current > 0 ? 100 : 0;
        return ((current - previous) / previous) * 100;
      };
      
      const incomeTrend = calculatePercentageChange(currentMonthIncome, previousMonthIncome);
      const pendingTrend = calculatePercentageChange(currentMonthPending, previousMonthPending);
      const clientsTrend = calculatePercentageChange(currentMonthClients, previousMonthClients);
      const overdueTrend = calculatePercentageChange(currentMonthOverdue, previousMonthOverdue);
      
      console.log('Trend calculations:', {
        currentMonthIncome,
        previousMonthIncome,
        incomeTrend,
        currentMonthPending,
        previousMonthPending,
        pendingTrend,
        currentMonthClients,
        previousMonthClients,
        clientsTrend,
        currentMonthOverdue,
        previousMonthOverdue,
        overdueTrend
      });
      
      return {
        totalIncome,
        pendingInvoices,
        totalClients,
        invoicesPaid,
        invoicesPending,
        invoicesOverdue,
        trends: {
          income: { value: Math.round(incomeTrend * 10) / 10, isPositive: incomeTrend >= 0 },
          pending: { value: Math.round(pendingTrend * 10) / 10, isPositive: pendingTrend >= 0 },
          clients: { value: Math.round(clientsTrend * 10) / 10, isPositive: clientsTrend >= 0 },
          overdue: { value: Math.round(overdueTrend * 10) / 10, isPositive: overdueTrend >= 0 }
        }
      };
    } catch (error) {
      console.error('Failed to get dashboard stats:', error);
      return {
        totalIncome: {},
        pendingInvoices: {},
        totalClients: 0,
        invoicesPaid: 0,
        invoicesPending: 0,
        invoicesOverdue: 0,
        trends: {
          income: { value: 0, isPositive: true },
          pending: { value: 0, isPositive: true },
          clients: { value: 0, isPositive: true },
          overdue: { value: 0, isPositive: false }
        }
      };
    }
  }
};

// Settings API methods
export const settingsApi = {
  getSettings: () => apiRequest<Settings>("/settings/"),
  updateSettings: (settings: Partial<Settings>) => 
    apiRequest<Settings>("/settings/", {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  exportData: async () => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/settings/export-data`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
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
    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_BASE_URL}/settings/import-data`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to import data');
    }
    
    return await response.json();
  },
};

// Discount Rules API methods
export const discountRulesApi = {
  getDiscountRules: () => apiRequest<DiscountRule[]>("/discount-rules/"),
  getDiscountRule: (id: number) => apiRequest<DiscountRule>(`/discount-rules/${id}`),
  createDiscountRule: (discountRule: DiscountRuleCreate) => 
    apiRequest<DiscountRule>("/discount-rules/", {
      method: 'POST',
      body: JSON.stringify(discountRule),
    }),
  updateDiscountRule: (id: number, discountRule: DiscountRuleUpdate) => 
    apiRequest<DiscountRule>(`/discount-rules/${id}`, {
      method: 'PUT',
      body: JSON.stringify(discountRule),
    }),
  deleteDiscountRule: (id: number) => 
    apiRequest(`/discount-rules/${id}`, {
      method: 'DELETE',
    }),
  calculateDiscount: (subtotal: number) => {
    console.log("Sending discount calculation request:", {
      url: `/discount-rules/calculate`,
      subtotal: subtotal
    });
    return apiRequest<DiscountCalculation>(`/discount-rules/calculate`, {
      method: 'POST',
      body: JSON.stringify({ subtotal: subtotal, currency: "USD" }),
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
  testAIConfig: (id: number) => 
    apiRequest<{success: boolean, message: string, response?: string}>(`/ai-config/test/${id}`),
  markAsTested: (id: number) =>
    apiRequest<{message: string}>(`/ai-config/mark-tested/${id}`, {
      method: 'POST',
    }),
};

// AI Assistant API methods
export const aiApi = {
  analyzePatterns: () => apiRequest<{success: boolean, data: any}>("/ai/analyze-patterns"),
  suggestActions: () => apiRequest<{success: boolean, data: any}>("/ai/suggest-actions"),
  chat: (message: string, configId: number) => 
    apiRequest<{success: boolean, data: any}>("/ai/chat", {
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
  delete: <T>(url: string, config?: { isLogin?: boolean }) => apiRequest<T>(url, { method: 'DELETE' }, config),
}; 

export const superAdminApi = {
  demoteSuperAdmin: async (email: string) => {
    return apiRequest<{ message: string }>("/super-admin/demote", {
      method: "POST",
      body: JSON.stringify({ email }),
    }, { skipTenant: true });
  },
};