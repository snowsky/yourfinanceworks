import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { onboardingApi, type SampleDataStatus } from '@/lib/api';
import { Button } from '@/components/ui/button';

interface SampleDataBannerProps {
  onChanged?: () => void;
}

export function SampleDataBanner({ onChanged }: SampleDataBannerProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<SampleDataStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setStatus(await onboardingApi.getSampleDataStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const load = async () => {
    setBusy(true);
    try {
      await onboardingApi.seedSampleData();
      toast.success(t('onboarding.sample_loaded'));
      await refresh();
      onChanged?.();
    } catch (e: any) {
      toast.error(e?.message || t('onboarding.sample_load_failed'));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await onboardingApi.clearSampleData();
      toast.success(t('onboarding.sample_removed'));
      await refresh();
      onChanged?.();
    } catch (e: any) {
      toast.error(e?.message || t('onboarding.sample_remove_failed'));
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;

  if (!status.has_any_data) {
    return (
      <div className="flex items-center justify-between gap-4 rounded-xl border border-primary/30 bg-primary/5 p-4">
        <div>
          <p className="font-semibold">{t('onboarding.sample_title')}</p>
          <p className="text-sm text-muted-foreground">
            {t('onboarding.sample_body')}
          </p>
        </div>
        <Button onClick={load} disabled={busy}>
          {t('onboarding.sample_load')}
        </Button>
      </div>
    );
  }

  if (status.has_sample_data) {
    return (
      <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-muted/30 px-4 py-2 text-sm">
        <span className="text-muted-foreground">
          {t('onboarding.sample_viewing')}
        </span>
        <Button variant="ghost" size="sm" onClick={remove} disabled={busy}>
          {t('onboarding.sample_remove')}
        </Button>
      </div>
    );
  }

  return null;
}
