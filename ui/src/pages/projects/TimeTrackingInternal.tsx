import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FolderKanban, Clock, Plus, Download, Search, DollarSign, Users, Activity, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useProjects, useCreateProject, useTimeEntries } from '@/plugins/time_tracking/plugin/ui/hooks';
import { timeEntryApi, Project } from '@/plugins/time_tracking/plugin/ui/api';
import { toast } from 'sonner';
import { PageHeader, ContentSection, EmptyState } from '@/components/ui/professional-layout';
import { ProfessionalCard, MetricCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { SearchableClientSelect } from '@/plugins/time_tracking/plugin/ui/components/SearchableClientSelect';

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
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      <PageHeader
        title="Time Tracking"
        description="Manage projects, tasks and your personal time log"
        actions={
          <div className="flex gap-2 p-1 bg-background/50 backdrop-blur-sm rounded-xl border border-border/50 shadow-inner">
            {TAB_OPTIONS.map(({ id, label, icon: Icon }) => (
              <Button
                key={id}
                variant={activeTab === id ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setTab(id)}
                className={cn(
                  "h-8 px-4 rounded-lg font-medium transition-all duration-200",
                  activeTab === id && "bg-white dark:bg-slate-800 shadow-sm text-primary"
                )}
              >
                <Icon className="w-4 h-4 mr-2" />
                {label}
              </Button>
            ))}
          </div>
        }
      />

      <ContentSection>
        {activeTab === 'projects' ? <ProjectsTab /> : <MyTimeTab />}
      </ContentSection>
    </div>
  );
}

// ─── Projects tab ─────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  active:    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 border-emerald-200/50',
  completed: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200/50',
  archived:  'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200/50',
  cancelled: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 border-red-200/50',
};

