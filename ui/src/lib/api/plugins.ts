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

  installFromGit: (gitUrl: string, ref: string = 'main', githubToken?: string) => {
    return apiRequest<{ job_id: string; message: string; status_url: string }>('/plugins/install', {
      method: 'POST',
      body: JSON.stringify({ git_url: gitUrl, ref, github_token: githubToken || undefined }),
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

  reinstallPlugin: (pluginId: string, options?: { githubToken?: string; gitUrl?: string; ref?: string }) => {
    return apiRequest<{ job_id: string; message: string; status_url: string }>(
      `/plugins/${pluginId}/reinstall`,
      {
        method: 'POST',
        body: JSON.stringify({
          github_token: options?.githubToken || undefined,
          git_url: options?.gitUrl || undefined,
          ref: options?.ref || undefined,
        }),
      },
    );
  },

  getPublicAccessConfig: (pluginId: string) =>
    apiRequest<{ plugin_id: string; enabled: boolean; require_login: boolean; stripe_price_id?: string | null; public_page: any }>(
      `/plugins/${pluginId}/public-access`,
    ),

  updatePublicAccessConfig: (pluginId: string, config: { enabled: boolean; require_login: boolean; stripe_price_id?: string | null }) =>
    apiRequest<{ plugin_id: string; enabled: boolean; require_login: boolean; stripe_price_id?: string | null; message: string }>(
      `/plugins/${pluginId}/public-access`,
      { method: 'PUT', body: JSON.stringify(config) },
    ),

  /**
   * No-auth check — used by PublicPluginWrapper to determine access mode.
   * Calls directly without Bearer token so it works for unauthenticated visitors.
   */
  getPluginPublicConfig: (pluginId: string, tenantId?: number | string) => {
    const url = tenantId != null
      ? `/api/v1/plugins/public-config/${pluginId}?tenant_id=${tenantId}`
      : `/api/v1/plugins/public-config/${pluginId}`;
    return fetch(url).then((r) => r.json()) as Promise<{
      plugin_id: string;
      enabled: boolean;
      require_login: boolean;
      public_page: { path: string; label: string; description?: string; ui_entry?: string } | null;
    }>;
  },
};
