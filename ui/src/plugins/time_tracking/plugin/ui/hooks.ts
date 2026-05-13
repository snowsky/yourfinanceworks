/**
 * Time Tracking Plugin — React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { projectApi, timeEntryApi } from './api';
import type { Project, ProjectCustomField, ProjectTask, TimeEntry, MissingProjectStrategy } from './api';

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
      qc.invalidateQueries({ queryKey: ['project-summary', id] });
      qc.invalidateQueries({ queryKey: ['project-unbilled', id] });
      qc.invalidateQueries({ queryKey: ['time-entries'] });
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

export const useProjectKanban = (projectId: number) =>
  useQuery({
    queryKey: ['project-kanban', projectId],
    queryFn: () => projectApi.getKanban(projectId),
    enabled: !!projectId,
  });

export const useCreateTask = (projectId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<ProjectTask>) => projectApi.createTask(projectId, data),
    onSuccess: () => {
      toast.success('Task created');
      qc.invalidateQueries({ queryKey: ['project-tasks', projectId] });
      qc.invalidateQueries({ queryKey: ['project-kanban', projectId] });
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
      qc.invalidateQueries({ queryKey: ['project-kanban', projectId] });
      qc.invalidateQueries({ queryKey: ['time-entries'] });
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
      qc.invalidateQueries({ queryKey: ['project-kanban', projectId] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to delete task'),
  });
};

export const useReorderKanbanTasks = (projectId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tasks: Array<{ task_id: number; kanban_status: string; kanban_position: number }>) =>
      projectApi.reorderKanban(projectId, { tasks }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project-kanban', projectId] });
      qc.invalidateQueries({ queryKey: ['project-tasks', projectId] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to move task'),
  });
};

export const useCreateCustomField = (projectId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<ProjectCustomField>) => projectApi.createCustomField(projectId, data),
    onSuccess: () => {
      toast.success('Custom field created');
      qc.invalidateQueries({ queryKey: ['project-kanban', projectId] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to create custom field'),
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
    onSuccess: (_result, variables) => {
      toast.success('Time entry logged');
      qc.invalidateQueries({ queryKey: ['time-entries'] });
      qc.invalidateQueries({ queryKey: ['project-summary'] });
      // Refresh unbilled tab so new entry appears immediately
      if (variables.project_id) {
        qc.invalidateQueries({ queryKey: ['project-unbilled', variables.project_id] });
      }
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to log time'),
  });
};

export const useUpdateTimeEntry = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<TimeEntry> }) =>
      timeEntryApi.update(id, data),
    onSuccess: (_result, variables) => {
      toast.success('Time entry updated');
      qc.invalidateQueries({ queryKey: ['time-entries'] });
      qc.invalidateQueries({ queryKey: ['project-summary'] });
      // Refresh unbilled tab if we know the project
      if (variables.data.project_id) {
        qc.invalidateQueries({ queryKey: ['project-unbilled', variables.data.project_id] });
      } else {
        // Fallback: invalidate all unbilled queries
        qc.invalidateQueries({ queryKey: ['project-unbilled'] });
      }
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
      qc.invalidateQueries({ queryKey: ['project-unbilled'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to delete time entry'),
  });
};

export const useImportTimeEntriesCsv = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      useAi,
      missingProjectStrategy,
      fallbackProjectName,
    }: {
      file: File;
      useAi: boolean;
      missingProjectStrategy: MissingProjectStrategy;
      fallbackProjectName?: string;
    }) => timeEntryApi.importCsv(file, useAi, missingProjectStrategy, fallbackProjectName),
    onSuccess: (result) => {
      const suffix = result.skipped_rows ? `, ${result.skipped_rows} skipped` : '';
      toast.success(`Imported ${result.created_time_entries} time entries${suffix}`);
      qc.invalidateQueries({ queryKey: ['time-entries'] });
      qc.invalidateQueries({ queryKey: ['projects'] });
      qc.invalidateQueries({ queryKey: ['project-summary'] });
      qc.invalidateQueries({ queryKey: ['project-unbilled'] });
    },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : 'Failed to import CSV'),
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
      // Refresh all unbilled tabs — we don't know which project the timer was for
      qc.invalidateQueries({ queryKey: ['project-unbilled'] });
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to stop timer'),
  });
};
