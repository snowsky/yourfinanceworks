import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { ShieldCheck, Loader } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import type { OnboardingAction, ProposedAction } from '@/lib/api/onboarding';

const FIELDS: Record<string, { key: string; label: string; placeholder?: string }[]> = {
  create_client: [
    { key: 'name', label: 'Name' },
    { key: 'email', label: 'Email' },
  ],
  set_branding: [
    { key: 'brand_color', label: 'Brand color', placeholder: '#1e3a8a' },
    { key: 'accent_color', label: 'Accent color', placeholder: '#3b82f6' },
  ],
  create_invoice: [
    { key: 'client_id', label: 'Client ID' },
    { key: 'amount', label: 'Amount' },
    { key: 'due_date', label: 'Due date (YYYY-MM-DD)' },
  ],
  create_expense: [
    { key: 'amount', label: 'Amount' },
    { key: 'category', label: 'Category' },
    { key: 'vendor', label: 'Vendor' },
  ],
};

export function ConfirmActionCard({
  action,
  onConfirm,
  onCancel,
}: {
  action: ProposedAction;
  onConfirm: (a: OnboardingAction) => void | Promise<void>;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const configuredFields = FIELDS[action.action] ?? [];
  const fields = [...configuredFields, ...Object.keys(action.params)
    .filter(key => !configuredFields.some(field => field.key === key))
    .map(key => ({ key, label: key.replace(/_/g, ' '), placeholder: undefined }))];
  const submitting = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const confirm = async () => {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError('');
    try {
      await onConfirm({ action: action.action, params });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed');
      submitting.current = false;
      setBusy(false);
    }
  };
  const [params, setParams] = useState<Record<string, unknown>>({ ...action.params });

  return (
    <div className="overflow-hidden rounded-xl border border-primary/25 bg-card shadow-sm" data-testid="confirm-action-card">
      <div className="flex items-start gap-3 border-b border-primary/10 bg-primary/5 p-4">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
        <div>
          <h3 className="text-sm font-semibold">{t('aiAssistant.reviewAction')}: <span className="capitalize">{t(`aiAssistant.actions.${action.action}`, { defaultValue: action.action.replace(/_/g, ' ') })}</span></h3>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{t('aiAssistant.reviewHint')}</p>
        </div>
      </div>
      <div className="grid gap-3 p-4 sm:grid-cols-2">
      {fields.map((f) => (
        <label key={f.key} className="block space-y-1.5 text-xs font-medium text-muted-foreground">
          {t(`aiAssistant.fields.${f.key}`, { defaultValue: f.label })}
          <Input
            disabled={busy}
            value={Array.isArray(params[f.key]) ? (params[f.key] as unknown[]).join(', ') : String(params[f.key] ?? '')}
            placeholder={f.placeholder}
            onChange={(e) => setParams((p) => ({ ...p, [f.key]: Array.isArray(action.params[f.key]) ? e.target.value.split(',').map(value => value.trim()).filter(Boolean) : e.target.value }))}
          />
        </label>
      ))}
      </div>
      {error && <div role="alert" className="mx-4 mb-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>}
      <div className="flex flex-wrap items-center justify-end gap-2 border-t bg-muted/20 px-4 py-3">
        <Button size="sm" disabled={busy} onClick={confirm}>
          {busy && <Loader className="mr-2 h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
          {t(busy ? 'aiAssistant.applyingAction' : 'aiAssistant.confirmAction')}
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={onCancel}>
          {t('aiAssistant.cancelAction')}
        </Button>
      </div>
    </div>
  );
}
