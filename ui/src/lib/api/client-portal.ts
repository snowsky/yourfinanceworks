import { API_BASE_URL } from './_base';

// The client portal uses its own bearer token (never the staff JWT cookie),
// stored separately. All calls are raw fetch so the staff tenant header/auth is
// never attached.
const TOKEN_KEY = 'client-portal-token';
const SLUG_KEY = 'client-portal-slug';

export const clientPortalSession = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
  getSlug: () => localStorage.getItem(SLUG_KEY),
  setSlug: (s: string) => localStorage.setItem(SLUG_KEY, s),
};

export class ClientPortalAuthError extends Error {
  constructor() {
    super('Your session has expired. Please sign in again.');
    this.name = 'ClientPortalAuthError';
  }
}

export interface PortalBranding {
  company_name: string;
  company_logo_url: string | null;
  brand_color: string;
  accent_color: string;
  footer_text: string | null;
}

export interface PortalInvoice {
  id: number;
  number: string;
  status: string;
  currency: string;
  amount: number;
  due_date: string | null;
  created_at: string;
  paid_amount: number;
  outstanding: number;
}

export interface PortalInvoiceItem {
  description: string;
  quantity: number;
  price: number;
  amount: number;
  unit_of_measure?: string | null;
}

export interface PortalInvoiceDetail extends PortalInvoice {
  subtotal: number;
  discount_type: string;
  discount_value: number;
  description?: string | null;
  items: PortalInvoiceItem[];
}

export interface PortalProfile {
  id: number;
  name: string;
  email: string;
  phone?: string | null;
  address?: string | null;
}

async function authed<T>(path: string, init?: RequestInit): Promise<T> {
  const token = clientPortalSession.getToken();
  const res = await fetch(`${API_BASE_URL}/client-portal${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (res.status === 401) {
    clientPortalSession.clear();
    throw new ClientPortalAuthError();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || 'Request failed');
  }
  return res.json();
}

export const clientPortalApi = {
  getBranding: async (slug: string): Promise<PortalBranding> => {
    const res = await fetch(`${API_BASE_URL}/client-portal/${slug}/branding`);
    if (!res.ok) throw new Error('Portal not found');
    return res.json();
  },

  requestLink: async (slug: string, email: string): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE_URL}/client-portal/${slug}/request-link`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || 'Unable to send a login link right now.');
    }
    return res.json();
  },

  verify: async (token: string): Promise<{ access_token: string; client: PortalProfile & { company_name: string } }> => {
    const res = await fetch(`${API_BASE_URL}/client-portal/verify/${token}`, { method: 'POST' });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || 'This sign-in link is invalid or has expired.');
    }
    return res.json();
  },

  getMe: () => authed<PortalProfile>('/me'),
  updateMe: (body: Partial<Pick<PortalProfile, 'name' | 'phone' | 'address'>>) =>
    authed<PortalProfile>('/me', { method: 'PATCH', body: JSON.stringify(body) }),
  getInvoices: () => authed<{ invoices: PortalInvoice[] }>('/invoices'),
  getInvoice: (id: number) => authed<PortalInvoiceDetail>(`/invoices/${id}`),

  downloadPdf: async (id: number, number: string): Promise<void> => {
    const token = clientPortalSession.getToken();
    const res = await fetch(`${API_BASE_URL}/client-portal/invoices/${id}/pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Failed to download PDF');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `invoice-${number}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  },
};
