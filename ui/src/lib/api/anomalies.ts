import { apiRequest } from './_base';

export type AnomalyRiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface Anomaly {
  id: number;
  entity_type: string; // 'invoice' | 'expense' | 'bank_transaction'
  entity_id: number;
  risk_score: number; // 0–100
  risk_level: AnomalyRiskLevel | string;
  reason: string;
  rule_id: string | null;
  details: unknown;
  created_at: string;
  /** Parent statement id for bank-transaction anomalies (else null). */
  statement_id?: number | null;
}

export interface AnomalyListResponse {
  total: number;
  summary: Record<AnomalyRiskLevel, number>;
  skip: number;
  limit: number;
  items: Anomaly[];
}

export const anomaliesApi = {
  list: (params: { skip?: number; limit?: number; risk_level?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.skip != null) q.set('skip', String(params.skip));
    if (params.limit != null) q.set('limit', String(params.limit));
    if (params.risk_level) q.set('risk_level', params.risk_level);
    const qs = q.toString();
    return apiRequest<AnomalyListResponse>(`/anomalies${qs ? `?${qs}` : ''}`);
  },

  dismiss: (id: number, notes?: string) =>
    apiRequest<{ id: number; is_dismissed: boolean }>(`/anomalies/${id}/dismiss`, {
      method: 'PATCH',
      body: JSON.stringify({ notes: notes ?? null }),
    }),
};
