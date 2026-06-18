import { useState } from 'react';
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
  onConfirm: (a: OnboardingAction) => void;
  onCancel: () => void;
}) {
  const fields = FIELDS[action.action] ?? [];
  const [params, setParams] = useState<Record<string, unknown>>({ ...action.params });

  return (
    <div className="rounded-lg border p-3 space-y-2" data-testid="confirm-action-card">
      <div className="text-sm font-medium">Confirm: {action.action.replace('_', ' ')}</div>
      {fields.map((f) => (
        <label key={f.key} className="block text-xs">
          {f.label}
          <Input
            value={String(params[f.key] ?? '')}
            placeholder={f.placeholder}
            onChange={(e) => setParams((p) => ({ ...p, [f.key]: e.target.value }))}
          />
        </label>
      ))}
      <div className="flex gap-2 pt-1">
        <Button size="sm" onClick={() => onConfirm({ action: action.action, params })}>
          Confirm
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
