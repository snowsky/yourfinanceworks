import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

vi.mock('@/lib/api/onboarding', () => ({
  onboardingAssistantApi: { sendOnboardingMessage: vi.fn() },
}));
import { onboardingAssistantApi } from '@/lib/api/onboarding';
import { useOnboardingConversation } from './useOnboardingConversation';

describe('useOnboardingConversation', () => {
  beforeEach(() => vi.clearAllMocks());

  it('surfaces a proposed_action as pendingAction without executing', async () => {
    (onboardingAssistantApi.sendOnboardingMessage as any).mockResolvedValue({
      success: true,
      data: { type: 'proposed_action', action: 'create_client', params: { name: 'Acme' }, source: 'onboarding' },
    });
    const { result } = renderHook(() => useOnboardingConversation());
    await act(async () => { await result.current.send('add a client Acme'); });
    await waitFor(() => expect(result.current.pendingAction?.action).toBe('create_client'));
  });

  it('confirm() forwards confirmed_action and clears the pending action', async () => {
    (onboardingAssistantApi.sendOnboardingMessage as any).mockResolvedValue({
      success: true,
      data: { response: '✅ Client created.', executed_action: 'create_client' },
    });
    const { result } = renderHook(() => useOnboardingConversation());
    await act(async () => {
      await result.current.confirm({ action: 'create_client', params: { name: 'Acme' } });
    });
    expect(onboardingAssistantApi.sendOnboardingMessage).toHaveBeenCalledWith({
      message: '',
      confirmed_action: { action: 'create_client', params: { name: 'Acme' } },
    });
    expect(result.current.pendingAction).toBeNull();
  });
});
