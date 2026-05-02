import { apiRequest } from './_base';

// Types
export interface CashFlowReference {
  type: string;
  id: number;
  label: string;
  url?: string | null;
}

export interface CashFlowEntry {
  date: string;
  amount: number;
  type: 'inflow' | 'outflow';
  category: string;
  description?: string | null;
  reference_id?: number | null;
  confidence: number;
  source: string;
  source_label: string;
  source_details?: string | null;
  references?: CashFlowReference[];
}

export interface DailyBalance {
  date: string;
  projected_inflows: number;
  projected_outflows: number;
  net_change: number;
  projected_balance: number;
}

export interface CashFlowForecastResponse {
  period: string;
  start_date: string;
  end_date: string;
  current_balance: number;
  projected_end_balance: number;
  total_projected_inflows: number;
  total_projected_outflows: number;
  net_change: number;
  daily_balances: DailyBalance[];
  inflow_entries: CashFlowEntry[];
  outflow_entries: CashFlowEntry[];
  alerts: string[];
}

export interface CashRunwayResponse {
  current_balance: number;
  average_daily_burn: number;
  average_daily_income: number;
  net_daily_burn: number;
  runway_days: number | null;
  runway_date: string | null;
  is_sustainable: boolean;
  monthly_burn_rate: number;
  monthly_income_rate: number;
}

export interface ScenarioInput {
  description: string;
  delayed_invoice_ids?: number[] | null;
  delay_days?: number;
  additional_expense?: number | null;
  additional_expense_date?: string | null;
  revenue_change_percent?: number | null;
  expense_change_percent?: number | null;
}

export interface ScenarioResult {
  scenario_description: string;
  baseline_end_balance: number;
  scenario_end_balance: number;
  balance_impact: number;
  lowest_balance: number;
  lowest_balance_date: string | null;
  days_below_threshold: number;
  alerts: string[];
  daily_balances: DailyBalance[];
}

export interface CashFlowThresholdSettings {
  safety_threshold: number;
  warning_threshold: number;
  currency: string;
  include_outstanding_invoices: boolean;
  include_recurring_invoices: boolean;
  include_upcoming_expenses: boolean;
  include_historical_averages: boolean;
  include_bank_statement_patterns: boolean;
  bank_statement_lookback_days: number;
  bank_statement_min_occurrences: number;
  bank_statement_intervals: number[];
  bank_statement_inflow_categories: string[];
  bank_statement_outflow_categories: string[];
}

export interface CashFlowAlertResponse {
  has_alerts: boolean;
  alerts: string[];
  current_balance: number;
  safety_threshold: number;
  warning_threshold: number;
  days_until_threshold_breach: number | null;
  breach_date: string | null;
}

export type ForecastPeriod = '7d' | '30d' | '90d' | '365d';

// API client
export const cashflowApi = {
  getForecast: (period: ForecastPeriod = '30d', currentBalance?: number) => {
    const params = new URLSearchParams({ period });
    if (currentBalance !== undefined) params.set('current_balance', String(currentBalance));
    return apiRequest<CashFlowForecastResponse>(`/cashflow/forecast?${params}`);
  },

  getRunway: (currentBalance?: number) => {
    const params = new URLSearchParams();
    if (currentBalance !== undefined) params.set('current_balance', String(currentBalance));
    const qs = params.toString();
    return apiRequest<CashRunwayResponse>(`/cashflow/runway${qs ? '?' + qs : ''}`);
  },

  runScenario: (scenario: ScenarioInput, period: ForecastPeriod = '30d', currentBalance?: number) => {
    const params = new URLSearchParams({ period });
    if (currentBalance !== undefined) params.set('current_balance', String(currentBalance));
    return apiRequest<ScenarioResult>(`/cashflow/scenario?${params}`, {
      method: 'POST',
      body: JSON.stringify(scenario),
    });
  },

  getAlerts: (currentBalance?: number) => {
    const params = new URLSearchParams();
    if (currentBalance !== undefined) params.set('current_balance', String(currentBalance));
    const qs = params.toString();
    return apiRequest<CashFlowAlertResponse>(`/cashflow/alerts${qs ? '?' + qs : ''}`);
  },

  getThresholds: () =>
    apiRequest<CashFlowThresholdSettings>('/cashflow/settings/thresholds'),

  updateThresholds: (data: Partial<CashFlowThresholdSettings>) =>
    apiRequest<CashFlowThresholdSettings>('/cashflow/settings/thresholds', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
};
