import { API_BASE_URL, apiRequest } from './_base';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';

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
  review_status?: 'not_started' | 'pending' | 'diff_found' | 'no_diff' | 'reviewed' | 'failed' | 'rejected';
  review_result?: any;
  reviewed_at?: string;
  is_inventory_consumption?: boolean;
}

export interface ExpenseAttachmentMeta {
  id: number;
  filename: string;
  content_type?: string;
  file_size?: number;
  uploaded_at?: string;
  analysis_status?: 'not_started' | 'processing' | 'done' | 'failed';
  analysis_error?: string;
  analysis_result?: any;
  extracted_amount?: number;
}

// Define recycle bin types
export interface DeletedExpense extends Expense {
  is_deleted: boolean;
  deleted_at?: string | null;
  deleted_by?: number | null;
  deleted_by_username?: string | null;
}

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
    const tenantId = getTenantId();

    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const uploadUrl = `${API_BASE_URL}/expenses/${expenseId}/upload-receipt`;
    const response = await fetch(uploadUrl, { method: 'POST', headers, body: formData, credentials: 'include' });
    if (!response.ok) {
      const errorText = await response.text();
      try { throw new Error(JSON.parse(errorText).detail || 'Failed to upload receipt'); }
      catch { throw new Error(errorText || 'Failed to upload receipt'); }
    }
    return response.json();
  },
  acceptReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/accept-review`, { method: 'POST' }),
  rejectReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/reject-review`, { method: 'POST' }),
  reReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/review`, { method: 'POST' }),
  cancelReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/cancel-review`, { method: 'POST' }),
  listAttachments: async (expenseId: number) => {
    return apiRequest<ExpenseAttachmentMeta[]>(`/expenses/${expenseId}/attachments`);
  },
  deleteAttachment: async (expenseId: number, attachmentId: number) => {
    return apiRequest(`/expenses/${expenseId}/attachments/${attachmentId}`, { method: 'DELETE' });
  },
  downloadAttachmentBlob: async (expenseId: number, attachmentId: number, inline: boolean = true): Promise<{ blob: Blob; contentType: string | null }> => {
    const tenantId = getTenantId();

    const headers: Record<string, string> = {};
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const url = `${API_BASE_URL}/expenses/${expenseId}/attachments/${attachmentId}/download?inline=${inline}`;
    const resp = await fetch(url, { headers, credentials: 'include' });
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
      body: JSON.stringify({ expenses }),
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
  getDeletedExpenses: (skip: number = 0, limit: number = 100) =>
    apiRequest<{ items: DeletedExpense[]; total: number }>(`/expenses/recycle-bin?skip=${skip}&limit=${limit}`),
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
