import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { DndContext, DragEndEvent, useDraggable, useDroppable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import {
  AlertCircle, Archive, CalendarDays, Clock, DollarSign, FileText, GripVertical, ListChecks,
  Receipt, BarChart3, Plus, Trash2, Play, CheckCircle2, Edit2, Save, X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useProject, useProjectSummary, useProjectTasks,
  useTimeEntries, useUnbilledItems, useCreateInvoiceFromProject,
  useCreateTask, useDeleteTask, useDeleteTimeEntry, useUpdateTimeEntry, useUpdateProject, useUpdateTask,
  useProjectKanban, useReorderKanbanTasks, useCreateCustomField
} from '@/plugins/time_tracking/plugin/ui/hooks';
import { SearchableClientSelect } from '@/plugins/time_tracking/plugin/ui/components/SearchableClientSelect';
import { KanbanColumn, Project, ProjectCustomField, ProjectSummary, TimeEntry, ProjectTask } from '@/plugins/time_tracking/plugin/ui/api';
import { useTimer } from '@/contexts/TimerContext';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalCard, MetricCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';

const TABS = ['Overview', 'Kanban', 'Tasks', 'Time Entries', 'Unbilled'] as const;
type TabType = typeof TABS[number];

export default function ProjectDetailInternal() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || '0', 10);
  const [tab, setTab] = useState<TabType>('Overview');
  const [selectedEntryIds, setSelectedEntryIds] = useState<number[]>([]);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editClientId, setEditClientId] = useState<number | undefined>(undefined);
  const [editHourlyRate, setEditHourlyRate] = useState('');
  // Timer start dialog
  const [showTimerDialog, setShowTimerDialog] = useState(false);
  const [timerTaskId, setTimerTaskId] = useState<number | undefined>(undefined);
  const [timerDesc, setTimerDesc] = useState('');

  const { data: project } = useProject(projectId);
  const { data: summary } = useProjectSummary(projectId);
  const { data: tasks = [] } = useProjectTasks(projectId);
  const { data: timeEntries = [] } = useTimeEntries({ project_id: projectId });
  const { data: unbilled } = useUnbilledItems(projectId);
  const createInvoice = useCreateInvoiceFromProject(projectId);
  const deleteEntry = useDeleteTimeEntry();
  const updateProject = useUpdateProject(projectId);
  const { startTimer, active: timerActive } = useTimer();

  // Initialize edit state when project data is loaded
  React.useEffect(() => {
    if (project && !isEditing) {
      setEditName(project.name);
      setEditClientId(project.client_id);
      setEditHourlyRate(project.hourly_rate != null ? String(project.hourly_rate) : '');
    }
  }, [project, isEditing]);

  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-muted-foreground animate-pulse font-medium">Loading project details…</p>
      </div>
    );
  }

  const handleInvoice = async () => {
    if (!selectedEntryIds.length && !unbilled?.expenses.length) return;
    await createInvoice.mutateAsync({
      time_entry_ids: selectedEntryIds,
      expense_ids: (unbilled?.expenses || []).map((e) => e.id),
    });
    setSelectedEntryIds([]);
  };

  const openTimerDialog = () => {
    // Default to first task (if any)
    setTimerTaskId(tasks[0]?.id);
    setTimerDesc('');
    setShowTimerDialog(true);
  };

  const handleStartTimer = async () => {
    const selectedTask = tasks.find((t) => t.id === timerTaskId);
    await startTimer({
      project_id: projectId,
      task_id: timerTaskId,
      description: timerDesc || undefined,
      hourly_rate: selectedTask?.hourly_rate ?? project.hourly_rate ?? 0,
    });
    setShowTimerDialog(false);
  };

  const handleSave = async () => {
    if (!editName || !editClientId) return;
    await updateProject.mutateAsync({
      name: editName,
      client_id: editClientId,
      hourly_rate: editHourlyRate ? parseFloat(editHourlyRate) : null,
    });
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditName(project.name);
    setEditClientId(project.client_id);
    setEditHourlyRate(project.hourly_rate != null ? String(project.hourly_rate) : '');
    setIsEditing(false);
  };

  const handleProjectStatus = async (status: 'active' | 'completed' | 'archived') => {
    await updateProject.mutateAsync({ status });
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      <PageHeader
        title={
          isEditing ? (
            <Input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="text-3xl font-bold h-12 bg-background/50 border-primary/30 max-w-xl"
              placeholder="Project Name"
              autoFocus
            />
          ) : (
            project.name
          )
        }
        description={
          isEditing ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl mt-2">
              <SearchableClientSelect
                value={editClientId}
                onChange={setEditClientId}
                placeholder="Select client"
                className="h-9"
              />
              <Input
                type="number"
                step="0.01"
                min="0"
                value={editHourlyRate}
                onChange={(e) => setEditHourlyRate(e.target.value)}
                placeholder="Project hourly rate"
                className="h-9 bg-background/50 border-border/50"
              />
            </div>
          ) : (
            `${project.client_name || `Client #${project.client_id}`}${project.hourly_rate != null ? ` • ${project.currency} ${project.hourly_rate}/hr` : ''}`
          )
        }
        breadcrumbs={[
          { label: 'Time Tracking', href: '/time-tracking' },
          { label: project.name }
        ]}
        actions={
          <div className="flex items-center gap-3">
            {isEditing ? (
              <>
                <ProfessionalButton
                  onClick={handleCancelEdit}
                  variant="ghost"
                  size="sm"
                  leftIcon={<X className="w-4 h-4" />}
                >
                  Cancel
                </ProfessionalButton>
                <ProfessionalButton
                  onClick={handleSave}
                  variant="gradient"
                  size="sm"
                  loading={updateProject.isPending}
                  leftIcon={<Save className="w-4 h-4" />}
                >
                  Save Changes
                </ProfessionalButton>
              </>
            ) : (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsEditing(true)}
                  className="rounded-full hover:bg-primary/10 hover:text-primary transition-colors h-10 w-10"
                >
                  <Edit2 className="w-5 h-5" />
                </Button>
                <Badge variant="outline" className={cn("px-3 py-1 rounded-full border border-border/50 font-bold uppercase tracking-wider text-[10px]", project.status === 'active' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30' : 'bg-slate-100 text-slate-700 dark:bg-slate-800')}>
                  {project.status}
                </Badge>
                {project.status === 'active' && (
                  <ProfessionalButton
                    onClick={() => handleProjectStatus('completed')}
                    variant="outline"
                    size="sm"
                    leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                  >
                    Complete
                  </ProfessionalButton>
                )}
                {project.status === 'active' ? (
                  <ProfessionalButton
                    onClick={() => handleProjectStatus('archived')}
                    variant="ghost"
                    size="sm"
                    leftIcon={<Archive className="w-3.5 h-3.5" />}
                  >
                    Archive
                  </ProfessionalButton>
                ) : (
                  <ProfessionalButton
                    onClick={() => handleProjectStatus('active')}
                    variant="outline"
                    size="sm"
                  >
                    Reopen
                  </ProfessionalButton>
                )}
                {!timerActive && project.status === 'active' && (
                  <ProfessionalButton
                    onClick={openTimerDialog}
                    variant="gradient"
                    className="shadow-lg shadow-primary/20 font-bold"
                    leftIcon={<Play className="w-3.5 h-3.5" />}
                  >
                    Start Timer
                  </ProfessionalButton>
                )}
              </>
            )}
          </div>
        }
      />

      <div className="flex gap-2 p-1 bg-background/50 backdrop-blur-sm rounded-xl border border-border/50 shadow-inner w-fit">
        {TABS.map((t) => (
          <Button
            key={t}
            variant={tab === t ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => setTab(t)}
            className={cn(
              "h-8 px-4 rounded-lg font-medium transition-all duration-200",
              tab === t && "bg-card shadow-sm text-primary"
            )}
          >
            {t}
          </Button>
        ))}
      </div>

      <ContentSection>
        {tab === 'Overview' && <OverviewTab summary={summary} project={project} />}
        {tab === 'Kanban' && <KanbanTab projectId={projectId} project={project} />}
        {tab === 'Tasks' && <TasksTab projectId={projectId} tasks={tasks} projectHourlyRate={project.hourly_rate} />}
        {tab === 'Time Entries' && (
          <TimeEntriesTab
            entries={timeEntries}
            tasks={tasks}
            project={project}
            onDelete={(id) => deleteEntry.mutate(id)}
          />
        )}
        {tab === 'Unbilled' && (
          <UnbilledTab
            unbilled={unbilled}
            selectedIds={selectedEntryIds}
            onToggleEntry={(id: number) =>
              setSelectedEntryIds((prev) =>
                prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
              )
            }
            onSelectAll={(ids: number[]) => setSelectedEntryIds(ids)}
            isAllSelected={(unbilled?.time_entries?.length ?? 0) > 0 && selectedEntryIds.length === (unbilled?.time_entries?.length ?? 0)}
            onInvoice={handleInvoice}
            isInvoicing={createInvoice.isPending}
            currency={project.currency}
          />
        )}
      </ContentSection>

      {/* ── Timer Start Dialog ─────────────────────────────────────────── */}
      {showTimerDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <ProfessionalCard variant="elevated" className="w-full max-w-md mx-4 p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Play className="w-5 h-5 text-primary" /> Start Timer
              </h3>
              <Button variant="ghost" size="icon" onClick={() => setShowTimerDialog(false)}>
                <X className="w-4 h-4" />
              </Button>
            </div>

            {tasks.length === 0 ? (
              /* No tasks — allow general project timer using the project rate */
              <div className="space-y-4">
                <div className="flex items-start gap-3 p-4 rounded-xl bg-primary/5 border border-primary/20">
                  <Clock className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-foreground text-sm">
                      General project time
                    </p>
                    <p className="text-muted-foreground text-xs mt-1">
                      This timer will use the project hourly rate: {project.hourly_rate != null ? `${project.currency} ${project.hourly_rate}/hr` : 'not set, so $0 will be charged'}.
                    </p>
                  </div>
                </div>
                <Input
                  placeholder={`Working on ${project?.name ?? 'project'}…`}
                  value={timerDesc}
                  onChange={(e) => setTimerDesc(e.target.value)}
                  className="bg-background/50 border-border/50 rounded-xl text-sm"
                />
                <div className="flex gap-2 justify-end">
                  <ProfessionalButton variant="ghost" onClick={() => setShowTimerDialog(false)}>Cancel</ProfessionalButton>
                  <ProfessionalButton
                    variant="gradient"
                    className="shadow-lg shadow-primary/20"
                    leftIcon={<Play className="w-3.5 h-3.5" />}
                    onClick={handleStartTimer}
                  >
                    Start
                  </ProfessionalButton>
                </div>
              </div>
            ) : (
              /* Task picker + optional description */
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                    Task <span className="text-destructive">*</span>
                  </label>
                  <select
                    className="flex h-10 w-full rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 transition-all cursor-pointer"
                    value={timerTaskId ?? ''}
                    onChange={(e) => setTimerTaskId(e.target.value ? Number(e.target.value) : undefined)}
                  >
                    <option value="">General project time</option>
                    {tasks.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}{t.hourly_rate ? ` — $${t.hourly_rate}/hr` : ' — inherits project rate'}
                      </option>
                    ))}
                  </select>
                  {/* Rate preview */}
                  {(() => {
                    const sel = tasks.find((t) => t.id === timerTaskId);
                    const rate = sel?.hourly_rate ?? project.hourly_rate ?? null;
                    return (
                      <p className="text-xs text-muted-foreground mt-1.5">
                        Hourly rate: <span className={cn("font-semibold", rate != null ? 'text-foreground' : 'text-warning')}>
                          {rate != null ? `$${rate}/hr` : 'not set — time tracked but $0 charged'}
                        </span>
                      </p>
                    );
                  })()}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                    Description <span className="text-muted-foreground font-normal">(optional)</span>
                  </label>
                  <Input
                    placeholder={`Working on ${project?.name ?? 'project'}…`}
                    value={timerDesc}
                    onChange={(e) => setTimerDesc(e.target.value)}
                    className="bg-background/50 border-border/50 rounded-xl text-sm"
                  />
                </div>

                <div className="flex gap-2 justify-end pt-2">
                  <ProfessionalButton variant="ghost" onClick={() => setShowTimerDialog(false)}>Cancel</ProfessionalButton>
                  <ProfessionalButton
                    variant="gradient"
                    className="shadow-lg shadow-primary/20"
                    leftIcon={<Play className="w-3.5 h-3.5" />}
                    onClick={handleStartTimer}
                  >
                    Start
                  </ProfessionalButton>
                </div>
              </div>
            )}
          </ProfessionalCard>
        </div>
      )}
    </div>
  );
}

