import { toast } from 'sonner';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import type { ExpenseApproval, ApprovalHistoryEntry, ApprovalDashboardStats, User, ApprovalDelegate, ApprovalDelegateCreate, ApprovalDelegateUpdate } from '@/types';

// Import DashboardStats type from the dashboard component
interface DashboardStats {
  totalIncome: Record<string, number>;
  pendingInvoices: Record<string, number>;
  totalExpenses: Record<string, number>;
  totalClients: number;
  invoicesPaid: number;
  invoicesPending: number;
  invoicesOverdue: number;
  paymentTrends: {
    onTimePaymentRate: number;
    averagePaymentTime: number;
    overdueRate: number;
  };
  trends: {
    income: { value: number; isPositive: boolean };
    pending: { value: number; isPositive: boolean };
    clients: { value: number; isPositive: boolean };
    overdue: { value: number; isPositive: boolean };
  };
}

// Define recycle bin types
export interface DeletedExpense extends Expense {
  is_deleted: boolean;
  deleted_at?: string | null;
  deleted_by?: number | null;
  deleted_by_username?: string | null;
}

export interface DeletedBankStatement extends BankStatementSummary {
  is_deleted: boolean;
  deleted_at?: string | null;
  deleted_by?: number | null;
  deleted_by_username?: string | null;
}

// API base URL comes from env var. Set VITE_API_URL in your environment.
// When running in containers, use nginx proxy on port 8080
export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Type definitions
export interface Client {
  id: number;
  name: string;
  email: string;
  phone: string;
  address: string;
  company?: string;
  balance: number;
  paid_amount: number;
  outstanding_balance?: number;
  preferred_currency?: string;
  labels?: string[];
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
  inventory_item_id?: number;
  unit_of_measure?: string;
  inventory_item?: {
    id: number;
    name: string;
    description?: string;
    sku?: string;
    unit_price: number;
    cost_price?: number;
    currency: string;
    track_stock: boolean;
    current_stock: number;
    minimum_stock: number;
    unit_of_measure: string;
    item_type: string;
    is_active: boolean;
    barcode?: string;
    category_id?: number;
  };
}

export const INVOICE_STATUSES = ["draft", "pending", "paid", "overdue", "partially_paid", "cancelled", "pending_approval", "approved", "rejected", "sent"] as const;
export type InvoiceStatus = typeof INVOICE_STATUSES[number];

export const isValidInvoiceStatus = (status: string): status is InvoiceStatus => {
  return (INVOICE_STATUSES as readonly string[]).includes(status);
};

