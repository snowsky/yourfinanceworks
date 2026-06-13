import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Circle } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { onboardingApi, type ChecklistStatus } from '@/lib/api';
import { Button } from '@/components/ui/button';

interface StepMeta {
  i18nKey: string;
  defaultLabel: string;
  to: string;
}

// key -> label + deep-link. Keeping this here keeps the API contract (keys) and the
// presentation (labels/links) in one place. Order is driven by the API response.
const STEP_META: Record<string, StepMeta> = {
  add_client: {
    i18nKey: 'onboarding.checklist_step_add_client',
    defaultLabel: 'Add your first client',
    to: '/clients/new',
  },
  create_invoice: {
    i18nKey: 'onboarding.checklist_step_create_invoice',
    defaultLabel: 'Create your first invoice',
    to: '/invoices/new',
  },
  record_expense: {
    i18nKey: 'onboarding.checklist_step_record_expense',
    defaultLabel: 'Record your first expense',
    to: '/expenses/new',
  },
  customize_branding: {
    i18nKey: 'onboarding.checklist_step_customize_branding',
    defaultLabel: 'Customize your invoice branding',
    to: '/settings',
  },
  send_invoice: {
    i18nKey: 'onboarding.checklist_step_send_invoice',
    defaultLabel: 'Send an invoice to a client',
    to: '/invoices',
  },
};

export function OnboardingChecklist() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ChecklistStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    onboardingApi
      .getChecklist()
      .then((s) => {
        if (active) setStatus(s);
      })
      .catch(() => {
        if (active) setStatus(null);
      });
    return () => {
      active = false;
    };
  }, []);

  if (!status || dismissed || status.dismissed || status.all_complete) return null;

  const dismiss = async () => {
    setBusy(true);
    try {
      await onboardingApi.dismissChecklist();
      setDismissed(true);
    } catch (e: any) {
      toast.error(
        e?.message ||
          t('onboarding.checklist_dismiss_failed', {
            defaultValue: 'Could not dismiss the checklist.',
          }),
      );
    } finally {
      setBusy(false);
    }
  };

  const pct = status.total > 0 ? Math.round((status.completed / status.total) * 100) : 0;

  return (
    <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-3">
      <div className="flex items-center justify-between gap-4">
        <p className="font-semibold">
          {t('onboarding.checklist_title', {
            completed: status.completed,
            total: status.total,
            defaultValue: 'Get started — {{completed}} of {{total}} done',
          })}
        </p>
        <Button variant="ghost" size="sm" onClick={dismiss} disabled={busy}>
          {t('onboarding.checklist_dismiss', { defaultValue: 'Dismiss' })}
        </Button>
      </div>

      <div
        role="progressbar"
        aria-valuenow={status.completed}
        aria-valuemin={0}
        aria-valuemax={status.total}
        aria-label={t('onboarding.checklist_title', {
          completed: status.completed,
          total: status.total,
          defaultValue: 'Get started — {{completed}} of {{total}} done',
        })}
        className="h-1.5 w-full rounded-full bg-muted"
      >
        <div className="h-1.5 rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>

      <ul className="space-y-1.5">
        {status.steps.map((step) => {
          const meta = STEP_META[step.key];
          if (!meta) return null;
          const label = t(meta.i18nKey, { defaultValue: meta.defaultLabel });
          const icon = step.done ? (
            <Check aria-hidden="true" className="h-4 w-4 text-primary shrink-0" />
          ) : (
            <Circle aria-hidden="true" className="h-4 w-4 text-muted-foreground shrink-0" />
          );
          return (
            <li key={step.key} className="flex items-center gap-2 text-sm">
              {icon}
              {step.done ? (
                <span className="text-muted-foreground line-through">{label}</span>
              ) : (
                <Link to={meta.to} className="text-foreground hover:underline">
                  {label}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
