import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  FolderKanban,
  Play,
  RefreshCw,
  Sparkles,
  Edit,
  Trash2,
  CheckCircle,
  AlertCircle,
  Calendar,
  Layers,
  ChevronDown,
} from 'lucide-react';

import { workflowsApi, type WorkflowDefinition, type WorkflowExecutionLog } from '@/lib/api';
import { getErrorMessage } from '@/lib/api';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { FeatureGate } from '@/components/FeatureGate';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ProfessionalInput } from '@/components/ui/professional-input';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const WorkflowBuilder: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [triggerType, setTriggerType] = React.useState('');
  const [selectedActions, setSelectedActions] = React.useState<string[]>([
    'send_internal_notification',
    'create_internal_task',
  ]);

  const { data: catalog } = useQuery({
    queryKey: ['workflow-catalog'],
    queryFn: () => workflowsApi.catalog(),
  });

  React.useEffect(() => {
    if (!triggerType && catalog?.triggers?.length) {
      setTriggerType(catalog.triggers[0].id);
    }
  }, [catalog, triggerType]);

  const createMutation = useMutation({
    mutationFn: () =>
      workflowsApi.create({
        name,
        description,
        trigger_type: triggerType,
        action_ids: selectedActions,
      }),
    onSuccess: () => {
      toast.success(t('workflows.create_success', { defaultValue: 'Workflow created' }));
      setName('');
      setDescription('');
      setSelectedActions(['send_internal_notification', 'create_internal_task']);
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, (key) => key));
    },
  });

  const toggleAction = (actionId: string, checked: boolean) => {
    setSelectedActions((current) => {
      if (checked) {
        return current.includes(actionId) ? current : [...current, actionId];
      }
      return current.filter((item) => item !== actionId);
    });
  };

  const canCreate = name.trim().length > 1 && triggerType && selectedActions.length > 0;

  return (
    <ProfessionalCard variant="elevated" className="border-primary/20">
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          {t('workflows.builder_title', { defaultValue: 'Create Workflow' })}
        </ProfessionalCardTitle>
        <p className="text-sm text-muted-foreground">
          {t(
            'workflows.builder_description',
            { defaultValue: 'Choose from supported triggers and actions. Only executable workflow options are shown here.' },
          )}
        </p>
      </ProfessionalCardHeader>
      <ProfessionalCardContent className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <ProfessionalInput
            label={t('workflows.name', { defaultValue: 'Workflow name' })}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Overdue invoice escalation"
          />
          <div className="space-y-2">
            <label className="text-sm font-medium">
              {t('workflows.trigger', { defaultValue: 'Trigger' })}
            </label>
            <Select value={triggerType} onValueChange={setTriggerType}>
              <SelectTrigger>
                <SelectValue placeholder="Select a trigger" />
              </SelectTrigger>
              <SelectContent>
                {(catalog?.triggers || []).map((trigger) => (
                  <SelectItem key={trigger.id} value={trigger.id}>
                    {trigger.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <ProfessionalInput
          label={t('workflows.description_label', { defaultValue: 'Description' })}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Follow up with overdue customers and make sure an owner is assigned."
        />

        <div className="space-y-3">
          <div>
            <p className="text-sm font-medium text-foreground">
              {t('workflows.actions', { defaultValue: 'Actions' })}
            </p>
            <p className="text-xs text-muted-foreground">
              {t('workflows.actions_help', { defaultValue: 'Each selected action will run when the trigger fires.' })}
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {(catalog?.actions || []).map((action) => {
              const checked = selectedActions.includes(action.id);
              return (
                <label
                  key={action.id}
                  className="flex items-start gap-3 rounded-xl border border-border/50 bg-muted/20 p-4 cursor-pointer hover:bg-muted/30 transition-colors"
                >
                  <Checkbox
                    checked={checked}
                    onCheckedChange={(value) => toggleAction(action.id, value === true)}
                    className="mt-0.5"
                  />
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-foreground">{action.label}</p>
                    <p className="text-xs text-muted-foreground">{action.description}</p>
                  </div>
                </label>
              );
            })}
          </div>
        </div>

        <div className="flex justify-end">
          <ProfessionalButton onClick={() => createMutation.mutate()} disabled={!canCreate} loading={createMutation.isPending}>
            Create workflow
          </ProfessionalButton>
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};

interface EditWorkflowDialogProps {
  workflow: WorkflowDefinition;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

const EditWorkflowDialog: React.FC<EditWorkflowDialogProps> = ({ workflow, isOpen, onOpenChange }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = React.useState(workflow.name);
  const [description, setDescription] = React.useState(workflow.description || '');

  const initialActions: string[] = [];
  if (workflow.actions?.send_internal_notification) {
    initialActions.push('send_internal_notification');
  }
  if (workflow.actions?.create_internal_task) {
    initialActions.push('create_internal_task');
  }
  const [selectedActions, setSelectedActions] = React.useState<string[]>(initialActions);

  const { data: catalog } = useQuery({
    queryKey: ['workflow-catalog'],
    queryFn: () => workflowsApi.catalog(),
  });

  const toggleAction = (actionId: string, checked: boolean) => {
    setSelectedActions((current) => {
      if (checked) {
        return current.includes(actionId) ? current : [...current, actionId];
      }
      return current.filter((item) => item !== actionId);
    });
  };

  const updateMutation = useMutation({
    mutationFn: () =>
      workflowsApi.update(workflow.id, {
        name,
        description,
        action_ids: selectedActions,
      }),
    onSuccess: () => {
      toast.success(t('workflows.update_success', { defaultValue: 'Workflow updated successfully' }));
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      onOpenChange(false);
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, (key) => key));
    },
  });

  const canSave = name.trim().length > 1 && selectedActions.length > 0;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-background/95 backdrop-blur-xl border border-border/50 shadow-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold tracking-tight">
            <Sparkles className="h-5 w-5 text-primary" />
            {t('workflows.edit_title', { defaultValue: 'Edit Workflow' })}
          </DialogTitle>
          <DialogDescription>
            {t('workflows.edit_description', { defaultValue: 'Update workflow details and enabled actions.' })}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="space-y-4">
            <ProfessionalInput
              label={t('workflows.name', { defaultValue: 'Workflow name' })}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Overdue invoice escalation"
            />

            <ProfessionalInput
              label={t('workflows.description_label', { defaultValue: 'Description' })}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Follow up with overdue customers and make sure an owner is assigned."
            />

            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-foreground">
                  {t('workflows.actions', { defaultValue: 'Actions' })}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t('workflows.actions_help', { defaultValue: 'Each selected action will run when the trigger fires.' })}
                </p>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                {(catalog?.actions || []).map((action) => {
                  const checked = selectedActions.includes(action.id);
                  return (
                    <label
                      key={action.id}
                      className="flex items-start gap-3 rounded-xl border border-border/50 bg-muted/20 p-4 cursor-pointer hover:bg-muted/30 transition-colors"
                    >
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(value) => toggleAction(action.id, value === true)}
                        className="mt-0.5"
                      />
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-foreground">{action.label}</p>
                        <p className="text-xs text-muted-foreground">{action.description}</p>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <ProfessionalButton variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </ProfessionalButton>
          <ProfessionalButton
            onClick={() => updateMutation.mutate()}
            disabled={!canSave}
            loading={updateMutation.isPending}
          >
            Save changes
          </ProfessionalButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

interface DeleteWorkflowDialogProps {
  workflow: WorkflowDefinition;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

const DeleteWorkflowDialog: React.FC<DeleteWorkflowDialogProps> = ({ workflow, isOpen, onOpenChange }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => workflowsApi.delete(workflow.id),
    onSuccess: () => {
      toast.success(t('workflows.delete_success', { defaultValue: 'Workflow deleted successfully' }));
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      onOpenChange(false);
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, (key) => key));
    },
  });

  return (
    <AlertDialog open={isOpen} onOpenChange={onOpenChange}>
      <AlertDialogContent className="bg-background/95 backdrop-blur-xl border border-border/50 shadow-2xl">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-destructive flex items-center gap-2 text-lg font-bold">
            <Trash2 className="h-5 w-5" />
            {t('workflows.delete_title', { defaultValue: 'Delete Workflow' })}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-sm text-muted-foreground mt-2">
            {t('workflows.delete_confirm_desc', {
              defaultValue: 'Are you sure you want to delete this workflow? This action is permanent and will cascade-delete all execution logs associated with it.',
            })}
            <div className="mt-3 p-3 rounded-lg bg-muted/40 border border-border/50 font-medium text-foreground">
              {workflow.name}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex justify-end gap-3 mt-4">
          <AlertDialogCancel asChild>
            <ProfessionalButton variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </ProfessionalButton>
          </AlertDialogCancel>
          <ProfessionalButton
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
            loading={deleteMutation.isPending}
            className="bg-destructive hover:bg-destructive/90 text-white shadow-lg transition-all"
          >
            Delete
          </ProfessionalButton>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
};

const WorkflowCard: React.FC<{ workflow: WorkflowDefinition }> = ({ workflow }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [isEditDialogOpen, setIsEditDialogOpen] = React.useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = React.useState(false);

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
      queryClient.invalidateQueries({ queryKey: ['workflow-executions'] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, (key) => key));
    },
  });

  const hasNotification = workflow.actions?.send_internal_notification === true;
  const hasTask = workflow.actions?.create_internal_task === true;
  const actionsList = [];
  if (hasNotification) actionsList.push('Send internal reminder');
  if (hasTask) actionsList.push('create a reminder-backed task');

  const actionsText = actionsList.length > 0
    ? actionsList.join(' and ')
    : 'No actions configured';

  return (
    <>
      <ProfessionalCard variant="elevated" className="border-border/60">
        <ProfessionalCardHeader>
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <ProfessionalCardTitle className="flex items-center gap-2 text-lg font-bold tracking-tight">
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
              <p className="text-xs uppercase tracking-wide text-muted-foreground font-semibold">Trigger</p>
              <p className="mt-2 text-sm font-medium text-foreground">
                When an invoice first becomes overdue
              </p>
            </div>
            <div className="rounded-xl border border-border/50 bg-muted/30 p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground font-semibold">Actions</p>
              <p className="mt-2 text-sm font-medium text-foreground capitalize">
                {actionsText}
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

            <div className="flex flex-wrap gap-2">
              {!workflow.is_system && (
                <>
                  <ProfessionalButton
                    variant="outline"
                    onClick={() => setIsEditDialogOpen(true)}
                    className="border-primary/20 hover:bg-primary/5 h-9"
                  >
                    <Edit className="h-4 w-4 mr-2" />
                    Edit
                  </ProfessionalButton>
                  <ProfessionalButton
                    variant="outline"
                    onClick={() => setIsDeleteDialogOpen(true)}
                    className="border-destructive/20 hover:bg-destructive/5 hover:text-destructive h-9"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </ProfessionalButton>
                </>
              )}

              <ProfessionalButton
                variant="outline"
                onClick={() => runMutation.mutate()}
                disabled={runMutation.isPending}
                className="h-9"
              >
                {runMutation.isPending ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <Play className="h-4 w-4 mr-2" />}
                Run now
              </ProfessionalButton>
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      {isEditDialogOpen && (
        <EditWorkflowDialog
          workflow={workflow}
          isOpen={isEditDialogOpen}
          onOpenChange={setIsEditDialogOpen}
        />
      )}

      {isDeleteDialogOpen && (
        <DeleteWorkflowDialog
          workflow={workflow}
          isOpen={isDeleteDialogOpen}
          onOpenChange={setIsDeleteDialogOpen}
        />
      )}
    </>
  );
};

const ExecutionLogItem: React.FC<{ log: WorkflowExecutionLog }> = ({ log }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const isSuccess = log.status === 'success';

  return (
    <div className="border border-border/50 rounded-xl bg-card overflow-hidden shadow-sm transition-all duration-200 hover:border-border/80">
      <div
        className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 cursor-pointer select-none bg-muted/5 hover:bg-muted/10 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          {isSuccess ? (
            <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/10 border-emerald-500/20 px-2.5 py-0.5 rounded-full flex items-center gap-1">
              <CheckCircle className="h-3.5 w-3.5" />
              Success
            </Badge>
          ) : (
            <Badge className="bg-destructive/10 text-destructive hover:bg-destructive/10 border-destructive/20 px-2.5 py-0.5 rounded-full flex items-center gap-1">
              <AlertCircle className="h-3.5 w-3.5" />
              Failed
            </Badge>
          )}
          <div>
            <h4 className="font-semibold text-foreground text-sm">
              {log.workflow_name || log.workflow_key || 'Unknown Workflow'}
            </h4>
            <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {new Date(log.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between md:justify-end gap-6 text-sm">
          <div className="text-right">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Entity</p>
            <p className="font-medium text-foreground mt-0.5">
              {log.entity_type}: {log.details?.invoice_number ? `#${log.details.invoice_number}` : log.entity_id}
            </p>
          </div>

          <div className="text-right hidden sm:block">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Trigger Event</p>
            <p className="font-mono text-xs text-foreground mt-0.5 bg-muted/40 px-2 py-0.5 rounded border border-border/40">
              {log.event_key}
            </p>
          </div>

          <ProfessionalButton
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            className="text-muted-foreground hover:text-foreground h-8 w-8 p-0"
          >
            <ChevronDown className={`h-4 w-4 transform transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
          </ProfessionalButton>
        </div>
      </div>

      {isExpanded && (
        <div className="border-t border-border/40 p-5 bg-muted/5 space-y-4 animate-fade-in">
          {!isSuccess && log.details?.error && (
            <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive flex gap-3">
              <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Execution Error</p>
                <p className="mt-1 font-mono text-xs bg-black/5 dark:bg-black/20 p-2.5 rounded border border-destructive/10 overflow-x-auto whitespace-pre-wrap">
                  {log.details.error}
                </p>
              </div>
            </div>
          )}

          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-3">
              <h5 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                Execution Metadata
              </h5>
              <div className="rounded-xl border border-border/40 bg-card p-4 space-y-2.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Workflow ID</span>
                  <span className="font-mono font-medium">{log.workflow_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Event Key</span>
                  <span className="font-mono font-medium">{log.event_key}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Entity Type</span>
                  <span className="font-medium">{log.entity_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Entity ID</span>
                  <span className="font-mono font-medium">{log.entity_id}</span>
                </div>
                {log.details?.amount !== undefined && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Invoice Amount</span>
                    <span className="font-medium text-foreground">
                      {log.details.amount} {log.details.currency || 'USD'}
                    </span>
                  </div>
                )}
                {log.details?.client_name && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Client</span>
                    <span className="font-medium text-foreground">{log.details.client_name}</span>
                  </div>
                )}
                {log.details?.task_id && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Created Task ID</span>
                    <span className="font-mono font-medium text-primary">#{log.details.task_id}</span>
                  </div>
                )}
                {log.details?.assigned_user_id && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Assigned User ID</span>
                    <span className="font-mono font-medium">{log.details.assigned_user_id}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-3">
              <h5 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                Raw Execution Payload
              </h5>
              <div className="rounded-xl border border-border/40 bg-black/5 dark:bg-black/20 p-4 font-mono text-xs text-foreground overflow-x-auto max-h-[220px]">
                <pre>{JSON.stringify(log.details || {}, null, 2)}</pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Workflows: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = React.useState<string>('all');
  const [page, setPage] = React.useState(1);
  const limit = 10;
  const offset = (page - 1) * limit;

  const { data: workflows = [], isLoading: isWorkflowsLoading, refetch: refetchWorkflows, isFetching: isWorkflowsFetching } = useQuery({
    queryKey: ['workflows'],
    queryFn: () => workflowsApi.list(),
  });

  const { data: executionData, isLoading: isExecutionsLoading, refetch: refetchExecutions, isFetching: isExecutionsFetching } = useQuery({
    queryKey: ['workflow-executions', { status: statusFilter, limit, offset }],
    queryFn: () => workflowsApi.listExecutions({
      status: statusFilter === 'all' ? undefined : statusFilter,
      limit,
      offset,
    }),
  });

  React.useEffect(() => {
    setPage(1);
  }, [statusFilter]);

  const totalLogs = executionData?.total || 0;
  const totalPages = Math.ceil(totalLogs / limit) || 1;

  const handleRefreshAll = () => {
    refetchWorkflows();
    refetchExecutions();
    toast.success('Data refreshed successfully');
  };

  return (
    <FeatureGate
      feature="workflow_automation"
      showUpgradePrompt={true}
      upgradeMessage="Workflow automation requires a business license."
    >
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={t('navigation.workflows', { defaultValue: 'Workflows' })}
          description={t(
            'workflows.description',
            {
              defaultValue: 'Automate follow-up actions across finance operations. Customise and trigger business rules based on overdue invoices, client activity, and more.',
            },
          )}
        />

        <ContentSection className="space-y-6 slide-in">
          <Tabs defaultValue="active" className="w-full">
            <TabsList className="grid grid-cols-2 w-[400px] mb-6 border-b border-border bg-transparent p-0 rounded-none h-12">
              <TabsTrigger
                value="active"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none h-full font-medium"
              >
                <Layers className="h-4 w-4 mr-2" />
                Active Workflows
              </TabsTrigger>
              <TabsTrigger
                value="history"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none h-full font-medium"
              >
                <Sparkles className="h-4 w-4 mr-2" />
                Execution History
              </TabsTrigger>
            </TabsList>

            <TabsContent value="active" className="space-y-6">
              <WorkflowBuilder />

              <div className="flex justify-end gap-2">
                <ProfessionalButton variant="outline" onClick={handleRefreshAll} disabled={isWorkflowsFetching}>
                  {isWorkflowsFetching ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                  Refresh
                </ProfessionalButton>
              </div>

              {isWorkflowsLoading ? (
                <ProfessionalCard variant="elevated">
                  <ProfessionalCardContent className="p-8 text-sm text-muted-foreground flex items-center justify-center gap-2">
                    <RefreshCw className="h-4 w-4 animate-spin text-primary" />
                    Loading workflows...
                  </ProfessionalCardContent>
                </ProfessionalCard>
              ) : workflows.length === 0 ? (
                <div className="py-12 flex flex-col items-center justify-center text-center space-y-3 opacity-60 border border-dashed rounded-xl bg-card">
                  <FolderKanban className="h-12 w-12 text-muted-foreground" />
                  <p className="text-sm font-medium">No workflows configured yet.</p>
                </div>
              ) : (
                <div className="grid gap-6">
                  {workflows.map((workflow) => (
                    <WorkflowCard key={workflow.id} workflow={workflow} />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="history" className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium">Status Filter:</span>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="All Statuses" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Statuses</SelectItem>
                      <SelectItem value="success">Success</SelectItem>
                      <SelectItem value="failed">Failed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex gap-2">
                  <ProfessionalButton variant="outline" onClick={() => refetchExecutions()} disabled={isExecutionsFetching}>
                    {isExecutionsFetching ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                    Refresh logs
                  </ProfessionalButton>
                </div>
              </div>

              {isExecutionsLoading ? (
                <ProfessionalCard variant="elevated">
                  <ProfessionalCardContent className="p-8 text-sm text-muted-foreground flex items-center justify-center gap-2">
                    <RefreshCw className="h-4 w-4 animate-spin text-primary" />
                    Loading executions...
                  </ProfessionalCardContent>
                </ProfessionalCard>
              ) : !executionData || executionData.logs.length === 0 ? (
                <div className="py-12 flex flex-col items-center justify-center text-center space-y-3 opacity-60 border border-dashed rounded-xl bg-card">
                  <AlertCircle className="h-12 w-12 text-muted-foreground" />
                  <p className="text-sm font-medium">No execution history matching criteria found.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid gap-4">
                    {executionData.logs.map((log: WorkflowExecutionLog) => (
                      <ExecutionLogItem key={log.id} log={log} />
                    ))}
                  </div>

                  {/* Pagination Controls */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between border-t border-border/50 pt-4 mt-6">
                      <p className="text-sm text-muted-foreground">
                        Showing page {page} of {totalPages} ({totalLogs} runs total)
                      </p>
                      <div className="flex gap-2">
                        <ProfessionalButton
                          variant="outline"
                          size="sm"
                          disabled={page === 1}
                          onClick={() => setPage((p) => Math.max(p - 1, 1))}
                        >
                          Previous
                        </ProfessionalButton>
                        <ProfessionalButton
                          variant="outline"
                          size="sm"
                          disabled={page === totalPages}
                          onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                        >
                          Next
                        </ProfessionalButton>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </ContentSection>
      </div>
    </FeatureGate>
  );
};

export default Workflows;
