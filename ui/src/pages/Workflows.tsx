import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { FolderKanban, Play, RefreshCw } from 'lucide-react';

import { workflowsApi, type WorkflowDefinition } from '@/lib/api';
import { getErrorMessage } from '@/lib/api';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';

const WorkflowCard: React.FC<{ workflow: WorkflowDefinition }> = ({ workflow }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const toggleMutation = useMutation({
    mutationFn: (isEnabled: boolean) => workflowsApi.toggle(workflow.id, isEnabled),
    onSuccess: () => {
      toast.success(t('workflows.toggle_success', { defaultValue: 'Workflow updated' }));
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, (key) => key));
    },
  });

  const runMutation = useMutation({
    mutationFn: () => workflowsApi.runNow(workflow.id),
    onSuccess: (result) => {
      const message = `Processed ${result.processed_count}, created ${result.created_task_count} task(s), notified ${result.notification_count} teammate(s).`;
      toast.success(message);
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, (key) => key));
    },
  });

  return (
    <ProfessionalCard variant="elevated" className="border-border/60">
      <ProfessionalCardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <ProfessionalCardTitle className="flex items-center gap-2">
              <FolderKanban className="h-5 w-5 text-primary" />
              {workflow.name}
            </ProfessionalCardTitle>
            <p className="text-sm text-muted-foreground">
              {workflow.description}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {workflow.is_default && <Badge variant="secondary">Default</Badge>}
            {workflow.is_system && <Badge variant="outline">System</Badge>}
          </div>
        </div>
      </ProfessionalCardHeader>
      <ProfessionalCardContent className="space-y-5">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-xl border border-border/50 bg-muted/30 p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Trigger</p>
            <p className="mt-2 text-sm font-medium text-foreground">
              When an invoice first becomes overdue
            </p>
          </div>
          <div className="rounded-xl border border-border/50 bg-muted/30 p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Actions</p>
            <p className="mt-2 text-sm font-medium text-foreground">
              Send internal reminder and create a reminder-backed task
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-amber-200/50 bg-amber-50/50 p-4 text-sm text-amber-900 dark:border-amber-700/40 dark:bg-amber-950/20 dark:text-amber-200">
          Internal tasks are currently implemented with the existing reminders system so assignees get due dates, notifications, and a clear follow-up queue without a separate task module yet.
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Switch
              checked={workflow.is_enabled}
              onCheckedChange={(checked) => toggleMutation.mutate(checked)}
              disabled={toggleMutation.isPending}
            />
            <div>
              <p className="text-sm font-medium text-foreground">
                {workflow.is_enabled ? 'Enabled' : 'Disabled'}
              </p>
              <p className="text-xs text-muted-foreground">
                {workflow.last_run_at
                  ? `Last run: ${new Date(workflow.last_run_at).toLocaleString()}`
                  : 'No runs yet'}
              </p>
            </div>
          </div>

          <div className="flex gap-2">
            <ProfessionalButton
              variant="outline"
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending}
            >
              {runMutation.isPending ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Run now
            </ProfessionalButton>
          </div>
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};

const Workflows: React.FC = () => {
  const { t } = useTranslation();

  const { data: workflows = [], isLoading, refetch, isFetching } = useQuery({
    queryKey: ['workflows'],
    queryFn: () => workflowsApi.list(),
  });

  return (
    <div className="h-full space-y-6 fade-in">
      <PageHeader
        title={t('navigation.workflows', { defaultValue: 'Workflows' })}
        description={t(
          'workflows.description',
          {
            defaultValue: 'Automate follow-up actions across finance operations. The first system workflow handles overdue invoices by notifying a teammate and creating an internal follow-up task.',
          },
        )}
      />

      <ContentSection className="space-y-6 slide-in">
        <div className="flex justify-end">
          <ProfessionalButton variant="outline" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? <RefreshCw className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </ProfessionalButton>
        </div>

        {isLoading ? (
          <ProfessionalCard variant="elevated">
            <ProfessionalCardContent className="p-8 text-sm text-muted-foreground">
              Loading workflows...
            </ProfessionalCardContent>
          </ProfessionalCard>
        ) : (
          workflows.map((workflow) => (
            <WorkflowCard key={workflow.id} workflow={workflow} />
          ))
        )}
      </ContentSection>
    </div>
  );
};

export default Workflows;