function ProjectsTab() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [showNewForm, setShowNewForm] = useState(false);
  const [newProject, setNewProject] = useState({ name: '', client_id: undefined as number | undefined, billing_method: 'hourly', currency: 'USD' });

  const { data: projects = [], isLoading } = useProjects({ status: statusFilter || undefined });
  const createProject = useCreateProject();

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.client_name || '').toLowerCase().includes(search.toLowerCase())
  );

  const handleCreate = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!newProject.name || !newProject.client_id) return;
    const result = await createProject.mutateAsync({
      name: newProject.name,
      client_id: newProject.client_id,
      billing_method: newProject.billing_method,
      currency: newProject.currency,
    });
    setShowNewForm(false);
    setNewProject({ name: '', client_id: undefined, billing_method: 'hourly', currency: 'USD' });
    navigate(`/projects/${result.id}`);
  };

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex flex-col lg:flex-row gap-4 items-center justify-between bg-card/50 backdrop-blur-sm p-4 rounded-2xl border border-border/50 shadow-sm">
        <div className="flex flex-1 items-center gap-3 w-full">
          <div className="relative flex-1 max-w-md group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
            <Input
              placeholder="Search projects…"
              className="pl-10 h-10 bg-background/50 border-border/50 focus-visible:ring-primary/20 focus-visible:border-primary transition-all rounded-xl"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            {(['', 'active', 'completed', 'archived'] as const).map((s) => (
              <Button
                key={s}
                variant={statusFilter === s ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setStatusFilter(s)}
                className={cn(
                  "h-8 px-3 rounded-lg font-medium transition-all duration-200",
                  statusFilter === s && "bg-white dark:bg-slate-800 shadow-sm text-primary"
                )}
              >
                {s === '' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </Button>
            ))}
          </div>
        </div>
        <ProfessionalButton
          onClick={() => setShowNewForm(true)}
          variant="gradient"
          className="shadow-lg shadow-primary/20 font-bold px-6"
        >
          <Plus className="w-4 h-4 mr-2" /> New Project
        </ProfessionalButton>
      </div>

      {/* New project form */}
      {showNewForm && (
        <ProfessionalCard variant="elevated" className="mb-6 p-6 border-l-4 border-l-primary bg-card/50 backdrop-blur-sm">
          <h3 className="font-bold text-xl tracking-tight mb-4 text-foreground">New Project</h3>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <Input
              required
              className="col-span-1 sm:col-span-2 bg-background/50 border-border/50 rounded-xl px-3 py-2 text-sm focus-visible:ring-primary/20"
              placeholder="Project name *"
              value={newProject.name}
              onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
            />
            <div className="col-span-1 sm:col-span-1">
              <SearchableClientSelect
                value={newProject.client_id}
                onChange={(id) => setNewProject({ ...newProject, client_id: id })}
                placeholder="Client *"
              />
            </div>
            <select
              className="flex h-10 w-full rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 transition-all cursor-pointer"
              value={newProject.billing_method}
              onChange={(e) => setNewProject({ ...newProject, billing_method: e.target.value })}
            >
              <option value="hourly">Hourly</option>
              <option value="fixed_cost">Fixed Cost</option>
            </select>
            <div className="col-span-1 sm:col-span-4 flex gap-2 justify-end mt-2">
              <ProfessionalButton type="button" variant="ghost" onClick={() => setShowNewForm(false)}>Cancel</ProfessionalButton>
              <ProfessionalButton type="submit" loading={createProject.isPending} variant="default">
                Create Project
              </ProfessionalButton>
            </div>
          </form>
        </ProfessionalCard>
      )}

      {/* Projects grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 rounded-2xl bg-muted/50 animate-pulse border border-border/50 shadow-sm"></div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No projects found"
          description={search ? "No projects match your current search criteria." : "It looks like you haven't created any projects yet."}
          icon={<FolderKanban className="w-12 h-12" />}
          action={
            <Button variant="default" onClick={() => setShowNewForm(true)}>
              <Plus className="w-4 h-4 mr-2" /> Create First Project
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((project) => (
            <ProjectCardUI key={project.id} project={project} onClick={() => navigate(`/projects/${project.id}`)} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCardUI({ project, onClick }: { project: Project; onClick: () => void }) {
  const pct = project.budget_hours
    ? Math.min(100, ((project.total_hours_logged || 0) / project.budget_hours) * 100)
    : null;

  return (
    <ProfessionalCard
      variant="elevated"
      interactive
      onClick={onClick}
      className="group relative overflow-hidden border-border/40 hover:border-primary/30 p-6"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
             <div className="p-1.5 rounded-lg bg-primary/5 text-primary group-hover:bg-primary group-hover:text-white transition-all duration-300 shadow-sm border border-primary/10">
                <FolderKanban className="w-4 h-4" />
             </div>
             <h3 className="text-lg font-bold group-hover:text-primary transition-colors line-clamp-1">{project.name}</h3>
          </div>
          <p className="text-muted-foreground text-xs mt-0.5 flex items-center gap-1.5 ml-8">
            <Users className="w-3 h-3 opacity-60" /> {project.client_name || `Client #${project.client_id}`}
          </p>
        </div>
        <Badge variant="outline" className={cn("px-2.5 py-0.5 rounded-full border border-border/50 font-medium whitespace-nowrap", STATUS_COLORS[project.status] || STATUS_COLORS.active)}>
          {project.status}
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs mb-4">
        <div className="bg-muted/30 rounded-xl p-3 border border-border/10">
          <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 font-medium uppercase tracking-wider text-[10px]">
            <Clock className="w-3 h-3" /> Hours logged
          </div>
          <div className="text-lg font-bold tracking-tight">{(project.total_hours_logged || 0).toFixed(1)}h</div>
        </div>
        <div className="bg-muted/30 rounded-xl p-3 border border-border/10">
          <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 font-medium uppercase tracking-wider text-[10px]">
            <DollarSign className="w-3 h-3" /> Unbilled
          </div>
          <div className="text-lg font-bold tracking-tight">{project.currency} {(project.total_amount_logged || 0).toFixed(2)}</div>
        </div>
      </div>

      {pct !== null && (
        <div className="mt-4">
          <div className="flex justify-between text-[11px] font-semibold text-muted-foreground mb-1.5 uppercase tracking-wider">
            <span>Budget used</span>
            <span>{pct.toFixed(0)}%</span>
          </div>
          <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden shadow-inner">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                pct >= 90 ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.4)]' : 
                pct >= 70 ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]' : 
                'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]'
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      <div className="mt-6 pt-4 border-t border-border/30">
        <ProfessionalButton
          variant="outline"
          className="w-full rounded-xl font-bold shadow-sm border-secondary/30 text-secondary hover:bg-secondary/5 group-hover:bg-primary group-hover:text-white group-hover:border-primary transition-all duration-300"
        >
          View Details
        </ProfessionalButton>
      </div>
    </ProfessionalCard>
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
    return d.getFullYear() === year && d.getMonth() === month - 1;
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
    <div className="space-y-8">
      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard
          title="Hours this month"
          value={`${totalHours.toFixed(1)}h`}
          icon={Clock}
          description="Total hours logged current month"
        />
        <MetricCard
          title="Billable hours"
          value={`${billableHours.toFixed(1)}h`}
          icon={Activity}
          description="Hours logged to billable tasks"
          variant="success"
        />
        <MetricCard
          title="Amount logged"
          value={`$${totalAmount.toFixed(2)}`}
          icon={DollarSign}
          description="Estimated revenue from logged time"
          variant="success"
        />
      </div>

      {/* Toolbar */}
      <div className="flex justify-end bg-card/50 backdrop-blur-sm p-4 rounded-2xl border border-border/50 shadow-sm uppercase tracking-wider text-[10px] font-bold">
        <ProfessionalButton
          onClick={() => setShowExport((v) => !v)}
          variant="outline"
          className="rounded-xl border-border/50 bg-background/50 backdrop-blur-sm hover:bg-background transition-colors"
        >
          <Download className="w-4 h-4 mr-2" /> Export Excel
        </ProfessionalButton>
      </div>

      {/* Export panel */}
      {showExport && (
        <ProfessionalCard variant="elevated" className="p-6 border-l-4 border-l-primary overflow-hidden bg-card/50 backdrop-blur-sm">
          <h3 className="font-bold text-xl tracking-tight mb-4">Monthly Time Report</h3>
          <div className="flex flex-wrap gap-4 items-center">
            <select
              className="flex h-10 rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 transition-all cursor-pointer"
              value={year}
              onChange={(e) => setYear(parseInt(e.target.value))}
            >
              {[now.getFullYear(), now.getFullYear() - 1, now.getFullYear() - 2].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <select
              className="flex h-10 rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 transition-all cursor-pointer"
              value={month}
              onChange={(e) => setMonth(parseInt(e.target.value))}
            >
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={i + 1}>
                  {new Date(2000, i).toLocaleString('default', { month: 'long' })}
                </option>
              ))}
            </select>
            <ProfessionalButton onClick={handleExport} loading={isExporting} variant="default" className="shadow-lg shadow-primary/20">
              Download .xlsx
            </ProfessionalButton>
          </div>
        </ProfessionalCard>
      )}

      {/* Time entries */}
      <div className="space-y-4">
        <h2 className="text-2xl font-bold tracking-tight">Recent Activity</h2>
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 rounded-xl bg-muted/50 animate-pulse border border-border/50"></div>
            ))}
          </div>
        ) : entries.length === 0 ? (
          <EmptyState
            title="No time logged yet"
            description="Your recent time logs will appear here once you start tracking time."
            icon={<Clock className="w-12 h-12" />}
          />
        ) : (
          <div className="space-y-3">
            {entries.map((entry) => (
              <ProfessionalCard key={entry.id} className="p-4 bg-card/50 border border-border/50 hover:border-primary/20 transition-all hover:shadow-md group">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="p-2 rounded-xl bg-primary/5 text-primary group-hover:bg-primary group-hover:text-white transition-colors border border-primary/10">
                      <Clock className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-foreground font-bold text-sm tracking-tight truncate">
                        {entry.project_name || `Project #${entry.project_id}`}
                      </div>
                      <div className="text-muted-foreground text-[10px] sm:text-xs mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 font-medium">
                        <span className="flex items-center gap-1"><Calendar className="w-3 h-3 opacity-60" /> {new Date(entry.started_at).toLocaleDateString()}</span>
                        <span className="opacity-30">•</span>
                        <span>{entry.task_name || 'General'}</span>
                        <span className="opacity-30">•</span>
                        <span className="font-bold text-foreground/80">{entry.hours.toFixed(2)}h</span>
                        {entry.description && (
                          <>
                            <span className="opacity-30">•</span>
                            <span className="truncate max-w-48 text-muted-foreground/60 italic">"{entry.description}"</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 ml-4">
                    <Badge variant="outline" className={cn("text-[10px] px-2 py-0.5 rounded-full", entry.billable ? 'bg-primary/10 text-primary border-primary/20' : 'bg-muted/50 text-muted-foreground')}>
                      {entry.billable ? 'Billable' : 'Non-billable'}
                    </Badge>
                    <div className="text-foreground font-bold text-sm bg-muted/30 px-3 py-1.5 rounded-xl border border-border/10">
                      ${(entry.amount || 0).toFixed(2)}
                    </div>
                  </div>
                </div>
              </ProfessionalCard>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


