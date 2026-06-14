import { apiRequest } from './_base';

export type SubscriptionStatus =
  | 'active'
  | 'dismissed'
  | 'canceled_by_user'
  | 'not_a_subscription';

export interface SubscriptionResponse {
  id: number;
  merchant_key: string;
  label: string;
  category?: string | null;
  amount: number;
  last_amount?: number | null;
  currency: string;
  cadence_days: number;
  confidence: number;
  first_seen_date: string;
  last_seen_date: string;
  next_expected_date?: string | null;
  charge_count: number;
  status: SubscriptionStatus;
  cancel_reminder_at?: string | null;
  price_change_acknowledged: boolean;
  source_transaction_ids?: number[] | null;
  notes?: string | null;
  dismissed_at?: string | null;
  created_at: string;
  updated_at: string;
  review_reason?: 'lapsed' | 'long_running' | null;
  days_overdue?: number | null;
  months_running?: number | null;
}

export interface SubscriptionSummary {
  total_count: number;
  active_count: number;
  monthly_cost: number;
  annual_cost: number;
  next_charge_date?: string | null;
  needs_review_count: number;
  items: SubscriptionResponse[];
}

export interface ChargeHistoryEntry {
  transaction_id: number;
  date: string;
  amount: number;
  description: string;
}

export interface ChargeHistoryResponse {
  subscription_id: number;
  entries: ChargeHistoryEntry[];
}

export interface ScanRequest {
  lookback_days?: number;
  emit_notifications?: boolean;
}

export interface ScanResponse {
  scanned_transactions: number;
  candidate_groups: number;
  new_subscriptions: number;
  updated_subscriptions: number;
  price_changed_subscriptions: number;
  skipped_excluded: number;
  new_subscription_ids: number[];
  price_changed_subscription_ids: number[];
}

export const subscriptionsApi = {
  list: (
    params: {
      status?: SubscriptionStatus;
      includeLowConfidence?: boolean;
      needsReview?: boolean;
    } = {},
  ) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set('status', params.status);
    if (params.includeLowConfidence) qs.set('include_low_confidence', 'true');
    if (params.needsReview) qs.set('needs_review', 'true');
    const tail = qs.toString();
    return apiRequest<SubscriptionSummary>(`/subscriptions${tail ? `?${tail}` : ''}`);
  },

  get: (id: number) => apiRequest<SubscriptionResponse>(`/subscriptions/${id}`),

  charges: (id: number) =>
    apiRequest<ChargeHistoryResponse>(`/subscriptions/${id}/charges`),

  scan: (body: ScanRequest = {}) =>
    apiRequest<ScanResponse>('/subscriptions/scan', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateStatus: (id: number, status: SubscriptionStatus) =>
    apiRequest<SubscriptionResponse>(`/subscriptions/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),

  setCancelReminder: (id: number, remindOn: string | null) =>
    apiRequest<SubscriptionResponse>(`/subscriptions/${id}/cancel-reminder`, {
      method: 'POST',
      body: JSON.stringify({ remind_on: remindOn }),
    }),

  acknowledgePriceChange: (id: number) =>
    apiRequest<SubscriptionResponse>(`/subscriptions/${id}/acknowledge-price-change`, {
      method: 'POST',
    }),
};
