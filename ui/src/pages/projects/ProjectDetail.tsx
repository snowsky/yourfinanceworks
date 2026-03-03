import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Clock, DollarSign, FolderKanban, ListChecks,
  Receipt, BarChart3, Plus, Trash2, Edit2, Play, Download, FileText
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useProject, useProjectSummary, useProjectTasks,
  useTimeEntries, useUnbilledItems, useCreateInvoiceFromProject,
  useCreateTask, useDeleteTask, useDeleteTimeEntry
} from '@/plugins/time_tracking/hooks';
import { TimeEntry, ProjectTask } from '@/plugins/time_tracking/api';
import { useTimer } from '@/contexts/TimerContext';
import { timeEntryApi } from '@/plugins/time_tracking/api';

const TABS = ['Overview', 'Tasks', 'Time Entries', 'Unbilled'];

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || '0', 10);
  const navigate = useNavigate();
  const [tab, setTab] = useState('Overview');
  const [showLog, setShowLog] = useState(false);
  const [selectedEntryIds, setSelectedEntryIds] = useState<number[]>([]);

  const { data: project } = useProject(projectId);
  const { data: summary } = useProjectSummary(projectId);
  const { data: tasks = [] } = useProjectTasks(projectId);
  const { data: timeEntries = [] } = useTimeEntries({ project_id: projectId });
  const { data: unbilled } = useUnbilledItems(projectId);
  const createInvoice = useCreateInvoiceFromProject(projectId);
  const deleteEntry = useDeleteTimeEntry();
  const { startTimer, active: timerActive } = useTimer();

  if (!project) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <p className="text-slate-400">Loading project…</p>
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      {/* Header */}
      <div className="flex items-start gap-4 mb-8">
        <button onClick={() => navigate('/projects')} className="mt-1 text-slate-400 hover:text-white transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-white">{project.name}</h1>
          <p className="text-slate-400 text-sm mt-0.5">{project.client_name || `Client #${project.client_id}`}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={project.status === 'active' ? 'bg-emerald-600' : 'bg-slate-600'}>
            {project.status}
          </Badge>
          {!timerActive && (
            <Button
              onClick={handleStartTimer}
              className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm flex items-center gap-1.5"
            >
              <Play className="w-3.5 h-3.5" /> Start Timer
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-slate-800/40 p-1 rounded-xl w-fit">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t
                ? 'bg-blue-600 text-white shadow-lg'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
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
          onInvoice={handleInvoice}
          isInvoicing={createInvoice.isPending}
        />
      )}
    </div>
  );
}

// ---- Sub-components ----

