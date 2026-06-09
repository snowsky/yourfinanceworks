import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { TrendingUp, TrendingDown, ArrowRight, AlertTriangle } from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from 'recharts';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Skeleton } from '@/components/ui/skeleton';
import { useFeatures } from '@/contexts/FeatureContext';
import { cashflowApi } from '@/lib/api';

const fmt = (amount: number, currency = 'USD') => {
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${Math.round(amount).toLocaleString()}`;
  }
};

/**
 * Compact 30-day cash-flow forecast for the dashboard. Renders nothing when the
 * commercial cash_flow feature is not licensed.
 */
export function CashFlowForecastCard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isFeatureEnabled } = useFeatures();
  const enabled = isFeatureEnabled('cash_flow');

  // Currency lives on the cash-flow threshold settings (same source the
  // CashFlow page uses); share its query key so the cache is reused.
  const { data: thresholds } = useQuery({
    queryKey: ['cashflow-settings'],
    queryFn: () => cashflowApi.getThresholds(),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
  const currency = thresholds?.currency || 'USD';

  const { data, isLoading, isError } = useQuery({
    queryKey: ['cashflow', 'forecast', '30d'],
    queryFn: () => cashflowApi.getForecast('30d'),
    enabled,
    staleTime: 60_000,
  });

  if (!enabled || isError) return null;

  const positive = (data?.net_change ?? 0) >= 0;
  const chartData = (data?.daily_balances ?? []).map((d) => ({
    date: d.date,
    balance: Math.round(d.projected_balance),
  }));

  return (
    <ProfessionalCard variant="elevated" className="p-5 md:p-6" data-tour="dashboard-cashflow">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className={`p-3 rounded-xl ${positive ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
            {positive ? (
              <TrendingUp className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <TrendingDown className="h-6 w-6 text-red-600 dark:text-red-400" />
            )}
          </div>
          <div>
            <h3 className="text-lg font-bold">
              {t('dashboard.cashflow.title')}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t('dashboard.cashflow.subtitle')}
            </p>
          </div>
        </div>
        <ProfessionalButton variant="ghost" size="sm" onClick={() => navigate('/cashflow')}>
          {t('dashboard.cashflow.view')}
          <ArrowRight className="h-3 w-3" />
        </ProfessionalButton>
      </div>

      {isLoading ? (
        <div className="mt-4 space-y-3">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-muted-foreground">{t('dashboard.cashflow.end_balance')}</p>
              <p className="text-xl font-bold tabular-nums">{fmt(data?.projected_end_balance ?? 0, currency)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{t('dashboard.cashflow.net_change')}</p>
              <p className={`text-xl font-bold tabular-nums ${positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                {positive ? '+' : ''}{fmt(data?.net_change ?? 0, currency)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{t('dashboard.cashflow.inflows')}</p>
              <p className="text-base font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                {fmt(data?.total_projected_inflows ?? 0, currency)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{t('dashboard.cashflow.outflows')}</p>
              <p className="text-base font-semibold tabular-nums text-red-600 dark:text-red-400">
                {fmt(data?.total_projected_outflows ?? 0, currency)}
              </p>
            </div>
          </div>

          {chartData.length > 1 && (
            <div className="mt-4 h-28">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="cfGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={positive ? '#10b981' : '#ef4444'} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={positive ? '#10b981' : '#ef4444'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <YAxis hide domain={['dataMin', 'dataMax']} />
                  <Tooltip
                    formatter={(value: number) => [fmt(value, currency), t('dashboard.cashflow.balance')]}
                    labelFormatter={(label) => label}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="balance"
                    stroke={positive ? '#10b981' : '#ef4444'}
                    strokeWidth={2}
                    fill="url(#cfGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {(data?.alerts?.length ?? 0) > 0 && (
            <div className="mt-3 flex items-start gap-2 rounded-lg bg-amber-500/10 px-3 py-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
              <p className="text-sm text-amber-700 dark:text-amber-300">{data!.alerts[0]}</p>
            </div>
          )}
        </>
      )}
    </ProfessionalCard>
  );
}
