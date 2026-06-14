import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { FinancesTabIntro } from '../FinancesTabIntro';

// The test harness (src/test/setup.ts) mocks window.localStorage with vi.fn()s
// (getItem -> null, setItem -> no-op). We drive those mocks here.

const props = {
  storageKey: 'finances_intro_test',
  title: "What's in Cash Flow",
  description: 'Projects money in and out.',
  sources: ['Unpaid invoices', 'Recorded expenses', 'Bank patterns'],
  output: 'Forecast, runway & scenario planning',
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(window.localStorage.getItem).mockReturnValue(null);
});

describe('FinancesTabIntro', () => {
  it('renders the title, each source, and the output when not dismissed', () => {
    render(<FinancesTabIntro {...props} />);
    expect(screen.getByText("What's in Cash Flow")).toBeInTheDocument();
    expect(screen.getByText('Unpaid invoices')).toBeInTheDocument();
    expect(screen.getByText('Recorded expenses')).toBeInTheDocument();
    expect(screen.getByText('Bank patterns')).toBeInTheDocument();
    expect(screen.getByText(/Forecast, runway/)).toBeInTheDocument();
  });

  it('dismisses on × click and persists the dismissal', () => {
    render(<FinancesTabIntro {...props} />);
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByText("What's in Cash Flow")).not.toBeInTheDocument();
    expect(window.localStorage.setItem).toHaveBeenCalledWith(
      'finances_intro_test',
      'true',
    );
  });

  it('renders nothing when already dismissed', () => {
    vi.mocked(window.localStorage.getItem).mockReturnValue('true');
    const { container } = render(<FinancesTabIntro {...props} />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText("What's in Cash Flow")).not.toBeInTheDocument();
  });
});