// ---- Sub-components ----

function OverviewTab({ summary, project }: { summary?: ProjectSummary; project: Project }) {
  if (!summary) return <div className="text-muted-foreground animate-pulse py-8">Calculating summary statistics…</div>;
  
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Hours Logged"
          value={`${summary.total_hours_logged.toFixed(1)}h`}
          icon={Clock}
          description="Total time tracked for this project"
        />
        <MetricCard
          title="Unbilled Amount"
          value={`${project.currency} ${summary.unbilled_amount.toFixed(2)}`}
          icon={DollarSign}
          description="Ready to be invoiced"
          variant="warning"
        />
        <MetricCard
          title="Total Expenses"
          value={`${project.currency} ${summary.total_expenses.toFixed(2)}`}
          icon={Receipt}
          description="Associated project costs"
        />
        <MetricCard
          title="Billed to Date"
          value={`${project.currency} ${summary.total_amount_logged.toFixed(2)}`}
          icon={BarChart3}
          description="Cumulative invoiced revenue"
          variant="success"
        />
      </div>

      <ProfessionalCard variant="elevated" className="p-6 bg-card/50 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-primary" />
              Project Hourly Rate
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Used when a task does not define its own rate.
            </p>
          </div>
          <div className="text-2xl font-bold tracking-tight">
            {project.hourly_rate != null ? `${project.currency} ${project.hourly_rate}/hr` : 'Not set'}
          </div>
        </div>
      </ProfessionalCard>

      {summary.budget_hours && (
        <ProfessionalCard variant="elevated" className="p-6 bg-card/50 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-primary" />
              Hours Budget Progress
            </h3>
            <span className="text-sm font-bold text-muted-foreground tracking-tight">
              {summary.total_hours_logged.toFixed(1)} / {summary.budget_hours}h ({summary.hours_used_pct}%)
            </span>
          </div>
          <div className="w-full h-3 bg-muted rounded-full overflow-hidden shadow-inner">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-700",
                (summary.hours_used_pct || 0) >= 90 ? 'bg-destructive shadow-[0_0_12px_rgba(239,68,68,0.4)]' :
                (summary.hours_used_pct || 0) >= 75 ? 'bg-warning shadow-[0_0_12px_rgba(245,158,11,0.4)]' :
                'bg-success shadow-[0_0_12px_rgba(16,185,129,0.4)]'
              )}
              style={{ width: `${Math.min(100, summary.hours_used_pct || 0)}%` }}
            />
          </div>
          <p className="mt-4 text-xs text-muted-foreground font-medium italic">
            {(summary.hours_used_pct || 0) >= 100 
              ? "Project has exceeded its allocated hourly budget." 
              : `Approximately ${Math.max(0, summary.budget_hours - summary.total_hours_logged).toFixed(1)}h remaining.`}
          </p>
        </ProfessionalCard>
      )}
    </div>
  );
}

