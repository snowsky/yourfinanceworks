import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import type { SubscriptionSummary } from '@/lib/api/subscriptions';

const listMock = vi.fn();
vi.mock('@/lib/api/subscriptions', () => ({
  subscriptionsApi: {
    list: (...args: unknown[]) => listMock(...args),
    scan: vi.fn(),
    updateStatus: vi.fn(),
    setCancelReminder: vi.fn(),
    acknowledgePriceChange: vi.fn(),
  },
}));

import SubscriptionsPage from '../Subscriptions';

const summary: SubscriptionSummary = {
  total_count: 1,
  active_count: 1,
  monthly_cost: 15.99,
  annual_cost: 191.88,
  next_charge_date: null,
  needs_review_count: 1,
  items: [
    {
      id: 1,
      merchant_key: 'netflix',
      label: 'Netflix',
      amount: 15.99,
      currency: 'USD',
      cadence_days: 30,
      confidence: 0.9,
      first_seen_date: '2025-01-01',
      last_seen_date: '2026-04-01',
      next_expected_date: '2026-05-01',
      charge_count: 12,
      status: 'active',
      price_change_acknowledged: false,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
      review_reason: 'lapsed',
      days_overdue: 44,
    },
  ],
};

beforeEach(() => {
  listMock.mockReset();
  listMock.mockResolvedValue(summary);
});

describe('Subscriptions needs-review surfacing', () => {
  it('shows the Needs review tile and a per-row reason badge', async () => {
    render(<SubscriptionsPage />);
    expect(await screen.findByText('Needs review')).toBeInTheDocument();
    expect(await screen.findByText('Possibly canceled')).toBeInTheDocument();
  });
});
