import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Archive, CheckCircle2, FolderKanban, Clock, Plus, Download, Search, DollarSign, Users, Activity, Calendar, Upload, Sparkles, Grid3X3, List } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useProjects, useCreateProject, useImportTimeEntriesCsv, useTimeEntries, useUpdateProject } from '@/plugins/time_tracking/plugin/ui/hooks';
import { projectApi, timeEntryApi } from '@/plugins/time_tracking/plugin/ui/api';
import type { Project, MissingProjectStrategy } from '@/plugins/time_tracking/plugin/ui/api';
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

type CsvPreview = {
  headers: string[];
  rows: string[][];
};

function parseCsvPreview(text: string, maxRows = 5): CsvPreview {
  const source = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  const parsedRows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let inQuotes = false;

  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    const next = source[index + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      row.push(cell);
      cell = '';
    } else if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') {
        index += 1;
      }
      row.push(cell);
      parsedRows.push(row);
      if (parsedRows.length > maxRows) break;
      row = [];
      cell = '';
    } else {
      cell += char;
    }
  }

  if (parsedRows.length <= maxRows && (cell || row.length)) {
    row.push(cell);
    parsedRows.push(row);
  }

  const [headers = [], ...rows] = parsedRows;
  return { headers, rows: rows.slice(0, maxRows) };
}

