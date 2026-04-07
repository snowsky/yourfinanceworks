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

export interface PluginBillingConfig {
  plugin_id: string;
  enabled: boolean;
  provider: string;
  free_endpoint_calls: number;
  usage_count: number;
  usage_by_endpoint: Record<string, number>;
  checkout_url?: string | null;
  stripe_price_id?: string | null;
  price_label?: string | null;
  title?: string | null;
  description?: string | null;
  button_label?: string | null;
  payment_completed: boolean;
  payment_required: boolean;
  payment_configured: boolean;
  remaining_free_calls?: number | null;
  message?: string;
}

export interface PublicPluginConfig {
  plugin_id: string;
  enabled: boolean;
  require_login: boolean;
  public_page: { path: string; label: string; description?: string; ui_entry?: string } | null;
  billing: PluginBillingConfig;
  organization?: {
    id: number;
    name: string;
    logo_url?: string | null;
  };
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
    apiRequest<{ plugin_id: string; enabled: boolean; require_login: boolean; public_page: any }>(
      `/plugins/${pluginId}/public-access`,
    ),

  updatePublicAccessConfig: (pluginId: string, config: { enabled: boolean; require_login: boolean }) =>
    apiRequest<{ plugin_id: string; enabled: boolean; require_login: boolean; message: string }>(
      `/plugins/${pluginId}/public-access`,
      { method: 'PUT', body: JSON.stringify(config) },
    ),

  getBillingConfig: (pluginId: string) =>
    apiRequest<PluginBillingConfig>(`/plugins/${pluginId}/billing-config`),

  updateBillingConfig: (
    pluginId: string,
    config: Partial<PluginBillingConfig> & {
      enabled: boolean;
      provider: string;
      free_endpoint_calls: number;
      checkout_url?: string;
      price_label?: string;
      title?: string;
      description?: string;
      button_label?: string;
      payment_completed?: boolean;
      usage_count?: number;
      usage_by_endpoint?: Record<string, number>;
    },
  ) =>
    apiRequest<PluginBillingConfig>(`/plugins/${pluginId}/billing-config`, {
      method: 'PUT',
      body: JSON.stringify(config),
    }),

  /**
   * No-auth check — used by PublicPluginWrapper to determine access mode.
   * Calls directly without Bearer token so it works for unauthenticated visitors.
   */
  getPluginPublicConfig: (pluginId: string, tenantId?: number | string) => {
    const url = tenantId != null
      ? `/api/v1/plugins/public-config/${pluginId}?tenant_id=${tenantId}`
      : `/api/v1/plugins/public-config/${pluginId}`;
    return fetch(url).then((r) => r.json()) as Promise<PublicPluginConfig>;
  },

  recordPublicUsage: (
    pluginId: string,
    payload: { tenantId?: number | string; endpointKey?: string; quantity?: number } = {},
  ) => {
    const tenantSuffix = payload.tenantId != null
      ? `?tenant_id=${encodeURIComponent(String(payload.tenantId))}`
      : '';

    return fetch(`/api/v1/plugins/public-usage/${pluginId}${tenantSuffix}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        endpoint_key: payload.endpointKey,
        quantity: payload.quantity,
      }),
    }).then((r) => r.json()) as Promise<PluginBillingConfig>;
  },

  createPublicCheckoutSession: (
    pluginId: string,
    payload: { tenantId?: number | string; currentUrl?: string } = {},
  ) => {
    const tenantSuffix = payload.tenantId != null
      ? `?tenant_id=${encodeURIComponent(String(payload.tenantId))}`
      : '';

    return fetch(`/api/v1/plugins/public-checkout/${pluginId}${tenantSuffix}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        current_url: payload.currentUrl,
      }),
    }).then(async (r) => {
      const data = await r.json();
      if (!r.ok) {
        throw new Error(data?.detail || `Checkout failed with status ${r.status}`);
      }
      return data;
    }) as Promise<{
      plugin_id: string;
      tenant_id: number;
      checkout_url?: string | null;
      session_id?: string | null;
    }>;
  },

  getPublicCheckoutStatus: (
    pluginId: string,
    payload: { tenantId?: number | string; sessionId: string },
  ) => {
    const params = new URLSearchParams();
    params.set('session_id', payload.sessionId);
    if (payload.tenantId != null) {
      params.set('tenant_id', String(payload.tenantId));
    }

    return fetch(`/api/v1/plugins/public-checkout-status/${pluginId}?${params.toString()}`, {
      credentials: 'include',
    }).then(async (r) => {
      const data = await r.json();
      if (!r.ok) {
        throw new Error(data?.detail || `Checkout status failed with status ${r.status}`);
      }
      return data;
    }) as Promise<{
      plugin_id: string;
      tenant_id: number;
      session_id: string;
      checkout_status?: string | null;
      payment_status?: string | null;
      subscription_status?: string | null;
      payment_completed: boolean;
    }>;
  },

  getPublicTransactions: (
    pluginId: string,
    payload: { tenantId?: number | string; limit?: number } = {},
  ) => {
    const params = new URLSearchParams();
    if (payload.tenantId != null) {
      params.set('tenant_id', String(payload.tenantId));
    }
    if (payload.limit != null) {
      params.set('limit', String(payload.limit));
    }

    return fetch(`/api/v1/plugins/public-transactions/${pluginId}?${params.toString()}`, {
      credentials: 'include',
    }).then(async (r) => {
      const data = await r.json();
      if (!r.ok) {
        throw new Error(data?.detail || `Transactions lookup failed with status ${r.status}`);
      }
      return data;
    }) as Promise<{
      transactions: Array<{
        id: string;
        created?: number | null;
        mode?: string | null;
        status?: string | null;
        payment_status?: string | null;
        customer_email?: string | null;
        amount_total?: number | null;
        currency?: string | null;
      }>;
    }>;
  },

  getPaymentTransactions: (limit = 20) =>
    apiRequest<{
      transactions: Array<{
        id: string;
        plugin_id?: string | null;
        created?: number | null;
        mode?: string | null;
        status?: string | null;
        payment_status?: string | null;
        subscription_status?: string | null;
        is_paid?: boolean;
        customer_email?: string | null;
        amount_total?: number | null;
        currency?: string | null;
      }>;
    }>(`/plugins/payment-transactions?limit=${limit}`),
};
