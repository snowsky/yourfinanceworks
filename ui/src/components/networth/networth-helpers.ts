import type { HistoryPointResponse } from '@/lib/api/networth';

export const formatCurrency = (
  amount: number,
  currency: string = 'USD',
): string => {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `$${amount.toFixed(0)}`;
  }
};

export interface DeltaInfo {
  delta: number;
  pct: number | null;
  direction: 'up' | 'down' | 'flat';
}

export const monthOverMonthDelta = (
  points: HistoryPointResponse[],
): DeltaInfo => {
  if (points.length < 2) {
    return { delta: 0, pct: null, direction: 'flat' };
  }
  const latest = points[points.length - 1].net_worth;
  const previous = points[points.length - 2].net_worth;
  const delta = latest - previous;
  const pct = previous !== 0 ? (delta / Math.abs(previous)) * 100 : null;
  const direction = delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';
  return { delta, pct, direction };
};

export const KIND_LABELS: Record<string, string> = {
  credit_card: 'Credit Card',
  loan: 'Loan',
  mortgage: 'Mortgage',
  other: 'Other',
};
