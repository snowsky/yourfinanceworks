import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { CalendarClock, ArrowRight } from 'lucide-react';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { invoiceApi, type PaymentForecastItem } from '@/lib/api';

const CONFIDENCE_BADGE: Record<string, string> = {
  high: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  medium: 'bg-primary/10 text-primary border-primary/25',
  low: 'bg-muted text-muted-foreground border-border',
  none: 'bg-muted text-muted-foreground border-border',
};

function fmtAmount(amount: number, currency: string) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);
  } catch {
    return `${currency} ${Math.round(amount).toLocaleString()}`;
  }
}

function whenLabel(item: PaymentForecastItem, t: TFunction): string {
  const d = item.expected_in_days;
  if (d <= 0) return t('dashboard.expected_payments.soon') as string;
  if (d === 1) return t('dashboard.expected_payments.tomorrow') as string;
  return t('dashboard.expected_payments.in_days', { count: d }) as string;
}

/**
 * Dashboard widget listing the outstanding invoices expected to be paid soonest,
 * using the payment-date forecast. Renders nothing when there are none.
 */
export function ExpectedPaymentsCard() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['invoices', 'payment-forecast'],
    queryFn: () => invoiceApi.getPaymentForecast(),
    staleTime: 5 * 60 * 1000,
  });

  if (isError) return null;
  if (!isLoading && (data?.count ?? 0) === 0) return null;

  const items = (data?.items ?? []).slice(0, 5);

  return (
    <ProfessionalCard variant="elevated" className="p-5 md:p-6" data-tour="dashboard-expected-payments">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-3 rounded-xl bg-primary/10">
            <CalendarClock className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-bold">
              {t('dashboard.expected_payments.title')}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t('dashboard.expected_payments.subtitle')}
            </p>
          </div>
        </div>
        <ProfessionalButton variant="ghost" size="sm" onClick={() => navigate('/invoices')}>
          {t('dashboard.expected_payments.view_all')}
          <ArrowRight className="h-3 w-3" />
        </ProfessionalButton>
      </div>

      <div className="mt-4 space-y-2">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)
        ) : (
          items.map((item) => (
            <button
              key={item.invoice_id}
              type="button"
              onClick={() => navigate(`/invoices/view/${item.invoice_id}`)}
              className="flex w-full items-center justify-between gap-3 rounded-lg bg-muted/30 px-3 py-2 text-left hover:bg-muted/60 transition-colors"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{item.number}</p>
                <p className="text-xs text-muted-foreground">{whenLabel(item, t)}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-sm font-semibold tabular-nums">{fmtAmount(item.amount, item.currency)}</span>
                {item.confidence !== 'none' && (
                  <Badge variant="outline" className={CONFIDENCE_BADGE[item.confidence]}>
                    {t(`dashboard.expected_payments.confidence.${item.confidence}`, item.confidence)}
                  </Badge>
                )}
              </div>
            </button>
          ))
        )}
      </div>
    </ProfessionalCard>
  );
}
