import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useFeatures } from '@/contexts/FeatureContext';
import { onboardingApi, onboardingAssistantApi, type AssistantStatus } from '@/lib/api/onboarding';
import { useOnboardingConversation } from './useOnboardingConversation';
import { ConfirmActionCard } from './ConfirmActionCard';

export function OnboardingAssistantCard() {
  const { isFeatureEnabled } = useFeatures();
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [hidden, setHidden] = useState(false);
  const [input, setInput] = useState('');
  const { messages, pendingAction, send, confirm, cancelPending, loading } = useOnboardingConversation();

  useEffect(() => {
    if (!isFeatureEnabled('ai_chat')) {
      setHidden(true);
      return;
    }
    Promise.all([onboardingAssistantApi.getAssistantStatus(), onboardingApi.getChecklist()])
      .then(([s, checklist]) => {
        if (s.dismissed || checklist.all_complete) setHidden(true);
        else setStatus(s);
      })
      .catch(() => setHidden(true));
  }, [isFeatureEnabled]);

  if (hidden || !status) return null;

  const dismiss = () => {
    setHidden(true);
    onboardingAssistantApi.dismissAssistant().catch(() => {});
  };

  if (!status.ai_configured) {
    return (
      <div className="rounded-lg border p-4 space-y-2" data-testid="onboarding-assistant-card">
        <div className="font-medium">Set up your AI provider first</div>
        <p className="text-sm text-muted-foreground">
          The setup assistant needs an AI provider. Add one to get guided, hands-on help.
        </p>
        <div className="flex gap-2">
          <Button asChild size="sm">
            <Link to="/settings?tab=ai-config">Configure AI provider</Link>
          </Button>
          <Button size="sm" variant="ghost" onClick={dismiss}>
            Dismiss
          </Button>
        </div>
      </div>
    );
  }

  const submit = (e: { preventDefault: () => void }) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput('');
    void send(text);
  };

  return (
    <div className="rounded-lg border p-4 space-y-3" data-testid="onboarding-assistant-card">
      <div className="flex items-center justify-between">
        <div className="font-medium">Let's get you set up</div>
        <Button size="sm" variant="ghost" onClick={dismiss}>
          Dismiss
        </Button>
      </div>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {messages.map((m) => (
          <div key={m.id} className={m.role === 'user' ? 'text-right text-sm' : 'text-sm'}>
            {m.text}
          </div>
        ))}
        {pendingAction && (
          <ConfirmActionCard action={pendingAction} onConfirm={confirm} onCancel={cancelPending} />
        )}
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <Input
          value={input}
          placeholder="Tell me what you'd like to set up…"
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <Button type="submit" size="sm" disabled={loading}>
          Send
        </Button>
      </form>
    </div>
  );
}
