import { apiRequest } from './_base';

export interface CrmContact {
  id: number;
  client_id: number | null;
  tenant_id: number;
  name: string;
  email: string | null;
  phone: string | null;
  role: string | null;
  notes: string | null;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

export interface CrmContactCreate {
  client_id?: number;
  name: string;
  email?: string;
  phone?: string;
  role?: string;
  is_primary?: boolean;
}

export const crmApi = {
  contacts: {
    list: (clientId?: number) =>
      apiRequest<CrmContact[]>(`/crm/contacts${clientId !== undefined ? `?client_id=${clientId}` : ''}`),
    create: (data: CrmContactCreate) =>
      apiRequest<CrmContact>('/crm/contacts', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: number) =>
      apiRequest<void>(`/crm/contacts/${id}`, { method: 'DELETE' }),
  },
};
