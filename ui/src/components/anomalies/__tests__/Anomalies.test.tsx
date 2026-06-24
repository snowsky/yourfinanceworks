import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Anomalies from '@/pages/Anomalies';

// Minimal stand-in for the real en.json strings the page/drawer look up
// without a literal fallback (e.g. `t('anomalies.confirm_real')`), plus the
// tab labels (the page passes the lowercase status as its fallback, but the
// real translation is capitalized).
const I18N_FIXTURES: Record<string, string> = {
  'anomalies.confirm_real': 'Confirm real',
  'anomalies.dismiss_false': 'False positive',
  'anomalies.tab.open': 'Open',
  'anomalies.tab.confirmed': 'Confirmed',
  'anomalies.tab.dismissed': 'Dismissed',
  'anomalies.status.open': 'Open',
  'anomalies.status.confirmed': 'Confirmed',
  'anomalies.status.dismissed': 'Dismissed',
};
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fb?: unknown) =>
      I18N_FIXTURES[key] ?? (typeof fb === 'string' ? fb : key),
  }),
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/components/FeatureGate', () => ({
  FeatureGate: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// vi.mock factories are hoisted above top-level const declarations, so the
// mocks used inside the factory below must be created via vi.hoisted().
const { listMock, resolveMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  resolveMock: vi.fn().mockResolvedValue({ id: 1, status: 'confirmed' }),
}));
vi.mock('@/lib/api', () => ({
  anomaliesApi: {
    list: (...a: unknown[]) => listMock(...a),
    get: vi.fn(),
    resolve: (...a: unknown[]) => resolveMock(...a),
  },
}));

const row = {
  id: 1, entity_type: 'invoice', entity_id: 9, risk_score: 80, risk_level: 'high',
  reason: 'Duplicate billing', rule_id: 'duplicate_billing', details: { amount: 100 },
  created_at: '2026-06-01T00:00:00Z', status: 'open', statement_id: null,
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/anomalies']}>
        <Anomalies />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Anomalies triage page', () => {
  beforeEach(() => {
    listMock.mockReset();
    listMock.mockResolvedValue({ total: 1, summary: {}, skip: 0, limit: 20, items: [row] });
    resolveMock.mockClear();
  });

  it('lists with the default open status filter', async () => {
    renderPage();
    await waitFor(() => expect(listMock).toHaveBeenCalledWith(expect.objectContaining({ status: 'open' })));
    expect(await screen.findByText('Duplicate billing')).toBeInTheDocument();
  });

  it('switches the status filter when a tab is clicked', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Duplicate billing');
    await user.click(screen.getByText('Confirmed'));
    await waitFor(() => expect(listMock).toHaveBeenCalledWith(expect.objectContaining({ status: 'confirmed' })));
  });

  it('opens the drawer and resolves as confirmed', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('Duplicate billing'));
    const confirm = await screen.findByText('Confirm real');
    await user.click(confirm);
    await waitFor(() => expect(resolveMock).toHaveBeenCalledWith(1, 'confirmed', undefined));
  });
});
