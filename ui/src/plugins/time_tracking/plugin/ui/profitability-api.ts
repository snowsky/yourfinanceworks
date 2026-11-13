import { apiRequest } from '@/lib/api';

/** All new monetary and hour decimals are serialized by Pydantic as strings. */
export type Decimal = string;
export interface TenantContributor { id: number; email: string; first_name: string | null; last_name: string | null; role: string; is_active: boolean }
export interface CostRateWrite { user_id: number; currency: string; effective_from: string; hourly_cost: Decimal; contributor_kind: 'owner' | 'employee' | 'subcontractor' }
export interface CostRate extends CostRateWrite { id: number }
export interface BackfillEntry { entry_id: number; work_date: string; duration_minutes: number | null; entry_version: string; status: string; user_id: number; cost_version: number | null; source_rate_id: number | null; hourly_cost: Decimal | null; currency: string; before_cost: Decimal | null; after_cost: Decimal | null }
export interface BackfillPreview { project_id: number; entry_ids: number[]; entries: BackfillEntry[]; before_total: Decimal; after_total: Decimal; fingerprint: string }
export interface Replacement { method: 'hourly' | 'supplier_expense'; expense_ids: number[] }
export interface EntryCost { time_entry_id: number; method: Replacement['method']; hourly_cost: Decimal | null; currency: string; source_rate_id: number | null; version: number }
export interface Breakdown { id: number | null; completed_hours: Decimal; hourly_cost: Decimal; entry_ids: number[]; supplier_expense_ids: number[] }
export interface CostRecord { record_type: 'time_entry' | 'expense'; record_id: number; reason: string }
export interface ProjectProfitabilityResponse {
  project_id: number; currency: string; status: 'complete' | 'incomplete' | 'unsupported_billing_method';
  work_value: Decimal; known_cost: Decimal; contribution: Decimal | null; margin_percent: Decimal | null;
  completed_hours: Decimal; billable_hours: Decimal; nonbillable_hours: Decimal; missing_hours: Decimal;
  unresolved_records: CostRecord[]; excluded_records: CostRecord[]; contributors: Breakdown[]; tasks: Breakdown[];
  expense_bucket: { amount: Decimal; expense_ids: number[]; cost_basis: 'amount' };
  hours_budget_percent: Decimal | null; amount_budget_percent: Decimal | null; budget_warnings: string[];
  billing: null | { currency: string; unbilled_work_value: Decimal; invoiced_pre_tax: Decimal; collected_cash: Decimal; collections_include_tax: boolean; invoicing_complete: boolean; cash_complete: boolean; attributed_invoice_ids: number[]; unresolved_invoice_ids: number[]; unresolved_invoices: { invoice_id: number; reasons: string[] }[] };
}
export const getProjectProfitability = (id: number, signal?: AbortSignal) => apiRequest<ProjectProfitabilityResponse>(`/projects/${id}/profitability`, { signal });
export const profitabilityApi = {
  rates: (user: number, currency: string) => apiRequest<CostRate[]>(`/projects/cost-rates?user_id=${user}&currency=${encodeURIComponent(currency)}`),
  saveRate: (data: CostRateWrite) => apiRequest<CostRate>('/projects/cost-rates', { method: 'POST', body: JSON.stringify(data) }),
  preview: (id: number, entry_ids: number[]) => apiRequest<BackfillPreview>(`/projects/${id}/cost-backfill/preview`, { method: 'POST', body: JSON.stringify({ entry_ids }) }),
  apply: (id: number, data: BackfillPreview) => apiRequest<{ applied_entry_ids: number[] }>(`/projects/${id}/cost-backfill/apply`, { method: 'POST', body: JSON.stringify(data) }),
  replace: (id: number, entry: number, data: Replacement) => apiRequest<EntryCost>(`/projects/${id}/entry-costs/${entry}`, { method: 'PUT', body: JSON.stringify(data) }),
};
