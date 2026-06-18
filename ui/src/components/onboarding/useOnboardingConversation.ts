import { useState, useCallback, useEffect, useRef } from 'react';
import {
  onboardingAssistantApi,
  onboardingAiSummary,
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

/**
 * @param enabled When false, the hook does NOT touch the network on mount. This
 * gates the shared-history load so it only happens when the onboarding card is
 * actually shown — avoiding an ungated /ai/chat/history call (a write-path that
 * purges old rows) on every dashboard load for every user.
 */
export function useOnboardingConversation(enabled: boolean = true) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingAction, setPendingAction] = useState<ProposedAction | null>(null);
  const [loading, setLoading] = useState(false);
  const historyLoaded = useRef(false);

  const push = (role: ChatMessage['role'], text: string) =>
    setMessages((m) => [...m, { id: nextId(), role, text }]);

  // Onboarding shares the assistant's persisted history — hydrate once, only
  // when the card is actually shown (enabled).
  useEffect(() => {
    if (!enabled || historyLoaded.current) return;
    historyLoaded.current = true;
    let active = true;
    onboardingAssistantApi
      .getHistory()
      .then((items) => {
        if (!active || !Array.isArray(items)) return;
        setMessages(
          items.map((it, i) => ({
            id: `h${i}`,
            role: it.sender === 'ai' ? 'assistant' : 'user',
            text: it.message,
          })),
        );
      })
      .catch(() => {
        historyLoaded.current = false; // allow a retry on next enable
      });
    return () => {
      active = false;
    };
  }, [enabled]);

  const send = useCallback(async (text: string) => {
    push('user', text);
    void onboardingAssistantApi.saveMessage(text, 'user');
    setLoading(true);
    try {
      const res = await onboardingAssistantApi.sendOnboardingMessage({ message: text });
      const data = res?.data;
      const aiText = res?.error ?? onboardingAiSummary(data);
      if (data?.type === 'proposed_action') {
        setPendingAction(data as ProposedAction);
      } else {
        push('assistant', aiText);
      }
      void onboardingAssistantApi.saveMessage(aiText, 'ai');
    } finally {
      setLoading(false);
    }
  }, []);

  const confirm = useCallback(async (action: OnboardingAction) => {
    setLoading(true);
    try {
      const res = await onboardingAssistantApi.sendOnboardingMessage({ message: '', confirmed_action: action });
      setPendingAction(null);
      const aiText = res?.data?.response ?? res?.error ?? 'Done.';
      push('assistant', aiText);
      void onboardingAssistantApi.saveMessage(aiText, 'ai');
    } finally {
      setLoading(false);
    }
  }, []);

  const cancelPending = useCallback(() => setPendingAction(null), []);

  return { messages, pendingAction, send, confirm, cancelPending, loading };
}