export const formatStatus = (status?: string | null) => {
  if (!status) return '';
  return status.split('_').map(word =>
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
};

export interface InvoiceAttachmentMeta {
  id: number;
  filename: string;
  file_size: number;
  content_type: string;
  attachment_type: string;
  created_at: string;
}

export interface Invoice {
  id: number;
  number: string;
  client_id: number;
  client_name: string;
  client_email: string;
  client_company?: string;
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
  show_discount_in_pdf?: boolean;
  has_attachment?: boolean;
  attachment_filename?: string;
  attachments?: InvoiceAttachmentMeta[];
  attachment_count?: number;
  payer?: string;
  labels?: string[];
  // User attribution fields
  created_by_user_id?: number;
  created_by_username?: string;
  created_by_email?: string;
  // Review fields
  review_status?: 'not_started' | 'pending' | 'diff_found' | 'no_diff' | 'reviewed' | 'failed';
  review_result?: any;
  reviewed_at?: string;
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

// Inventory Management Types
export interface InventoryCategory {
  id: number;
  name: string;
  description?: string;
  color?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InventoryItem {
  id: number;
  name: string;
  description?: string;
  sku?: string;
  category_id?: number;
  category?: InventoryCategory;
  unit_price: number;
  cost_price?: number;
  currency: string;
  track_stock: boolean;
  current_stock: number;
  minimum_stock: number;
  unit_of_measure: string;
  item_type: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StockMovement {
  id: number;
  item_id: number;
  movement_type: string;
  quantity: number;
  unit_cost?: number;
  reference_type?: string;
  reference_id?: number;
  notes?: string;
  user_id: number;
  movement_date: string;
  created_at: string;
  item?: InventoryItem;
}

export interface StockMovementCreate {
  item_id: number;
  movement_type: string;
  quantity: number;
  unit_cost?: number;
  reference_type?: string;
  reference_id?: number;
  notes?: string;
  movement_date: string;
}

export interface InventoryAnalytics {
  total_items: number;
  active_items: number;
  low_stock_items: number;
  total_value: number;
  currency: string;
}

export interface InventorySearchFilters {
  query?: string;
  category_id?: number;
  item_type?: string;
  is_active?: boolean;
  track_stock?: boolean;
  low_stock_only?: boolean;
  min_price?: number;
  max_price?: number;
}

export interface InventoryListResponse {
  items: InventoryItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface InventoryValueReport {
  total_inventory_value: number;
  total_cost_value: number;
  potential_profit: number;
  currency: string;
  items: any[];
}

export interface InventoryPurchaseItem {
  item_id: number;
  quantity: number;
  unit_cost: number;
  item_name?: string;
}

export interface InventoryPurchaseCreate {
  vendor: string;
  reference_number?: string;
  purchase_date: string;
  currency: string;
  items: InventoryPurchaseItem[];
  notes?: string;
  payment_method?: string;
  tax_rate?: number;
}

export interface LowStockAlert {
  item_id: number;
  item_name: string;
  sku?: string;
  current_stock: number;
  minimum_stock: number;
  sold_last_30_days: number;
  daily_sales_rate: number;
  days_until_empty?: number;
  weeks_stock_remaining?: number;
  alert_level: 'critical' | 'warning' | 'normal';
  message: string;
}

export interface LowStockAlertsResponse {
  generated_at: string;
  threshold_days: number;
  alerts: LowStockAlert[];
  summary: {
    total_items: number;
    critical_alerts: number;
    warning_alerts: number;
    normal_items: number;
  };
}

// Invoice-Inventory Linking Interfaces
export interface InvoiceInventoryLink {
  id: number;
  number: string;
  amount: number;
  currency: string;
  status: string;
  due_date?: string;
  created_at: string;
  client_id: number;
  invoice_items: Array<{
    quantity: number;
    price: number;
    amount: number;
  }>;
  stock_movements: Array<{
    id: number;
    quantity: number;
    movement_type: string;
    movement_date: string;
    notes?: string;
  }>;
}

export interface InventoryStockSummary {
  item_id: number;
  movement_summary: Record<string, {
    total_quantity: number;
    count: number;
  }>;
  recent_movements: Array<{
    id: number;
    movement_type: string;
    quantity: number;
    reference_type?: string;
    reference_id?: number;
    movement_date: string;
    notes?: string;
  }>;
  linked_references: {
    invoices: Array<{
      id: number;
      number: string;
      amount: number;
      currency: string;
      status: string;
      client_id: number;
    }>;
    expenses: Array<{
      id: number;
      amount: number;
      currency: string;
      category?: string;
      vendor?: string;
    }>;
  };
  period_days: number;
}

export interface ProfitabilityAnalysis {
  period: {
    start_date: string;
    end_date: string;
  };
  summary: {
    total_revenue: number;
    total_cost: number;
    total_profit: number;
    overall_margin_percent: number;
  };
  items: any[];
}

export interface InventoryTurnoverAnalysis {
  analysis_period_months: number;
  summary: {
    total_inventory_value: number;
    total_cogs: number;
    overall_turnover_ratio: number;
    items_analyzed: number;
  };
  turnover_categories: {
    excellent: number;
    good: number;
    fair: number;
    slow: number;
    very_slow: number;
  };
  items: any[];
}

export interface CategoryPerformanceReport {
  period: {
    start_date: string;
    end_date: string;
  };
  categories: any[];
  summary: {
    total_categories: number;
    total_revenue: number;
    total_inventory_value: number;
  };
}

export interface InventoryDashboardData {
  analytics: InventoryAnalytics;
  alerts: {
    critical_alerts: number;
    warning_alerts: number;
    normal_items: number;
  };
  recent_activity: {
    period_days: number;
    total_sold: number;
    total_revenue: number;
    invoice_count: number;
  };
  top_selling_items: Array<{
    item_name: string;
    total_sold: number;
    total_revenue: number;
  }>;
  generated_at: string;
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
  user_id?: number;
  created_at: string;
  updated_at: string;
  imported_from_attachment?: boolean;
  analysis_status?: 'not_started' | 'queued' | 'processing' | 'done' | 'failed' | 'cancelled';
  manual_override?: boolean;
  receipt_timestamp?: string | null;
  receipt_time_extracted?: boolean;
  // User attribution fields
  created_by_user_id?: number;
  created_by_username?: string;
  created_by_email?: string;
  // Review fields
  review_status?: 'not_started' | 'pending' | 'diff_found' | 'no_diff' | 'reviewed' | 'failed';
  review_result?: any;
  reviewed_at?: string;
}

export interface ExpenseAttachmentMeta {
  id: number;
  filename: string;
  content_type?: string;
  size_bytes?: number;
  uploaded_at?: string;
  analysis_status?: 'not_started' | 'processing' | 'done' | 'failed';
  analysis_error?: string;
  analysis_result?: any;
  extracted_amount?: number;
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
  extraction_method?: string | null;
  analysis_error?: string | null;
  analysis_updated_at?: string | null;
  labels?: string[] | null;
  notes?: string | null;
  created_at?: string;
  // User attribution fields
  created_by_user_id?: number;
  created_by_username?: string;
  created_by_email?: string;
  // Review fields
  review_status?: 'not_started' | 'pending' | 'diff_found' | 'no_diff' | 'reviewed' | 'failed';
  review_result?: any;
  reviewed_at?: string;
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

    const url = `${API_BASE_URL}/statements/upload`;
    const resp = await fetch(url, { method: 'POST', headers, body: formData });
    const text = await resp.text();
    if (!resp.ok) {
      try { throw new Error(JSON.parse(text).detail || 'Failed to process bank statements'); }
      catch { throw new Error(text || 'Failed to process bank statements'); }
    }
    return JSON.parse(text);
  },

  list: async (skip: number = 0, limit: number = 100, label?: string, search?: string, status?: string): Promise<{ statements: BankStatementSummary[], total: number }> => {
    const params = new URLSearchParams();
    params.set('skip', skip.toString());
    params.set('limit', limit.toString());
    if (label) params.set('label', label);
    if (search) params.set('search', search);
    if (status) params.set('status', status);
    const data = await apiRequest<{ success: boolean; statements: BankStatementSummary[]; total: number }>(
      `/statements?${params.toString()}`,
      { method: 'GET' }
    );
    return { statements: data.statements, total: data.total };
  },

  get: async (statementId: number): Promise<BankStatementDetail> => {
    const data = await apiRequest<{ success: boolean; statement: BankStatementDetail }>(
      `/statements/${statementId}`,
      { method: 'GET' }
    );
    return data.statement;
  },

  updateMeta: async (
    statementId: number,
    updates: { labels?: string[] | null; notes?: string | null }
  ): Promise<{ success: boolean; statement: BankStatementSummary }> => {
    return apiRequest<{ success: boolean; statement: BankStatementSummary }>(
      `/statements/${statementId}`,
      { method: 'PUT', body: JSON.stringify(updates) }
    );
  },

  replaceTransactions: async (
    statementId: number,
    transactions: BankTransactionEntry[]
  ): Promise<{ success: boolean; updated_count: number }> => {
    return apiRequest<{ success: boolean; updated_count: number }>(
      `/statements/${statementId}/transactions`,
      { method: 'PUT', body: JSON.stringify({ transactions }) }
    );
  },

  reprocess: async (statementId: number): Promise<{ success: boolean; message: string }> => {
    return apiRequest<{ success: boolean; message: string }>(
      `/statements/${statementId}/reprocess`,
      { method: 'POST' }
    );
  },
  acceptReview: (statementId: number) => apiRequest<{ success: boolean; statement: BankStatementSummary }>(`/statements/${statementId}/accept-review`, { method: 'POST' }),
  reReview: (statementId: number) => apiRequest<{ success: boolean; statement: BankStatementSummary }>(`/statements/${statementId}/review`, { method: 'POST' }),
  cancelReview: (statementId: number) => apiRequest<{ success: boolean; statement: BankStatementSummary }>(`/statements/${statementId}/cancel-review`, { method: 'POST' }),

  // Build URLs for preview/download (relative if API_BASE_URL is relative)
  fileUrl: (statementId: number, inline = true): string => {
    const base = API_BASE_URL.replace(/\/$/, '');
    return `${base}/statements/${statementId}/file${inline ? '?inline=true' : ''}`;
  },

  fetchFileBlob: async (
    statementId: number,
    inline = true
  ): Promise<{ blob: Blob; filename: string; contentType: string }> => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
      try { const user = JSON.parse(localStorage.getItem('user') || '{}'); return user.tenant_id?.toString(); } catch { return undefined; }
    })();
    const base = API_BASE_URL.replace(/\/$/, '');
    const url = `${base}/statements/${statementId}/file${inline ? '?inline=true' : ''}`;
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
    const normalizedBlob = blob.type === type ? blob : new Blob([blob], { type });
    return { blob: normalizedBlob, filename, contentType: type };
  },

  delete: async (statementId: number): Promise<void> => {
    await apiRequest<{ success: boolean }>(
      `/statements/${statementId}`,
      { method: 'DELETE' }
    );
  },

  // Recycle bin methods
  getDeletedStatements: () =>
    apiRequest<DeletedBankStatement[]>('/statements/recycle-bin'),
  restoreStatement: (id: number, newStatus: string = 'processed') =>
    apiRequest(`/statements/${id}/restore`, {
      method: 'POST',
      body: JSON.stringify({ new_status: newStatus }),
    }),
  permanentlyDeleteStatement: (id: number) =>
    apiRequest(`/statements/${id}/permanent`, { method: 'DELETE' }),
  emptyRecycleBin: () =>
    apiRequest('/statements/recycle-bin/empty', { method: 'POST' }),
  bulkLabels: (ids: number[], action: 'add' | 'remove', label: string) =>
    apiRequest<{ success: boolean; count: number }>('/statements/bulk-labels', {
      method: 'POST',
      body: JSON.stringify({ ids, action, label }),
    }),
  merge: (ids: number[]) =>
    apiRequest<{ success: boolean; message: string; id: number }>('/statements/merge', {
      method: 'POST',
      body: JSON.stringify({ ids }),
    }),
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
  timezone?: string;
  email_settings?: any;
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

export interface TaxIntegrationStatus {
  enabled: boolean;
  configured: boolean;
  connection_tested: boolean;
  last_test_result?: string;
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
      } else {
        // Fallback to user's default tenant
        const userStr = localStorage.getItem('user');
        if (userStr) {
          const user = JSON.parse(userStr);
          if (user && user.tenant_id) {
            tenantId = String(user.tenant_id);
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
      // Ensure tenant ID is a valid number string
      const numericTenantId = parseInt(tenantId, 10);
      if (!isNaN(numericTenantId)) {
        headers['X-Tenant-ID'] = numericTenantId.toString();
      } else {
        console.warn(`⚠️ Invalid tenant ID: ${tenantId}`);
      }
    } else if (!config.skipTenant) {
      console.warn(`⚠️ No tenant ID available for request to ${requestUrl}`);
    }
    const response = await fetch(requestUrl, {
      ...options,
      headers,
    });

    // Log the raw response text for debugging
    const responseText = await response.text();

    if (!response.ok) {
      // Try to parse error response
      let errorData;
      try {
        errorData = JSON.parse(responseText);
      } catch (e) {
        // If JSON parsing fails, use status text
        throw new Error(`Error: ${response.status} ${response.statusText}`);
      }

      // Handle authentication errors
      if (!config.isLogin && response.status === 401) {
        // Don't log out for super-admin endpoints - they might fail for other reasons
        if (!requestUrl.includes('/super-admin/')) {
          // Only log out on 401 (unauthorized) - token is invalid/expired
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          localStorage.removeItem('selected_tenant_id');
          // Show toast and redirect to login only if not already on login page
          if (!window.location.pathname.includes('/login')) {
            toast.error('Session expired. Please log in again.');
            // Use window.location.replace for reliability
            setTimeout(() => window.location.replace('/login'), 100);
          }
          throw new Error('Authentication failed. Please log in again.');
        } else {
          // For super-admin endpoints, just throw the error without logging out
          throw new Error(errorData.detail || 'Authentication failed');
        }
      }

      // Handle 403 (forbidden) errors - could be permission or tenant context issues
      if (response.status === 403) {
        // Check if it's a tenant context error (but not for super-admin endpoints)
        if (!requestUrl.includes('/super-admin/') && errorData.detail && errorData.detail.includes('Tenant context required')) {
          // This is a session/tenant context issue - log out the user
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          localStorage.removeItem('selected_tenant_id');
          toast.error('Session expired. Please log in again.');
          window.location.replace('/login');
          throw new Error('Session expired. Please log in again.');
        } else {
          // User is authenticated but lacks permissions - don't log out
          throw new Error(errorData.detail || 'Access denied. You do not have permission to access this resource.');
        }
      }

      // Handle 400 errors that might be tenant context issues
      if (response.status === 400 && errorData.detail && typeof errorData.detail === 'string' && errorData.detail.includes('Tenant context required')) {
        // This is a session/tenant context issue - log out the user (but not for super-admin endpoints)
        if (!requestUrl.includes('/super-admin/')) {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          localStorage.removeItem('selected_tenant_id');
          toast.error('Session expired. Please log in again.');
          window.location.replace('/login');
          throw new Error('Session expired. Please log in again.');
        } else {
          // For super-admin endpoints, just throw the error
          throw new Error(errorData.detail || 'Request failed');
        }
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
        } else if (typeof errorData.detail === 'object' && errorData.detail !== null) {
          // Handle object error details (e.g., {error: "CODE", message: "text"})
          const message = errorData.detail.message || errorData.detail.error || JSON.stringify(errorData.detail);
          console.error('API error:', errorData.detail);
          throw new Error(message);
        } else {
          // Handle string error details
          console.error('API error:', errorData.detail);
          throw new Error(String(errorData.detail));
        }
      }

      // Handle other errors with object details
      if (errorData.detail) {
        let errorMessage: string;
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          // Handle FastAPI validation errors format
          const validationError = errorData.detail[0];
          if (validationError?.msg) {
            // Extract the actual error message from "Value error, Organization name must be at least 2 characters long"
            errorMessage = validationError.msg.replace('Value error, ', '');
          } else if (validationError?.ctx?.error) {
            errorMessage = validationError.ctx.error;
          } else {
            errorMessage = JSON.stringify(validationError);
          }
        } else if (typeof errorData.detail === 'object' && errorData.detail !== null) {
          // Handle object error details (e.g., {error: "CODE", message: "text"})
          errorMessage = errorData.detail.message || errorData.detail.error || JSON.stringify(errorData.detail);
        } else {
          errorMessage = String(errorData.detail);
        }
        throw new Error(errorMessage);
      }

      // Fallback error message
      throw new Error(`Error: ${response.status} ${response.statusText}`);
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
      throw new Error('Invalid JSON response from server');
    }

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

// Approval API methods
export const approvalApi = {
  // Get pending approvals for current user
  getPendingApprovals: (filters?: {
    limit?: number;
    offset?: number;
    category?: string;
    min_amount?: number;
    max_amount?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }) => {
    const params = new URLSearchParams();
    if (filters?.limit) params.append('limit', filters.limit.toString());
    if (filters?.offset) params.append('offset', filters.offset.toString());
    if (filters?.category) params.append('category', filters.category);
    if (filters?.min_amount) params.append('min_amount', filters.min_amount.toString());
    if (filters?.max_amount) params.append('max_amount', filters.max_amount.toString());
    if (filters?.sort_by) params.append('sort_by', filters.sort_by);
    if (filters?.sort_order) params.append('sort_order', filters.sort_order);

    const queryString = params.toString();
    return apiRequest<{ approvals: ExpenseApproval[]; total: number; }>(`/approvals/pending${queryString ? `?${queryString}` : ''}`);
  },

  // Get approval dashboard statistics
  getDashboardStats: () => apiRequest<ApprovalDashboardStats>("/approvals/dashboard-stats"),

  // Get expenses approved by current user
  getApprovedExpenses: (filters?: {
    skip?: number;
    limit?: number;
  }) => {
    const params = new URLSearchParams();
    if (filters?.skip !== undefined) params.append('skip', filters.skip.toString());
    if (filters?.limit !== undefined) params.append('limit', filters.limit.toString());

    const queryString = params.toString();
    return apiRequest<{ expenses: Expense[]; total: number; }>(`/approvals/approved-expenses${queryString ? `?${queryString}` : ''}`);
  },

  // Get expenses processed (approved/rejected) by current user
  getProcessedExpenses: (filters?: {
    skip?: number;
    limit?: number;
  }) => {
    const params = new URLSearchParams();
    if (filters?.skip !== undefined) params.append('skip', filters.skip.toString());
    if (filters?.limit !== undefined) params.append('limit', filters.limit.toString());

    const queryString = params.toString();
    return apiRequest<{ expenses: Expense[]; total: number; }>(`/approvals/processed-expenses${queryString ? `?${queryString}` : ''}`);
  },

  // Get invoices processed (approved/rejected) by current user
  getProcessedInvoices: (filters?: {
    skip?: number;
    limit?: number;
  }) => {
    const params = new URLSearchParams();
    if (filters?.skip !== undefined) params.append('skip', filters.skip.toString());
    if (filters?.limit !== undefined) params.append('limit', filters.limit.toString());

    const queryString = params.toString();
    return apiRequest<{ invoices: any[]; total: number; }>(`/approvals/invoices/processed${queryString ? `?${queryString}` : ''}`);
  },

  // Approve an expense
  approveExpense: (approvalId: number, notes?: string) =>
    apiRequest<{ success: boolean; message: string; }>(`/approvals/${approvalId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ status: 'approved', notes }),
    }),

  // Reject an expense
  rejectExpense: (approvalId: number, reason: string, notes?: string) =>
    apiRequest<{ success: boolean; message: string; }>(`/approvals/${approvalId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ status: 'rejected', rejection_reason: reason, notes }),
    }),

  // Get approval history for an expense
  getApprovalHistory: (expenseId: number) =>
    apiRequest<{ history: ApprovalHistoryEntry[]; }>(`/approvals/history/${expenseId}`),

  // Submit expense for approval
  submitForApproval: (expenseId: number, approverId: number, notes?: string) =>
    apiRequest<ExpenseApproval[]>(`/approvals/expenses/${expenseId}/submit-approval`, {
      method: 'POST',
      body: JSON.stringify({ expense_id: expenseId, notes, approver_id: approverId }),
    }),

  // Get list of available approvers
  getApprovers: () => apiRequest<Array<{ id: number; name: string; email: string }>>(`/approvals/approvers`),

  // Invoice Approval Methods
  submitInvoiceForApproval: (invoiceId: number, data: { approver_id: number; notes?: string }) =>
    apiRequest<Array<{ id: number; status: string; approval_level: number }>>(`/approvals/invoices/${invoiceId}/submit-approval`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getPendingInvoiceApprovals: (filters?: { limit?: number; offset?: number }) => {
    const params = new URLSearchParams();
    if (filters?.limit) params.append('limit', filters.limit.toString());
    if (filters?.offset) params.append('offset', filters.offset.toString());

    const queryString = params.toString();
    return apiRequest<{ approvals: any[]; total: number; }>(`/approvals/invoices/pending${queryString ? `?${queryString}` : ''}`);
  },

  approveInvoice: (approvalId: number, notes?: string) =>
    apiRequest<{ id: number; status: string; invoice_id: number }>(`/approvals/invoices/${approvalId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),

  getInvoiceApprovalHistory: (invoiceId: number) =>
    apiRequest<{ invoice_id: number; current_status: string; approval_history: ApprovalHistoryEntry[]; }>(`/approvals/invoices/history/${invoiceId}`),

  rejectInvoice: (approvalId: number, reason: string, notes?: string) =>
    apiRequest<{ id: number; status: string; invoice_id: number }>(`/approvals/invoices/${approvalId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ rejection_reason: reason, notes }),
    }),



  // Approval Delegation Management
  getDelegations: (filters?: {
    approver_id?: number;
    delegate_id?: number;
    is_active?: boolean;
    limit?: number;
    offset?: number;
  }) => {
    const params = new URLSearchParams();
    if (filters?.approver_id) params.append('approver_id', filters.approver_id.toString());
    if (filters?.delegate_id) params.append('delegate_id', filters.delegate_id.toString());
    if (filters?.is_active !== undefined) params.append('is_active', filters.is_active.toString());
    if (filters?.limit) params.append('limit', filters.limit.toString());
    if (filters?.offset) params.append('offset', filters.offset.toString());

    const queryString = params.toString();
    return apiRequest<ApprovalDelegate[]>(`/approvals/delegates${queryString ? `?${queryString}` : ''}`);
  },

  createDelegation: (delegationData: ApprovalDelegateCreate) =>
    apiRequest<ApprovalDelegate>('/approvals/delegate', {
      method: 'POST',
      body: JSON.stringify(delegationData),
    }),

  updateDelegation: (delegationId: number, delegationData: ApprovalDelegateUpdate) =>
    apiRequest<ApprovalDelegate>(`/approvals/delegates/${delegationId}`, {
      method: 'PUT',
      body: JSON.stringify(delegationData),
    }),

  deleteDelegation: (delegationId: number) =>
    apiRequest<{ message: string }>(`/approvals/delegates/${delegationId}`, {
      method: 'DELETE',
    }),
};

