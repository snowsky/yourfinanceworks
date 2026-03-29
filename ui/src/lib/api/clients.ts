import { apiRequest } from './_base';

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
  owner_user_id?: number | null;
  stage?: string;
  relationship_status?: string;
  source?: string | null;
  last_contact_at?: string | null;
  next_follow_up_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClientRecordSummary {
  open_invoices_count: number;
  overdue_invoices_count: number;
  total_outstanding: number;
  total_paid: number;
  open_tasks_count: number;
  completed_tasks_count: number;
  last_payment_at?: string | null;
  last_invoice_at?: string | null;
}

export interface ClientActivityItem {
  type: string;
  timestamp: string;
  title: string;
  description?: string | null;
  actor_name?: string | null;
  entity_type: string;
  entity_id: string;
  metadata?: Record<string, unknown> | null;
}

export interface ClientTaskItem {
  id: number;
  title: string;
  description?: string | null;
  due_date: string;
  status: string;
  priority: string;
  assigned_to_id: number;
  task_origin?: string | null;
  workflow_id?: number | null;
}

export interface ClientRecordResponse {
  client: Client;
  summary: ClientRecordSummary;
  recent_activity: ClientActivityItem[];
  open_tasks: ClientTaskItem[];
}

export interface ClientRecordUpdateRequest {
  owner_user_id?: number | null;
  stage?: string;
  relationship_status?: string;
  source?: string | null;
  last_contact_at?: string | null;
  next_follow_up_at?: string | null;
}

export interface ClientTaskCreateRequest {
  title: string;
  description?: string | null;
  due_date: string;
  priority: string;
  assigned_to_id: number;
}

export interface ClientNote {
  id: number;
  note: string;
  user_id: number;
  client_id: number;
  created_at: string;
  updated_at: string;
}

// Client Activity Timeline types
export interface TimelineEvent {
  id: string;
  event_type: 'invoice' | 'payment' | 'expense' | 'bank_transaction' | 'note';
  title: string;
  description: string;
  amount: number | null;
  currency: string | null;
  status: string | null;
  date: string;
  source: 'invoice' | 'expense' | 'bank_statement' | 'note';
  metadata: Record<string, unknown>;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface TimelineParams {
  page?: number;
  page_size?: number;
  event_types?: string;
  source?: string;
}

// Client API methods
export const clientApi = {
  getClients: async (skip: number = 0, limit: number = 100, label?: string): Promise<{ items: Client[], total: number }> => {
    // Ensure skip and limit are valid numbers
    const skipNum = typeof skip === 'number' ? skip : parseInt(String(skip), 10) || 0;
    const limitNum = typeof limit === 'number' ? limit : parseInt(String(limit), 10) || 100;

    let url = `/clients/?skip=${skipNum}&limit=${limitNum}`;
    if (label) url += `&label_filter=${encodeURIComponent(label)}`;
    return apiRequest<{ items: Client[], total: number }>(url);
  },
  bulkLabels: (ids: number[], action: 'add' | 'remove', label: string) =>
    apiRequest<{ success: boolean; count: number }>('/clients/bulk-labels', {
      method: 'POST',
      body: JSON.stringify({ ids, action, label }),
    }),
  getClient: (id: number) => apiRequest<Client>(`/clients/${id}`),
  getClientRecord: (id: number) => apiRequest<ClientRecordResponse>(`/clients/${id}/record`),
  updateClientRecord: (id: number, payload: ClientRecordUpdateRequest) =>
    apiRequest<Client>(`/clients/${id}/record`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  getClientTasks: (id: number) => apiRequest<ClientTaskItem[]>(`/clients/${id}/tasks`),
  createClientTask: (id: number, payload: ClientTaskCreateRequest) =>
    apiRequest<ClientTaskItem>(`/clients/${id}/tasks`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
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
  summarizeClientNotes: (clientId: number, language: string = "English") =>
    apiRequest<{ success: boolean; data?: { summary: string; provider: string; model: string }; error?: string }>(`/ai/summarize-client-notes/${clientId}?language=${encodeURIComponent(language)}`, {
      method: 'POST',
    }),
};

export const timelineApi = {
  getTimeline: (clientId: number, params: TimelineParams = {}) => {
    const searchParams = new URLSearchParams();
    if (params.page !== undefined) searchParams.append('page', params.page.toString());
    if (params.page_size !== undefined) searchParams.append('page_size', params.page_size.toString());
    if (params.event_types) searchParams.append('event_types', params.event_types);
    if (params.source) searchParams.append('source', params.source);
    const qs = searchParams.toString();
    return apiRequest<TimelineResponse>(`/clients/${clientId}/timeline${qs ? `?${qs}` : ''}`);
  },
};
