import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { ShieldAlert, ShieldCheck, ArrowRight, X } from 'lucide-react';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useFeatures } from '@/contexts/FeatureContext';
import { anomaliesApi } from '@/lib/api';
import { RISK_BADGE, entityHref, entityLabel } from '@/lib/anomaly-ui';

/**
 * Tenant-facing summary of open anomalies/fraud flags, surfaced on the
 * dashboard. Renders nothing when the commercial feature is off, so tenants
 * without a license see no change.
 */
export function AnomalyInsightsCard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isFeatureEnabled } = useFeatures();
  const enabled = isFeatureEnabled('anomaly_detection');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['anomalies', 'dashboard'],
    queryFn: () => anomaliesApi.list({ limit: 4 }),
    enabled,
    staleTime: 60_000,
  });

  const dismiss = useMutation({
    mutationFn: (id: number) => anomaliesApi.dismiss(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies'] });
      toast.success(t('dashboard.anomalies.dismissed'));
    },
    onError: () => toast.error(t('dashboard.anomalies.dismiss_failed')),
  });

  if (!enabled || isError) return null;

  const total = data?.total ?? 0;
  const summary = data?.summary ?? { critical: 0, high: 0, medium: 0, low: 0 };
  const highRisk = (summary.critical ?? 0) + (summary.high ?? 0);
  const hasIssues = total > 0;

  return (
    <ProfessionalCard
      variant="elevated"
      className={`p-5 md:p-6 border ${
        hasIssues ? 'border-amber-500/30' : 'border-emerald-500/25'
      }`}
      data-tour="dashboard-anomalies"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div
            className={`p-3 rounded-xl ${
              hasIssues ? 'bg-amber-500/10' : 'bg-emerald-500/10'
            }`}
          >
            {hasIssues ? (
              <ShieldAlert className="h-6 w-6 text-amber-600 dark:text-amber-400" />
            ) : (
              <ShieldCheck className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
            )}
          </div>
          <div className="space-y-1">
            <h3 className="text-lg font-bold">
              {t('dashboard.anomalies.title')}
            </h3>
            {isLoading ? (
              <Skeleton className="h-4 w-48" />
            ) : hasIssues ? (
              <p className="text-sm text-muted-foreground">
                {t('dashboard.anomalies.flagged', {
                  count: total,
                })}
                {highRisk > 0 && (
                  <>
                    {' · '}
                    <span className="font-medium text-red-600 dark:text-red-400">
                      {t('dashboard.anomalies.high_risk', {
                        count: highRisk,
                      })}
                    </span>
                  </>
                )}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t(
                  'dashboard.anomalies.all_clear',
                  'No issues flagged on your recent invoices and expenses.'
                )}
              </p>
            )}
          </div>
        </div>

        {hasIssues && (
          <div className="flex flex-wrap items-center gap-2">
            {(['critical', 'high', 'medium', 'low'] as const)
              .filter((lvl) => (summary[lvl] ?? 0) > 0)
              .map((lvl) => (
                <Badge key={lvl} variant="outline" className={RISK_BADGE[lvl]}>
                  {summary[lvl]} {t(`dashboard.anomalies.level.${lvl}`, lvl)}
                </Badge>
              ))}
          </div>
        )}
      </div>

      {hasIssues && !isLoading && (
        <div className="mt-4 space-y-2 border-t pt-4">
          {(data?.items ?? []).map((a) => {
            const href = entityHref(a);
            return (
              <div
                key={a.id}
                className="flex items-center gap-2 rounded-lg bg-muted/30 px-3 py-2"
              >
                <button
                  type="button"
                  disabled={!href}
                  title={a.reason}
                  onClick={() => href && navigate(href)}
                  className={`flex flex-1 items-center justify-between gap-3 min-w-0 text-left ${
                    href ? 'hover:opacity-80 transition-opacity' : 'cursor-default'
                  }`}
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <Badge variant="outline" className={RISK_BADGE[a.risk_level] ?? ''}>
                      {t(`dashboard.anomalies.level.${a.risk_level}`, a.risk_level)}
                    </Badge>
                    <span className="truncate text-sm">{a.reason}</span>
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {entityLabel(a)}
                  </span>
                </button>
                <button
                  type="button"
                  title={t('dashboard.anomalies.dismiss')}
                  disabled={dismiss.isPending}
                  onClick={() => dismiss.mutate(a.id)}
                  className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors disabled:opacity-50"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })}
          <ProfessionalButton
            variant="ghost"
            size="sm"
            className="w-full"
            onClick={() => navigate('/anomalies')}
          >
            {total > (data?.items?.length ?? 0)
              ? t('dashboard.anomalies.view_all_count', {
                  count: total,
                })
              : t('dashboard.anomalies.view_all')}
            <ArrowRight className="h-3 w-3" />
          </ProfessionalButton>
        </div>
      )}
    </ProfessionalCard>
  );
}
