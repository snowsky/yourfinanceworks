import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('@/hooks/useCurrencyCache', () => ({
  fetchCurrenciesWithCache: vi.fn().mockResolvedValue({
    currencies: [
      { code: 'USD', symbol: '$', decimal_places: 2, is_active: true },
      { code: 'JPY', symbol: '¥', decimal_places: 0, is_active: true },
    ],
  }),
}));

import { CurrencyDisplay } from '../currency-display';

describe('CurrencyDisplay', () => {
  it('groups thousands and keeps the currency decimals', async () => {
    render(<CurrencyDisplay amount={84210.5} currency="USD" />);
    expect(await screen.findByText('$84,210.50')).toBeInTheDocument();
  });

  it('respects currencies without decimals', async () => {
    render(<CurrencyDisplay amount={1234567} currency="JPY" />);
    expect(await screen.findByText('¥1,234,567')).toBeInTheDocument();
  });

  it('shows the code when asked and treats missing amounts as zero', async () => {
    render(<CurrencyDisplay amount={null as unknown as number} currency="USD" showCode />);
    expect(await screen.findByText('$0.00 USD')).toBeInTheDocument();
  });
});
