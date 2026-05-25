import { describe, expect, it } from 'vitest';

import {
  annualizedCost,
  cadenceLabel,
  formatCurrency,
  hasUnacknowledgedPriceChange,
  monthlyCost,
  priceChangePercent,
} from '../subscription-helpers';
import type { SubscriptionResponse } from '@/lib/api/subscriptions';

const baseSub: SubscriptionResponse = {
  id: 1,
  merchant_key: 'netflix',
  label: 'Netflix',
  amount: 15.99,
  last_amount: 15.99,
  currency: 'USD',
  cadence_days: 30,
  confidence: 0.85,
  first_seen_date: '2025-12-25',
  last_seen_date: '2026-04-25',
  next_expected_date: '2026-05-25',
  charge_count: 4,
  status: 'active',
  price_change_acknowledged: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-04-25T00:00:00Z',
};

describe('subscription-helpers', () => {
  it('labels common cadences', () => {
    expect(cadenceLabel(7)).toBe('Weekly');
    expect(cadenceLabel(30)).toBe('Monthly');
    expect(cadenceLabel(90)).toBe('Quarterly');
    expect(cadenceLabel(365)).toBe('Annually');
    expect(cadenceLabel(45)).toBe('Every 45 days');
  });

  it('formats currency with locale fallback', () => {
    expect(formatCurrency(15.99, 'USD')).toMatch(/15\.99/);
  });

  it('computes annual and monthly cost from cadence', () => {
    expect(annualizedCost(baseSub)).toBeCloseTo(15.99 * (365 / 30), 1);
    expect(monthlyCost(baseSub)).toBeCloseTo(15.99 * (30 / 30), 1);
  });

  it('returns null price change when amount unchanged', () => {
    expect(priceChangePercent(baseSub)).toBeNull();
  });

  it('computes price change percent on increase', () => {
    const bumped: SubscriptionResponse = {
      ...baseSub,
      amount: 17.99,
      last_amount: 15.99,
    };
    expect(priceChangePercent(bumped)).toBeCloseTo(((17.99 - 15.99) / 15.99) * 100, 2);
  });

  it('flags unacknowledged price change', () => {
    const bumped: SubscriptionResponse = {
      ...baseSub,
      amount: 17.99,
      last_amount: 15.99,
      price_change_acknowledged: false,
    };
    expect(hasUnacknowledgedPriceChange(bumped)).toBe(true);
  });

  it('hides acknowledged price changes', () => {
    const bumped: SubscriptionResponse = {
      ...baseSub,
      amount: 17.99,
      last_amount: 15.99,
      price_change_acknowledged: true,
    };
    expect(hasUnacknowledgedPriceChange(bumped)).toBe(false);
  });
});
