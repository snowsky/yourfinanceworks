import { apiRequest } from './_base';

export interface WorkflowDefinition {
  id: number;
  name: string;
  key: string;
  description?: string | null;
  trigger_type: string;
  conditions?: Record<string, any> | null;
  actions?: Record<string, any> | null;
  is_enabled: boolean;
  is_system: boolean;
  is_default: boolean;
  last_run_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRunNowResponse {
  workflow_id: number;
  processed_count: number;
  created_task_count: number;
  notification_count: number;
  skipped_count: number;
  errors: string[];
}

export interface WorkflowOption {
  id: string;
  label: string;
  description: string;
}

export interface WorkflowCatalogResponse {
  triggers: WorkflowOption[];
  actions: WorkflowOption[];
}

export interface WorkflowExecutionLog {
  id: number;
  workflow_id: number;
  workflow_name?: string | null;
  workflow_key?: string | null;
  event_key: string;
  entity_type: string;
  entity_id: string;
  status: 'success' | 'failed';
  details?: Record<string, any> | null;
  created_at: string;
}

export interface WorkflowExecutionLogListResponse {
  total: number;
  logs: WorkflowExecutionLog[];
}

export const workflowsApi = {
  list: () => apiRequest<WorkflowDefinition[]>('/workflows/'),
  catalog: () => apiRequest<WorkflowCatalogResponse>('/workflows/catalog'),
  create: (payload: { name: string; description?: string; trigger_type: string; action_ids: string[]; assigned_user_id?: number | null }) =>
    apiRequest<WorkflowDefinition>('/workflows/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  toggle: (id: number, is_enabled: boolean) =>
    apiRequest<WorkflowDefinition>(`/workflows/${id}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ is_enabled }),
    }),
  runNow: (id: number) =>
    apiRequest<WorkflowRunNowResponse>(`/workflows/${id}/run`, {
      method: 'POST',
    }),
  listExecutions: (params?: { status?: string; limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
    const query = searchParams.toString();
    return apiRequest<WorkflowExecutionLogListResponse>(`/workflows/executions${query ? `?${query}` : ''}`);
  },
  listWorkflowExecutions: (workflowId: number, params?: { status?: string; limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
    const query = searchParams.toString();
    return apiRequest<WorkflowExecutionLogListResponse>(`/workflows/${workflowId}/executions${query ? `?${query}` : ''}`);
  },
  update: (id: number, payload: { name: string; description?: string | null; action_ids: string[]; assigned_user_id?: number | null }) =>
    apiRequest<WorkflowDefinition>(`/workflows/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  delete: (id: number) =>
    apiRequest<void>(`/workflows/${id}`, {
      method: 'DELETE',
    }),
};