// Client API methods
export const clientApi = {
  getClients: async (skip: number = 0, limit: number = 100, label?: string): Promise<{ items: Client[], total: number }> => {
    let url = `/clients/?skip=${skip}&limit=${limit}`;
    if (label) url += `&label_filter=${encodeURIComponent(label)}`;
    return apiRequest<{ items: Client[], total: number }>(url);
  },
  bulkLabels: (ids: number[], action: 'add' | 'remove', label: string) =>
    apiRequest<{ success: boolean; count: number }>('/clients/bulk-labels', {
      method: 'POST',
      body: JSON.stringify({ ids, action, label }),
    }),
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

  // Organization join request functions
  lookupOrganization: (organizationName: string) =>
    apiRequest<{ exists: boolean; tenant_id?: number; organization_name?: string; message: string }>('/organization-join/lookup', {
      method: 'POST',
      body: JSON.stringify({ organization_name: organizationName }),
    }),

  submitJoinRequest: (requestData: any) =>
    apiRequest<{ success: boolean; message: string; request_id?: number }>('/organization-join/request', {
      method: 'POST',
      body: JSON.stringify(requestData),
    }),

  // Admin functions for managing join requests
  getPendingJoinRequests: () =>
    apiRequest<any[]>('/organization-join/pending', {
      method: 'GET',
    }),

  getJoinRequestDetails: (requestId: number) =>
    apiRequest<any>(`/organization-join/${requestId}`, {
      method: 'GET',
    }),

  processJoinRequest: (requestId: number, approvalData: any) =>
    apiRequest<{ success: boolean; message: string }>(`/organization-join/${requestId}/approve`, {
      method: 'POST',
      body: JSON.stringify(approvalData),
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
  changePassword: (data: any) =>
    apiRequest<{ message: string; success: boolean }>(`/auth/change-password`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateCurrentUser: (data: any) =>
    apiRequest<any>(`/auth/me`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  activateUser: (inviteId: number, activationData: { password?: string; first_name?: string; last_name?: string }) =>
    apiRequest<any>(`/auth/invites/${inviteId}/activate`, {
      method: 'POST',
      body: JSON.stringify(activationData),
    }),
  getCurrentUser: () => apiRequest<any>('/auth/me', {}, { skipTenant: true }),
  getSSOStatus: () => apiRequest<{ google: boolean; microsoft: boolean; has_sso: boolean }>('/auth/sso-status', {}, { skipTenant: true }),
  getPasswordRequirements: () => apiRequest<{ min_length: number; complexity: any; requirements: string[] }>('/auth/password-requirements', {}, { skipTenant: true }),
};

// User API methods
export const userApi = {
  getUsers: () => apiRequest<User[]>('/auth/users'),
  getUser: (id: number) => apiRequest<User>(`/auth/users/${id}`),
  updateUser: (id: number, userData: Partial<User>) =>
    apiRequest<User>(`/auth/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    }),
  deleteUser: (id: number) =>
    apiRequest<{ message: string }>(`/auth/users/${id}`, {
      method: 'DELETE',
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
      const response = await apiRequest<{ items: any[] }>(`/invoices/${params.toString() ? `?${params.toString()}` : ''}`);
      const mappedInvoices: Invoice[] = response.items.map(apiInvoice => ({
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
  getInvoices: async (status?: string, label?: string, skip: number = 0, limit: number = 100): Promise<{ items: Invoice[], total: number }> => {
    try {
      const params = new URLSearchParams();
      if (status) params.set('status_filter', status);
      if (label) params.set('label', label);
      params.set('skip', skip.toString());
      params.set('limit', limit.toString());
      const response = await apiRequest<{ items: any[], total: number }>(`/invoices/${params.toString() ? `?${params.toString()}` : ''}`);

      // Map API response to frontend Invoice interface
      const mappedInvoices: Invoice[] = response.items.map(apiInvoice => ({
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
        payer: apiInvoice.payer || 'Client',
        labels: apiInvoice.labels || [],
        // User attribution fields
        created_by_user_id: apiInvoice.created_by_user_id,
        created_by_username: apiInvoice.created_by_username,
        created_by_email: apiInvoice.created_by_email,
      }));

      return { items: mappedInvoices, total: response.total };
    } catch (error) {
      console.error('Failed to fetch invoices:', error);
      throw error;
    }
  },
  bulkLabels: (ids: number[], action: 'add' | 'remove', label: string) =>
    apiRequest<{ success: boolean; count: number }>('/invoices/bulk-labels', {
      method: 'POST',
      body: JSON.stringify({ ids, action, label }),
    }),
  getInvoice: async (id: number) => {
    try {
      // Get invoice data from API
      const apiResponse = await apiRequest<any>(`/invoices/${id}`);

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
          amount: item.amount || (item.quantity || 1) * (item.price || 0),
          inventory_item_id: item.inventory_item_id,
          unit_of_measure: item.unit_of_measure,
          inventory_item: item.inventory_item // Include the inventory item data!
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
        attachments: apiResponse.attachments || [],
        attachment_count: apiResponse.attachment_count || 0,
        payer: apiResponse.payer || 'Client',
        // User attribution fields
        created_by_user_id: apiResponse.created_by_user_id,
        created_by_username: apiResponse.created_by_username,
        created_by_email: apiResponse.created_by_email,
      };

      return invoice;
    } catch (error) {
      console.error("Error fetching invoice:", error);
      throw error;
    }
  },
  createInvoice: (invoiceData: {
    number?: string;
    client_id: number;
    date?: string;
    due_date?: string;
    amount: number;
    currency?: string;
    paid_amount?: number;
    status?: string;
    notes?: string;
    is_recurring?: boolean;
    recurring_frequency?: string;
    discount_type?: string;
    discount_value?: number;
    subtotal?: number;
    custom_fields?: Record<string, any>;
    show_discount_in_pdf?: boolean;
    items?: any[];
    payer?: string;
  }) =>
    apiRequest<Invoice>('/invoices/', {
      method: 'POST',
      body: JSON.stringify(invoiceData),
    }),
  updateInvoice: (id: number, invoiceData: Partial<Invoice & { payer?: string }>) =>
    apiRequest<Invoice>(`/invoices/${id}`, {
      method: 'PUT',
      body: JSON.stringify(invoiceData),
    }),
  cloneInvoice: (id: number) =>
    apiRequest<Invoice>(`/invoices/${id}/clone`, { method: 'POST' }),
  deleteInvoice: (id: number) =>
    apiRequest(`/invoices/${id}`, { method: 'DELETE' }),
  bulkDelete: (invoiceIds: number[]) =>
    apiRequest(`/invoices/bulk-delete`, {
      method: 'DELETE',
      body: JSON.stringify({ invoice_ids: invoiceIds }),
    }),

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

    const response = await fetch(uploadUrl, {
      method: 'POST',
      headers,
      body: formData,
    });

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
  downloadAttachment: (invoiceId: number, attachmentId?: number) => {
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
    if (attachmentId) {
      url.searchParams.set('attachment_id', attachmentId.toString());
    }
    form.action = url.toString();

    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
  },
  getAttachmentInfo: (invoiceId: number) =>
    apiRequest<{ has_attachment: boolean; filename?: string; content_type?: string; size_bytes?: number }>(`/invoices/${invoiceId}/attachment-info`),
  previewAttachmentBlob: async (invoiceId: number, attachmentId?: number): Promise<Blob> => {
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

    let url = `${API_BASE_URL}/invoices/${invoiceId}/preview-attachment`;
    if (attachmentId) {
      url += `?attachment_id=${attachmentId}`;
    }
    const resp = await fetch(url, { headers });
    if (!resp.ok) {
      const text = await resp.text();
      try { throw new Error(JSON.parse(text).detail || 'Failed to preview'); }
      catch { throw new Error(text || 'Failed to preview'); }
    }
    return await resp.blob();
  },
  deleteAttachment: (invoiceId: number, attachmentId: number) =>
    apiRequest(`/invoices/${invoiceId}/attachments/${attachmentId}`, { method: 'DELETE' }),

  // Invoice history methods
  send: (id: number) => apiRequest(`/invoices/${id}/send`, { method: 'POST' }),
  reminder: (id: number) => apiRequest(`/invoices/${id}/reminder`, { method: 'POST' }),
  duplicate: (id: number) => apiRequest<Invoice>(`/invoices/${id}/duplicate`, { method: 'POST' }),
  getHistory: (id: number) => apiRequest<InvoiceHistory[]>(`/invoices/${id}/history`),
  acceptReview: (id: number) => apiRequest<Invoice>(`/invoices/${id}/accept-review`, { method: 'POST' }),
  reReview: (id: number) => apiRequest<Invoice>(`/invoices/${id}/review`, { method: 'POST' }),
  cancelReview: (id: number) => apiRequest<Invoice>(`/invoices/${id}/cancel-review`, { method: 'POST' }),

  createInvoiceHistoryEntry: (invoiceId: number, historyEntry: InvoiceHistoryCreate) =>
    apiRequest<InvoiceHistory>(`/invoices/${invoiceId}/history`, {
      method: 'POST',
      body: JSON.stringify(historyEntry),
    }),
};

// Payment API methods
export const paymentApi = {
  getPayments: async (params: { limit?: number; offset?: number } = {}) => {
    const { limit = 10, offset = 0 } = params;
    const response = await apiRequest<{ success: boolean; data: Payment[]; count: number; chart_data: any }>(`/payments/?limit=${limit}&offset=${offset}`);
    return response;
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
    const response = await apiRequest<{ success: boolean, expenses: Expense[], total: number }>(`/expenses/${query}`);
    // Extract the expenses array from the response
    const list = response.expenses;
    // Ensure list is an array before mapping
    if (!Array.isArray(list)) {
      console.warn('Expenses API returned non-array response:', list);
      return [];
    }
    // Normalize category to a known option; fallback to 'General'
    const validCategories = EXPENSE_CATEGORY_OPTIONS;
    return list.map(e => ({
      ...e,
      category: validCategories.includes(e.category) ? e.category : 'General'
    }));
  },
  getExpensesFiltered: async (opts: { category?: string; label?: string; invoiceId?: number; unlinkedOnly?: boolean; skip?: number; limit?: number; excludeStatus?: string; search?: string } = {}) => {
    const params = new URLSearchParams();
    if (opts.category && opts.category !== 'all') params.set('category', opts.category);
    if (opts.label) params.set('label', opts.label);
    if (typeof opts.invoiceId === 'number') params.set('invoice_id', String(opts.invoiceId));
    if (opts.unlinkedOnly) params.set('unlinked_only', 'true');
    if (typeof opts.skip === 'number') params.set('skip', String(opts.skip));
    if (typeof opts.limit === 'number') params.set('limit', String(opts.limit));
    if (opts.excludeStatus) params.set('exclude_status', opts.excludeStatus);
    if (opts.search) params.set('search', opts.search);
    const qs = params.toString();
    const url = `/expenses/${qs ? `?${qs}` : ''}`;
    const response = await apiRequest<{ success: boolean; expenses: Expense[]; total: number }>(url);
    return response.expenses;
  },
  getExpensesPaginated: async (opts: { category?: string; label?: string; invoiceId?: number; unlinkedOnly?: boolean; skip?: number; limit?: number; excludeStatus?: string; search?: string } = {}) => {
    const params = new URLSearchParams();
    if (opts.category && opts.category !== 'all') params.set('category', opts.category);
    if (opts.label) params.set('label', opts.label);
    if (typeof opts.invoiceId === 'number') params.set('invoice_id', String(opts.invoiceId));
    if (opts.unlinkedOnly) params.set('unlinked_only', 'true');
    if (typeof opts.skip === 'number') params.set('skip', String(opts.skip));
    if (typeof opts.limit === 'number') params.set('limit', String(opts.limit));
    if (opts.excludeStatus) params.set('exclude_status', opts.excludeStatus);
    if (opts.search) params.set('search', opts.search);
    params.set('include_total', 'true'); // Add flag to get total count
    const qs = params.toString();
    const data = await apiRequest<{ success: boolean; expenses: Expense[]; total: number }>(
      `/expenses/?${qs}`,
      { method: 'GET' }
    );
    return { expenses: data.expenses, total: data.total };
  },
  getExpense: async (id: number) => {
    const maxRetries = 5;
    let lastError: any;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const e = await apiRequest<Expense>(`/expenses/${id}`);
        const validCategories = EXPENSE_CATEGORY_OPTIONS;
        return {
          ...e,
          category: validCategories.includes(e.category) ? e.category : 'General'
        };
      } catch (error) {
        lastError = error;
        const errorMessage = error instanceof Error ? error.message : String(error);

        // Check if it's a 404 error (expense not found)
        const is404 = errorMessage.includes('404') || errorMessage.includes('not found');

        // If it's a 404 and we haven't exhausted retries, wait and try again
        if (is404 && attempt < maxRetries - 1) {
          // Exponential backoff: 500ms, 1000ms, 1500ms, 2000ms, 2500ms
          const delayMs = 500 * (attempt + 1);
          await new Promise(resolve => setTimeout(resolve, delayMs));
        } else if (!is404) {
          // If it's not a 404, don't retry - throw immediately
          throw error;
        }
      }
    }

    // If all retries failed, throw the last error
    throw lastError;
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
  bulkDelete: (expenseIds: number[]) =>
    apiRequest(`/expenses/bulk-delete`, {
      method: 'DELETE',
      body: JSON.stringify({ expense_ids: expenseIds }),
    }),
  deleteExpense: async (id: number) =>
    apiRequest(`/expenses/${id}`, { method: 'DELETE' }),
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
  acceptReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/accept-review`, { method: 'POST' }),
  reReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/review`, { method: 'POST' }),
  cancelReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/cancel-review`, { method: 'POST' }),
  listAttachments: async (expenseId: number) => {
    return apiRequest<ExpenseAttachmentMeta[]>(`/expenses/${expenseId}/attachments`);
  },
  deleteAttachment: async (expenseId: number, attachmentId: number) => {
    return apiRequest(`/expenses/${expenseId}/attachments/${attachmentId}`, { method: 'DELETE' });
  },
  downloadAttachmentBlob: async (expenseId: number, attachmentId: number, inline: boolean = true): Promise<{ blob: Blob; contentType: string | null }> => {
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

    let url = `${API_BASE_URL}/expenses/${expenseId}/attachments/${attachmentId}/download?inline=${inline}`;
    const resp = await fetch(url, { headers });
    if (!resp.ok) {
      const text = await resp.text();
      try { throw new Error(JSON.parse(text).detail || 'Failed to download'); }
      catch { throw new Error(text || 'Failed to download'); }
    }
    const blob = await resp.blob();
    const contentType = resp.headers.get('content-type');
    return { blob, contentType };
  },
  reprocessExpense: (expenseId: number) =>
    apiRequest<{ message: string; status: string }>(`/expenses/${expenseId}/reprocess`, {
      method: 'POST',
    }),
  bulkCreateExpenses: (expenses: Omit<Expense, 'id' | 'created_at' | 'updated_at' | 'receipt_filename'>[]) =>
    apiRequest<Expense[]>(`/expenses/bulk-create`, {
      method: 'POST',
      body: JSON.stringify(expenses),
    }),

  // Basic Expense Analytics (for Expenses page summary)
  getExpenseSummary: (params?: {
    period?: string;
    start_date?: string;
    end_date?: string;
    compare_with_previous?: boolean;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.period) searchParams.set('period', params.period);
    if (params?.start_date) searchParams.set('start_date', params.start_date);
    if (params?.end_date) searchParams.set('end_date', params.end_date);
    if (params?.compare_with_previous !== undefined) searchParams.set('compare_with_previous', params.compare_with_previous.toString());
    return apiRequest<{
      period: any;
      current_period: any;
      previous_period?: any;
      changes?: any;
      category_breakdown: any[];
      daily_totals: any[];
    }>(`/expenses/analytics/summary${searchParams.toString() ? `?${searchParams.toString()}` : ''}`);
  },

  getExpenseTrends: (params?: {
    days?: number;
    group_by?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.days) searchParams.set('days', params.days.toString());
    if (params?.group_by) searchParams.set('group_by', params.group_by);
    return apiRequest<{
      period: any;
      trends: any[];
      analysis: any;
    }>(`/expenses/analytics/trends${searchParams.toString() ? `?${searchParams.toString()}` : ''}`);
  },

  getExpenseCategoriesAnalytics: (params?: {
    start_date?: string;
    end_date?: string;
    category_filter?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.start_date) searchParams.set('start_date', params.start_date);
    if (params?.end_date) searchParams.set('end_date', params.end_date);
    if (params?.category_filter) searchParams.set('category_filter', params.category_filter);
    return apiRequest<{
      date_range: any;
      grand_total: number;
      categories: any[];
      total_categories: number;
    }>(`/expenses/analytics/categories${searchParams.toString() ? `?${searchParams.toString()}` : ''}`);
  },

  // Recycle bin methods
  getDeletedExpenses: () =>
    apiRequest<DeletedExpense[]>('/expenses/recycle-bin'),
  restoreExpense: (id: number, newStatus: string = 'recorded') =>
    apiRequest(`/expenses/${id}/restore`, {
      method: 'POST',
      body: JSON.stringify({ new_status: newStatus }),
    }),
  permanentlyDeleteExpense: (id: number) =>
    apiRequest(`/expenses/${id}/permanent`, { method: 'DELETE' }),
  emptyRecycleBin: () =>
    apiRequest('/expenses/recycle-bin/empty', { method: 'POST' }),
};

// Dashboard API
export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    try {
      const [clientsData, invoicesData, payments] = await Promise.all([
        clientApi.getClients(0, 1000), // get more for dashboard
        invoiceApi.getInvoices(undefined, undefined, 0, 1000),
        paymentApi.getPayments(),
      ]);

      const clients = clientsData.items;
      const invoices = invoicesData.items;

      const totalClients = clientsData.total;
      // Group totals by currency
      const totalIncome: Record<string, number> = {};
      const pendingInvoices: Record<string, number> = {};
      const totalExpenses: Record<string, number> = {};

      invoices.forEach(invoice => {
        const currency = invoice.currency || 'USD';

        // Only count income from invoices where the payer is 'Client'
        if ((invoice.status === 'paid' || invoice.status === 'partially_paid') && invoice.payer === 'Client') {
          totalIncome[currency] = (totalIncome[currency] || 0) + invoice.paid_amount;
        }
        // Calculate pending amounts for invoices that are not fully paid
        if (invoice.status === 'pending' || invoice.status === 'overdue' || invoice.status === 'partially_paid') {
          const outstandingAmount = invoice.amount - (invoice.paid_amount || 0);
          if (outstandingAmount > 0) {
            pendingInvoices[currency] = (pendingInvoices[currency] || 0) + outstandingAmount;
          }
        }
      });

      // Fetch and calculate total expenses
      try {
        const expenses = await expenseApi.getExpenses();
        // Ensure expenses is an array before iterating
        if (Array.isArray(expenses)) {
          expenses.forEach(expense => {
            const currency = expense.currency || 'USD';
            const amount = expense.total_amount || expense.amount || 0;

            totalExpenses[currency] = (totalExpenses[currency] || 0) + amount;
          });
        } else {
          console.warn('Expenses API returned non-array response:', expenses);
        }
      } catch (error) {
        console.error('Failed to fetch expenses for dashboard:', error);
      }

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

      // Calculate real payment trends metrics
      let onTimePaymentRate = 0;
      let averagePaymentTime = 0;
      let overdueRate = 0;

      if (invoices && invoices.length > 0) {
        const paidInvoices = invoices.filter(inv => inv.status === 'paid' || inv.status === 'partially_paid');
        const overdueInvoices = invoices.filter(inv => inv.status === 'overdue');
        
        // Calculate on-time payment rate
        if (paidInvoices.length > 0) {
          const onTimePayments = paidInvoices.filter(invoice => {
            if (!invoice.due_date || !invoice.updated_at) return false;
            const dueDate = new Date(invoice.due_date);
            const paidDate = new Date(invoice.updated_at);
            return paidDate <= dueDate;
          });
          onTimePaymentRate = Math.round((onTimePayments.length / paidInvoices.length) * 100);
        }

        // Calculate average payment time (in days)
        if (paidInvoices.length > 0) {
          const totalPaymentDays = paidInvoices.reduce((sum, invoice) => {
            if (!invoice.date || !invoice.updated_at) return sum;
            const createdDate = new Date(invoice.date);
            const paidDate = new Date(invoice.updated_at);
            const daysDiff = Math.ceil((paidDate.getTime() - createdDate.getTime()) / (1000 * 60 * 60 * 24));
            return sum + daysDiff;
          }, 0);
          averagePaymentTime = Math.round(totalPaymentDays / paidInvoices.length);
        }

        // Calculate overdue rate
        overdueRate = Math.round((overdueInvoices.length / invoices.length) * 100);
      }

      console.log('Payment trends calculations:', {
        onTimePaymentRate,
        averagePaymentTime,
        overdueRate
      });

      return {
        totalIncome,
        pendingInvoices,
        totalExpenses,
        totalClients,
        invoicesPaid,
        invoicesPending,
        invoicesOverdue,
        paymentTrends: {
          onTimePaymentRate,
          averagePaymentTime,
          overdueRate
        },
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
        totalExpenses: {},
        totalClients: 0,
        invoicesPaid: 0,
        invoicesPending: 0,
        invoicesOverdue: 0,
        paymentTrends: {
          onTimePaymentRate: 0,
          averagePaymentTime: 0,
          overdueRate: 0
        },
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
  testEmailConfiguration: () => apiRequest<any>("/email/test", { method: 'POST' }),
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
};

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
      console.log('DownloadReport: Starting download for report ID:', reportId);

      // For downloads, we need to bypass the JSON parsing in apiRequest
      const token = localStorage.getItem('token');
      const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
        try { const user = JSON.parse(localStorage.getItem('user') || '{}'); return user.tenant_id?.toString(); } catch { return undefined; }
      })();

      console.log('DownloadReport: Auth check - token exists:', !!token, 'tenantId:', tenantId);

      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const downloadUrl = `${API_BASE_URL}/reports/download/${reportId}`;
      console.log('DownloadReport: Making request to:', downloadUrl);

      const response = await fetch(downloadUrl, {
        method: 'GET',
        headers,
      });

      console.log('DownloadReport: Response status:', response.status, response.statusText);

      // Handle 401 errors specifically for downloads
      if (response.status === 401) {
        console.error('DownloadReport: 401 Unauthorized - clearing auth data');
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        localStorage.removeItem('selected_tenant_id');
        window.location.replace('/login');
        throw new Error('Authentication failed. Please log in again.');
      }

      if (!response.ok) {
        console.error('DownloadReport: Request failed with status:', response.status, response.statusText);
        throw new Error(`Download failed: ${response.status} ${response.statusText}`);
      }

      console.log('DownloadReport: Download successful');
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

// === INVENTORY MANAGEMENT API ===

export const inventoryApi = {
  // Categories
  getCategories: (activeOnly = true) =>
    apiRequest<InventoryCategory[]>(`/inventory/categories?active_only=${activeOnly}`),

  getCategory: (id: number) =>
    apiRequest<InventoryCategory>(`/inventory/categories/${id}`),

  createCategory: (category: Omit<InventoryCategory, 'id' | 'created_at' | 'updated_at'>) =>
    apiRequest<InventoryCategory>('/inventory/categories', {
      method: 'POST',
      body: JSON.stringify(category),
    }),

  updateCategory: (id: number, category: Partial<Omit<InventoryCategory, 'id' | 'created_at' | 'updated_at'>>) =>
    apiRequest<InventoryCategory>(`/inventory/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(category),
    }),

  deleteCategory: (id: number) =>
    apiRequest(`/inventory/categories/${id}`, {
      method: 'DELETE',
    }),

  // Items
  getItems: (params?: {
    skip?: number;
    limit?: number;
    query?: string;
    category_id?: number;
    item_type?: string;
    is_active?: boolean;
    track_stock?: boolean;
    low_stock_only?: boolean;
    min_price?: number;
    max_price?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set('skip', params.skip.toString());
    if (params?.limit !== undefined) searchParams.set('limit', params.limit.toString());
    if (params?.query) searchParams.set('query', params.query);
    if (params?.category_id !== undefined) searchParams.set('category_id', params.category_id.toString());
    if (params?.item_type) searchParams.set('item_type', params.item_type);
    if (params?.is_active !== undefined) searchParams.set('is_active', params.is_active.toString());
    if (params?.track_stock !== undefined) searchParams.set('track_stock', params.track_stock.toString());
    if (params?.low_stock_only !== undefined) searchParams.set('low_stock_only', params.low_stock_only.toString());
    if (params?.min_price !== undefined) searchParams.set('min_price', params.min_price.toString());
    if (params?.max_price !== undefined) searchParams.set('max_price', params.max_price.toString());

    const queryString = searchParams.toString();
    return apiRequest<InventoryListResponse>(`/inventory/items${queryString ? `?${queryString}` : ''}`);
  },

  searchItems: (query: string, limit = 50) =>
    apiRequest<{ results: InventoryItem[]; total: number }>(`/inventory/items/search?q=${encodeURIComponent(query)}&limit=${limit}`),

  getItem: (id: number) =>
    apiRequest<InventoryItem>(`/inventory/items/${id}`),

  createItem: (item: Omit<InventoryItem, 'id' | 'created_at' | 'updated_at'>) =>
    apiRequest<InventoryItem>('/inventory/items', {
      method: 'POST',
      body: JSON.stringify(item),
    }),

  updateItem: (id: number, item: Partial<Omit<InventoryItem, 'id' | 'created_at' | 'updated_at'>>) =>
    apiRequest<InventoryItem>(`/inventory/items/${id}`, {
      method: 'PUT',
      body: JSON.stringify(item),
    }),

  deleteItem: (id: number) =>
    apiRequest(`/inventory/items/${id}`, {
      method: 'DELETE',
    }),

  // Stock Management
  adjustStock: (itemId: number, quantity: number, reason: string) =>
    apiRequest(`/inventory/items/${itemId}/stock/adjust`, {
      method: 'POST',
      body: JSON.stringify({ quantity, reason }),
    }),

  getStockMovements: (itemId: number, limit = 50, movementType?: string) => {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (movementType) params.set('movement_type', movementType);
    return apiRequest<StockMovement[]>(`/inventory/items/${itemId}/stock/movements?${params.toString()}`);
  },

  getStockMovementsByReference: (referenceType: string, referenceId: number) =>
    apiRequest<StockMovement[]>(`/inventory/movements/by-reference/${referenceType}/${referenceId}`),

  // Invoice-Inventory Linking
  getInvoicesLinkedToInventoryItem: (itemId: number) =>
    apiRequest<InvoiceInventoryLink[]>(`/inventory/items/${itemId}/linked-invoices`),

  getInventoryItemStockSummary: (itemId: number, days = 30) =>
    apiRequest<InventoryStockSummary>(`/inventory/items/${itemId}/stock-movement-summary?days=${days}`),

  getLowStockAlerts: (thresholdDays = 30) =>
    apiRequest<LowStockAlertsResponse>(`/inventory/alerts/low-stock?threshold_days=${thresholdDays}`),

  checkStockAvailability: (itemId: number, requestedQuantity: number) =>
    apiRequest(`/inventory/items/${itemId}/availability?requested_quantity=${requestedQuantity}`),

  // Analytics & Reporting
  getAnalytics: () =>
    apiRequest<InventoryAnalytics>('/inventory/analytics'),

  getAdvancedAnalytics: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const queryString = params.toString();
    return apiRequest(`/inventory/analytics/advanced${queryString ? `?${queryString}` : ''}`);
  },

  getSalesVelocity: (days = 30) =>
    apiRequest(`/inventory/analytics/sales-velocity?days=${days}`),

  getForecasting: (forecastDays = 90) =>
    apiRequest(`/inventory/analytics/forecasting?forecast_days=${forecastDays}`),

  getValueReport: () =>
    apiRequest<InventoryValueReport>('/inventory/reports/value'),

  getProfitabilityAnalysis: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const queryString = params.toString();
    return apiRequest<ProfitabilityAnalysis>(`/inventory/reports/profitability${queryString ? `?${queryString}` : ''}`);
  },

  getTurnoverAnalysis: (months = 12) =>
    apiRequest<InventoryTurnoverAnalysis>(`/inventory/reports/turnover?months=${months}`),

  getCategoryPerformance: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const queryString = params.toString();
    return apiRequest<CategoryPerformanceReport>(`/inventory/reports/categories${queryString ? `?${queryString}` : ''}`);
  },

  getSalesVelocityReport: (days = 30) =>
    apiRequest(`/inventory/reports/sales-velocity?days=${days}`),

  getDashboardData: () =>
    apiRequest<InventoryDashboardData>('/inventory/reports/dashboard'),

  getStockMovementSummary: (itemId?: number, days = 30) => {
    const params = new URLSearchParams({ days: days.toString() });
    if (itemId !== undefined) params.set('item_id', itemId.toString());
    return apiRequest(`/inventory/reports/stock-movements?${params.toString()}`);
  },

  // Integration APIs
  populateInvoiceItem: (inventoryItemId: number, quantity = 1) =>
    apiRequest(`/inventory/invoice-items/populate?inventory_item_id=${inventoryItemId}&quantity=${quantity}`),

  validateInvoiceStock: (invoiceItems: any[]) =>
    apiRequest('/inventory/invoice-items/validate-stock', {
      method: 'POST',
      body: JSON.stringify({ invoice_items: invoiceItems }),
    }),

  getInvoiceInventorySummary: (invoiceId: number) =>
    apiRequest(`/inventory/invoice/${invoiceId}/inventory-summary`),

  createInventoryPurchase: (purchase: InventoryPurchaseCreate) =>
    apiRequest('/inventory/expenses/purchase', {
      method: 'POST',
      body: JSON.stringify(purchase),
    }),

  getInventoryPurchaseSummary: (params?: {
    start_date?: string;
    end_date?: string;
    vendor?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.start_date) searchParams.set('start_date', params.start_date);
    if (params?.end_date) searchParams.set('end_date', params.end_date);
    if (params?.vendor) searchParams.set('vendor', params.vendor);
    const queryString = searchParams.toString();
    return apiRequest(`/inventory/expenses/purchase-summary${queryString ? `?${queryString}` : ''}`);
  },

  getExpenseInventorySummary: (expenseId: number) =>
    apiRequest(`/inventory/expense/${expenseId}/inventory-summary`),

  // Bulk Operations
  createCategoriesBulk: (categories: Omit<InventoryCategory, 'id' | 'created_at' | 'updated_at'>[]) =>
    apiRequest<InventoryCategory[]>('/inventory/categories/bulk', {
      method: 'POST',
      body: JSON.stringify(categories),
    }),

  createItemsBulk: (items: Omit<InventoryItem, 'id' | 'created_at' | 'updated_at'>[]) =>
    apiRequest<InventoryItem[]>('/inventory/items/bulk', {
      method: 'POST',
      body: JSON.stringify(items),
    }),

  createStockMovementsBulk: (movements: StockMovementCreate[]) =>
    apiRequest<StockMovement[]>('/inventory/stock-movements/bulk', {
      method: 'POST',
      body: JSON.stringify(movements),
    }),

  // Barcode Management
  getItemByBarcode: (barcode: string) =>
    apiRequest<InventoryItem>(`/inventory/items/barcode/${encodeURIComponent(barcode)}`),

  updateItemBarcode: (itemId: number, barcodeData: {
    barcode: string;
    barcode_type?: string;
    barcode_format?: string;
  }) =>
    apiRequest(`/inventory/items/${itemId}/barcode`, {
      method: 'POST',
      body: JSON.stringify(barcodeData),
    }),

  validateBarcode: (barcode: string) =>
    apiRequest(`/inventory/barcode/validate`, {
      method: 'POST',
      body: JSON.stringify({ barcode }),
    }),

  getBarcodeSuggestions: (itemName: string, sku?: string) => {
    const params = new URLSearchParams({ item_name: itemName });
    if (sku) params.set('sku', sku);
    return apiRequest<{ suggestions: string[] }>(`/inventory/barcode/suggestions?${params.toString()}`);
  },

  bulkUpdateBarcodes: (barcodeUpdates: Array<{
    item_id: number;
    barcode: string;
    barcode_type?: string;
    barcode_format?: string;
  }>) =>
    apiRequest('/inventory/barcode/bulk-update', {
      method: 'POST',
      body: JSON.stringify(barcodeUpdates),
    }),

  // Import/Export
  uploadReceipt: async (id: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest<Expense>(`/expenses/${id}/receipt`, {
      method: 'POST',
      body: formData,
    });
  },
  acceptReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/accept-review`, { method: 'POST' }),
  reReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/review`, { method: 'POST' }),
  importInventoryCSV: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest('/inventory/import/csv', {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set content-type for FormData
    });
  },

  exportInventoryCSV: async (params?: {
    include_inactive?: boolean;
    category_id?: number;
  }) => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') ||
      (() => {
        try { const user = JSON.parse(localStorage.getItem('user') || '{}'); return user.tenant_id?.toString(); } catch { return undefined; }
      })();

    const searchParams = new URLSearchParams();
    if (params?.include_inactive) searchParams.set('include_inactive', 'true');
    if (params?.category_id) searchParams.set('category_id', params.category_id.toString());
    const queryString = searchParams.toString();

    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const response = await fetch(`${API_BASE_URL}/inventory/export/csv${queryString ? `?${queryString}` : ''}`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      const errorText = await response.text();
      try { throw new Error(JSON.parse(errorText).detail || 'Export failed'); }
      catch { throw new Error(errorText || 'Export failed'); }
    }

    return response.blob();
  },
};

// Reminder API methods
export const reminderApi = {
  // Reminders CRUD
  getReminders: async (params: {
    page?: number;
    per_page?: number;
    status?: string[];
    priority?: string[];
    assigned_to_id?: number;
    created_by_id?: number;
    due_date_from?: string;
    due_date_to?: string;
    search?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  } = {}) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          value.forEach(v => searchParams.append(key, v));
        } else {
          searchParams.set(key, String(value));
        }
      }
    });
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return apiRequest<any>(`/reminders/${query}`);
  },

  getReminder: async (id: number) => {
    return apiRequest<any>(`/reminders/${id}`);
  },

  createReminder: async (reminder: any) => {
    return apiRequest<any>('/reminders/', {
      method: 'POST',
      body: JSON.stringify(reminder),
    });
  },

  updateReminder: async (id: number, reminder: any) => {
    return apiRequest<any>(`/reminders/${id}`, {
      method: 'PUT',
      body: JSON.stringify(reminder),
    });
  },

  updateReminderStatus: async (id: number, statusData: any) => {
    return apiRequest<any>(`/reminders/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify(statusData),
    });
  },

  deleteReminder: async (id: number) => {
    return apiRequest(`/reminders/${id}`, {
      method: 'DELETE',
    });
  },

  bulkUpdateReminders: async (data: any) => {
    return apiRequest<any>('/reminders/bulk-update', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  bulkDeleteReminders: async (reminderIds: number[]) => {
    return apiRequest<any>('/reminders/bulk-delete', {
      method: 'DELETE',
      body: JSON.stringify(reminderIds),
    });
  },

  getDueToday: async () => {
    return apiRequest<any>('/reminders/due/today');
  },

  getOverdue: async () => {
    return apiRequest<any>('/reminders/overdue/');
  },

  // Notification methods
  getUnreadNotificationCount: async () => {
    return apiRequest<{ count: number }>('/reminders/notifications/unread-count');
  },

  getRecentNotifications: async (limit: number = 20) => {
    return apiRequest<any>(`/reminders/notifications/recent?limit=${limit}`);
  },

  markNotificationAsRead: async (notificationId: number) => {
    return apiRequest(`/reminders/notifications/${notificationId}/read`, {
      method: 'POST',
    });
  },

  markAllNotificationsAsRead: async () => {
    return apiRequest('/reminders/notifications/mark-all-read', {
      method: 'POST',
    });
  },

  dismissNotification: async (notificationId: number) => {
    return apiRequest(`/reminders/notifications/${notificationId}`, {
      method: 'DELETE',
    });
  },

  getReminderNotifications: async (reminderId: number) => {
    return apiRequest<any>(`/reminders/${reminderId}/notifications`);
  },

  unsnoozeReminder: async (id: number) => {
    return apiRequest<any>(`/reminders/${id}/unsnooze`, {
      method: 'POST',
    });
  },
};

// Activity API methods
export interface ActivityItem {
  id: string;
  type: 'invoice' | 'client' | 'inventory' | 'approval' | 'reminder' | 'expense' | 'report';
  title: string;
  description: string;
  timestamp: string;
  status?: string;
  amount?: number;
  currency?: string;
  link?: string;
  user_id?: number;
  entity_id?: string;
}

export const activityApi = {
  // Get recent activities across all modules
  getRecentActivities: async (limit = 10): Promise<ActivityItem[]> => {
    try {
      // This would be implemented as a backend endpoint that aggregates activities
      // For now, we'll fetch from multiple endpoints and combine them
      const activities: ActivityItem[] = [];

      // Fetch recent invoices
      try {
        const data = await invoiceApi.getInvoices();
        const invoices = data.items;
        const recentInvoices = invoices
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
          .slice(0, 3)
          .map(invoice => ({
            id: `invoice-${invoice.id}`,
            type: 'invoice' as const,
            title: `Invoice ${invoice.number} ${invoice.status === 'draft' ? 'created' : invoice.status}`,
            description: `Invoice for ${invoice.client_name || 'client'}`,
            timestamp: invoice.created_at,
            status: invoice.status,
            amount: invoice.amount,
            currency: invoice.currency,
            link: `/invoices/${invoice.id}`
          }));
        activities.push(...recentInvoices);
      } catch (error) {
        console.warn('Failed to fetch recent invoices for activity feed:', error);
      }

      // Fetch recent clients
      try {
        const data = await clientApi.getClients(0, 10);
        const clients = data.items;
        const recentClients = clients
          .sort((a, b) => {
            const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
            const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
            return dateB - dateA;
          })
          .slice(0, 2)
          .map(client => ({
            id: `client-${client.id}`,
            type: 'client' as const,
            title: 'New client added',
            description: `${client.name} joined as a client`,
            timestamp: client.created_at,
            link: `/clients/${client.id}`
          }));
        activities.push(...recentClients);
      } catch (error) {
        console.warn('Failed to fetch recent clients for activity feed:', error);
      }

      // Fetch recent expenses
      try {
        const expenses = await expenseApi.getExpenses();
        const recentExpenses = expenses
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
          .slice(0, 2)
          .map(expense => ({
            id: `expense-${expense.id}`,
            type: 'expense' as const,
            title: `Expense ${(expense as any).approval_status || 'submitted'}`,
            description: (expense as any).description || expense.category || 'Business expense',
            timestamp: expense.created_at,
            status: (expense as any).approval_status,
            amount: expense.amount,
            currency: expense.currency,
            link: `/expenses/${expense.id}`
          }));
        activities.push(...recentExpenses);
      } catch (error) {
        console.warn('Failed to fetch recent expenses for activity feed:', error);
      }

      // Fetch recent approvals
      try {
        const approvalsResponse = await approvalApi.getPendingApprovals();
        const approvals = Array.isArray(approvalsResponse) ? approvalsResponse : approvalsResponse.approvals || [];
        const recentApprovals = approvals
          .sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime())
          .slice(0, 2)
          .map(approval => ({
            id: `approval-${approval.id}`,
            type: 'approval' as const,
            title: `${approval.expense_type || 'Expense'} approval ${approval.status}`,
            description: approval.description || 'Expense approval',
            timestamp: approval.submitted_at,
            status: approval.status,
            amount: approval.amount,
            currency: approval.currency,
            link: `/approvals/${approval.id}`
          }));
        activities.push(...recentApprovals);
      } catch (error) {
        console.warn('Failed to fetch recent approvals for activity feed:', error);
      }

      // Sort all activities by timestamp and limit
      return activities
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        .slice(0, limit);

    } catch (error) {
      console.error('Failed to fetch recent activities:', error);
      throw error;
    }
  },

  // Get activities for a specific type
  getActivitiesByType: async (type: ActivityItem['type'], limit = 10): Promise<ActivityItem[]> => {
    const allActivities = await activityApi.getRecentActivities(50);
    return allActivities.filter(activity => activity.type === type).slice(0, limit);
  },

  // Get activities for a specific date range
  getActivitiesByDateRange: async (startDate: string, endDate: string): Promise<ActivityItem[]> => {
    const allActivities = await activityApi.getRecentActivities(100);
    return allActivities.filter(activity => {
      const activityDate = new Date(activity.timestamp);
      return activityDate >= new Date(startDate) && activityDate <= new Date(endDate);
    });
  }
};

