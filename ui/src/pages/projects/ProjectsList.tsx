import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, FolderKanban, Clock, DollarSign, Users, Search, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useProjects, useCreateProject, useDeleteProject } from '@/plugins/time_tracking/hooks';
import { Project } from '@/plugins/time_tracking/api';

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
  completed: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  archived: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400',
  cancelled: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

export default function ProjectsList() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('active');
  const [showNewForm, setShowNewForm] = useState(false);
  const [newProject, setNewProject] = useState({ name: '', client_id: '', billing_method: 'hourly', currency: 'USD' });

  const { data: projects = [], isLoading } = useProjects({ status: statusFilter || undefined });
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();

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
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-2">
            <FolderKanban className="w-8 h-8 text-blue-400" /> Projects
          </h1>
          <p className="text-slate-400 mt-1">Manage projects, tasks, and time tracking</p>
        </div>
        <Button
          onClick={() => setShowNewForm(true)}
          className="bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white font-semibold px-4 py-2 rounded-xl"
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
              className="col-span-1 sm:col-span-2 bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Project name *"
              value={newProject.name}
              onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
            />
            <input
              required
              type="number"
              className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Client ID *"
              value={newProject.client_id}
              onChange={(e) => setNewProject({ ...newProject, client_id: e.target.value })}
            />
            <select
              className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={newProject.billing_method}
              onChange={(e) => setNewProject({ ...newProject, billing_method: e.target.value })}
            >
              <option value="hourly">Hourly</option>
              <option value="fixed_cost">Fixed Cost</option>
            </select>

            <div className="col-span-1 sm:col-span-4 flex gap-2 justify-end">
              <Button type="button" variant="ghost" className="text-slate-400" onClick={() => setShowNewForm(false)}>Cancel</Button>
              <Button type="submit" disabled={createProject.isPending} className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl">
                {createProject.isPending ? 'Creating…' : 'Create Project'}
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            className="pl-9 bg-slate-800/50 border-slate-700 text-white placeholder-slate-500 rounded-xl"
            placeholder="Search projects…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          {['', 'active', 'completed', 'archived'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                statusFilter === s
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-700/50 border border-slate-700/50'
              }`}
            >
              {s === '' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Projects grid */}
      {isLoading ? (
        <div className="text-slate-400 text-center py-12">Loading projects…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-24">
          <FolderKanban className="w-16 h-16 text-slate-700 mx-auto mb-4" />
          <p className="text-slate-400">No projects found</p>
          <Button onClick={() => setShowNewForm(true)} className="mt-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl">
            Create your first project
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onClick={() => navigate(`/projects/${project.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project, onClick }: { project: Project; onClick: () => void }) {
  const hoursUsedPct = project.budget_hours
    ? Math.min(100, ((project.total_hours_logged || 0) / project.budget_hours) * 100)
    : null;

  return (
    <div
      onClick={onClick}
      className="cursor-pointer rounded-2xl border border-slate-700/50 bg-slate-800/40 hover:bg-slate-800/70 hover:border-blue-500/30 transition-all duration-200 p-5 group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold truncate group-hover:text-blue-300 transition-colors">
            {project.name}
          </h3>
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
          <div className="text-slate-400 mb-0.5 flex items-center gap-1">
            <Clock className="w-3 h-3" /> Hours logged
          </div>
          <div className="text-white font-semibold">{(project.total_hours_logged || 0).toFixed(1)}h</div>
        </div>
        <div className="bg-slate-700/30 rounded-lg p-2">
          <div className="text-slate-400 mb-0.5 flex items-center gap-1">
            <DollarSign className="w-3 h-3" /> Unbilled
          </div>
          <div className="text-white font-semibold">
            {project.currency} {(project.total_amount_logged || 0).toFixed(2)}
          </div>
        </div>
      </div>

      {hoursUsedPct !== null && (
        <div>
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span>Budget used</span>
            <span>{hoursUsedPct.toFixed(0)}%</span>
          </div>
          <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${hoursUsedPct >= 90 ? 'bg-red-500' : hoursUsedPct >= 70 ? 'bg-amber-500' : 'bg-emerald-500'}`}
              style={{ width: `${hoursUsedPct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
