import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { InvoiceSettingsTab } from '../InvoiceSettingsTab';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const previewMock = vi.hoisted(() => vi.fn());

vi.mock('@/lib/api', async () => {
  const { DEFAULT_BRANDING } = await import('@/lib/invoice-branding');
  return {
    settingsApi: {
      getSettings: vi.fn().mockResolvedValue({
        invoice_settings: {}, invoice_branding: { ...DEFAULT_BRANDING }, company_info: { name: 'Acme', logo: '' },
      }),
      getClientPortalLink: vi.fn().mockResolvedValue({ enabled: false, portal_url: null, path: null }),
      updateSettings: vi.fn().mockResolvedValue({}),
      previewInvoiceTemplate: (...args: unknown[]) => previewMock(...args),
    },
  };
});

previewMock.mockResolvedValue('<html><body>preview</body></html>');

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <InvoiceSettingsTab isAdmin={true} />
    </QueryClientProvider>,
  );
}

describe('InvoiceSettingsTab template editor', () => {
  beforeEach(() => previewMock.mockClear());

  it('renders the font controls once settings load', async () => {
    renderTab();
    expect(await screen.findByText('settings.branding.font_serif')).toBeInTheDocument();
  });

  it('debounce-fetches the server preview', async () => {
    renderTab();
    await screen.findByText('settings.branding.font_serif');
    await waitFor(() => expect(previewMock).toHaveBeenCalled());
  });

  it('updates the draft and re-previews when a font is chosen', async () => {
    const user = userEvent.setup();
    renderTab();
    const serif = await screen.findByText('settings.branding.font_serif');
    previewMock.mockClear();
    await user.click(serif);
    await waitFor(() =>
      expect(previewMock).toHaveBeenCalledWith(expect.objectContaining({ font_family: 'serif' })),
    );
  });
});