// ============================================================================
// Export Destination API Types
// ============================================================================

export interface ExportDestination {
  id: number;
  tenant_id: number;
  name: string;
  destination_type: 's3' | 'azure' | 'gcs' | 'google_drive' | 'local';
  is_active: boolean;
  is_default: boolean;
  config?: Record<string, any>;
  masked_credentials?: Record<string, string>;
  last_test_at?: string;
  last_test_success?: boolean;
  last_test_error?: string;
  created_at: string;
  updated_at?: string;
  created_by?: number;
  testable?: boolean;
}

export interface ExportDestinationCreate {
  name: string;
  destination_type: 's3' | 'azure' | 'gcs' | 'google_drive' | 'local';
  credentials: Record<string, any>;
  config?: Record<string, any>;
  is_default?: boolean;
}

export interface ExportDestinationUpdate {
  name?: string;
  credentials?: Record<string, any>;
  config?: Record<string, any>;
  is_active?: boolean;
  is_default?: boolean;
}

export interface ExportDestinationTestResult {
  success: boolean;
  message: string;
  error_details?: string;
  tested_at: string;
}

// ============================================================================
// Export Destination API Methods
// ============================================================================

export const exportDestinationApi = {
  // Get all export destinations for the current tenant
  getDestinations: () =>
    apiRequest<ExportDestination[]>('/export-destinations/'),

  // Get a specific export destination
  getDestination: (id: number) =>
    apiRequest<ExportDestination>(`/export-destinations/${id}`),

  // Create a new export destination
  createDestination: (data: ExportDestinationCreate) =>
    apiRequest<ExportDestination>('/export-destinations/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Update an export destination
  updateDestination: (id: number, data: ExportDestinationUpdate) =>
    apiRequest<ExportDestination>(`/export-destinations/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Delete an export destination
  deleteDestination: (id: number) =>
    apiRequest<{ message: string }>(`/export-destinations/${id}`, {
      method: 'DELETE',
    }),

  // Test connection to an export destination
  testConnection: (id: number) =>
    apiRequest<ExportDestinationTestResult>(`/export-destinations/${id}/test`, {
      method: 'POST',
    }),
};

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

// Gamification API methods
export const gamificationApi = {
  // Module status and control
  getStatus: () =>
    apiRequest<import('@/types/gamification').ModuleStatus>('/gamification/status'),

  enable: (request: import('@/types/gamification').EnableGamificationRequest) =>
    apiRequest<import('@/types/gamification').UserGamificationProfile>('/gamification/enable', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  disable: (request: import('@/types/gamification').DisableGamificationRequest) =>
    apiRequest<{ message: string }>('/gamification/disable', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  // User profile and preferences
  getProfile: () =>
    apiRequest<import('@/types/gamification').UserGamificationProfile | null>('/gamification/profile'),

  updatePreferences: (preferences: import('@/types/gamification').GamificationPreferences) =>
    apiRequest<import('@/types/gamification').UserGamificationProfile>('/gamification/preferences', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    }),

  // Dashboard data
  getDashboard: () =>
    apiRequest<import('@/types/gamification').GamificationDashboard | null>('/gamification/dashboard'),

  // Level progression
  getLevelProgress: () =>
    apiRequest<import('@/types/gamification').LevelProgress | null>('/gamification/level/progress'),

  getLevelRewards: (level: number) =>
    apiRequest<any>(`/gamification/level/rewards/${level}`),

  getLevelCurve: () =>
    apiRequest<any>('/gamification/level/curve'),

  // Achievements
  getAchievements: (category?: string, completedOnly = false) =>
    apiRequest<import('@/types/gamification').UserAchievement[]>(`/gamification/achievements?${new URLSearchParams({
      ...(category && { category }),
      completed_only: completedOnly.toString()
    })}`),

  getAchievementProgress: (achievementId: string) =>
    apiRequest<any>(`/gamification/achievements/${achievementId}/progress`),

  getMilestoneAchievements: (category: string) =>
    apiRequest<import('@/types/gamification').Achievement[]>(`/gamification/achievements/milestones/${category}`),

  // Achievement Rules
  getAchievementRules: () =>
    apiRequest<{ rules: any[], total_count: number }>('/gamification/admin/achievements/rules'),

  toggleAchievementRule: (achievementId: string) =>
    apiRequest<{ achievement_id: string, is_active: boolean, message: string }>(`/gamification/admin/achievements/rules/${achievementId}/toggle`, {
      method: 'PUT',
    }),

  // Streaks
  getStreaks: () =>
    apiRequest<import('@/types/gamification').UserStreak[]>('/gamification/streaks'),

  getStreakAnalytics: () =>
    apiRequest<any>('/gamification/streaks/analytics'),

  handleStreakBreak: (habitType: string) =>
    apiRequest<any>(`/gamification/streaks/${habitType}/break`, {
      method: 'POST',
    }),

  // Challenges
  getAvailableChallenges: (challengeType?: string) =>
    apiRequest<import('@/types/gamification').Challenge[]>(`/gamification/challenges/available?${new URLSearchParams({
      ...(challengeType && { challenge_type: challengeType })
    })}`),

  getWeeklyChallenges: () =>
    apiRequest<import('@/types/gamification').Challenge[]>('/gamification/challenges/weekly'),

  getMonthlyChallenges: () =>
    apiRequest<import('@/types/gamification').Challenge[]>('/gamification/challenges/monthly'),

  optIntoChallenge: (challengeId: number) =>
    apiRequest<import('@/types/gamification').UserChallenge>(`/gamification/challenges/${challengeId}/opt-in`, {
      method: 'POST',
    }),

  optOutOfChallenge: (challengeId: number) =>
    apiRequest<{ message: string }>(`/gamification/challenges/${challengeId}/opt-out`, {
      method: 'POST',
    }),

  getMyChallenges: (activeOnly = true, completedOnly = false) =>
    apiRequest<import('@/types/gamification').UserChallenge[]>(`/gamification/challenges/my?${new URLSearchParams({
      active_only: activeOnly.toString(),
      completed_only: completedOnly.toString()
    })}`),

  getChallengeProgress: (challengeId: number) =>
    apiRequest<any>(`/gamification/challenges/${challengeId}/progress`),

  // Financial Health Score
  getFinancialHealthScore: () =>
    apiRequest<any>('/gamification/health-score'),

  getHealthScoreComponents: () =>
    apiRequest<any>('/gamification/health-score/components'),

  recalculateHealthScore: () =>
    apiRequest<{ message: string; new_score: number }>('/gamification/health-score/recalculate', {
      method: 'POST',
    }),

  // Event processing
  processEvent: (event: import('@/types/gamification').FinancialEvent) =>
    apiRequest<import('@/types/gamification').ProcessFinancialEventResponse>('/gamification/events/process', {
      method: 'POST',
      body: JSON.stringify({ event }),
    }),

  // Validation
  validate: () =>
    apiRequest<any>('/gamification/validate'),
};
