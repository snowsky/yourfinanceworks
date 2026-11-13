import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
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
    <div className="rounded-lg border p-3 space-y-2" data-testid="confirm-action-card">
      <div className="text-sm font-medium">Confirm: {action.action.replace('_', ' ')}</div>
      {fields.map((f) => (
        <label key={f.key} className="block text-xs">
          {f.label}
          <Input
            disabled={busy}
            value={Array.isArray(params[f.key]) ? (params[f.key] as unknown[]).join(', ') : String(params[f.key] ?? '')}
            placeholder={f.placeholder}
            onChange={(e) => setParams((p) => ({ ...p, [f.key]: Array.isArray(action.params[f.key]) ? e.target.value.split(',').map(value => value.trim()).filter(Boolean) : e.target.value }))}
          />
        </label>
      ))}
      <div role="alert">{error}</div>
      <div className="flex gap-2 pt-1">
        <Button size="sm" disabled={busy} onClick={confirm}>
          Confirm
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
