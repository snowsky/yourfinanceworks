import './authTestSetup';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('@/lib/api/bank-statements', () => ({ bankStatementApi: { delete: vi.fn() } }));

import { DuplicateStatementPanel } from '../Statements/DuplicateStatementPanel';
import { DuplicateTransactionPanel } from '../Statements/DuplicateTransactionPanel';

const wrap = (ui: React.ReactElement) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

const FILES = [
  [
    { id: 1, original_filename: 'jan.pdf', extracted_count: 1, created_at: null, status: 'processed' },
    { id: 2, original_filename: 'jan-copy.pdf', extracted_count: 3, created_at: null, status: 'processed' },
  ],
] as never;

const TXNS = [
  [
    { id: 1, statement_id: 10, statement_filename: 'a.pdf', date: '2026-01-02', description: 'Coffee', amount: 4.5 },
    { id: 2, statement_id: 11, statement_filename: 'b.pdf', date: '2026-01-02', description: 'Coffee', amount: 4.5 },
  ],
] as never;

describe('DuplicateStatementPanel', () => {
  it('shows translated summary and expands to the group', () => {
    wrap(<DuplicateStatementPanel groups={FILES} onViewStatement={vi.fn()} />);
    expect(screen.getByText(/statements\.duplicateFiles\.detectedOne/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { expanded: false }));
    expect(screen.getByText('statements.duplicateFiles.clickToHide')).toBeTruthy();
    expect(screen.getByText('statements.duplicateFiles.deleteDuplicate')).toBeTruthy();
  });

  it('opens the delete dialog with translated actions and a confirm step', () => {
    wrap(<DuplicateStatementPanel groups={FILES} onViewStatement={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { expanded: false }));
    fireEvent.click(screen.getByText('statements.duplicateFiles.deleteDuplicate'));
    expect(screen.getByText('statements.duplicateFiles.removeTitle')).toBeTruthy();
    expect(screen.getByText('statements.duplicateFiles.keep')).toBeTruthy();
    fireEvent.click(screen.getByText('statements.duplicateFiles.deleteCountOne'));
    expect(screen.getByText('statements.duplicateFiles.moveToBin')).toBeTruthy();
    fireEvent.click(screen.getByText('statements.duplicateFiles.back'));
    expect(screen.getByText('statements.duplicateFiles.deleteCountOne')).toBeTruthy();
  });
});

describe('DuplicateTransactionPanel', () => {
  it('shows the translated summary, bulk button and per-group action', () => {
    wrap(<DuplicateTransactionPanel groups={TXNS} onViewTransaction={vi.fn()} />);
    expect(screen.getByText(/statements\.duplicateTransactions\.detectedOne/)).toBeTruthy();
    expect(screen.getByTitle('statements.duplicateTransactions.reviewAllTitle')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { expanded: false }));
    expect(screen.getByTitle('statements.duplicateTransactions.reviewDeleteTitle')).toBeTruthy();
  });

  it('reviews a group and walks to the confirm step', () => {
    wrap(<DuplicateTransactionPanel groups={TXNS} onViewTransaction={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { expanded: false }));
    fireEvent.click(screen.getByTitle('statements.duplicateTransactions.reviewDeleteTitle'));
    expect(screen.getByText('statements.duplicateTransactions.reviewGroup')).toBeTruthy();
    fireEvent.click(screen.getByText('statements.duplicateTransactions.deleteCountOne'));
    expect(screen.getByText('statements.duplicateTransactions.moveToBinBodyOne')).toBeTruthy();
    expect(screen.getByText('statements.duplicateFiles.confirm')).toBeTruthy();
  });
});
