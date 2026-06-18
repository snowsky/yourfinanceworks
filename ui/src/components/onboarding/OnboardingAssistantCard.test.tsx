import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('@/contexts/FeatureContext', () => ({ useFeatures: () => ({ isFeatureEnabled: () => true }) }));
vi.mock('@/lib/api/onboarding', () => ({
  onboardingAssistantApi: {
    getAssistantStatus: vi.fn(),
    dismissAssistant: vi.fn(),
    sendOnboardingMessage: vi.fn(),
    getHistory: vi.fn().mockResolvedValue([]),
    saveMessage: vi.fn().mockResolvedValue({ success: true }),
  },
  onboardingAiSummary: (d: any) => d?.response ?? 'help',
  onboardingApi: { getChecklist: vi.fn().mockResolvedValue({ all_complete: false }) },
}));
import { onboardingAssistantApi } from '@/lib/api/onboarding';
import { OnboardingAssistantCard } from './OnboardingAssistantCard';

const renderCard = () =>
  render(
    <MemoryRouter>
      <OnboardingAssistantCard />
    </MemoryRouter>,
  );

describe('OnboardingAssistantCard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows the configure-AI prompt when ai is not configured', async () => {
    (onboardingAssistantApi.getAssistantStatus as any).mockResolvedValue({ ai_configured: false, dismissed: false });
    renderCard();
    await waitFor(() => expect(screen.getByText(/Set up your AI provider first/i)).toBeInTheDocument());
  });

  it('shows the chat composer when ai is configured', async () => {
    (onboardingAssistantApi.getAssistantStatus as any).mockResolvedValue({ ai_configured: true, dismissed: false });
    renderCard();
    await waitFor(() => expect(screen.getByPlaceholderText(/set up/i)).toBeInTheDocument());
  });

  it('renders nothing when dismissed', async () => {
    (onboardingAssistantApi.getAssistantStatus as any).mockResolvedValue({ ai_configured: true, dismissed: true });
    const { container } = renderCard();
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
