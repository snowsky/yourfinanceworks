import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// Stub the two heavy tab bodies so we test hub behavior in isolation.
vi.mock('@/pages/CashFlow', () => ({
  CashFlowTabContent: () => <div>CASHFLOW_BODY</div>,
}));
vi.mock('@/components/networth/NetWorthTabContent', () => ({
  NetWorthTabContent: () => <div>NETWORTH_BODY</div>,
}));

// Configurable feature flags.
const flags: Record<string, boolean> = { cash_flow: true, net_worth: true };
vi.mock('@/contexts/FeatureContext', () => ({
  useFeatures: () => ({ isFeatureEnabled: (f: string) => !!flags[f] }),
}));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (_k: string, o?: { defaultValue?: string }) => o?.defaultValue ?? _k }),
}));

import Finances from '../Finances';

const renderAt = (path: string) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Finances />
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

beforeEach(() => {
  flags.cash_flow = true;
  flags.net_worth = true;
});

describe('Finances hub', () => {
  it('shows both tabs, defaulting to Cash Flow', () => {
    renderAt('/finances');
    expect(screen.getByRole('tab', { name: 'Cash Flow' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Net Worth' })).toBeInTheDocument();
    expect(screen.getByText('CASHFLOW_BODY')).toBeInTheDocument();
  });

  it('deep-links to the Net Worth tab via ?tab=networth', () => {
    renderAt('/finances?tab=networth');
    expect(screen.getByText('NETWORTH_BODY')).toBeInTheDocument();
  });

  it('hides the Cash Flow tab when only net_worth is enabled', () => {
    flags.cash_flow = false;
    renderAt('/finances');
    expect(screen.queryByRole('tab', { name: 'Cash Flow' })).not.toBeInTheDocument();
    expect(screen.getByText('NETWORTH_BODY')).toBeInTheDocument();
  });
});
