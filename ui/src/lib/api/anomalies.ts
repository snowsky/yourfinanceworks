import { apiRequest } from './_base';

export interface AnomalyRuleSettings {
  enabled: boolean;
  min_amount?: number;       // rounding_anomaly
  min_count?: number;        // threshold_splitting
  proximity_pct?: number;    // threshold_splitting
  start_hour?: number;       // temporal_anomaly
  end_hour?: number;         // temporal_anomaly
  flag_weekend?: boolean;    // temporal_anomaly
}

export interface AnomalyRuleConfig {
  min_risk_score: number;
  rules: Record<string, AnomalyRuleSettings>;
}

export type AnomalyRiskLevel = 'low' | 'medium' | 'high' | 'critical';

export type AnomalyStatus = 'open' | 'confirmed' | 'dismissed';

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
  status: AnomalyStatus;
  resolution_note?: string | null;
  resolved_at?: string | null;
}

export interface AnomalyListResponse {
  total: number;
  summary: Record<AnomalyRiskLevel, number>;
  skip: number;
  limit: number;
  items: Anomaly[];
}

export const anomaliesApi = {
  list: (params: { skip?: number; limit?: number; risk_level?: string; status?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.skip != null) q.set('skip', String(params.skip));
    if (params.limit != null) q.set('limit', String(params.limit));
    if (params.risk_level) q.set('risk_level', params.risk_level);
    if (params.status) q.set('status', params.status);
    const qs = q.toString();
    return apiRequest<AnomalyListResponse>(`/anomalies${qs ? `?${qs}` : ''}`);
  },

  get: (id: number) => apiRequest<Anomaly>(`/anomalies/${id}`),

  resolve: (id: number, status: 'confirmed' | 'dismissed', note?: string) =>
    apiRequest<{ id: number; status: AnomalyStatus }>(`/anomalies/${id}/resolve`, {
      method: 'PATCH',
      body: JSON.stringify({ status, note: note ?? null }),
    }),

  dismiss: (id: number, notes?: string) =>
    apiRequest<{ id: number; is_dismissed: boolean }>(`/anomalies/${id}/dismiss`, {
      method: 'PATCH',
      body: JSON.stringify({ notes: notes ?? null }),
    }),

  getConfig: () => apiRequest<AnomalyRuleConfig>('/anomalies/config'),

  updateConfig: (config: Partial<AnomalyRuleConfig>) =>
    apiRequest<AnomalyRuleConfig>('/anomalies/config', {
      method: 'PUT',
      body: JSON.stringify({ config }),
    }),
};
