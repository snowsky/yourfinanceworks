import { apiRequest } from './_base';

export interface SampleDataStatus {
  has_sample_data: boolean;
  has_any_data: boolean;
}

export interface SampleDataCounts {
  clients: number;
  invoices: number;
  expenses: number;
  payments: number;
}

export interface ChecklistStep {
  key: string;
  done: boolean;
}

export interface ChecklistStatus {
  steps: ChecklistStep[];
  completed: number;
  total: number;
  all_complete: boolean;
  dismissed: boolean;
}

export const onboardingApi = {
  getSampleDataStatus: () => apiRequest<SampleDataStatus>('/onboarding/sample-data'),
  seedSampleData: () => apiRequest<SampleDataCounts>('/onboarding/sample-data', { method: 'POST' }),
  clearSampleData: () => apiRequest<SampleDataCounts>('/onboarding/sample-data', { method: 'DELETE' }),
  getChecklist: () => apiRequest<ChecklistStatus>('/onboarding/checklist'),
  dismissChecklist: () =>
    apiRequest<ChecklistStatus>('/onboarding/checklist/dismiss', { method: 'POST' }),
};
