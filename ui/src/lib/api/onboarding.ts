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

export interface AssistantStatus {
  ai_configured: boolean;
  dismissed: boolean;
}

export interface OnboardingAction {
  action: string;
  params: Record<string, unknown>;
}

export interface ProposedAction extends OnboardingAction {
  type: 'proposed_action';
  source: 'onboarding';
}

export interface ChatEnvelope {
  success: boolean;
  data?: any;
  error?: string;
}

export interface ChatHistoryItem {
  sender: 'user' | 'ai';
  message: string;
  created_at?: string;
}

export const onboardingAssistantApi = {
  getAssistantStatus: () => apiRequest<AssistantStatus>('/onboarding/assistant/status'),
  dismissAssistant: () =>
    apiRequest<AssistantStatus>('/onboarding/assistant/dismiss', { method: 'POST' }),
  sendOnboardingMessage: (body: { message: string; confirmed_action?: OnboardingAction }) =>
    apiRequest<ChatEnvelope>('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({
        message: body.message,
        mode: 'onboarding',
        ...(body.confirmed_action ? { confirmed_action: body.confirmed_action } : {}),
      }),
    }),
  // Onboarding shares the AI assistant's persisted chat history.
  getHistory: () => apiRequest<ChatHistoryItem[]>('/ai/chat/history?limit=20&offset=0'),
  saveMessage: (message: string, sender: 'user' | 'ai') =>
    apiRequest<{ success: boolean }>('/ai/chat/message', {
      method: 'POST',
      body: JSON.stringify({ message, sender }),
    }),
};

/** Human-readable AI text for persisting an onboarding turn to chat history. */
export function onboardingAiSummary(data: any): string {
  if (data?.response) return data.response;
  if (data?.type === 'proposed_action') {
    return `Let's ${String(data.action).replace(/_/g, ' ')} — please review and confirm the details.`;
  }
  return 'Let me help you get set up.';
}