function OverviewTab({ summary, project }: any) {
  if (!summary) return <div className="text-slate-400">Loading summary…</div>;
  const cards = [
    { label: 'Hours Logged', value: `${summary.total_hours_logged.toFixed(1)}h`, icon: <Clock className="w-5 h-5" />, color: 'from-blue-500 to-indigo-600' },
    { label: 'Unbilled', value: `${project.currency} ${summary.unbilled_amount.toFixed(2)}`, icon: <DollarSign className="w-5 h-5" />, color: 'from-amber-500 to-orange-600' },
    { label: 'Total Expenses', value: `${project.currency} ${summary.total_expenses.toFixed(2)}`, icon: <Receipt className="w-5 h-5" />, color: 'from-emerald-500 to-teal-600' },
    { label: 'Billed to Date', value: `${project.currency} ${summary.total_amount_logged.toFixed(2)}`, icon: <BarChart3 className="w-5 h-5" />, color: 'from-purple-500 to-pink-600' },
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div key={c.label} className={`bg-gradient-to-br ${c.color} rounded-2xl p-4 text-white`}>
            <div className="flex items-center gap-2 mb-2 opacity-80">{c.icon} <span className="text-xs font-medium">{c.label}</span></div>
            <div className="text-2xl font-bold">{c.value}</div>
          </div>
        ))}
      </div>

      {summary.budget_hours && (
        <div className="bg-slate-800/40 rounded-2xl p-4 border border-slate-700/50">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-slate-300 font-medium">Hours Budget</span>
            <span className="text-slate-400">{summary.total_hours_logged.toFixed(1)} / {summary.budget_hours}h ({summary.hours_used_pct}%)</span>
          </div>
          <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${(summary.hours_used_pct || 0) >= 90 ? 'bg-red-500' : 'bg-blue-500'}`}
              style={{ width: `${Math.min(100, summary.hours_used_pct || 0)}%` }}
            />
          </div>
        </div>
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
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setShowAdd(true)} className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm">
          <Plus className="w-4 h-4 mr-1" /> Add Task
        </Button>
      </div>

      {showAdd && (
        <form onSubmit={handleAdd} className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-4 grid grid-cols-3 gap-3">
          <input required className="col-span-3 bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Task name *" value={newTask.name} onChange={(e) => setNewTask({ ...newTask, name: e.target.value })} />
          <input type="number" step="0.5" className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Est. hours" value={newTask.estimated_hours} onChange={(e) => setNewTask({ ...newTask, estimated_hours: e.target.value })} />
          <input type="number" step="0.01" className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Hourly rate" value={newTask.hourly_rate} onChange={(e) => setNewTask({ ...newTask, hourly_rate: e.target.value })} />
          <div className="flex gap-2">
            <Button type="button" variant="ghost" className="text-slate-400 flex-1" onClick={() => setShowAdd(false)}>Cancel</Button>
            <Button type="submit" disabled={createTask.isPending} className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl flex-1">Save</Button>
          </div>
        </form>
      )}

      {tasks.map((task) => (
        <div key={task.id} className="flex items-center justify-between bg-slate-800/40 border border-slate-700/50 rounded-2xl p-4">
          <div>
            <div className="text-white font-medium">{task.name}</div>
            <div className="text-slate-400 text-xs mt-0.5">
              {task.estimated_hours ? `Est: ${task.estimated_hours}h` : 'No estimate'} •
              {task.hourly_rate ? ` $${task.hourly_rate}/hr` : ' No rate'} •
              Logged: {(task.actual_hours || 0).toFixed(1)}h
            </div>
          </div>
          <button onClick={() => deleteTask.mutate(task.id)} className="text-slate-500 hover:text-red-400 transition-colors ml-4">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      {tasks.length === 0 && <p className="text-slate-400 text-center py-8">No tasks yet</p>}
    </div>
  );
}

function TimeEntriesTab({ entries, onDelete }: { entries: TimeEntry[]; onDelete: (id: number) => void }) {
  return (
    <div className="space-y-2">
      {entries.map((entry) => (
        <div key={entry.id} className="flex items-center justify-between bg-slate-800/40 border border-slate-700/50 rounded-xl px-4 py-3">
          <div className="flex-1 min-w-0">
            <div className="text-white text-sm font-medium truncate">
              {entry.description || entry.task_name || 'Time entry'}
            </div>
            <div className="text-slate-400 text-xs mt-0.5">
              {new Date(entry.started_at).toLocaleDateString()} •
              {entry.hours.toFixed(2)}h •
              ${(entry.amount || 0).toFixed(2)} •
              <span className={`ml-1 ${entry.invoiced ? 'text-blue-400' : 'text-amber-400'}`}>
                {entry.invoiced ? 'Invoiced' : 'Unbilled'}
              </span>
            </div>
          </div>
          {!entry.invoiced && (
            <button onClick={() => onDelete(entry.id)} className="text-slate-500 hover:text-red-400 transition-colors ml-3">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      ))}
      {entries.length === 0 && <p className="text-slate-400 text-center py-8">No time entries yet</p>}
    </div>
  );
}

function UnbilledTab({ unbilled, selectedIds, onToggleEntry, onInvoice, isInvoicing }: any) {
  if (!unbilled) return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="space-y-4">
      {/* Time entries */}
      <div className="bg-slate-800/40 border border-slate-700/50 rounded-2xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700/50">
          <h3 className="text-white font-semibold text-sm">Unbilled Time</h3>
        </div>
        {unbilled.time_entries.map((entry: any) => (
          <div key={entry.id} className="flex items-center gap-3 px-4 py-3 border-b border-slate-700/30 last:border-0">
            <input
              type="checkbox"
              checked={selectedIds.includes(entry.id)}
              onChange={() => onToggleEntry(entry.id)}
              className="rounded"
            />
            <div className="flex-1 min-w-0">
              <div className="text-white text-sm">{entry.description || entry.task_name || 'Time'}</div>
              <div className="text-slate-400 text-xs">{new Date(entry.started_at).toLocaleDateString()} • {entry.hours.toFixed(2)}h</div>
            </div>
            <div className="text-white font-medium text-sm">${entry.amount.toFixed(2)}</div>
          </div>
        ))}
        {unbilled.time_entries.length === 0 && <p className="text-slate-400 text-center py-4 text-sm">No unbilled time</p>}
      </div>

      {/* Totals + invoice button */}
      <div className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-4 flex items-center justify-between">
        <div>
          <div className="text-slate-400 text-sm">Grand total</div>
          <div className="text-2xl font-bold text-white">${unbilled.grand_total.toFixed(2)}</div>
        </div>
        <Button
          onClick={onInvoice}
          disabled={isInvoicing || (!selectedIds.length && !unbilled.expenses.length)}
          className="bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white rounded-xl font-semibold"
        >
          <FileText className="w-4 h-4 mr-2" />
          {isInvoicing ? 'Creating…' : 'Create Invoice'}
        </Button>
      </div>
    </div>
  );
}
