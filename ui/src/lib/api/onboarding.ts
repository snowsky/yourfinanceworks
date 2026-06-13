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

export const onboardingApi = {
  getSampleDataStatus: () => apiRequest<SampleDataStatus>('/onboarding/sample-data'),
  seedSampleData: () => apiRequest<SampleDataCounts>('/onboarding/sample-data', { method: 'POST' }),
  clearSampleData: () => apiRequest<SampleDataCounts>('/onboarding/sample-data', { method: 'DELETE' }),
};
