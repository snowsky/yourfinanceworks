import { apiRequest, API_BASE_URL } from './_base';

export interface ShareTokenResponse {
  token: string;
  record_type: string;
  record_id: number;
  share_url: string;
  created_at: string;
  expires_at: string | null;
  is_active: boolean;
  access_type: ShareAccessType;
  security_question: string | null;
  one_time: boolean;
  access_count: number;
  max_access_count: number | null;
}

export type RecordType = 'invoice' | 'expense' | 'payment' | 'client' | 'bank_statement' | 'portfolio';
export type ShareAccessType = 'public' | 'password' | 'question';

export interface CreateShareTokenPayload {
  record_type: RecordType;
  record_id: number;
  access_type?: ShareAccessType;
  expires_in_hours?: number;
  one_time?: boolean;
  password?: string;
  security_question?: string;
  security_answer?: string;
}

export interface ShareAccessRequirement {
  code: 'share_access_required';
  access_type: ShareAccessType;
  security_question?: string | null;
}

export class ShareAccessRequiredError extends Error {
  requirement: ShareAccessRequirement;

  constructor(requirement: ShareAccessRequirement) {
    super('This shared link requires verification');
    this.name = 'ShareAccessRequiredError';
    this.requirement = requirement;
  }
}

export const shareTokenApi = {
  createToken: (record_type: RecordType, record_id: number, options: Omit<CreateShareTokenPayload, 'record_type' | 'record_id'> = {}) =>
    apiRequest<ShareTokenResponse>('/share-tokens/', {
      method: 'POST',
      body: JSON.stringify({ record_type, record_id, ...options }),
    }),

  getToken: (record_type: RecordType, record_id: number) =>
    apiRequest<ShareTokenResponse | null>(`/share-tokens/${record_type}/${record_id}`),

  revokeToken: (token: string) =>
    apiRequest<void>(`/share-tokens/${token}`, { method: 'DELETE' }),

  // Uses raw fetch — bypasses tenant header injection since this is a public endpoint
  getPublicRecord: async (
    token: string,
    access?: { password?: string; security_answer?: string },
  ): Promise<Record<string, unknown>> => {
    const url = access ? `${API_BASE_URL}/shared/${token}/access` : `${API_BASE_URL}/shared/${token}`;
    const res = await fetch(url, access ? {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(access),
    } : undefined);
    if (res.status === 401) {
      const body = await res.json().catch(() => null);
      const detail = body?.detail;
      if (detail?.code === 'share_access_required') {
        throw new ShareAccessRequiredError(detail);
      }
      throw new Error('This shared link requires verification');
    }
    if (res.status === 403) throw new Error('The verification response was incorrect');
    if (res.status === 404) throw new Error('Link not found or has been revoked');
    if (res.status === 410) throw new Error('This link has expired or has already been used');
    if (!res.ok) throw new Error('Failed to load shared record');
    return res.json();
  },
};
