import type { SubscriptionResponse } from '@/lib/api/subscriptions';

export const cadenceLabel = (days: number): string => {
  if (days === 7) return 'Weekly';
  if (days === 14) return 'Every 2 weeks';
  if (days === 30) return 'Monthly';
  if (days === 90) return 'Quarterly';
  if (days === 365) return 'Annually';
  return `Every ${days} days`;
};

export const formatCurrency = (amount: number, currency = 'USD'): string => {
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
};

export const annualizedCost = (sub: SubscriptionResponse): number => {
  if (!sub.cadence_days) return 0;
  return sub.amount * (365 / sub.cadence_days);
};

export const monthlyCost = (sub: SubscriptionResponse): number => {
  if (!sub.cadence_days) return 0;
  return sub.amount * (30 / sub.cadence_days);
};

export const priceChangePercent = (sub: SubscriptionResponse): number | null => {
  if (sub.last_amount == null || sub.last_amount === sub.amount) return null;
  const baseline = sub.last_amount;
  if (baseline === 0) return null;
  return ((sub.amount - baseline) / baseline) * 100;
};

export const hasUnacknowledgedPriceChange = (sub: SubscriptionResponse): boolean =>
  !!sub.last_amount &&
  sub.last_amount !== sub.amount &&
  !sub.price_change_acknowledged;
