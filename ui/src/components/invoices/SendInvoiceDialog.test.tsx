import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, any>) => {
      let s = (opts?.defaultValue as string) ?? key;
      if (opts) for (const [k, v] of Object.entries(opts)) {
        if (k !== 'defaultValue') s = s.replace(`{{${k}}}`, String(v));
      }
      return s;
    },
  }),
}));
const apiRequest = vi.fn();
vi.mock('@/lib/api', () => ({ apiRequest: (...a: any[]) => apiRequest(...a) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { toast } from 'sonner';
import { SendInvoiceDialog } from './SendInvoiceDialog';

const baseInvoice = { id: 7, number: 'INV-7', status: 'draft', amount: 100, client_name: 'Acme', client_email: 'a@x.com' };

function openDialog() {
  fireEvent.click(screen.getByRole('button', { name: /send/i }));
}

describe('SendInvoiceDialog', () => {
  beforeEach(() => {
    apiRequest.mockReset();
    apiRequest.mockResolvedValue({});
    (toast.success as any).mockClear();
    (toast.error as any).mockClear();
  });

  it('shows the recipient and sends with send_copy', async () => {
    const onSent = vi.fn();
    render(<SendInvoiceDialog invoice={baseInvoice} settings={{ invoice_settings: { send_copy: true } }} onSent={onSent} />);
    openDialog();
    expect(screen.getByText(/a@x.com/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^send invoice$/i }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith('/email/send-invoice', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ invoice_id: 7, include_pdf: true, send_copy: true }),
    })));
    await waitFor(() => expect(onSent).toHaveBeenCalled());
  });

  it('blocks the send when approval is required', () => {
    render(<SendInvoiceDialog
      invoice={{ ...baseInvoice, status: 'pending_approval' }}
      settings={{ invoice_settings: { require_approval_before_send: true, approval_threshold_amount: 0 } }}
      onSent={vi.fn()} />);
    openDialog();
    expect(screen.getByText(/must be approved/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^send invoice$/i })).toBeDisabled();
  });

  it('treats a { success: false } response body as a failure', async () => {
    apiRequest.mockResolvedValue({ success: false, message: 'provider declined' });
    const onSent = vi.fn();
    render(<SendInvoiceDialog invoice={baseInvoice} settings={{ invoice_settings: { send_copy: true } }} onSent={onSent} />);
    openDialog();
    fireEvent.click(screen.getByRole('button', { name: /^send invoice$/i }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('provider declined'));
    expect(onSent).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });
});
