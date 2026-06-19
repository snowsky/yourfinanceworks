import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

vi.mock('@/lib/api/onboarding', () => ({
  onboardingAssistantApi: {
    sendOnboardingMessage: vi.fn(),
    getHistory: vi.fn().mockResolvedValue([]),
    saveMessage: vi.fn().mockResolvedValue({ success: true }),
  },
  onboardingAiSummary: (d: any) => d?.response ?? (d?.type === 'proposed_action' ? `proposed ${d.action}` : 'help'),
}));
import { onboardingAssistantApi } from '@/lib/api/onboarding';
import { useOnboardingConversation } from './useOnboardingConversation';

describe('useOnboardingConversation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (onboardingAssistantApi.getHistory as any).mockResolvedValue([]);
    (onboardingAssistantApi.saveMessage as any).mockResolvedValue({ success: true });
  });

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

  it('loads persisted history on mount when enabled', async () => {
    (onboardingAssistantApi.getHistory as any).mockResolvedValue([
      { sender: 'user', message: 'hi' },
      { sender: 'ai', message: 'hello there' },
    ]);
    const { result } = renderHook(() => useOnboardingConversation(true));
    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(result.current.messages[1]).toMatchObject({ role: 'assistant', text: 'hello there' });
  });

  it('does NOT load history when disabled', async () => {
    const { result } = renderHook(() => useOnboardingConversation(false));
    // give any effects a chance to run
    await new Promise((r) => setTimeout(r, 0));
    expect(onboardingAssistantApi.getHistory).not.toHaveBeenCalled();
    expect(result.current.messages).toHaveLength(0);
  });

  it('persists both the user message and the AI turn on send', async () => {
    (onboardingAssistantApi.sendOnboardingMessage as any).mockResolvedValue({
      success: true,
      data: { response: 'done' },
    });
    const { result } = renderHook(() => useOnboardingConversation());
    await act(async () => { await result.current.send('do it'); });
    expect(onboardingAssistantApi.saveMessage).toHaveBeenCalledWith('do it', 'user');
    expect(onboardingAssistantApi.saveMessage).toHaveBeenCalledWith('done', 'ai');
  });
});
