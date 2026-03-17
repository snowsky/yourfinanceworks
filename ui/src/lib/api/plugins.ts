import { apiRequest } from './_base';

export interface InstallJob {
  job_id: string;
  git_url: string;
  ref: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  plugin_id: string | null;
  error: string | null;
  restart_required: boolean;
  steps: Array<{ label: string; status: 'pending' | 'running' | 'done' | 'failed'; detail: string | null }>;
  created_at: string;
}

// Plugin Management API
export const pluginApi = {
  getPluginConfig: (pluginId: string) => {
    return apiRequest<{ plugin_id: string; config: Record<string, any> }>(`/plugins/settings/${pluginId}/config`);
  },

  updatePluginConfig: (pluginId: string, config: Record<string, any>) => {
    return apiRequest<{ plugin_id: string; config: Record<string, any>; message: string }>(`/plugins/settings/${pluginId}/config`, {
      method: 'PUT',
      body: JSON.stringify({ config }),
    });
  },

  installFromGit: (gitUrl: string, ref: string = 'main') => {
    return apiRequest<{ job_id: string; message: string; status_url: string }>('/plugins/install', {
      method: 'POST',
      body: JSON.stringify({ git_url: gitUrl, ref }),
    });
  },

  getInstallStatus: (jobId: string) => {
    return apiRequest<InstallJob>(`/plugins/install/status/${jobId}`);
  },

  uninstallPlugin: (pluginId: string) => {
    return apiRequest<{ plugin_id: string; message: string; restart_required: boolean }>(
      `/plugins/${pluginId}/uninstall`,
      { method: 'DELETE' },
    );
  },
};
