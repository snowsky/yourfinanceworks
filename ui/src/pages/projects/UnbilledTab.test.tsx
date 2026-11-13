import { fireEvent, render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import i18n from '@/i18n';
import { UnbilledTab } from './ProjectDetailInternal';

const props = { unbilled: undefined, selectedIds: [], onToggleEntry: vi.fn(), onSelectAll: vi.fn(), isAllSelected: false, onInvoice: vi.fn(), isInvoicing: false, currency: 'USD' };
describe('unbilled request states', () => {
  it('shows a retryable error instead of an endless loading message', async () => {
    await i18n.changeLanguage('en');
    const retry = vi.fn();
    render(<UnbilledTab {...props} isError onRetry={retry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Unbilled items could not be loaded');
    expect(screen.queryByText(/Auditing unbilled/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(retry).toHaveBeenCalledOnce();
  });
  it('localizes the loading message on a fresh page', async () => {
    await i18n.changeLanguage('fr');
    render(<UnbilledTab {...props} isError={false} onRetry={vi.fn()} />);
    expect(screen.getByText('Chargement des éléments non facturés…')).toBeInTheDocument();
  });
});
