import { apiRequest } from './_base';

export interface EmailReference {
  reference_id: number;
  raw_email_id: number;
  subject: string | null;
  sender: string | null;
  date: string | null;
  snippet: string | null;
  link_type: 'auto' | 'manual';
  notes: string | null;
  created_at: string;
}

export interface EmailSearchResult {
  id: number;
  subject: string | null;
  sender: string | null;
  date: string | null;
  status: string;
}

export interface LinkEmailPayload {
  document_type: string;
  document_id: number;
  notes?: string;
}

export interface UnlinkEmailPayload {
  document_type: string;
  document_id: number;
}

export const emailReferencesApi = {
  getForDocument: (path: string): Promise<EmailReference[]> =>
    apiRequest<EmailReference[]>(path),

  searchEmails: (q: string, limit = 20): Promise<EmailSearchResult[]> =>
    apiRequest<EmailSearchResult[]>(
      `/email-integration/emails/search?q=${encodeURIComponent(q)}&limit=${limit}`
    ),

  linkEmail: (rawEmailId: number, payload: LinkEmailPayload): Promise<EmailReference> =>
    apiRequest<EmailReference>(`/email-integration/emails/${rawEmailId}/link`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  unlinkEmail: (rawEmailId: number, payload: UnlinkEmailPayload): Promise<void> =>
    apiRequest<void>(`/email-integration/emails/${rawEmailId}/link`, {
      method: 'DELETE',
      body: JSON.stringify(payload),
    }),
};
