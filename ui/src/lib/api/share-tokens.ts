import { apiRequest, API_BASE_URL } from './_base';

export interface ShareTokenResponse {
  token: string;
  record_type: string;
  record_id: number;
  share_url: string;
  created_at: string;
  expires_at: string | null;
  is_active: boolean;
}

export type RecordType = 'invoice' | 'expense' | 'payment' | 'client' | 'bank_statement' | 'portfolio';

export const shareTokenApi = {
  createToken: (record_type: RecordType, record_id: number) =>
    apiRequest<ShareTokenResponse>('/share-tokens/', {
      method: 'POST',
      body: JSON.stringify({ record_type, record_id }),
    }),

  getToken: (record_type: RecordType, record_id: number) =>
    apiRequest<ShareTokenResponse | null>(`/share-tokens/${record_type}/${record_id}`),

  revokeToken: (token: string) =>
    apiRequest<void>(`/share-tokens/${token}`, { method: 'DELETE' }),

  // Uses raw fetch — bypasses tenant header injection since this is a public endpoint
  getPublicRecord: async (token: string): Promise<Record<string, unknown>> => {
    const res = await fetch(`${API_BASE_URL}/shared/${token}`);
    if (res.status === 404) throw new Error('Link not found or has been revoked');
    if (res.status === 410) throw new Error('This link has expired');
    if (!res.ok) throw new Error('Failed to load shared record');
    return res.json();
  },
};
