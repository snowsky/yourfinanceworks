import { API_BASE_URL, apiRequest } from './_base';
import type { InvoiceHistory, InvoiceHistoryCreate } from './discounts';

// Import DashboardStats type from the dashboard component
export interface DashboardStats {
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
  review_status?: 'not_started' | 'pending' | 'diff_found' | 'no_diff' | 'reviewed' | 'failed' | 'rejected';
  review_result?: any;
  reviewed_at?: string;
  // Bank statement link (reverse lookup)
  statement_transaction_id?: number | null;
  statement_id?: number | null;
}

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
        // Review fields
        review_status: apiInvoice.review_status,
        review_result: apiInvoice.review_result,
        reviewed_at: apiInvoice.reviewed_at,
        statement_transaction_id: apiInvoice.statement_transaction_id ?? null,
        statement_id: apiInvoice.statement_id ?? null,
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
        // Review fields
        review_status: apiInvoice.review_status,
        review_result: apiInvoice.review_result,
        reviewed_at: apiInvoice.reviewed_at,
        statement_transaction_id: apiInvoice.statement_transaction_id ?? null,
        statement_id: apiInvoice.statement_id ?? null,
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
        client_email: apiResponse.client_email || '',
        client_company: apiResponse.client_company || undefined,
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
        // Review fields
        review_status: apiResponse.review_status,
        review_result: apiResponse.review_result,
        reviewed_at: apiResponse.reviewed_at
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
  getDeletedInvoices: (skip: number = 0, limit: number = 100) =>
    apiRequest<{ items: any[]; total: number }>(`/invoices/recycle-bin?skip=${skip}&limit=${limit}`),
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
    const tenantId = localStorage.getItem('selected_tenant_id') ||
      (() => {
        try {
          const user = JSON.parse(localStorage.getItem('user') || '{}');
          return user.tenant_id?.toString();
        } catch { return undefined; }
      })();

    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};
    if (tenantId) {
      headers['X-Tenant-ID'] = tenantId;
    }

    const uploadUrl = `${API_BASE_URL}/invoices/${invoiceId}/upload-attachment`;

    const response = await fetch(uploadUrl, {
      method: 'POST',
      headers,
      credentials: 'include',
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
    const tenantId = localStorage.getItem('selected_tenant_id') ||
      (() => {
        try {
          const user = JSON.parse(localStorage.getItem('user') || '{}');
          return user.tenant_id?.toString();
        } catch { return undefined; }
      })();

    // Create a form to submit with proper headers
    // Auth is handled via the httpOnly cookie sent automatically by the browser
    const form = document.createElement('form');
    form.method = 'GET';
    form.action = `${API_BASE_URL}/invoices/${invoiceId}/download-attachment`;
    form.target = '_blank';

    const url = new URL(form.action);
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
    apiRequest<{ has_attachment: boolean; filename?: string; content_type?: string; file_size?: number }>(`/invoices/${invoiceId}/attachment-info`),
  previewAttachmentBlob: async (invoiceId: number, attachmentId?: number): Promise<Blob> => {
    const tenantId = getTenantId();

    const headers: Record<string, string> = {};
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    let url = `${API_BASE_URL}/invoices/${invoiceId}/preview-attachment`;
    if (attachmentId) {
      url += `?attachment_id=${attachmentId}`;
    }
    const resp = await fetch(url, { headers, credentials: 'include' });
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
  rejectReview: (id: number) => apiRequest<Invoice>(`/invoices/${id}/reject-review`, { method: 'POST' }),
  reReview: (id: number) => apiRequest<Invoice>(`/invoices/${id}/review`, { method: 'POST' }),
  cancelReview: (id: number) => apiRequest<Invoice>(`/invoices/${id}/cancel-review`, { method: 'POST' }),

  createInvoiceHistoryEntry: (invoiceId: number, historyEntry: InvoiceHistoryCreate) =>
    apiRequest<InvoiceHistory>(`/invoices/${invoiceId}/history`, {
      method: 'POST',
      body: JSON.stringify(historyEntry),
    }),
};

export const linkApi = {
  // Simple invoice list for selectors
  getInvoicesBasic: async () => {
    const list = await invoiceApi.getInvoicesWithParams({ limit: 1000 });
    // Map to minimal data
    return list.map(inv => ({ id: inv.id, number: inv.number, client_id: inv.client_id, client_name: inv.client_name, amount: inv.amount, status: inv.status }));
  },
};
