import { apiRequest } from './_base';
import type { ExpenseApproval, ApprovalHistoryEntry, ApprovalDashboardStats, ApprovalDelegate, ApprovalDelegateCreate, ApprovalDelegateUpdate } from '@/types';
import type { Expense } from './expenses';

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
    if (filters?.limit !== undefined) params.append('limit', filters.limit.toString());
    if (filters?.offset !== undefined) params.append('offset', filters.offset.toString());
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

  // Unsubmit an expense approval request
  unsubmitExpenseApproval: (expenseId: number) =>
    apiRequest<{ success: boolean; message: string; }>(`/approvals/expenses/${expenseId}/unsubmit`, {
      method: 'POST',
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
    if (filters?.limit !== undefined) params.append('limit', filters.limit.toString());
    if (filters?.offset !== undefined) params.append('offset', filters.offset.toString());

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

  // Unsubmit an invoice approval request
  unsubmitInvoiceApproval: (invoiceId: number) =>
    apiRequest<{ success: boolean; message: string; }>(`/approvals/invoices/${invoiceId}/unsubmit`, {
      method: 'POST',
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
    if (filters?.limit !== undefined) params.append('limit', filters.limit.toString());
    if (filters?.offset !== undefined) params.append('offset', filters.offset.toString());

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
