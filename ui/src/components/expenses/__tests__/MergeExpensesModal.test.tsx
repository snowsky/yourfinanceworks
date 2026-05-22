import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { MergeExpensesModal } from '../MergeExpensesModal';
import { expenseApi, MergePreviewResult } from '@/lib/api/expenses';

vi.mock('@/lib/api/expenses', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/expenses')>(
    '@/lib/api/expenses'
  );
  return {
    ...actual,
    expenseApi: {
      getMergePreview: vi.fn(),
      mergeExpenses: vi.fn(),
    },
  };
});

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

/** The global vitest setup stubs localStorage with no-op vi.fn()s. We need real
 *  round-trip behavior for the persistence tests, so swap in a per-test store. */
function installInMemoryLocalStorage(): void {
  const store = new Map<string, string>();
  Object.defineProperty(window, 'localStorage', {
    value: {
      getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
      setItem: (k: string, v: string) => {
        store.set(k, v);
      },
      removeItem: (k: string) => {
        store.delete(k);
      },
      clear: () => store.clear(),
      key: (i: number) => Array.from(store.keys())[i] ?? null,
      get length() {
        return store.size;
      },
    },
    writable: true,
    configurable: true,
  });
}

const buildPreview = (overrides: Partial<MergePreviewResult> = {}): MergePreviewResult => ({
  count: 2,
  total: 30.0,
  currency: 'USD',
  latest_date: '2026-03-15',
  category: 'Meals',
  vendor: 'STARBUCKS',
  labels: ['coffee', 'morning'],
  notes_preview: '### Merged expense\n\n| Source | Date | Vendor | Amount |',
  sources: [
    { id: 11, expense_date: '2026-03-14', vendor: 'STARBUCKS', amount: 7.4, category: 'Meals', currency: 'USD' },
    { id: 12, expense_date: '2026-03-15', vendor: 'STARBUCKS', amount: 22.6, category: 'Meals', currency: 'USD' },
  ],
  ...overrides,
});

