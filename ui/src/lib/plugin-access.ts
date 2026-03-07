import { apiRequest } from '@/lib/api';

export type PluginAccessType = 'read' | 'write';

export interface PluginAccessRequestRecord {
  id: string;
  source_plugin: string;
  target_plugin: string;
  access_type: PluginAccessType;
  status: 'pending' | 'approved' | 'denied';
  requested_by_user_id: number;
  requested_at: string;
  resolved_by_user_id?: number;
  resolved_at?: string;
  reason?: string;
  requested_path?: string;
  grant_id?: string;
}

export interface PluginAccessGrantRecord {
  id: string;
  source_plugin: string;
  target_plugin: string;
  access_type: PluginAccessType | '*';
  granted_to_user_id: number;
  granted_by_user_id?: number;
  granted_at: string;
  request_id?: string;
  allowed_paths?: string[];
}

export interface PluginAccessCheckResponse {
  granted: boolean;
  requires_approval: boolean;
  request?: PluginAccessRequestRecord;
  grant?: PluginAccessGrantRecord | Record<string, unknown>;
}

const READ_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

function normalizePluginId(pluginId: string): string {
  return pluginId.trim().toLowerCase().replace(/_/g, '-');
}

function toPlainHeaders(headers?: HeadersInit): Record<string, string> {
  if (!headers) {
    return {};
  }
  if (headers instanceof Headers) {
    const out: Record<string, string> = {};
    headers.forEach((value, key) => {
      out[key] = value;
    });
    return out;
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return headers as Record<string, string>;
}

function accessTypeForMethod(method?: string): PluginAccessType {
  const normalized = (method || 'GET').toUpperCase();
  return READ_METHODS.has(normalized) ? 'read' : 'write';
}

export async function pluginToPluginRequest<T>(params: {
  sourcePlugin: string;
  targetPlugin: string;
  url: string;
  options?: RequestInit;
  reason?: string;
}): Promise<T> {
  const sourcePlugin = normalizePluginId(params.sourcePlugin);
  const targetPlugin = normalizePluginId(params.targetPlugin);
  const method = params.options?.method || 'GET';
  const accessType = accessTypeForMethod(method);

  const check = await apiRequest<PluginAccessCheckResponse>('/plugins/access/check', {
    method: 'POST',
    body: JSON.stringify({
      source_plugin: sourcePlugin,
      target_plugin: targetPlugin,
      access_type: accessType,
      reason: params.reason,
      requested_path: params.url,
    }),
  });

  if (!check.granted) {
    const detail = {
      error_code: 'PLUGIN_ACCESS_APPROVAL_REQUIRED',
      message: `Plugin '${sourcePlugin}' needs your approval to access '${targetPlugin}' data.`,
      request: check.request,
    };
    window.dispatchEvent(new CustomEvent('plugin-access-approval-required', { detail }));

    const err = new Error(detail.message) as Error & { code?: string; request?: PluginAccessRequestRecord };
    err.code = 'PLUGIN_ACCESS_APPROVAL_REQUIRED';
    err.request = check.request;
    throw err;
  }

  const existingHeaders = toPlainHeaders(params.options?.headers);
  return apiRequest<T>(params.url, {
    ...(params.options || {}),
    headers: {
      ...existingHeaders,
      'X-Plugin-Caller': sourcePlugin,
    },
  });
}

export const pluginAccessApi = {
  check: (params: {
    source_plugin: string;
    target_plugin: string;
    access_type: PluginAccessType;
    reason?: string;
    requested_path?: string;
  }) =>
    apiRequest<PluginAccessCheckResponse>(
      '/plugins/access/check',
      {
        method: 'POST',
        body: JSON.stringify(params),
      }
    ),

  listPendingMine: () =>
    apiRequest<{ requests: PluginAccessRequestRecord[] }>(
      '/plugins/access-requests?status=pending&mine_only=true',
      { method: 'GET' }
    ),

  listGrantsMine: () =>
    apiRequest<{ grants: PluginAccessGrantRecord[] }>(
      '/plugins/access-grants?mine_only=true',
      { method: 'GET' }
    ),

  approve: (requestId: string) =>
    apiRequest<{
      message: string;
      request: PluginAccessRequestRecord;
      grant: Record<string, unknown>;
    }>(`/plugins/access-requests/${requestId}/approve`, { method: 'POST' }),

  deny: (requestId: string) =>
    apiRequest<{
      message: string;
      request: PluginAccessRequestRecord;
    }>(`/plugins/access-requests/${requestId}/deny`, { method: 'POST' }),

  revoke: (grantId: string) =>
    apiRequest<{ message: string }>(`/plugins/access-grants/${grantId}`, { method: 'DELETE' }),
};