function guessTaskNameColumn(headers: string[]): string {
  const aliases = new Set(['task', 'task name', 'task_name', 'activity', 'service']);
  return headers.find((header) => aliases.has(header.trim().toLowerCase())) || '';
}

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
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [viewMode, setViewMode] = useState<'cards' | 'list'>('cards');
  const [selectedProjectIds, setSelectedProjectIds] = useState<number[]>([]);
  const [bulkUpdating, setBulkUpdating] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newProject, setNewProject] = useState({ name: '', client_id: undefined as number | undefined, billing_method: 'hourly', hourly_rate: '', currency: 'USD' });

  const { data: projects = [], isLoading } = useProjects({ status: statusFilter || undefined });
  const createProject = useCreateProject();

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.client_name || '').toLowerCase().includes(search.toLowerCase())
  );
  const selectableProjectIds = filtered.map((project) => project.id);
  const selectedVisibleIds = selectedProjectIds.filter((id) => selectableProjectIds.includes(id));
  const allVisibleSelected = selectableProjectIds.length > 0 && selectedVisibleIds.length === selectableProjectIds.length;

  const toggleProjectSelection = (projectId: number) => {
    setSelectedProjectIds((prev) =>
      prev.includes(projectId) ? prev.filter((id) => id !== projectId) : [...prev, projectId]
    );
  };

  const toggleVisibleSelection = () => {
    setSelectedProjectIds((prev) => {
      if (allVisibleSelected) {
        return prev.filter((id) => !selectableProjectIds.includes(id));
      }
      return Array.from(new Set([...prev, ...selectableProjectIds]));
    });
  };

  const handleBulkStatus = async (status: 'active' | 'completed' | 'archived') => {
    const ids = selectedProjectIds.filter((id) => selectableProjectIds.includes(id));
    if (!ids.length) return;

    setBulkUpdating(true);
    try {
      await Promise.all(ids.map((projectId) => projectApi.update(projectId, { status })));
      const verb = status === 'active' ? 'reopened' : status === 'completed' ? 'closed' : 'archived';
      toast.success(`${ids.length} project${ids.length === 1 ? '' : 's'} ${verb}`);
      setSelectedProjectIds((prev) => prev.filter((id) => !ids.includes(id)));
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['project-summary'] });
      queryClient.invalidateQueries({ queryKey: ['project-unbilled'] });
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Failed to update selected projects');
    } finally {
      setBulkUpdating(false);
    }
  };

  const handleCreate = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!newProject.name || !newProject.client_id) return;
    const result = await createProject.mutateAsync({
      name: newProject.name,
      client_id: newProject.client_id,
      billing_method: newProject.billing_method,
      hourly_rate: newProject.hourly_rate ? parseFloat(newProject.hourly_rate) : undefined,
      currency: newProject.currency,
    });
    setShowNewForm(false);
    setNewProject({ name: '', client_id: undefined, billing_method: 'hourly', hourly_rate: '', currency: 'USD' });
    navigate(`/projects/${result.id}`);
  };

  const emptyCopy = search
    ? {
        title: 'No projects found',
        description: 'No projects match your current search criteria.',
        action: undefined,
      }
    : statusFilter === 'completed'
      ? {
          title: 'No completed projects',
          description: 'Active projects will appear here after you mark them complete.',
          action: undefined,
        }
      : statusFilter === 'archived'
        ? {
            title: 'No archived projects',
            description: 'Archived projects will appear here when you archive them from a project card or detail page.',
            action: undefined,
          }
        : {
            title: 'No projects found',
            description: "It looks like you haven't created any projects yet.",
            action: (
              <Button variant="default" onClick={() => setShowNewForm(true)}>
                <Plus className="w-4 h-4 mr-2" /> Create First Project
              </Button>
            ),
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
          <div className="flex gap-1 p-1 rounded-xl border border-border/50 bg-background/50 shadow-inner">
            <Button
              variant={viewMode === 'cards' ? 'secondary' : 'ghost'}
              size="icon"
              className={cn("h-8 w-8 rounded-lg", viewMode === 'cards' && "bg-white dark:bg-slate-800 shadow-sm text-primary")}
              onClick={() => setViewMode('cards')}
              title="Card view"
            >
              <Grid3X3 className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'secondary' : 'ghost'}
              size="icon"
              className={cn("h-8 w-8 rounded-lg", viewMode === 'list' && "bg-white dark:bg-slate-800 shadow-sm text-primary")}
              onClick={() => setViewMode('list')}
              title="List view"
            >
              <List className="h-4 w-4" />
            </Button>
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
            <Input
              type="number"
              step="0.01"
              min="0"
              className="col-span-1 sm:col-span-2 bg-background/50 border-border/50 rounded-xl px-3 py-2 text-sm focus-visible:ring-primary/20"
              placeholder="Project hourly rate"
              value={newProject.hourly_rate}
              onChange={(e) => setNewProject({ ...newProject, hourly_rate: e.target.value })}
            />
            <div className="col-span-1 sm:col-span-4 flex gap-2 justify-end mt-2">
              <ProfessionalButton type="button" variant="ghost" onClick={() => setShowNewForm(false)}>Cancel</ProfessionalButton>
              <ProfessionalButton type="submit" loading={createProject.isPending} variant="default">
                Create Project
              </ProfessionalButton>
            </div>
          </form>
        </ProfessionalCard>
      )}

      {filtered.length > 0 && (
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between rounded-2xl border border-border/50 bg-card/40 p-3 shadow-sm">
          <label className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border"
              checked={allVisibleSelected}
              onChange={toggleVisibleSelection}
            />
            <span>{selectedVisibleIds.length ? `${selectedVisibleIds.length} selected` : 'Select visible projects'}</span>
          </label>
          <div className="flex gap-2">
            <ProfessionalButton
              variant="outline"
              size="sm"
              disabled={selectedVisibleIds.length === 0 || bulkUpdating}
              loading={bulkUpdating}
              onClick={() => handleBulkStatus('active')}
            >
              Reopen Selected
            </ProfessionalButton>
            <ProfessionalButton
              variant="outline"
              size="sm"
              disabled={selectedVisibleIds.length === 0 || bulkUpdating}
              loading={bulkUpdating}
              onClick={() => handleBulkStatus('completed')}
              leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
            >
              Close Selected
            </ProfessionalButton>
            <ProfessionalButton
              variant="ghost"
              size="sm"
              disabled={selectedVisibleIds.length === 0 || bulkUpdating}
              loading={bulkUpdating}
              onClick={() => handleBulkStatus('archived')}
              leftIcon={<Archive className="w-3.5 h-3.5" />}
            >
              Archive Selected
            </ProfessionalButton>
          </div>
        </div>
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
          title={emptyCopy.title}
          description={emptyCopy.description}
          icon={<FolderKanban className="w-12 h-12" />}
          action={emptyCopy.action}
        />
      ) : (
        viewMode === 'cards' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filtered.map((project) => (
              <ProjectCardUI
                key={project.id}
                project={project}
                selected={selectedProjectIds.includes(project.id)}
                onSelect={() => toggleProjectSelection(project.id)}
                onClick={() => navigate(`/projects/${project.id}`)}
              />
            ))}
          </div>
        ) : (
          <ProjectListUI
            projects={filtered}
            selectedIds={selectedProjectIds}
            onToggleSelection={toggleProjectSelection}
            onOpen={(projectId) => navigate(`/projects/${projectId}`)}
          />
        )
      )}
    </div>
  );
}

