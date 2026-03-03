import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FolderKanban, Clock, Plus, Download, Search, DollarSign, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useProjects, useCreateProject, useTimeEntries } from '@/plugins/time_tracking/hooks';
import { timeEntryApi, Project } from '@/plugins/time_tracking/api';
import { toast } from 'sonner';

// ─── Shared tab pill ──────────────────────────────────────────────────────────

const TAB_OPTIONS = [
  { id: 'projects', label: 'Projects', icon: FolderKanban },
  { id: 'my-time', label: 'My Time',  icon: Clock },
] as const;

type TabId = typeof TAB_OPTIONS[number]['id'];

// ─── Root page ────────────────────────────────────────────────────────────────

export default function TimeTracking() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get('tab') as TabId) ?? 'projects';

  const setTab = (tab: TabId) => setSearchParams({ tab });

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white flex items-center gap-2">
          <FolderKanban className="w-8 h-8 text-violet-400" />
          Time Tracking
        </h1>
        <p className="text-slate-400 mt-1">Projects, tasks and your personal time log</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-slate-800/50 rounded-xl w-fit mb-8 border border-slate-700/50">
        {TAB_OPTIONS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
              activeTab === id
                ? 'bg-violet-600 text-white shadow-md'
                : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'projects' ? <ProjectsTab /> : <MyTimeTab />}
    </div>
  );
}

// ─── Projects tab ─────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  active:    'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
  completed: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  archived:  'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400',
  cancelled: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