function KanbanTab({ projectId, project }: { projectId: number; project: Project }) {
  const { data, isLoading } = useProjectKanban(projectId);
  const createTask = useCreateTask(projectId);
  const updateTask = useUpdateTask(projectId);
  const createField = useCreateCustomField(projectId);
  const reorderTasks = useReorderKanbanTasks(projectId);
  const { startTimer, active: timerActive } = useTimer();
  const [selectedTask, setSelectedTask] = useState<ProjectTask | null>(null);
  const [newTaskNames, setNewTaskNames] = useState<Record<string, string>>({});
  const [showFieldForm, setShowFieldForm] = useState(false);
  const [fieldForm, setFieldForm] = useState({ name: '', field_type: 'text' });

  if (isLoading || !data) {
    return <div className="text-muted-foreground animate-pulse py-8">Loading Kanban board…</div>;
  }

  const columns = data.columns.filter((column) => !column.hidden).sort((a, b) => a.position - b.position);
  const tasksByColumn = columns.reduce<Record<string, ProjectTask[]>>((acc, column) => {
    acc[column.key] = data.tasks
      .filter((task) => (task.kanban_status || 'todo') === column.key)
      .sort((a, b) => (a.kanban_position || 0) - (b.kanban_position || 0));
    return acc;
  }, {});

  const handleDragEnd = async (event: DragEndEvent) => {
    const task = event.active.data.current?.task as ProjectTask | undefined;
    const destinationColumn = event.over?.id ? String(event.over.id) : undefined;
    if (!task || !destinationColumn || task.kanban_status === destinationColumn) return;

    const destinationTasks = tasksByColumn[destinationColumn] || [];
    const nextPosition = destinationTasks.length
      ? Math.max(...destinationTasks.map((item) => item.kanban_position || 0)) + 1
      : 1;

    await reorderTasks.mutateAsync([
      { task_id: task.id, kanban_status: destinationColumn, kanban_position: nextPosition },
    ]);
  };

  const handleCreateTask = async (columnKey: string) => {
    const name = (newTaskNames[columnKey] || '').trim();
    if (!name) return;
    await createTask.mutateAsync({
      name,
      kanban_status: columnKey,
      kanban_position: (tasksByColumn[columnKey]?.length || 0) + 1,
      status: columnKey === 'done' ? 'completed' : 'active',
      custom_fields: {},
    });
    setNewTaskNames((prev) => ({ ...prev, [columnKey]: '' }));
  };

  const handleCreateField = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = fieldForm.name.trim();
    if (!name) return;
    await createField.mutateAsync({
      name,
      key: name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, ''),
      field_type: fieldForm.field_type,
      position: data.custom_fields.length,
      options: [],
      required: false,
    });
    setFieldForm({ name: '', field_type: 'text' });
    setShowFieldForm(false);
  };

  const handleStartTimer = async (task: ProjectTask) => {
    await startTimer({
      project_id: projectId,
      task_id: task.id,
      description: task.name,
      hourly_rate: task.hourly_rate ?? project.hourly_rate ?? 0,
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-2xl border border-border/50 bg-card/40 p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">Project Board</h3>
          <p className="text-sm text-muted-foreground">Plan work, track progress, and start timers from task cards.</p>
        </div>
        <ProfessionalButton
          variant="outline"
          size="sm"
          onClick={() => setShowFieldForm((value) => !value)}
        >
          <Plus className="w-4 h-4 mr-2" /> Custom Field
        </ProfessionalButton>
      </div>

      {showFieldForm && (
        <ProfessionalCard variant="elevated" className="p-4 border-l-4 border-l-primary bg-card/50">
          <form onSubmit={handleCreateField} className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <Input
              required
              className="sm:col-span-2 bg-background/50 border-border/50 rounded-xl"
              placeholder="Field name"
              value={fieldForm.name}
              onChange={(event) => setFieldForm({ ...fieldForm, name: event.target.value })}
            />
            <select
              className="flex h-10 w-full rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
              value={fieldForm.field_type}
              onChange={(event) => setFieldForm({ ...fieldForm, field_type: event.target.value })}
            >
              <option value="text">Text</option>
              <option value="number">Number</option>
              <option value="date">Date</option>
              <option value="checkbox">Checkbox</option>
            </select>
            <div className="flex justify-end gap-2">
              <ProfessionalButton type="button" variant="ghost" onClick={() => setShowFieldForm(false)}>Cancel</ProfessionalButton>
              <ProfessionalButton type="submit" loading={createField.isPending}>Save</ProfessionalButton>
            </div>
          </form>
        </ProfessionalCard>
      )}

      <DndContext onDragEnd={handleDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-4">
          {columns.map((column) => (
            <KanbanColumnPanel
              key={column.key}
              column={column}
              tasks={tasksByColumn[column.key] || []}
              customFields={data.custom_fields}
              currency={project.currency}
              timerActive={timerActive}
              newTaskName={newTaskNames[column.key] || ''}
              onNewTaskName={(value) => setNewTaskNames((prev) => ({ ...prev, [column.key]: value }))}
              onCreateTask={() => handleCreateTask(column.key)}
              onOpenTask={setSelectedTask}
              onStartTimer={handleStartTimer}
            />
          ))}
        </div>
      </DndContext>

      {selectedTask && (
        <KanbanTaskDrawer
          task={selectedTask}
          customFields={data.custom_fields}
          project={project}
          onClose={() => setSelectedTask(null)}
          onSave={async (updates) => {
            await updateTask.mutateAsync({ taskId: selectedTask.id, data: updates });
            setSelectedTask(null);
          }}
          saving={updateTask.isPending}
        />
      )}
    </div>
  );
}

function KanbanColumnPanel({
  column,
  tasks,
  customFields,
  currency,
  timerActive,
  newTaskName,
  onNewTaskName,
  onCreateTask,
  onOpenTask,
  onStartTimer,
}: {
  column: KanbanColumn;
  tasks: ProjectTask[];
  customFields: ProjectCustomField[];
  currency: string;
  timerActive: boolean;
  newTaskName: string;
  onNewTaskName: (value: string) => void;
  onCreateTask: () => void;
  onOpenTask: (task: ProjectTask) => void;
  onStartTimer: (task: ProjectTask) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.key });

  return (
    <section
      ref={setNodeRef}
      className={cn(
        "flex min-h-[520px] w-[320px] shrink-0 flex-col rounded-2xl border border-border/50 bg-muted/20 p-3 transition-colors",
        isOver && "border-primary/50 bg-primary/5"
      )}
    >
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h4 className="font-bold tracking-tight">{column.name}</h4>
          <p className="text-xs text-muted-foreground">{tasks.length} card{tasks.length === 1 ? '' : 's'}</p>
        </div>
        <Badge variant="outline" className="rounded-full text-[10px]">{column.position + 1}</Badge>
      </div>

      <div className="flex flex-1 flex-col gap-3">
        {tasks.map((task) => (
          <KanbanTaskCard
            key={task.id}
            task={task}
            customFields={customFields}
            currency={currency}
            timerActive={timerActive}
            onOpen={() => onOpenTask(task)}
            onStartTimer={() => onStartTimer(task)}
          />
        ))}
      </div>

      <div className="mt-3 space-y-2 rounded-xl border border-border/50 bg-background/60 p-2">
        <Input
          value={newTaskName}
          onChange={(event) => onNewTaskName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') onCreateTask();
          }}
          placeholder="Add task"
          className="h-9 rounded-lg border-border/50 bg-background text-sm"
        />
        <ProfessionalButton variant="ghost" size="sm" className="w-full justify-center" onClick={onCreateTask}>
          <Plus className="mr-2 h-3.5 w-3.5" /> Add Card
        </ProfessionalButton>
      </div>
    </section>
  );
}