function ProjectStatusActions({ project, compact = false }: { project: Project; compact?: boolean }) {
  const updateProject = useUpdateProject(project.id);

  if (project.status !== 'active') {
    return (
      <ProfessionalButton
        variant="outline"
        size="sm"
        className={cn("rounded-xl", compact && "h-7 px-2 text-[11px]")}
        onClick={(e) => {
          e.stopPropagation();
          updateProject.mutate({ status: 'active' });
        }}
      >
        Reopen
      </ProfessionalButton>
    );
  }

  return (
    <>
      <ProfessionalButton
        variant="outline"
        size="sm"
        className={cn("rounded-xl", compact && "h-7 px-2 text-[11px]")}
        onClick={(e) => {
          e.stopPropagation();
          updateProject.mutate({ status: 'completed' });
        }}
        leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
      >
        Complete
      </ProfessionalButton>
      <ProfessionalButton
        variant="ghost"
        size="sm"
        className={cn("rounded-xl", compact && "h-7 px-2 text-[11px]")}
        onClick={(e) => {
          e.stopPropagation();
          updateProject.mutate({ status: 'archived' });
        }}
        leftIcon={<Archive className="w-3.5 h-3.5" />}
      >
        Archive
      </ProfessionalButton>
    </>
  );
}

function ProjectListUI({
  projects,
  selectedIds,
  onToggleSelection,
  onOpen,
}: {
  projects: Project[];
  selectedIds: number[];
  onToggleSelection: (projectId: number) => void;
  onOpen: (projectId: number) => void;
}) {
  return (
    <div className="space-y-2">
      {projects.map((project) => (
        <ProfessionalCard
          key={project.id}
          interactive
          onClick={() => onOpen(project.id)}
          className="p-4 bg-card/50 border border-border/50 hover:border-primary/20 transition-all"
        >
          <div className="grid grid-cols-1 lg:grid-cols-[auto_minmax(0,1.5fr)_1fr_0.8fr_auto] gap-4 items-center">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border"
              checked={selectedIds.includes(project.id)}
              onClick={(e) => e.stopPropagation()}
              onChange={() => onToggleSelection(project.id)}
            />
            <div className="min-w-0">
              <div className="flex items-center gap-2 min-w-0">
                <FolderKanban className="h-4 w-4 text-primary shrink-0" />
                <h3 className="font-bold text-sm truncate">{project.name}</h3>
                <Badge variant="outline" className={cn("px-2 py-0.5 rounded-full border border-border/50 text-[10px] font-medium whitespace-nowrap", STATUS_COLORS[project.status] || STATUS_COLORS.active)}>
                  {project.status}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1.5">
                <Users className="w-3 h-3 opacity-60" />
                <span className="truncate">{project.client_name || `Client #${project.client_id}`}</span>
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <div className="text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">Hours</div>
                <div className="font-bold">{(project.total_hours_logged || 0).toFixed(1)}h</div>
              </div>
              <div>
                <div className="text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">Unbilled</div>
                <div className="font-bold">{project.currency} {(project.total_amount_logged || 0).toFixed(2)}</div>
              </div>
            </div>

            <div className="text-xs">
              <div className="text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">Rate</div>
              <div className="font-bold">{project.hourly_rate != null ? `${project.currency} ${project.hourly_rate}/hr` : 'Not set'}</div>
            </div>

            <div className="flex justify-end gap-2">
              <ProjectStatusActions project={project} compact />
            </div>
          </div>
        </ProfessionalCard>
      ))}
    </div>
  );
}

