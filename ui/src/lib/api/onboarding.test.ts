import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./_base', () => ({ apiRequest: vi.fn() }));
import { apiRequest } from './_base';
import { onboardingAssistantApi, onboardingAiSummary } from './onboarding';

describe('onboardingAssistantApi', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getAssistantStatus hits the status endpoint', async () => {
    (apiRequest as any).mockResolvedValue({ ai_configured: true, dismissed: false });
    const res = await onboardingAssistantApi.getAssistantStatus();
    expect(apiRequest).toHaveBeenCalledWith('/onboarding/assistant/status');
    expect(res.ai_configured).toBe(true);
  });

  it('sendOnboardingMessage posts to /ai/chat with onboarding mode', async () => {
    (apiRequest as any).mockResolvedValue({ success: true, data: {} });
    await onboardingAssistantApi.sendOnboardingMessage({ message: 'hi' });
    expect(apiRequest).toHaveBeenCalledWith('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ message: 'hi', mode: 'onboarding' }),
    });
  });

  it('sendOnboardingMessage forwards confirmed_action', async () => {
    (apiRequest as any).mockResolvedValue({ success: true, data: {} });
    const confirmed = { action: 'create_client', params: { name: 'Acme' } };
    await onboardingAssistantApi.sendOnboardingMessage({ message: '', confirmed_action: confirmed });
    expect(apiRequest).toHaveBeenCalledWith('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ message: '', mode: 'onboarding', confirmed_action: confirmed }),
    });
  });

  it('getHistory hits the shared chat-history endpoint', async () => {
    (apiRequest as any).mockResolvedValue([]);
    await onboardingAssistantApi.getHistory();
    expect(apiRequest).toHaveBeenCalledWith('/ai/chat/history?limit=20&offset=0');
  });

  it('saveMessage posts to the shared chat-message endpoint', async () => {
    (apiRequest as any).mockResolvedValue({ success: true });
    await onboardingAssistantApi.saveMessage('hello', 'user');
    expect(apiRequest).toHaveBeenCalledWith('/ai/chat/message', {
      method: 'POST',
      body: JSON.stringify({ message: 'hello', sender: 'user' }),
    });
  });
});

describe('onboardingAiSummary', () => {
  it('returns the response text when present', () => {
    expect(onboardingAiSummary({ response: '✅ Client created.' })).toBe('✅ Client created.');
  });
  it('summarizes a proposed action', () => {
    expect(onboardingAiSummary({ type: 'proposed_action', action: 'create_client' })).toMatch(/create client/i);
  });
  it('falls back for empty data', () => {
    expect(onboardingAiSummary({})).toMatch(/set up/i);
  });
});
