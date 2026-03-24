import { API_BASE_URL, apiRequest, getTenantId } from './_base';

export interface TransactionLinkInfo {
  id: number;
  link_type: 'transfer' | 'fx_conversion';
  notes?: string | null;
  linked_transaction_id: number;
  linked_statement_id: number;
  linked_statement_filename: string;
  created_at?: string | null;
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
  linked_transfer?: TransactionLinkInfo | null;
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
  card_type?: string;
  labels?: string[] | null;
  notes?: string | null;
  created_at?: string;
  // User attribution fields
  created_by_user_id?: number;
  created_by_username?: string;
  created_by_email?: string;
  // Review fields
  review_status?: 'not_started' | 'pending' | 'diff_found' | 'no_diff' | 'reviewed' | 'failed' | 'rejected';
  review_result?: any;
  reviewed_at?: string;
}

export interface BankStatementDetail extends BankStatementSummary {
  transactions: BankTransactionEntry[];
}

export interface DeletedBankStatement extends BankStatementSummary {
  is_deleted: boolean;
  deleted_at?: string | null;
  deleted_by?: number | null;
  deleted_by_username?: string | null;
}

export const bankStatementApi = {
  uploadAndExtract: async (
    files: File[],
    card_type: string = 'debit'
  ): Promise<{ success: boolean; statements: BankStatementSummary[] }> => {
    const tenantId = getTenantId();

    const formData = new FormData();
    files.slice(0, 12).forEach((f) => formData.append('files', f));
    formData.append('card_type', card_type);

    const headers: Record<string, string> = {};
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const url = `${API_BASE_URL}/statements/upload`;
    const resp = await fetch(url, { method: 'POST', headers, body: formData, credentials: 'include' });
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
  rejectReview: (statementId: number) => apiRequest<{ success: boolean; statement: BankStatementSummary }>(`/statements/${statementId}/reject-review`, { method: 'POST' }),
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
    const tenantId = getTenantId();
    const base = API_BASE_URL.replace(/\/$/, '');
    const url = `${base}/statements/${statementId}/file${inline ? '?inline=true' : ''}`;
    const headers: Record<string, string> = {};
    if (tenantId) headers['X-Tenant-ID'] = tenantId;
    const resp = await fetch(url, { method: 'GET', headers, credentials: 'include' });
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
  getDeletedStatements: (skip: number = 0, limit: number = 100) =>
    apiRequest<{ items: DeletedBankStatement[]; total: number }>(`/statements/recycle-bin?skip=${skip}&limit=${limit}`),
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

  createTransactionLink: (
    transactionAId: number,
    transactionBId: number,
    linkType: 'transfer' | 'fx_conversion' = 'transfer',
    notes?: string
  ) =>
    apiRequest<{ success: boolean; link: { id: number; link_type: string; notes?: string | null; created_at?: string | null; linked_for_a?: TransactionLinkInfo; linked_for_b?: TransactionLinkInfo } }>(
      '/statements/transactions/links',
      {
        method: 'POST',
        body: JSON.stringify({
          transaction_a_id: transactionAId,
          transaction_b_id: transactionBId,
          link_type: linkType,
          notes,
        }),
      }
    ),

  deleteTransactionLink: (linkId: number) =>
    apiRequest<{ success: boolean }>(`/statements/transactions/links/${linkId}`, { method: 'DELETE' }),
};