function ProjectCardUI({
  project,
  selected,
  onSelect,
  onClick,
}: {
  project: Project;
  selected: boolean;
  onSelect: () => void;
  onClick: () => void;
}) {
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
      <input
        type="checkbox"
        className="absolute right-4 top-4 z-10 h-4 w-4 rounded border-border"
        checked={selected}
        onClick={(e) => e.stopPropagation()}
        onChange={onSelect}
      />
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
        <div className="grid grid-cols-2 gap-2">
          {project.status === 'active' ? (
            <ProjectStatusActions project={project} />
          ) : (
            <div className="col-span-2">
              <ProjectStatusActions project={project} />
            </div>
          )}
        </div>
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
  const [showImport, setShowImport] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [useAiImport, setUseAiImport] = useState(true);
  const [missingProjectStrategy, setMissingProjectStrategy] = useState<MissingProjectStrategy>('error');
  const [fallbackProjectName, setFallbackProjectName] = useState('');
  const [fallbackProjectId, setFallbackProjectId] = useState('');
  const [csvPreview, setCsvPreview] = useState<CsvPreview | null>(null);
  const [csvPreviewError, setCsvPreviewError] = useState('');
  const [taskNameColumn, setTaskNameColumn] = useState('');
  const [importErrors, setImportErrors] = useState<Array<{ row: number; message: string }>>([]);

  const { data: entries = [], isLoading } = useTimeEntries({ limit: 200 });
  const { data: projects = [] } = useProjects({ status: 'active' });
  const importCsv = useImportTimeEntriesCsv();

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
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const handleImport = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!importFile) {
      toast.error('Choose a CSV file first');
      return;
    }
    if (missingProjectStrategy === 'existing_project' && !fallbackProjectId) {
      toast.error('Choose an existing project for unrecognized rows');
      return;
    }
    if (!taskNameColumn) {
      toast.error('Choose which CSV column should be used for task names');
      return;
    }
    setImportErrors([]);
    try {
      const result = await importCsv.mutateAsync({
        file: importFile,
        useAi: useAiImport,
        missingProjectStrategy,
        fallbackProjectName,
        fallbackProjectId: fallbackProjectId ? Number(fallbackProjectId) : undefined,
        taskNameColumn,
      });
      setImportErrors(result.errors);
      if (result.errors.length) {
        toast.warning(`${result.errors.length} row${result.errors.length === 1 ? '' : 's'} could not be imported`);
      }
      setImportFile(null);
      setShowImport(false);
    } catch (error: unknown) {
      const detail = (error as { response?: { data?: { detail?: { errors?: Array<{ row: number; message: string }> } } } })?.response?.data?.detail;
      if (detail?.errors?.length) {
        setImportErrors(detail.errors);
      }
    }
  };

  const loadCsvPreview = async (file: File | null) => {
    setCsvPreview(null);
    setCsvPreviewError('');
    setTaskNameColumn('');

    if (!file) return;

    try {
      const preview = parseCsvPreview(await file.text());
      if (!preview.headers.length) {
        setCsvPreviewError('CSV header row could not be read');
        return;
      }
      setCsvPreview(preview);
      setTaskNameColumn(guessTaskNameColumn(preview.headers));
    } catch (error: unknown) {
      setCsvPreviewError(error instanceof Error ? error.message : 'CSV preview failed');
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
      <div className="flex justify-end gap-2 bg-card/50 backdrop-blur-sm p-4 rounded-2xl border border-border/50 shadow-sm uppercase tracking-wider text-[10px] font-bold">
        <ProfessionalButton
          onClick={() => setShowImport((v) => !v)}
          variant="outline"
          className="rounded-xl border-border/50 bg-background/50 backdrop-blur-sm hover:bg-background transition-colors"
        >
          <Upload className="w-4 h-4 mr-2" /> Import CSV
        </ProfessionalButton>
        <ProfessionalButton
          onClick={() => setShowExport((v) => !v)}
          variant="outline"
          className="rounded-xl border-border/50 bg-background/50 backdrop-blur-sm hover:bg-background transition-colors"
        >
          <Download className="w-4 h-4 mr-2" /> Export Excel
        </ProfessionalButton>
      </div>

      {/* Import panel */}
      {showImport && (
        <ProfessionalCard variant="elevated" className="p-6 border-l-4 border-l-primary overflow-hidden bg-card/50 backdrop-blur-sm">
          <h3 className="font-bold text-xl tracking-tight mb-4">Import Time CSV</h3>
          <form onSubmit={handleImport} className="space-y-4">
            <Input
              type="file"
              accept=".csv,text/csv"
              className="bg-background/50 border-border/50 rounded-xl"
              onChange={(e) => {
                const file = e.target.files?.[0] || null;
                setImportFile(file);
                if (file && !fallbackProjectName.trim()) {
                  setFallbackProjectName(file.name.replace(/\.csv$/i, ''));
                }
                setImportErrors([]);
                void loadCsvPreview(file);
              }}
            />
            {(csvPreview || csvPreviewError) && (
              <div className="grid gap-3 rounded-xl border border-border/50 bg-background/40 p-4">
                <div className="text-sm font-medium text-foreground">Task name column</div>
                {csvPreviewError ? (
                  <div className="text-sm text-red-600 dark:text-red-300">{csvPreviewError}</div>
                ) : csvPreview ? (
                  <div className="overflow-x-auto rounded-lg border border-border/50">
                    <table className="min-w-full text-left text-xs">
                      <thead className="bg-muted/40">
                        <tr>
                          {csvPreview.headers.map((header, index) => {
                            const selected = taskNameColumn === header;
                            return (
                              <th key={`${header}-${index}`} className="whitespace-nowrap border-r border-border/40 p-2 last:border-r-0">
                                <button
                                  type="button"
                                  onClick={() => setTaskNameColumn(header)}
                                  className={cn(
                                    'rounded-md border px-2 py-1 text-left transition-colors',
                                    selected
                                      ? 'border-primary bg-primary text-primary-foreground'
                                      : 'border-border/50 bg-background/60 hover:border-primary/60'
                                  )}
                                >
                                  {header || `Column ${index + 1}`}
                                </button>
                              </th>
                            );
                          })}
                        </tr>
                      </thead>
                      <tbody>
                        {csvPreview.rows.map((row, rowIndex) => (
                          <tr key={rowIndex} className="border-t border-border/40">
                            {csvPreview.headers.map((header, columnIndex) => {
                              const selected = taskNameColumn === header;
                              return (
                                <td
                                  key={`${rowIndex}-${header}-${columnIndex}`}
                                  className={cn(
                                    'max-w-[220px] truncate border-r border-border/40 p-2 last:border-r-0',
                                    selected && 'bg-primary/10 text-primary'
                                  )}
                                  title={row[columnIndex] || ''}
                                >
                                  {row[columnIndex] || ''}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            )}
            <label className="flex items-center gap-3 text-sm text-muted-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={useAiImport}
                onChange={(e) => setUseAiImport(e.target.checked)}
              />
              <span className="flex items-center gap-1.5">
                <Sparkles className="h-4 w-4 text-primary" />
                Use AI to normalize unusual columns when available
              </span>
            </label>
            <div className="grid gap-3 rounded-xl border border-border/50 bg-background/40 p-4">
              <label className="grid gap-1.5 text-sm">
                <span className="font-medium text-foreground">Project handling</span>
                <select
                  className="flex h-10 rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 transition-all"
                  value={missingProjectStrategy}
                  onChange={(e) => setMissingProjectStrategy(e.target.value as MissingProjectStrategy)}
                >
                  <option value="error">Use projects from CSV; skip missing rows</option>
                  <option value="existing_project">Merge all rows into an existing project</option>
                  <option value="single_project">Create one new project for the import</option>
                  <option value="row_project">Create each row as its own project</option>
                </select>
              </label>
              {missingProjectStrategy === 'existing_project' && (
                <select
                  className="flex h-10 rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 transition-all"
                  value={fallbackProjectId}
                  onChange={(e) => setFallbackProjectId(e.target.value)}
                  required
                >
                  <option value="">Choose project</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              )}
              {missingProjectStrategy === 'single_project' && (
                <Input
                  value={fallbackProjectName}
                  onChange={(e) => setFallbackProjectName(e.target.value)}
                  placeholder="Project name"
                  className="bg-background/50 border-border/50 rounded-xl"
                />
              )}
            </div>
            <div className="flex justify-end">
              <ProfessionalButton type="submit" loading={importCsv.isPending} disabled={!importFile || !taskNameColumn} variant="default">
                Import entries
              </ProfessionalButton>
            </div>
            {importErrors.length > 0 && (
              <div className="rounded-xl border border-red-200/60 bg-red-50/70 p-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300">
                <div className="font-semibold mb-2">Rows that could not be imported</div>
                <ul className="space-y-1">
                  {importErrors.slice(0, 6).map((error) => (
                    <li key={`${error.row}-${error.message}`}>
                      Row {error.row}: {error.message}
                    </li>
                  ))}
                </ul>
                {importErrors.length > 6 && (
                  <div className="mt-2 text-xs opacity-80">
                    {importErrors.length - 6} more row errors hidden
                  </div>
                )}
              </div>
            )}
          </form>
        </ProfessionalCard>
      )}

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
