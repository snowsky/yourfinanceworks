import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, any>) => (opts?.defaultValue as string) ?? key,
  }),
}));

const api = vi.hoisted(() => ({
  scanReceipt: vi.fn(),
  createExpense: vi.fn(),
  uploadReceipt: vi.fn(),
}));
vi.mock('@/lib/api', () => ({ expenseApi: api }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { toast } from 'sonner';
import { ScanBillDialog } from './ScanBillDialog';

function pickFile() {
  const input = screen.getByLabelText(/receipt file/i) as HTMLInputElement;
  const file = new File(['x'], 'receipt.png', { type: 'image/png' });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

describe('ScanBillDialog', () => {
  beforeEach(() => {
    api.scanReceipt.mockReset();
    api.createExpense.mockReset();
    api.uploadReceipt.mockReset();
    (toast.success as any).mockClear();
    (toast.error as any).mockClear();
    api.createExpense.mockResolvedValue({ id: 42 });
    api.uploadReceipt.mockResolvedValue({});
  });

  function open() {
    render(<ScanBillDialog onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /scan a bill/i }));
  }

  it('pre-fills the form from extracted fields', async () => {
    api.scanReceipt.mockResolvedValue({ available: true, fields: { vendor: 'Acme', amount: 12.5 } });
    open();
    pickFile();
    await waitFor(() => expect(api.scanReceipt).toHaveBeenCalled());
    const vendor = await screen.findByLabelText(/vendor/i) as HTMLInputElement;
    expect(vendor.value).toBe('Acme');
    const amount = screen.getByLabelText(/amount/i) as HTMLInputElement;
    expect(amount.value).toBe('12.5');
  });

  it('shows the fallback notice when extraction is unavailable', async () => {
    api.scanReceipt.mockResolvedValue({ available: false, reason: 'no AI' });
    open();
    pickFile();
    expect(await screen.findByText(/couldn't read it automatically/i)).toBeInTheDocument();
    const amount = screen.getByLabelText(/amount/i) as HTMLInputElement;
    expect(amount.value).toBe('');
  });

  it('Save creates the expense then attaches the file', async () => {
    api.scanReceipt.mockResolvedValue({ available: true, fields: { vendor: 'Acme', amount: 12.5 } });
    open();
    const file = pickFile();
    await screen.findByLabelText(/vendor/i);
    fireEvent.click(screen.getByRole('button', { name: /^save expense$/i }));
    await waitFor(() => expect(api.createExpense).toHaveBeenCalled());
    const payload = api.createExpense.mock.calls[0][0];
    expect(payload.vendor).toBe('Acme');
    expect(payload.amount).toBe(12.5);
    await waitFor(() => expect(api.uploadReceipt).toHaveBeenCalledWith(42, file));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
  });

  it('Cancel persists nothing', async () => {
    api.scanReceipt.mockResolvedValue({ available: true, fields: { vendor: 'Acme', amount: 1 } });
    open();
    pickFile();
    await screen.findByLabelText(/vendor/i);
    fireEvent.click(screen.getByRole('button', { name: /^cancel$/i }));
    expect(api.createExpense).not.toHaveBeenCalled();
  });
});
