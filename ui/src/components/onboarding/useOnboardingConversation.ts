import { useState, useCallback } from 'react';
import {
  onboardingAssistantApi,
  type OnboardingAction,
  type ProposedAction,
} from '@/lib/api/onboarding';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

let _seq = 0;
const nextId = () => `m${_seq++}`;

export function useOnboardingConversation() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingAction, setPendingAction] = useState<ProposedAction | null>(null);
  const [loading, setLoading] = useState(false);

  const push = (role: ChatMessage['role'], text: string) =>
    setMessages((m) => [...m, { id: nextId(), role, text }]);

  const send = useCallback(async (text: string) => {
    push('user', text);
    setLoading(true);
    try {
      const res = await onboardingAssistantApi.sendOnboardingMessage({ message: text });
      const data = res?.data;
      if (data?.type === 'proposed_action') {
        setPendingAction(data as ProposedAction);
      } else if (data?.response) {
        push('assistant', data.response);
      } else if (res?.error) {
        push('assistant', res.error);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const confirm = useCallback(async (action: OnboardingAction) => {
    setLoading(true);
    try {
      const res = await onboardingAssistantApi.sendOnboardingMessage({ message: '', confirmed_action: action });
      setPendingAction(null);
      if (res?.data?.response) push('assistant', res.data.response);
      else if (res?.error) push('assistant', res.error);
    } finally {
      setLoading(false);
    }
  }, []);

  const cancelPending = useCallback(() => setPendingAction(null), []);

  return { messages, pendingAction, send, confirm, cancelPending, loading };
}
