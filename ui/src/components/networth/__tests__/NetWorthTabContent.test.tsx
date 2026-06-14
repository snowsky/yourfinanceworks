import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import type { NetWorthSummaryResponse, HistoryResponse } from '@/lib/api/networth';

const summary: NetWorthSummaryResponse = {
  snapshot_date: '2026-06-01',
  total_assets: 130000,
  total_liabilities: 12000,
  net_worth: 118000,
  bank_total: 42000,
  investment_total: 88000,
  liability_total: 12000,
  accounts: [
    { account_kind: 'investment', label: 'Brokerage', balance: 88000, currency: 'USD' },
    { account_kind: 'bank', label: 'Chase Checking', balance: 42000, currency: 'USD' },
    { account_kind: 'liability', label: 'Visa', balance: 12000, currency: 'USD' },
  ],
};
const history: HistoryResponse = {
  points: [
    { snapshot_date: '2026-05-01', total_assets: 120000, total_liabilities: 12000, net_worth: 108000 },
    { snapshot_date: '2026-06-01', total_assets: 130000, total_liabilities: 12000, net_worth: 118000 },
  ],
};

vi.mock('@/lib/api/networth', () => ({
  networthApi: {
    summary: () => Promise.resolve(summary),
    history: () => Promise.resolve(history),
    listLiabilities: () => Promise.resolve([
      { id: 1, name: 'Visa', kind: 'credit_card', balance: 12000, currency: 'USD',
        interest_rate: 19.9, notes: null, created_at: '', updated_at: '' },
    ]),
    snapshot: vi.fn(),
    deleteLiability: vi.fn(),
  },
}));

import { NetWorthTabContent } from '../NetWorthTabContent';

beforeEach(() => {});

describe('NetWorthTabContent', () => {
  it('renders the per-account breakdown, delta, and liabilities section', async () => {
    render(<NetWorthTabContent />);
    expect(await screen.findByText('Brokerage')).toBeInTheDocument();
    expect(await screen.findByText('Chase Checking')).toBeInTheDocument();
    expect(screen.getByText('Investments')).toBeInTheDocument();
    expect(screen.getByText('Accounts')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /snapshot now/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /add liability/i })).toBeInTheDocument();
  });
});