describe('MergeExpensesModal', () => {
  const onClose = vi.fn();
  const onMerged = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    installInMemoryLocalStorage();
  });

  it('renders summary, source list, and auto-derived fields', async () => {
    (expenseApi.getMergePreview as any).mockResolvedValue(buildPreview());

    render(
      <MergeExpensesModal
        isOpen
        expenseIds={[11, 12]}
        onClose={onClose}
        onMerged={onMerged}
      />
    );

    await waitFor(() => expect(screen.getByText('USD 30.00')).toBeInTheDocument());
    expect(screen.getByText('2026-03-15')).toBeInTheDocument();
    // Source rows render with id badges
    expect(screen.getByText('#11')).toBeInTheDocument();
    expect(screen.getByText('#12')).toBeInTheDocument();
    // Auto-derived locked fields
    expect(screen.getAllByText('Meals').length).toBeGreaterThan(0);
    expect(screen.getAllByText('STARBUCKS').length).toBeGreaterThan(0);
    // Disposition picker
    expect(
      screen.getByText(/What should happen to the 2 source expenses\?/i)
    ).toBeInTheDocument();
  });

  it('shows the server error message when the preview is invalid (currency mismatch)', async () => {
    (expenseApi.getMergePreview as any).mockRejectedValue(
      Object.assign(new Error('mismatch'), {
        status: 400,
        response: {
          status: 400,
          data: {
            detail: { code: 'currency_mismatch', message: 'Cannot merge expenses with different currencies' },
          },
        },
      })
    );

    render(
      <MergeExpensesModal
        isOpen
        expenseIds={[11, 12]}
        onClose={onClose}
        onMerged={onMerged}
      />
    );

    await waitFor(() =>
      expect(screen.getByText(/Cannot merge expenses with different currencies/i)).toBeInTheDocument()
    );
    expect(screen.getByRole('button', { name: /Merge expenses/i })).toBeDisabled();
  });

  it('includes user_tags and notes_prefix in the submission payload', async () => {
    (expenseApi.getMergePreview as any).mockResolvedValue(buildPreview());
    (expenseApi.mergeExpenses as any).mockResolvedValue({
      expense_id: 99,
      amount: 30.0,
      currency: 'USD',
      labels: ['coffee', 'morning', 'q1-trip'],
      source_count: 2,
    });

    const user = userEvent.setup();
    render(
      <MergeExpensesModal
        isOpen
        expenseIds={[11, 12]}
        onClose={onClose}
        onMerged={onMerged}
      />
    );
    await waitFor(() => expect(screen.getByText('USD 30.00')).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText(/Add a tag/i), 'q1-trip');
    await user.click(screen.getByRole('button', { name: /^Add$/ }));
    await user.type(
      screen.getByPlaceholderText(/Why are these expenses being merged/i),
      'Coffee run on march 15'
    );

    await user.click(screen.getByRole('button', { name: /^Merge expenses$/ }));

    await waitFor(() =>
      expect(expenseApi.mergeExpenses).toHaveBeenCalledWith(
        expect.objectContaining({
          expense_ids: [11, 12],
          user_tags: ['q1-trip'],
          notes_prefix: 'Coffee run on march 15',
        })
      )
    );
    expect(onMerged).toHaveBeenCalledWith(expect.objectContaining({ expense_id: 99 }));
    expect(onClose).toHaveBeenCalled();
  });

  it('defaults to consolidate when localStorage has no preference', async () => {
    window.localStorage.removeItem('expense-merge-keep-sources');
    (expenseApi.getMergePreview as any).mockResolvedValue(buildPreview());

    render(
      <MergeExpensesModal
        isOpen
        expenseIds={[11, 12]}
        onClose={onClose}
        onMerged={onMerged}
      />
    );

    await waitFor(() => expect(screen.getByText('USD 30.00')).toBeInTheDocument());
    const consolidate = screen.getByRole('radio', { name: /Move sources to recycle bin/i });
    const keep = screen.getByRole('radio', { name: /Keep sources visible/i });
    expect(consolidate.getAttribute('aria-checked')).toBe('true');
    expect(keep.getAttribute('aria-checked')).toBe('false');
    // First preview call uses keep_sources=false
    expect(expenseApi.getMergePreview).toHaveBeenCalledWith(
      expect.objectContaining({ expense_ids: [11, 12], keep_sources: false })
    );
  });

  it('initial radio reflects localStorage="true"', async () => {
    window.localStorage.setItem('expense-merge-keep-sources', 'true');
    (expenseApi.getMergePreview as any).mockResolvedValue(buildPreview());

    render(
      <MergeExpensesModal
        isOpen
        expenseIds={[11, 12]}
        onClose={onClose}
        onMerged={onMerged}
      />
    );

    await waitFor(() => expect(screen.getByText('USD 30.00')).toBeInTheDocument());
    const keep = screen.getByRole('radio', { name: /Keep sources visible/i });
    expect(keep.getAttribute('aria-checked')).toBe('true');
    expect(expenseApi.getMergePreview).toHaveBeenCalledWith(
      expect.objectContaining({ keep_sources: true })
    );

    window.localStorage.removeItem('expense-merge-keep-sources');
  });

  it('selecting "Keep sources" sends keep_sources=true and persists to localStorage', async () => {
    window.localStorage.removeItem('expense-merge-keep-sources');
    (expenseApi.getMergePreview as any).mockResolvedValue(buildPreview());
    (expenseApi.mergeExpenses as any).mockResolvedValue({
      expense_id: 101,
      amount: 30.0,
      currency: 'USD',
      labels: ['coffee', 'morning'],
      source_count: 2,
    });

    const user = userEvent.setup();
    render(
      <MergeExpensesModal
        isOpen
        expenseIds={[11, 12]}
        onClose={onClose}
        onMerged={onMerged}
      />
    );
    await waitFor(() => expect(screen.getByText('USD 30.00')).toBeInTheDocument());

    await user.click(screen.getByRole('radio', { name: /Keep sources visible/i }));
    await user.click(screen.getByRole('button', { name: /^Merge expenses$/ }));

    await waitFor(() =>
      expect(expenseApi.mergeExpenses).toHaveBeenCalledWith(
        expect.objectContaining({ keep_sources: true })
      )
    );
    expect(window.localStorage.getItem('expense-merge-keep-sources')).toBe('true');

    window.localStorage.removeItem('expense-merge-keep-sources');
  });

  it('surfaces a 400 returned by /expenses/merge as an inline error', async () => {
    (expenseApi.getMergePreview as any).mockResolvedValue(buildPreview());
    (expenseApi.mergeExpenses as any).mockRejectedValue(
      Object.assign(new Error('boom'), {
        status: 400,
        response: {
          status: 400,
          data: {
            detail: { code: 'currency_mismatch', message: 'Cannot merge expenses with different currencies' },
          },
        },
      })
    );

    const user = userEvent.setup();
    render(
      <MergeExpensesModal
        isOpen
        expenseIds={[11, 12]}
        onClose={onClose}
        onMerged={onMerged}
      />
    );
    await waitFor(() => expect(screen.getByText('USD 30.00')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /^Merge expenses$/ }));

    await waitFor(() =>
      expect(screen.getByText(/different currencies/i)).toBeInTheDocument()
    );
    expect(onMerged).not.toHaveBeenCalled();
  });
});
