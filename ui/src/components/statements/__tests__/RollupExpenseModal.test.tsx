import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { RollupExpenseModal } from '../RollupExpenseModal';
import { bankStatementApi, RollupPreview } from '@/lib/api/bank-statements';

vi.mock('@/lib/api/bank-statements', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/bank-statements')>(
    '@/lib/api/bank-statements'
  );
  return {
    ...actual,
    bankStatementApi: {
      getRollupPreview: vi.fn(),
      createRollupExpense: vi.fn(),
    },
  };
});

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const buildPreview = (overrides: Partial<RollupPreview> = {}): RollupPreview => ({
  statement_id: 1,
  count: 2,
  total: 30.5,
  currency: 'USD',
  latest_date: '2026-03-15T00:00:00Z',
  auto_labels: ['auto-imported', 'statement:march.pdf', 'Meals'],
  debits: [
    {
      transaction_id: 11,
      date: '2026-03-14T00:00:00Z',
      description: 'STARBUCKS',
      amount: 7.4,
      category: 'Meals',
      linked_expense_id: 42,
    },
    {
      transaction_id: 12,
      date: '2026-03-15T00:00:00Z',
      description: 'UBER',
      amount: 23.1,
      category: 'Transportation',
      linked_expense_id: null,
    },
  ],
  notes_preview: 'Bookkeeping rollup for statement: march.pdf\n---\n2026-03-14 | STARBUCKS | 7.40',
  existing_rollup_id: null,
  ...overrides,
});

describe('RollupExpenseModal', () => {
  const onClose = vi.fn();
  const onCreated = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders preview summary and per-debit rows with linked-expense badges', async () => {
    (bankStatementApi.getRollupPreview as any).mockResolvedValue(buildPreview());

    render(
      <RollupExpenseModal isOpen statementId={1} onClose={onClose} onCreated={onCreated} />
    );

    await waitFor(() => expect(screen.getByText('STARBUCKS')).toBeInTheDocument());

    expect(screen.getByText('2')).toBeInTheDocument(); // count
    expect(screen.getByText('USD 30.50')).toBeInTheDocument();
    expect(screen.getByText('linked #42')).toBeInTheDocument();
    expect(screen.getByText('UBER')).toBeInTheDocument();
    // Auto labels visible
    expect(screen.getByText('auto-imported')).toBeInTheDocument();
    expect(screen.getByText('statement:march.pdf')).toBeInTheDocument();
    expect(screen.getByText('Meals')).toBeInTheDocument();
  });

  it('lets the user add a tag and includes it in the submission payload', async () => {
    (bankStatementApi.getRollupPreview as any).mockResolvedValue(buildPreview());
    (bankStatementApi.createRollupExpense as any).mockResolvedValue({
      expense_id: 99,
      statement_id: 1,
      amount: 30.5,
      currency: 'USD',
      labels: ['auto-imported', 'statement:march.pdf', 'q1-trip'],
      debit_count: 2,
    });

    const user = userEvent.setup();
    render(
      <RollupExpenseModal isOpen statementId={1} onClose={onClose} onCreated={onCreated} />
    );
    await waitFor(() => expect(screen.getByText('STARBUCKS')).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText(/Add a tag/i), 'q1-trip');
    await user.click(screen.getByRole('button', { name: /^Add$/ }));
    await user.click(screen.getByRole('button', { name: /Create rollup expense/i }));

    await waitFor(() =>
      expect(bankStatementApi.createRollupExpense).toHaveBeenCalledWith(1, {
        user_tags: ['q1-trip'],
        replace: false,
      })
    );
    expect(onCreated).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('shows Open/Replace UI on 409 conflict and re-submits with replace=true', async () => {
    (bankStatementApi.getRollupPreview as any).mockResolvedValue(buildPreview());
    const conflictError = Object.assign(new Error('exists'), {
      status: 409,
      response: {
        status: 409,
        data: { detail: { message: 'already exists', existing_expense_id: 77 } },
      },
    });
    (bankStatementApi.createRollupExpense as any)
      .mockRejectedValueOnce(conflictError)
      .mockResolvedValueOnce({
        expense_id: 100,
        statement_id: 1,
        amount: 30.5,
        currency: 'USD',
        labels: [],
        debit_count: 2,
      });

    const onOpenExpense = vi.fn();
    const user = userEvent.setup();
    render(
      <RollupExpenseModal
        isOpen
        statementId={1}
        onClose={onClose}
        onCreated={onCreated}
        onOpenExpense={onOpenExpense}
      />
    );
    await waitFor(() => expect(screen.getByText('STARBUCKS')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /Create rollup expense/i }));
    await waitFor(() => expect(screen.getByText(/already exists/i)).toBeInTheDocument());
    expect(screen.getByText(/Existing rollup: Expense #77/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^Open$/i }));
    expect(onOpenExpense).toHaveBeenCalledWith(77);

    await user.click(screen.getByRole('button', { name: /^Replace$/i }));
    await waitFor(() =>
      expect(bankStatementApi.createRollupExpense).toHaveBeenLastCalledWith(1, {
        user_tags: [],
        replace: true,
      })
    );
  });

  it('shows existing rollup banner when preview reports existing_rollup_id', async () => {
    (bankStatementApi.getRollupPreview as any).mockResolvedValue(
      buildPreview({ existing_rollup_id: 55 })
    );

    render(
      <RollupExpenseModal isOpen statementId={1} onClose={onClose} onCreated={onCreated} />
    );

    await waitFor(() => expect(screen.getByText(/Existing rollup: Expense #55/)).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /Create rollup expense/i })).not.toBeInTheDocument();
  });

  it('disables submit when there are no debits', async () => {
    (bankStatementApi.getRollupPreview as any).mockResolvedValue(
      buildPreview({ count: 0, total: 0, debits: [], latest_date: null })
    );

    render(
      <RollupExpenseModal isOpen statementId={1} onClose={onClose} onCreated={onCreated} />
    );

    await waitFor(() =>
      expect(screen.getByText(/no debit transactions to roll up/i)).toBeInTheDocument()
    );
    expect(screen.getByRole('button', { name: /Create rollup expense/i })).toBeDisabled();
  });
});
