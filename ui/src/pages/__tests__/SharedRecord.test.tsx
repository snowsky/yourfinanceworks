import './authTestSetup';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const mocks = vi.hoisted(() => {
  class ShareAccessRequiredError extends Error {
    requirement: unknown;
    constructor(requirement: unknown) {
      super('This shared link requires verification');
      this.requirement = requirement;
    }
  }
  return { getPublicRecord: vi.fn(), ShareAccessRequiredError };
});
vi.mock('@/lib/api/share-tokens', () => ({
  shareTokenApi: { getPublicRecord: mocks.getPublicRecord },
  ShareAccessRequiredError: mocks.ShareAccessRequiredError,
}));

import SharedRecord from '../SharedRecord';

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/shared/tok']}>
      <Routes>
        <Route path="/shared/:token" element={<SharedRecord />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  mocks.getPublicRecord.mockReset();
});

describe('Shared record page', () => {
  it('renders an expense with translated labels', async () => {
    mocks.getPublicRecord.mockResolvedValue({
      record_type: 'expense',
      amount: 12.5,
      currency: 'USD',
      category: 'Travel',
      expense_date: '2026-01-05',
      status: 'approved',
      vendor: 'Rail Co',
    });
    renderPage();
    expect(await screen.findByText('sharedRecord.types.expense')).toBeInTheDocument();
    for (const k of ['amount', 'category', 'date', 'status', 'vendor']) {
      expect(screen.getByText(`sharedRecord.fields.${k}`)).toBeInTheDocument();
    }
    expect(screen.getByText('Rail Co')).toBeInTheDocument();
    expect(screen.getByText('common.powered_by')).toBeInTheDocument();
    expect(screen.queryByText('Vendor')).not.toBeInTheDocument();
  });

  it('renders invoice line items and offers a CSV export', async () => {
    mocks.getPublicRecord.mockResolvedValue({
      record_type: 'invoice',
      number: 'INV-9',
      status: 'sent',
      currency: 'USD',
      subtotal: 100,
      amount: 100,
      discount_value: 0,
      items: [{ description: 'Design work', quantity: 2, price: 50, amount: 100 }],
    });
    renderPage();
    expect(await screen.findByText('Design work')).toBeInTheDocument();
    expect(screen.getByText('sharedRecord.lineItems')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'sharedRecord.fields.qty' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'sharedRecord.exportCsv' })).toBeInTheDocument();
  });

  it('falls back to a generic title for an unknown record type', async () => {
    mocks.getPublicRecord.mockResolvedValue({ record_type: 'mystery' });
    renderPage();
    expect(await screen.findByText('sharedRecord.types.record')).toBeInTheDocument();
  });

  it('asks for the password, then shows the record', async () => {
    mocks.getPublicRecord.mockRejectedValueOnce(
      new mocks.ShareAccessRequiredError({ code: 'share_access_required', access_type: 'password' }),
    );
    renderPage();
    const input = await screen.findByLabelText('sharedRecord.verification.password');
    const submit = screen.getByRole('button', { name: 'sharedRecord.verification.submit' });
    expect(submit).toBeDisabled();

    mocks.getPublicRecord.mockResolvedValueOnce({ record_type: 'client', name: 'Zed', created_at: '2026-01-01' });
    fireEvent.change(input, { target: { value: 's3cret' } });
    fireEvent.click(submit);
    expect(await screen.findByText('Zed')).toBeInTheDocument();
    expect(mocks.getPublicRecord).toHaveBeenLastCalledWith('tok', { password: 's3cret', security_answer: undefined });
  });

  it('shows the security question when one is set', async () => {
    mocks.getPublicRecord.mockRejectedValue(
      new mocks.ShareAccessRequiredError({
        code: 'share_access_required',
        access_type: 'question',
        security_question: 'First pet?',
      }),
    );
    renderPage();
    expect(await screen.findByLabelText('First pet?')).toBeInTheDocument();
  });

  it('announces a dead link', async () => {
    mocks.getPublicRecord.mockRejectedValue(new Error('Link not found'));
    renderPage();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Link not found');
    expect(alert).toHaveTextContent('sharedRecord.linkHint');
  });
});
