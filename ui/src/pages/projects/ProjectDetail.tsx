import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Clock, DollarSign, ListChecks,
  Receipt, BarChart3, Plus, Trash2, Play, FileText, CheckCircle2, AlertCircle, Edit2, Save, X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useProject, useProjectSummary, useProjectTasks,
  useTimeEntries, useUnbilledItems, useCreateInvoiceFromProject,
  useCreateTask, useDeleteTask, useDeleteTimeEntry, useUpdateProject
} from '@/plugins/time_tracking/hooks';
import { SearchableClientSelect } from '@/plugins/time_tracking/components/SearchableClientSelect';
import { TimeEntry, ProjectTask } from '@/plugins/time_tracking/api';
import { useTimer } from '@/contexts/TimerContext';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalCard, MetricCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';

const TABS = ['Overview', 'Tasks', 'Time Entries', 'Unbilled'] as const;
type TabType = typeof TABS[number];

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || '0', 10);
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabType>('Overview');
  const [selectedEntryIds, setSelectedEntryIds] = useState<number[]>([]);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editClientId, setEditClientId] = useState<number | undefined>(undefined);

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

  const handleStartTimer = async () => {
    const defaultRate = tasks[0]?.hourly_rate || 100;
    await startTimer({
      project_id: projectId,
      description: `Working on ${project.name}`,
      hourly_rate: defaultRate,
    });
  };

  const handleSave = async () => {
    if (!editName || !editClientId) return;
    await updateProject.mutateAsync({
      name: editName,
      client_id: editClientId,
    });
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditName(project.name);
    setEditClientId(project.client_id);
    setIsEditing(false);
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
            <div className="max-w-md mt-2">
              <SearchableClientSelect
                value={editClientId}
                onChange={setEditClientId}
                placeholder="Select client"
                className="h-9"
              />
            </div>
          ) : (
            project.client_name || `Client #${project.client_id}`
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
                {!timerActive && (
                  <ProfessionalButton
                    onClick={handleStartTimer}
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
              tab === t && "bg-white dark:bg-slate-800 shadow-sm text-primary"
            )}
          >
            {t}
          </Button>
        ))}
      </div>

      <ContentSection>
        {tab === 'Overview' && <OverviewTab summary={summary} project={project} />}
        {tab === 'Tasks' && <TasksTab projectId={projectId} tasks={tasks} />}
        {tab === 'Time Entries' && (
          <TimeEntriesTab
            entries={timeEntries}
            onDelete={(id) => deleteEntry.mutate(id)}
          />
        )}
        {tab === 'Unbilled' && (
          <UnbilledTab
            unbilled={unbilled}
            selectedIds={selectedEntryIds}
            onToggleEntry={(id) =>
              setSelectedEntryIds((prev) =>
                prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
              )
            }
            onSelectAll={(ids) => setSelectedEntryIds(ids)}
            isAllSelected={unbilled?.time_entries.length > 0 && selectedEntryIds.length === unbilled?.time_entries.length}
            onInvoice={handleInvoice}
            isInvoicing={createInvoice.isPending}
            currency={project.currency}
          />
        )}
      </ContentSection>
    </div>
  );
}

// ---- Sub-components ----

function OverviewTab({ summary, project }: any) {
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
                (summary.hours_used_pct || 0) >= 90 ? 'bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.4)]' : 
                (summary.hours_used_pct || 0) >= 75 ? 'bg-amber-500 shadow-[0_0_12px_rgba(245,158,11,0.4)]' : 
                'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.4)]'
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

function TasksTab({ projectId, tasks }: { projectId: number; tasks: ProjectTask[] }) {
  const createTask = useCreateTask(projectId);
  const deleteTask = useDeleteTask(projectId);
  const [newTask, setNewTask] = useState({ name: '', estimated_hours: '', hourly_rate: '' });
  const [showAdd, setShowAdd] = useState(false);

  const handleAdd = async (e: React.FormEvent) => {
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
              <div className="text-foreground font-bold text-sm tracking-tight">{task.name}</div>
              <div className="text-muted-foreground text-[10px] mt-1 flex items-center gap-2 font-medium">
                <Badge variant="outline" className="text-[9px] px-1.5 py-0 rounded-md">
                   {task.estimated_hours ? `Est: ${task.estimated_hours}h` : 'No estimate'}
                </Badge>
                <span className="opacity-30">•</span>
                <span>{task.hourly_rate ? `$${task.hourly_rate}/hr` : 'No rate'}</span>
                <span className="opacity-30">•</span>
                <span className="text-primary font-bold">Logged: {(task.actual_hours || 0).toFixed(1)}h</span>
              </div>
            </div>
            <ProfessionalButton 
              variant="ghost" 
              size="icon-sm" 
              className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
              onClick={() => deleteTask.mutate(task.id)}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </ProfessionalButton>
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

function TimeEntriesTab({ entries, onDelete }: { entries: TimeEntry[]; onDelete: (id: number) => void }) {
  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <ProfessionalCard key={entry.id} className="p-4 bg-card/50 border border-border/50 hover:border-primary/20 transition-all hover:shadow-md group">
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
                <Badge variant="outline" className={cn("text-[9px] px-1.5 rounded-md", entry.invoiced ? 'border-primary/20 text-primary bg-primary/5' : 'border-amber-200 text-amber-600 bg-amber-50')}>
                  {entry.invoiced ? 'Billed' : 'Unbilled'}
                </Badge>
              </div>
            </div>
            {!entry.invoiced && (
              <ProfessionalButton 
                variant="ghost" 
                size="icon-sm" 
                className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive ml-4"
                onClick={() => onDelete(entry.id)}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </ProfessionalButton>
            )}
          </div>
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

