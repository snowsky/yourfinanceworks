/**
 * Time Tracking Plugin — API Client
 *
 * Typed API functions using the `api` helper from lib/api.ts.
 */

import { api, apiRequest, API_BASE_URL } from '@/lib/api';

// -------------------------------------------------------------------------
// Types
// -------------------------------------------------------------------------

export interface Project {
  id: number;
  client_id: number;
  name: string;
  description?: string | null;
  billing_method: string;
  hourly_rate?: number | null;
  fixed_amount?: number | null;
  budget_hours?: number | null;
  budget_amount?: number | null;
  status: string;
  currency: string;
  created_by?: number | null;
  created_at: string;
  updated_at: string;
  // enriched
  client_name?: string | null;
  total_hours_logged?: number;
  total_amount_logged?: number;
}

export interface ProjectTask {
  id: number;
  project_id: number;
  name: string;
  description?: string | null;
  estimated_hours?: number | null;
  hourly_rate?: number | null;
  status: string;
  kanban_status: string;
  kanban_position: number;
  priority?: string | null;
  due_date?: string | null;
  custom_fields: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  actual_hours?: number;
}

export interface KanbanColumn {
  id: number;
  project_id: number;
  key: string;
  name: string;
  position: number;
  hidden: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectCustomField {
  id: number;
  project_id: number;
  key: string;
  name: string;
  field_type: string;
  options: string[];
  required: boolean;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectKanban {
  project: Project;
  columns: KanbanColumn[];
  tasks: ProjectTask[];
  custom_fields: ProjectCustomField[];
}

export interface TimeEntry {
  id: number;
  project_id: number;
  task_id?: number | null;
  user_id: number;
  client_id: number;
  description?: string | null;
  notes?: string | null;
  started_at: string;
  ended_at?: string | null;
  duration_minutes?: number | null;
  hourly_rate: number;
  billable: boolean;
  amount?: number | null;
  status: string;
  invoiced: boolean;
  invoice_id?: number | null;
  invoice_number?: string | null;
  created_at: string;
  updated_at: string;
  // computed
  hours: number;
  // enriched
  project_name?: string | null;
  task_name?: string | null;
  client_name?: string | null;
}

export interface TimerActiveResponse {
  active: boolean;
  entry?: TimeEntry | null;
  elapsed_seconds?: number | null;
}

export interface ProjectSummary {
  project_id: number;
  project_name: string;
  client_id: number;
  client_name?: string | null;
  status: string;
  billing_method: string;
  budget_hours?: number | null;
  budget_amount?: number | null;
  total_hours_logged: number;
  total_amount_logged: number;
  total_expenses: number;
  unbilled_hours: number;
  unbilled_amount: number;
  hours_used_pct?: number | null;
  budget_used_pct?: number | null;
}

export interface UnbilledItems {
  project_id: number;
  time_entries: UnbilledTimeEntry[];
  expenses: UnbilledExpense[];
  total_time_amount: number;
  total_expense_amount: number;
  grand_total: number;
}

export interface UnbilledTimeEntry {
  id: number;
  task_name?: string | null;
  description?: string | null;
  started_at: string;
  hours: number;
  hourly_rate: number;
  amount: number;
  billable: boolean;
}

export interface UnbilledExpense {
  id: number;
  category?: string | null;
  vendor?: string | null;
  expense_date: string;
  amount: number;
  currency?: string | null;
}

export interface ProjectInvoiceResult {
  invoice_id: number;
  invoice_number: string;
  amount: number;
  currency: string;
}

export interface TimeImportError {
  row: number;
  message: string;
}

export interface TimeImportResult {
  created_clients: number;
  created_projects: number;
  reused_projects: number;
  created_tasks: number;
  created_time_entries: number;
  skipped_rows: number;
  ai_used: boolean;
  errors: TimeImportError[];
}

export type MissingProjectStrategy = 'error' | 'single_project' | 'row_project';

// -------------------------------------------------------------------------
// Projects API
// -------------------------------------------------------------------------

export const projectApi = {
  list: (params?: { status?: string; client_id?: number; skip?: number; limit?: number }) =>
    api.get<Project[]>(`/projects${params ? '?' + new URLSearchParams(Object.entries(params || {}).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])).toString() : ''}`),

  get: (id: number) => api.get<Project>(`/projects/${id}`),

  create: (data: Partial<Project>) => api.post<Project>('/projects', data),

  update: (id: number, data: Partial<Project>) => api.patch<Project>(`/projects/${id}`, data),

  delete: (id: number) => api.delete<void>(`/projects/${id}`),

  getSummary: (id: number) => api.get<ProjectSummary>(`/projects/${id}/summary`),

  getUnbilled: (id: number) => api.get<UnbilledItems>(`/projects/${id}/unbilled`),

  createInvoice: (
    id: number,
    data: { time_entry_ids: number[]; expense_ids: number[]; due_date?: string; notes?: string }
  ) => api.post<ProjectInvoiceResult>(`/projects/${id}/invoice`, data),

  // Tasks
  listTasks: (projectId: number) => api.get<ProjectTask[]>(`/projects/${projectId}/tasks`),

  createTask: (projectId: number, data: Partial<ProjectTask>) =>
    api.post<ProjectTask>(`/projects/${projectId}/tasks`, { ...data, project_id: projectId }),

  updateTask: (projectId: number, taskId: number, data: Partial<ProjectTask>) =>
    api.patch<ProjectTask>(`/projects/${projectId}/tasks/${taskId}`, data),

  deleteTask: (projectId: number, taskId: number) =>
    api.delete<void>(`/projects/${projectId}/tasks/${taskId}`),

  getKanban: (projectId: number) =>
    api.get<ProjectKanban>(`/projects/${projectId}/kanban`),

  reorderKanban: (
    projectId: number,
    data: { tasks: Array<{ task_id: number; kanban_status: string; kanban_position: number }> }
  ) => api.post<ProjectTask[]>(`/projects/${projectId}/kanban/reorder`, data),

  updateKanbanColumns: (projectId: number, columns: Array<Pick<KanbanColumn, 'key' | 'name' | 'position' | 'hidden'>>) =>
    api.patch<KanbanColumn[]>(`/projects/${projectId}/kanban/columns`, columns),

  createCustomField: (projectId: number, data: Partial<ProjectCustomField>) =>
    api.post<ProjectCustomField>(`/projects/${projectId}/custom-fields`, data),

  updateCustomField: (projectId: number, fieldId: number, data: Partial<ProjectCustomField>) =>
    api.patch<ProjectCustomField>(`/projects/${projectId}/custom-fields/${fieldId}`, data),

  deleteCustomField: (projectId: number, fieldId: number) =>
    api.delete<void>(`/projects/${projectId}/custom-fields/${fieldId}`),
};

// -------------------------------------------------------------------------
// Time Entries API
// -------------------------------------------------------------------------

export const timeEntryApi = {
  list: (params?: {
    project_id?: number;
    task_id?: number;
    user_id?: number;
    client_id?: number;
    status?: string;
    invoiced?: boolean;
    skip?: number;
    limit?: number;
  }) => {
    const filteredParams = Object.entries(params || {}).filter(([, v]) => v !== undefined);
    const qs = filteredParams.length ? '?' + new URLSearchParams(filteredParams.map(([k, v]) => [k, String(v)])).toString() : '';
    return api.get<TimeEntry[]>(`/time-entries${qs}`);
  },

  create: (data: Partial<TimeEntry> & { started_at: string }) =>
    api.post<TimeEntry>('/time-entries', data),

  update: (id: number, data: Partial<TimeEntry>) =>
    api.patch<TimeEntry>(`/time-entries/${id}`, data),

  delete: (id: number) => api.delete<void>(`/time-entries/${id}`),

  importCsv: (file: File, useAi: boolean, missingProjectStrategy: MissingProjectStrategy, fallbackProjectName?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('use_ai', String(useAi));
    formData.append('missing_project_strategy', missingProjectStrategy);
    if (fallbackProjectName?.trim()) {
      formData.append('fallback_project_name', fallbackProjectName.trim());
    }
    return apiRequest<TimeImportResult>('/time-entries/import/csv', {
      method: 'POST',
      body: formData,
    });
  },

  // Timer
  startTimer: (data: {
    project_id: number;
    task_id?: number;
    description?: string;
    hourly_rate: number;
    billable?: boolean;
  }) => api.post<TimeEntry>('/time-entries/timer/start', data),

  stopTimer: (data?: { notes?: string; ended_at?: string }) =>
    api.post<TimeEntry>('/time-entries/timer/stop', data || {}),

  getActiveTimer: () => api.get<TimerActiveResponse>('/time-entries/timer/active'),

  // Monthly Excel export — returns a Blob download
  downloadMonthlyExport: async (params: {
    year: number;
    month: number;
    project_id?: number;
    client_id?: number;
    user_id?: number;
    billable_only?: boolean;
  }): Promise<void> => {
    const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
      try {
        const u = JSON.parse(localStorage.getItem('user') || '{}');
        return u.tenant_id?.toString();
      } catch { return undefined; }
    })();

    const filteredParams = Object.entries(params).filter(([, v]) => v !== undefined);
    const qs = '?' + new URLSearchParams(filteredParams.map(([k, v]) => [k, String(v)])).toString();
    const url = `${API_BASE_URL}/time-entries/export/monthly${qs}`;

    const headers: Record<string, string> = {};
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const resp = await fetch(url, { method: 'GET', headers, credentials: 'include' });
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      throw new Error(text || `Export failed (${resp.status})`);
    }

    const blob = await resp.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `time_report_${params.year}_${String(params.month).padStart(2, '0')}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(blobUrl);
  },
};
