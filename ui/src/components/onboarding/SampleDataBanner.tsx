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
      toast.success(t('onboarding.sample_loaded', { defaultValue: 'Example data loaded.' }));
      await refresh();
      onChanged?.();
    } catch (e: any) {
      toast.error(e?.message || t('onboarding.sample_load_failed', { defaultValue: 'Could not load example data.' }));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await onboardingApi.clearSampleData();
      toast.success(t('onboarding.sample_removed', { defaultValue: 'Sample data removed.' }));
      await refresh();
      onChanged?.();
    } catch (e: any) {
      toast.error(e?.message || t('onboarding.sample_remove_failed', { defaultValue: 'Could not remove sample data.' }));
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;

  if (!status.has_any_data) {
    return (
      <div className="flex items-center justify-between gap-4 rounded-xl border border-primary/30 bg-primary/5 p-4">
        <div>
          <p className="font-semibold">{t('onboarding.sample_title', { defaultValue: 'New here?' })}</p>
          <p className="text-sm text-muted-foreground">
            {t('onboarding.sample_body', { defaultValue: 'Load example data to see how everything works. You can remove it anytime.' })}
          </p>
        </div>
        <Button onClick={load} disabled={busy}>
          {t('onboarding.sample_load', { defaultValue: 'Load example data' })}
        </Button>
      </div>
    );
  }

  if (status.has_sample_data) {
    return (
      <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-muted/30 px-4 py-2 text-sm">
        <span className="text-muted-foreground">
          {t('onboarding.sample_viewing', { defaultValue: "You're viewing sample data." })}
        </span>
        <Button variant="ghost" size="sm" onClick={remove} disabled={busy}>
          {t('onboarding.sample_remove', { defaultValue: 'Remove sample data' })}
        </Button>
      </div>
    );
  }

  return null;
}