function KanbanTaskCard({
  task,
  customFields,
  currency,
  timerActive,
  onOpen,
  onStartTimer,
}: {
  task: ProjectTask;
  customFields: ProjectCustomField[];
  currency: string;
  timerActive: boolean;
  onOpen: () => void;
  onStartTimer: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `task-${task.id}`,
    data: { task },
  });
  const style = { transform: CSS.Translate.toString(transform) };

  return (
    <ProfessionalCard
      ref={setNodeRef}
      style={style}
      className={cn(
        "p-4 bg-card border border-border/60 shadow-sm transition-all hover:border-primary/30 hover:shadow-md",
        isDragging && "opacity-70 shadow-xl"
      )}
    >
      <div className="flex items-start gap-2">
        <button
          type="button"
          className="mt-0.5 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <button type="button" className="min-w-0 flex-1 text-left" onClick={onOpen}>
          <div className="font-bold text-sm tracking-tight text-foreground">{task.name}</div>
          {task.description && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{task.description}</p>}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-medium text-muted-foreground">
        <Badge variant="outline" className="rounded-md text-[10px]">{(task.actual_hours || 0).toFixed(1)}h logged</Badge>
        {task.estimated_hours != null && <Badge variant="outline" className="rounded-md text-[10px]">Est {task.estimated_hours}h</Badge>}
        {task.priority && <Badge variant="outline" className="rounded-md text-[10px]">{task.priority}</Badge>}
        {task.due_date && (
          <Badge variant="outline" className="rounded-md text-[10px]">
            <CalendarDays className="mr-1 h-3 w-3" /> {task.due_date}
          </Badge>
        )}
      </div>

      {customFields.length > 0 && (
        <div className="mt-3 space-y-1 border-t border-border/50 pt-3">
          {customFields.slice(0, 3).map((field) => {
            const value = task.custom_fields?.[field.key];
            if (value === undefined || value === null || value === '') return null;
            return (
              <div key={field.id} className="flex items-center justify-between gap-2 text-[11px]">
                <span className="truncate text-muted-foreground">{field.name}</span>
                <span className="truncate font-semibold text-foreground">{String(value)}</span>
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-border/50 pt-3">
        <span className="text-[11px] font-semibold text-muted-foreground">
          {task.hourly_rate != null ? `${currency} ${task.hourly_rate}/hr` : 'Project rate'}
        </span>
        <ProfessionalButton
          variant="ghost"
          size="icon-sm"
          disabled={timerActive || task.status === 'completed'}
          onClick={onStartTimer}
          title="Start timer"
        >
          <Play className="h-3.5 w-3.5" />
        </ProfessionalButton>
      </div>
    </ProfessionalCard>
  );
}

function KanbanTaskDrawer({
  task,
  customFields,
  project,
  onClose,
  onSave,
  saving,
}: {
  task: ProjectTask;
  customFields: ProjectCustomField[];
  project: Project;
  onClose: () => void;
  onSave: (updates: Partial<ProjectTask>) => Promise<void>;
  saving: boolean;
}) {
  const [form, setForm] = useState({
    name: task.name,
    description: task.description || '',
    estimated_hours: task.estimated_hours != null ? String(task.estimated_hours) : '',
    hourly_rate: task.hourly_rate != null ? String(task.hourly_rate) : '',
    priority: task.priority || '',
    due_date: task.due_date || '',
    custom_fields: { ...(task.custom_fields || {}) } as Record<string, unknown>,
  });

  const setCustomField = (key: string, value: unknown) => {
    setForm((prev) => ({ ...prev, custom_fields: { ...prev.custom_fields, [key]: value } }));
  };

  const handleSave = async () => {
    await onSave({
      name: form.name,
      description: form.description || null,
      estimated_hours: form.estimated_hours ? parseFloat(form.estimated_hours) : null,
      hourly_rate: form.hourly_rate ? parseFloat(form.hourly_rate) : null,
      priority: form.priority || null,
      due_date: form.due_date || null,
      custom_fields: form.custom_fields,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-sm">
      <ProfessionalCard variant="elevated" className="h-full w-full max-w-xl overflow-y-auto rounded-none p-6 shadow-2xl">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-xl font-bold tracking-tight">Task Details</h3>
            <p className="text-sm text-muted-foreground">Update the card, billing details, and project custom fields.</p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4">
          <Input
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            className="bg-background/50 border-border/50 rounded-xl"
            placeholder="Task name"
          />
          <textarea
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            className="min-h-28 w-full rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
            placeholder="Description"
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Input
              type="number"
              step="0.25"
              value={form.estimated_hours}
              onChange={(event) => setForm({ ...form, estimated_hours: event.target.value })}
              className="bg-background/50 border-border/50 rounded-xl"
              placeholder="Estimated hours"
            />
            <Input
              type="number"
              step="0.01"
              value={form.hourly_rate}
              onChange={(event) => setForm({ ...form, hourly_rate: event.target.value })}
              className="bg-background/50 border-border/50 rounded-xl"
              placeholder={`Hourly rate (${project.currency})`}
            />
            <select
              value={form.priority}
              onChange={(event) => setForm({ ...form, priority: event.target.value })}
              className="flex h-10 w-full rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
            >
              <option value="">No priority</option>
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
              <option value="Urgent">Urgent</option>
            </select>
            <Input
              type="date"
              value={form.due_date}
              onChange={(event) => setForm({ ...form, due_date: event.target.value })}
              className="bg-background/50 border-border/50 rounded-xl"
            />
          </div>

          {customFields.length > 0 && (
            <div className="space-y-3 rounded-2xl border border-border/50 bg-muted/20 p-4">
              <h4 className="text-sm font-bold tracking-tight">Custom Fields</h4>
              {customFields.map((field) => (
                <label key={field.id} className="block space-y-1.5 text-sm font-medium">
                  <span>{field.name}</span>
                  {field.field_type === 'checkbox' ? (
                    <input
                      type="checkbox"
                      checked={Boolean(form.custom_fields[field.key])}
                      onChange={(event) => setCustomField(field.key, event.target.checked)}
                      className="h-4 w-4 rounded border-border"
                    />
                  ) : (
                    <Input
                      type={field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text'}
                      value={String(form.custom_fields[field.key] ?? '')}
                      onChange={(event) => {
                        const value = field.field_type === 'number' && event.target.value
                          ? Number(event.target.value)
                          : event.target.value;
                        setCustomField(field.key, value);
                      }}
                      className="bg-background/50 border-border/50 rounded-xl"
                    />
                  )}
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-2 border-t border-border/50 pt-4">
          <ProfessionalButton variant="ghost" onClick={onClose}>Cancel</ProfessionalButton>
          <ProfessionalButton variant="gradient" loading={saving} onClick={handleSave}>
            <Save className="mr-2 h-4 w-4" /> Save Card
          </ProfessionalButton>
        </div>
      </ProfessionalCard>
    </div>
  );
}

function TasksTab({ projectId, tasks, projectHourlyRate }: { projectId: number; tasks: ProjectTask[]; projectHourlyRate?: number | null }) {
  const createTask = useCreateTask(projectId);
  const deleteTask = useDeleteTask(projectId);
  const updateTask = useUpdateTask(projectId);
  const [newTask, setNewTask] = useState({ name: '', estimated_hours: '', hourly_rate: '' });
  const [showAdd, setShowAdd] = useState(false);

  const handleAdd = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    await createTask.mutateAsync({
      name: newTask.name,
      estimated_hours: newTask.estimated_hours ? parseFloat(newTask.estimated_hours) : undefined,
      hourly_rate: newTask.hourly_rate ? parseFloat(newTask.hourly_rate) : undefined,
    });
    setNewTask({ name: '', estimated_hours: '', hourly_rate: '' });
    setShowAdd(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <ProfessionalButton onClick={() => setShowAdd(true)} variant="gradient" size="sm">
          <Plus className="w-4 h-4 mr-2" /> Add Task
        </ProfessionalButton>
      </div>

      {showAdd && (
        <ProfessionalCard variant="elevated" className="p-6 border-l-4 border-l-primary bg-card/50 backdrop-blur-sm">
          <h3 className="font-bold text-lg mb-4">Create New Task</h3>
          <form onSubmit={handleAdd} className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Input 
              required 
              className="col-span-1 sm:col-span-3 bg-background/50 border-border/50 rounded-xl" 
              placeholder="Task name *" 
              value={newTask.name} 
              onChange={(e) => setNewTask({ ...newTask, name: e.target.value })} 
            />
            <Input 
              type="number" 
              step="0.5" 
              className="bg-background/50 border-border/50 rounded-xl" 
              placeholder="Est. hours" 
              value={newTask.estimated_hours} 
              onChange={(e) => setNewTask({ ...newTask, estimated_hours: e.target.value })} 
            />
            <Input 
              type="number" 
              step="0.01" 
              className="bg-background/50 border-border/50 rounded-xl" 
              placeholder="Hourly rate" 
              value={newTask.hourly_rate} 
              onChange={(e) => setNewTask({ ...newTask, hourly_rate: e.target.value })} 
            />
            <div className="flex gap-2 justify-end">
              <ProfessionalButton type="button" variant="ghost" onClick={() => setShowAdd(false)}>Cancel</ProfessionalButton>
              <ProfessionalButton type="submit" loading={createTask.isPending} variant="default">Save Task</ProfessionalButton>
            </div>
          </form>
        </ProfessionalCard>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {tasks.map((task) => (
          <ProfessionalCard key={task.id} className="p-4 bg-card/50 border border-border/50 hover:border-primary/20 transition-all hover:shadow-md group flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <div className="text-foreground font-bold text-sm tracking-tight">{task.name}</div>
                <Badge variant="outline" className={cn("text-[9px] px-1.5 py-0 rounded-md", task.status === 'completed' ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200')}>
                  {task.status}
                </Badge>
              </div>
              <div className="text-muted-foreground text-[10px] mt-1 flex items-center gap-2 font-medium">
                <Badge variant="outline" className="text-[9px] px-1.5 py-0 rounded-md">
                   {task.estimated_hours ? `Est: ${task.estimated_hours}h` : 'No estimate'}
                </Badge>
                <span className="opacity-30">•</span>
                <span>{task.hourly_rate ? `$${task.hourly_rate}/hr` : projectHourlyRate != null ? `Inherits $${projectHourlyRate}/hr` : 'No rate'}</span>
                <span className="opacity-30">•</span>
                <span className="text-primary font-bold">Logged: {(task.actual_hours || 0).toFixed(1)}h</span>
              </div>
            </div>
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {task.status === 'completed' ? (
                <ProfessionalButton
                  variant="ghost"
                  size="sm"
                  onClick={() => updateTask.mutate({ taskId: task.id, data: { status: 'active' } })}
                >
                  Reopen
                </ProfessionalButton>
              ) : (
                <ProfessionalButton
                  variant="ghost"
                  size="icon-sm"
                  className="text-muted-foreground hover:text-primary"
                  onClick={() => updateTask.mutate({ taskId: task.id, data: { status: 'completed' } })}
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                </ProfessionalButton>
              )}
              <ProfessionalButton
                variant="ghost"
                size="icon-sm"
                className="text-muted-foreground hover:text-destructive"
                onClick={() => deleteTask.mutate(task.id)}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </ProfessionalButton>
            </div>
          </ProfessionalCard>
        ))}
      </div>
      {tasks.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center bg-muted/20 rounded-2xl border-2 border-dashed border-border/50">
           <ListChecks className="w-12 h-12 text-muted-foreground opacity-20 mb-3" />
           <p className="text-muted-foreground font-medium">No tasks defined for this project.</p>
        </div>
      )}
    </div>
  );
}

function TimeEntriesTab({ entries, tasks, project, onDelete }: { entries: TimeEntry[]; tasks: ProjectTask[]; project: Project; onDelete: (id: number) => void }) {
  const updateEntry = useUpdateTimeEntry();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ description: '', hours: '', billable: true, task_id: undefined as number | undefined });

  const startEdit = (entry: TimeEntry) => {
    setEditingId(entry.id);
    setEditForm({
      description: entry.description || '',
      hours: entry.hours.toFixed(2),
      billable: entry.billable,
      task_id: entry.task_id ?? undefined,
    });
  };

  const cancelEdit = () => { setEditingId(null); };

  const saveEdit = async (entry: TimeEntry) => {
    const projectId = entry.project_id;
    const selectedTask = tasks.find((t) => t.id === editForm.task_id);
    const hourlyRate = selectedTask?.hourly_rate ?? project.hourly_rate;
    await updateEntry.mutateAsync({
      id: entry.id,
      data: {
        description: editForm.description,
        duration_minutes: Math.round(parseFloat(editForm.hours) * 60),
        billable: editForm.billable,
        task_id: editForm.task_id ?? null,
        // Keep hourly_rate in sync with chosen task
        ...(hourlyRate != null ? { hourly_rate: hourlyRate } : {}),
        project_id: projectId,
      },
    });
    setEditingId(null);
  };

  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <ProfessionalCard key={entry.id} className="p-4 bg-card/50 border border-border/50 hover:border-primary/20 transition-all hover:shadow-md group">
          {editingId === entry.id ? (
            /* ── Inline edit form ── */
            <div className="space-y-3">
              {/* Row 1: Task + Hours */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* Task selector */}
                <select
                  className="sm:col-span-2 flex h-10 w-full rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 transition-all cursor-pointer"
                  value={editForm.task_id ?? ''}
                  onChange={(e) => setEditForm({ ...editForm, task_id: e.target.value ? Number(e.target.value) : undefined })}
                >
                  <option value="">— No task —</option>
                  {tasks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}{t.hourly_rate ? ` — $${t.hourly_rate}/hr` : project.hourly_rate != null ? ` — inherits $${project.hourly_rate}/hr` : ''}
                    </option>
                  ))}
                </select>
                <Input
                  type="number" step="0.25" min="0.01"
                  className="bg-background/50 border-border/50 rounded-xl text-sm"
                  placeholder="Hours"
                  value={editForm.hours}
                  onChange={(e) => setEditForm({ ...editForm, hours: e.target.value })}
                />
              </div>
              {/* Row 2: Description */}
              <Input
                className="bg-background/50 border-border/50 rounded-xl text-sm"
                placeholder="Description"
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                autoFocus
              />
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={editForm.billable}
                    onChange={(e) => setEditForm({ ...editForm, billable: e.target.checked })}
                    className="rounded h-4 w-4 text-primary focus:ring-primary/20"
                  />
                  Billable
                </label>
                <div className="flex gap-2">
                  <ProfessionalButton variant="ghost" size="sm" onClick={cancelEdit}>
                    <X className="w-3.5 h-3.5 mr-1" /> Cancel
                  </ProfessionalButton>
                  <ProfessionalButton
                    variant="default" size="sm"
                    loading={updateEntry.isPending}
                    onClick={() => saveEdit(entry)}
                  >
                    <Save className="w-3.5 h-3.5 mr-1" /> Save
                  </ProfessionalButton>
                </div>
              </div>
            </div>
          ) : (
            /* ── Read view ── */
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="text-foreground font-bold text-sm tracking-tight truncate">
                  {entry.description || entry.task_name || 'Working session'}
                </div>
                <div className="text-muted-foreground text-[10px] mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 font-medium">
                  <span className="flex items-center gap-1 font-semibold">{new Date(entry.started_at).toLocaleDateString()}</span>
                  <span className="opacity-30">•</span>
                  <span>{entry.hours.toFixed(2)}h logged</span>
                  <span className="opacity-30">•</span>
                  <span className="text-foreground/80">${(entry.amount || 0).toFixed(2)}</span>
                  <span className="opacity-30">•</span>
                  <Badge variant="outline" className={cn("text-[9px] px-1.5 rounded-md", entry.invoiced ? 'border-primary/20 text-primary bg-primary/5' : 'border-warning/30 text-warning bg-warning/10')}>
                    {entry.invoiced ? 'Billed' : 'Unbilled'}
                  </Badge>
                </div>
              </div>
              <div className="flex items-center gap-1 ml-4 opacity-0 group-hover:opacity-100 transition-opacity">
                {!entry.invoiced && (
                  <>
                    <ProfessionalButton
                      variant="ghost" size="icon-sm"
                      className="text-muted-foreground hover:text-primary"
                      onClick={() => startEdit(entry)}
                      title="Edit entry"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </ProfessionalButton>
                    <ProfessionalButton
                      variant="ghost" size="icon-sm"
                      className="text-muted-foreground hover:text-destructive"
                      onClick={() => onDelete(entry.id)}
                      title="Delete entry"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </ProfessionalButton>
                  </>
                )}
              </div>
            </div>
          )}
        </ProfessionalCard>
      ))}
      {entries.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center bg-muted/20 rounded-2xl border-2 border-dashed border-border/50">
           <Clock className="w-12 h-12 text-muted-foreground opacity-20 mb-3" />
           <p className="text-muted-foreground font-medium">No time entries recorded yet.</p>
        </div>
      )}
    </div>
  );
}

function UnbilledTab({ unbilled, selectedIds, onToggleEntry, onSelectAll, isAllSelected, onInvoice, isInvoicing, currency }: any) {
  if (!unbilled) return <div className="text-muted-foreground animate-pulse py-8">Auditing unbilled items…</div>;

  return (
    <div className="space-y-6">
      {/* Time entries */}
      <ProfessionalCard variant="elevated" className="overflow-hidden bg-card/50 backdrop-blur-sm border-border/30">
        <div className="px-6 py-4 border-b border-border/30 bg-muted/30 flex items-center justify-between">
          <h3 className="text-foreground font-bold text-sm flex items-center gap-2">
            <Clock className="w-4 h-4 text-primary" />
            Unbilled Time Entries
          </h3>
          {unbilled.time_entries.length > 0 && (
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="select-all-time"
                checked={isAllSelected}
                onChange={(e) => {
                  if (e.target.checked) {
                    onSelectAll(unbilled.time_entries.map((en: any) => en.id));
                  } else {
                    onSelectAll([]);
                  }
                }}
                className="rounded-lg h-4 w-4 border-border shadow-sm text-primary focus:ring-primary/20 cursor-pointer"
              />
              <label htmlFor="select-all-time" className="text-xs font-medium text-muted-foreground cursor-pointer select-none">
                Select All
              </label>
            </div>
          )}
        </div>
        <div className="divide-y divide-border/20">
          {unbilled.time_entries.map((entry: any) => (
            <div key={entry.id} className="flex items-center gap-4 px-6 py-4 hover:bg-primary/5 transition-all group">
              <input
                type="checkbox"
                checked={selectedIds.includes(entry.id)}
                onChange={() => onToggleEntry(entry.id)}
                className="rounded-lg h-5 w-5 border-border shadow-sm text-primary focus:ring-primary/20 cursor-pointer"
              />
              <div className="flex-1 min-w-0">
                <div className="text-foreground font-bold text-sm tracking-tight">{entry.description || entry.task_name || 'Time'}</div>
                <div className="text-muted-foreground text-[10px] sm:text-xs mt-0.5 flex items-center gap-2">
                  <span className="font-semibold">{new Date(entry.started_at).toLocaleDateString()}</span>
                  <span className="opacity-30">•</span>
                  <span>{entry.hours.toFixed(2)}h</span>
                </div>
              </div>
              <div className="text-foreground font-bold text-sm bg-muted/30 px-3 py-1.5 rounded-xl border border-border/10">
                {currency} {entry.amount.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
        {unbilled.time_entries.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 opacity-60">
             <AlertCircle className="w-8 h-8 mb-2" />
             <p className="text-sm font-medium">All time entries have been billed.</p>
          </div>
        )}
      </ProfessionalCard>

      {/* Totals + invoice button */}
      <ProfessionalCard variant="elevated" className="p-6 flex flex-col sm:flex-row items-center justify-between gap-6 border-l-4 border-l-primary shadow-xl">
        <div className="flex flex-col">
          <span className="text-muted-foreground text-[11px] font-bold uppercase tracking-widest mb-1">Total Unbilled Balance</span>
          <div className="text-4xl font-extrabold tracking-tighter text-foreground">
            {currency} {unbilled.grand_total.toFixed(2)}
          </div>
          <p className="text-xs text-muted-foreground font-medium mt-1">
            {selectedIds.length} time entries selected for invoicing
          </p>
        </div>
        <ProfessionalButton
          onClick={onInvoice}
          disabled={isInvoicing || (!selectedIds.length && !unbilled.expenses.length)}
          variant="gradient"
          size="xl"
          className="shadow-xl shadow-primary/20 w-full sm:w-auto"
          leftIcon={<FileText className="w-5 h-5" />}
        >
          {isInvoicing ? 'Generating Invoice…' : 'Generate Invoice'}
        </ProfessionalButton>
      </ProfessionalCard>
    </div>
  );
}
