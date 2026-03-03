/**
 * Time Tracking Plugin — React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { projectApi, timeEntryApi, Project, ProjectTask, TimeEntry } from './api';

// -------------------------------------------------------------------------
// Project hooks
// -------------------------------------------------------------------------

export const useProjects = (params?: { status?: string; client_id?: number }) =>
  useQuery({
    queryKey: ['projects', params],
    queryFn: () => projectApi.list(params),
  });

export const useProject = (id: number) =>
  useQuery({
    queryKey: ['project', id],
    queryFn: () => projectApi.get(id),
    enabled: !!id,
  });

export const useProjectSummary = (id: number) =>
  useQuery({
    queryKey: ['project-summary', id],
    queryFn: () => projectApi.getSummary(id),
    enabled: !!id,
  });

export const useUnbilledItems = (id: number) =>
  useQuery({
    queryKey: ['project-unbilled', id],
    queryFn: () => projectApi.getUnbilled(id),
    enabled: !!id,
  });

export const useCreateProject = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Project>) => projectApi.create(data),
    onSuccess: () => {
      toast.success('Project created');
      qc.invalidateQueries({ queryKey: ['projects'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to create project'),
  });
};

export const useUpdateProject = (id: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Project>) => projectApi.update(id, data),
    onSuccess: () => {
      toast.success('Project updated');
      qc.invalidateQueries({ queryKey: ['project', id] });
      qc.invalidateQueries({ queryKey: ['projects'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to update project'),
  });
};

export const useDeleteProject = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => projectApi.delete(id),
    onSuccess: () => {
      toast.success('Project archived');
      qc.invalidateQueries({ queryKey: ['projects'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to archive project'),
  });
};

export const useCreateInvoiceFromProject = (projectId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { time_entry_ids: number[]; expense_ids: number[]; due_date?: string; notes?: string }) =>
      projectApi.createInvoice(projectId, data),
    onSuccess: (result) => {
      toast.success(`Invoice ${result.invoice_number} created`);
      qc.invalidateQueries({ queryKey: ['project-unbilled', projectId] });
      qc.invalidateQueries({ queryKey: ['time-entries'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to create invoice'),
  });
};

// -------------------------------------------------------------------------
// Task hooks
// -------------------------------------------------------------------------

export const useProjectTasks = (projectId: number) =>
  useQuery({
    queryKey: ['project-tasks', projectId],
    queryFn: () => projectApi.listTasks(projectId),
    enabled: !!projectId,
  });

export const useCreateTask = (projectId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<ProjectTask>) => projectApi.createTask(projectId, data),
    onSuccess: () => {
      toast.success('Task created');
      qc.invalidateQueries({ queryKey: ['project-tasks', projectId] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to create task'),
  });
};

export const useUpdateTask = (projectId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, data }: { taskId: number; data: Partial<ProjectTask> }) =>
      projectApi.updateTask(projectId, taskId, data),
    onSuccess: () => {
      toast.success('Task updated');
      qc.invalidateQueries({ queryKey: ['project-tasks', projectId] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to update task'),
  });
};

export const useDeleteTask = (projectId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: number) => projectApi.deleteTask(projectId, taskId),
    onSuccess: () => {
      toast.success('Task deleted');
      qc.invalidateQueries({ queryKey: ['project-tasks', projectId] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to delete task'),
  });
};

// -------------------------------------------------------------------------
// Time entry hooks
// -------------------------------------------------------------------------

export const useTimeEntries = (params?: {
  project_id?: number;
  task_id?: number;
  user_id?: number;
  status?: string;
  invoiced?: boolean;
  limit?: number;
}) =>
  useQuery({
    queryKey: ['time-entries', params],
    queryFn: () => timeEntryApi.list(params),
  });

export const useCreateTimeEntry = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<TimeEntry> & { started_at: string }) =>
      timeEntryApi.create(data),
    onSuccess: () => {
      toast.success('Time entry logged');
      qc.invalidateQueries({ queryKey: ['time-entries'] });
      qc.invalidateQueries({ queryKey: ['project-summary'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to log time'),
  });
};

export const useUpdateTimeEntry = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<TimeEntry> }) =>
      timeEntryApi.update(id, data),
    onSuccess: () => {
      toast.success('Time entry updated');
      qc.invalidateQueries({ queryKey: ['time-entries'] });
      qc.invalidateQueries({ queryKey: ['project-summary'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to update time entry'),
  });
};

export const useDeleteTimeEntry = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => timeEntryApi.delete(id),
    onSuccess: () => {
      toast.success('Time entry deleted');
      qc.invalidateQueries({ queryKey: ['time-entries'] });
      qc.invalidateQueries({ queryKey: ['project-summary'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to delete time entry'),
  });
};

// -------------------------------------------------------------------------
// Timer hooks
// -------------------------------------------------------------------------

export const useActiveTimer = () =>
  useQuery({
    queryKey: ['active-timer'],
    queryFn: () => timeEntryApi.getActiveTimer(),
    refetchInterval: 30000, // poll every 30s to keep elapsed_seconds fresh
    retry: false,
  });

export const useStartTimer = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      project_id: number;
      task_id?: number;
      description?: string;
      hourly_rate: number;
      billable?: boolean;
    }) => timeEntryApi.startTimer(data),
    onSuccess: () => {
      toast.success('Timer started');
      qc.invalidateQueries({ queryKey: ['active-timer'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to start timer'),
  });
};

export const useStopTimer = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data?: { notes?: string }) => timeEntryApi.stopTimer(data),
    onSuccess: () => {
      toast.success('Timer stopped and time logged');
      qc.invalidateQueries({ queryKey: ['active-timer'] });
      qc.invalidateQueries({ queryKey: ['time-entries'] });
      qc.invalidateQueries({ queryKey: ['project-summary'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to stop timer'),
  });
};