function ProjectsTab() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [showNewForm, setShowNewForm] = useState(false);
  const [newProject, setNewProject] = useState({ name: '', client_id: '', billing_method: 'hourly', currency: 'USD' });

  const { data: projects = [], isLoading } = useProjects({ status: statusFilter || undefined });
  const createProject = useCreateProject();

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.client_name || '').toLowerCase().includes(search.toLowerCase())
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProject.name || !newProject.client_id) return;
    const result = await createProject.mutateAsync({
      name: newProject.name,
      client_id: parseInt(newProject.client_id),
      billing_method: newProject.billing_method,
      currency: newProject.currency,
    });
    setShowNewForm(false);
    setNewProject({ name: '', client_id: '', billing_method: 'hourly', currency: 'USD' });
    navigate(`/projects/${result.id}`);
  };

  return (
    <div>
      {/* Toolbar */}
      <div className="flex flex-wrap gap-3 mb-6 items-center justify-between">
        <div className="flex flex-wrap gap-3 flex-1">
          <div className="relative min-w-48">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              className="pl-9 bg-slate-800/50 border-slate-700 text-white placeholder-slate-500 rounded-xl"
              placeholder="Search projects…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            {(['', 'active', 'completed', 'archived'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                  statusFilter === s
                    ? 'bg-violet-600 text-white'
                    : 'bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-700/50 border border-slate-700/50'
                }`}
              >
                {s === '' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <Button
          onClick={() => setShowNewForm(true)}
          className="bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 text-white font-semibold px-4 py-2 rounded-xl"
        >
          <Plus className="w-4 h-4 mr-2" /> New Project
        </Button>
      </div>

      {/* New project form */}
      {showNewForm && (
        <div className="mb-6 p-5 rounded-2xl border border-slate-700/50 bg-slate-800/40 backdrop-blur-sm">
          <h3 className="text-white font-semibold mb-4">New Project</h3>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <input
              required
              className="col-span-1 sm:col-span-2 bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-500"
              placeholder="Project name *"
              value={newProject.name}
              onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
            />
            <input
              required
              type="number"
              className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-500"
              placeholder="Client ID *"
              value={newProject.client_id}
              onChange={(e) => setNewProject({ ...newProject, client_id: e.target.value })}
            />
            <select
              className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={newProject.billing_method}
              onChange={(e) => setNewProject({ ...newProject, billing_method: e.target.value })}
            >
              <option value="hourly">Hourly</option>
              <option value="fixed_cost">Fixed Cost</option>
            </select>
            <div className="col-span-1 sm:col-span-4 flex gap-2 justify-end">
              <Button type="button" variant="ghost" className="text-slate-400" onClick={() => setShowNewForm(false)}>Cancel</Button>
              <Button type="submit" disabled={createProject.isPending} className="bg-violet-600 hover:bg-violet-700 text-white rounded-xl">
                {createProject.isPending ? 'Creating…' : 'Create Project'}
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Projects grid */}
      {isLoading ? (
        <div className="text-slate-400 text-center py-12">Loading projects…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-24">
          <FolderKanban className="w-16 h-16 text-slate-700 mx-auto mb-4" />
          <p className="text-slate-400">No projects found</p>
          <Button onClick={() => setShowNewForm(true)} className="mt-4 bg-violet-600 hover:bg-violet-700 text-white rounded-xl">
            Create your first project
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((project) => (
            <ProjectCard key={project.id} project={project} onClick={() => navigate(`/projects/${project.id}`)} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project, onClick }: { project: Project; onClick: () => void }) {
  const pct = project.budget_hours
    ? Math.min(100, ((project.total_hours_logged || 0) / project.budget_hours) * 100)
    : null;

  return (
    <div
      onClick={onClick}
      className="cursor-pointer rounded-2xl border border-slate-700/50 bg-slate-800/40 hover:bg-slate-800/70 hover:border-violet-500/30 transition-all duration-200 p-5 group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold truncate group-hover:text-violet-300 transition-colors">{project.name}</h3>
          <p className="text-slate-400 text-xs mt-0.5 flex items-center gap-1">
            <Users className="w-3 h-3" /> {project.client_name || `Client #${project.client_id}`}
          </p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ml-2 ${STATUS_COLORS[project.status] || STATUS_COLORS.active}`}>
          {project.status}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
        <div className="bg-slate-700/30 rounded-lg p-2">
          <div className="text-slate-400 mb-0.5 flex items-center gap-1"><Clock className="w-3 h-3" /> Hours logged</div>
          <div className="text-white font-semibold">{(project.total_hours_logged || 0).toFixed(1)}h</div>
        </div>
        <div className="bg-slate-700/30 rounded-lg p-2">
          <div className="text-slate-400 mb-0.5 flex items-center gap-1"><DollarSign className="w-3 h-3" /> Unbilled</div>
          <div className="text-white font-semibold">{project.currency} {(project.total_amount_logged || 0).toFixed(2)}</div>
        </div>
      </div>
      {pct !== null && (
        <div>
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span>Budget used</span><span>{pct.toFixed(0)}%</span>
          </div>
          <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-emerald-500'}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ─── My Time tab ──────────────────────────────────────────────────────────────

function MyTimeTab() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [isExporting, setIsExporting] = useState(false);
  const [showExport, setShowExport] = useState(false);

  const { data: entries = [], isLoading } = useTimeEntries({ limit: 200 });

  const monthEntries = entries.filter((e) => {
    const d = new Date(e.started_at);
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
  });

  const totalHours   = monthEntries.reduce((s, e) => s + e.hours, 0);
  const totalAmount  = monthEntries.reduce((s, e) => s + (e.amount || 0), 0);
  const billableHours = monthEntries.filter((e) => e.billable).reduce((s, e) => s + e.hours, 0);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await timeEntryApi.downloadMonthlyExport({ year, month });
      toast.success('Export downloaded');
      setShowExport(false);
    } catch (e: any) {
      toast.error(e?.message || 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div>
      {/* Toolbar */}
      <div className="flex justify-end mb-6">
        <Button
          onClick={() => setShowExport((v) => !v)}
          className="bg-slate-700 hover:bg-slate-600 text-white rounded-xl border border-slate-600"
        >
          <Download className="w-4 h-4 mr-2" /> Export Excel
        </Button>
      </div>

      {/* Export panel */}
      {showExport && (
        <div className="mb-6 p-5 rounded-2xl border border-slate-700/50 bg-slate-800/40">
          <h3 className="text-white font-semibold mb-4">Monthly Time Report</h3>
          <div className="flex flex-wrap gap-3 items-center">
            <select
              className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={year}
              onChange={(e) => setYear(parseInt(e.target.value))}
            >
              {[now.getFullYear(), now.getFullYear() - 1, now.getFullYear() - 2].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <select
              className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={month}
              onChange={(e) => setMonth(parseInt(e.target.value))}
            >
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={i + 1}>
                  {new Date(2000, i).toLocaleString('default', { month: 'long' })}
                </option>
              ))}
            </select>
            <Button onClick={handleExport} disabled={isExporting} className="bg-violet-600 hover:bg-violet-700 text-white rounded-xl">
              {isExporting ? 'Exporting…' : 'Download .xlsx'}
            </Button>
          </div>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Hours this month', value: `${totalHours.toFixed(1)}h` },
          { label: 'Billable hours',   value: `${billableHours.toFixed(1)}h` },
          { label: 'Amount logged',    value: `$${totalAmount.toFixed(2)}` },
        ].map((s) => (
          <div key={s.label} className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-4">
            <div className="text-slate-400 text-xs mb-1">{s.label}</div>
            <div className="text-2xl font-bold text-white">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Time entries */}
      {isLoading ? (
        <div className="text-slate-400 text-center py-12">Loading entries…</div>
      ) : entries.length === 0 ? (
        <div className="text-center py-24">
          <Clock className="w-16 h-16 text-slate-700 mx-auto mb-4" />
          <p className="text-slate-400">No time logged yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between bg-slate-800/40 border border-slate-700/50 rounded-xl px-4 py-3">
              <div className="flex-1 min-w-0">
                <div className="text-white text-sm font-medium truncate">
                  {entry.project_name || `Project #${entry.project_id}`}
                </div>
                <div className="text-slate-400 text-xs mt-0.5 flex items-center gap-2">
                  <span>{new Date(entry.started_at).toLocaleDateString()}</span>
                  <span>•</span>
                  <span>{entry.task_name || 'General'}</span>
                  <span>•</span>
                  <span>{entry.hours.toFixed(2)}h</span>
                  {entry.description && <><span>•</span><span className="truncate max-w-48">{entry.description}</span></>}
                </div>
              </div>
              <div className="flex items-center gap-3 ml-4">
                <span className={`text-xs px-2 py-0.5 rounded-full ${entry.billable ? 'bg-violet-900/30 text-violet-400' : 'bg-slate-700 text-slate-400'}`}>
                  {entry.billable ? 'Billable' : 'Non-billable'}
                </span>
                <span className="text-white font-semibold text-sm">${(entry.amount || 0).toFixed(2)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
