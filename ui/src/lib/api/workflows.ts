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

export const workflowsApi = {
  list: () => apiRequest<WorkflowDefinition[]>('/workflows/'),
  toggle: (id: number, is_enabled: boolean) =>
    apiRequest<WorkflowDefinition>(`/workflows/${id}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ is_enabled }),
    }),
  runNow: (id: number) =>
    apiRequest<WorkflowRunNowResponse>(`/workflows/${id}/run`, {
      method: 'POST',
    }),
};
