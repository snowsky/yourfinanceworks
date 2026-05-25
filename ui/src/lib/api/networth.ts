import { apiRequest } from './_base';

export type LiabilityKind = 'credit_card' | 'loan' | 'mortgage' | 'other';
export type AccountKind = 'bank' | 'investment' | 'liability';

export interface AccountBalanceResponse {
  account_kind: AccountKind;
  label: string;
  balance: number;
  currency: string;
  account_ref?: number | null;
}

export interface NetWorthSummaryResponse {
  snapshot_date?: string | null;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  bank_total: number;
  investment_total: number;
  liability_total: number;
  accounts: AccountBalanceResponse[];
}

export interface SnapshotResponse {
  snapshot_date: string;
  rows_written: number;
  summary: NetWorthSummaryResponse;
}

export interface HistoryPointResponse {
  snapshot_date: string;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
}

export interface HistoryResponse {
  points: HistoryPointResponse[];
}

export interface LiabilityResponse {
  id: number;
  name: string;
  kind: LiabilityKind;
  balance: number;
  currency: string;
  interest_rate?: number | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LiabilityCreateRequest {
  name: string;
  kind?: LiabilityKind;
  balance: number;
  currency?: string;
  interest_rate?: number | null;
  notes?: string | null;
}

export type LiabilityUpdateRequest = Partial<LiabilityCreateRequest>;

export const networthApi = {
  summary: () => apiRequest<NetWorthSummaryResponse>('/networth/summary'),

  history: (months: number = 12) =>
    apiRequest<HistoryResponse>(`/networth/history?months=${months}`),

  snapshot: () =>
    apiRequest<SnapshotResponse>('/networth/snapshot', { method: 'POST' }),

  listLiabilities: () =>
    apiRequest<LiabilityResponse[]>('/networth/liabilities'),

  createLiability: (body: LiabilityCreateRequest) =>
    apiRequest<LiabilityResponse>('/networth/liabilities', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateLiability: (id: number, body: LiabilityUpdateRequest) =>
    apiRequest<LiabilityResponse>(`/networth/liabilities/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteLiability: (id: number) =>
    apiRequest<void>(`/networth/liabilities/${id}`, { method: 'DELETE' }),
};
