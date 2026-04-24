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
    apiRequest<{ 
      plugin_id: string; 
      enabled: boolean; 
      require_login: boolean; 
      stripe_price_id?: string | null; 
      free_clicks: number;
      show_sidebar: boolean;
      show_header: boolean;
      manual_usage_tracking: boolean;
      service_user_email?: string | null;
      public_page: any 
    }>(
      `/plugins/${pluginId}/public-access`,
    ),

  updatePublicAccessConfig: (pluginId: string, config: { 
    enabled: boolean; 
    require_login: boolean; 
    stripe_price_id?: string | null;
    free_clicks: number;
    show_sidebar: boolean;
    show_header: boolean;
    manual_usage_tracking: boolean;
    service_user_email?: string | null;
  }) =>
    apiRequest<{ 
      plugin_id: string; 
      enabled: boolean; 
      require_login: boolean; 
      stripe_price_id?: string | null; 
      message: string 
    }>(
      `/plugins/${pluginId}/public-access`,
      { method: 'PUT', body: JSON.stringify(config) },
    ),

  // ---------------------------------------------------------------------------
  // Super-admin plugin access management
  // ---------------------------------------------------------------------------

  /** List all plugin grants across all tenants (super admin only). */
  listAllPluginAccess: () =>
    apiRequest<{ grants: Array<{ id: number; plugin_id: string; tenant_id: number; tenant_name: string | null; granted_by_id: number; granted_at: string }> }>(
      '/plugins/admin/access',
    ),

  /** List plugins granted to a specific tenant (super admin only). */
  getTenantPluginAccess: (tenantId: number) =>
    apiRequest<{ tenant_id: number; allowed_plugins: string[] }>(
      `/plugins/admin/tenants/${tenantId}/access`,
    ),

  /** Get plugin config for an explicit tenant (super admin only). */
  getAdminTenantPluginConfig: (tenantId: number, pluginId: string) =>
    apiRequest<{ tenant_id: number; plugin_id: string; config: Record<string, any> }>(
      `/plugins/admin/tenants/${tenantId}/settings/${pluginId}/config`,
    ),

  /** Update plugin config for an explicit tenant (super admin only). */
  updateAdminTenantPluginConfig: (tenantId: number, pluginId: string, config: Record<string, any>) =>
    apiRequest<{ tenant_id: number; plugin_id: string; config: Record<string, any>; message: string }>(
      `/plugins/admin/tenants/${tenantId}/settings/${pluginId}/config`,
      { method: 'PUT', body: JSON.stringify({ config }) },
    ),

  /** Grant a plugin to a tenant (super admin only). */
  grantPluginAccess: (tenantId: number, pluginId: string) =>
    apiRequest<{ message: string; plugin_id: string; tenant_id: number; granted_at: string }>(
      `/plugins/admin/tenants/${tenantId}/access`,
      { method: 'POST', body: JSON.stringify({ plugin_id: pluginId }) },
    ),

  /** Revoke a plugin grant from a tenant (super admin only). */
  revokePluginAccess: (tenantId: number, pluginId: string) =>
    apiRequest<{ message: string }>(
      `/plugins/admin/tenants/${tenantId}/access/${pluginId}`,
      { method: 'DELETE' },
    ),

  /** List tenants that have access to a plugin (super admin only). */
  getPluginTenantAccess: (pluginId: string) =>
    apiRequest<{ plugin_id: string; tenants: Array<{ tenant_id: number; tenant_name: string | null }> }>(
      `/plugins/admin/plugins/${pluginId}/tenants`,
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
      show_sidebar: boolean;
      show_header: boolean;
      manual_usage_tracking: boolean;
      service_user_email: string | null;
      public_page: { path: string; label: string; description?: string; ui_entry?: string } | null;
    }>;
  },
};
