import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { NotificationsTab } from '../NotificationsTab';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock('@/lib/api', () => ({
  settingsApi: {
    getSetting: vi.fn().mockResolvedValue({ value: {} }),
    getNotificationSettings: vi.fn().mockResolvedValue({
      user_created: false, user_updated: false, user_deleted: false, user_login: false,
      client_created: false, client_updated: false, client_deleted: false,
      invoice_created: false, invoice_updated: false, invoice_deleted: false,
      invoice_sent: false, invoice_paid: false, invoice_overdue: false,
      payment_created: false, payment_updated: false, payment_deleted: false,
      expense_created: false, expense_updated: false, expense_deleted: false,
      expense_approved: false, expense_rejected: false, expense_submitted: false,
      inventory_created: false, inventory_updated: false, inventory_deleted: false,
      inventory_low_stock: false, inventory_out_of_stock: false,
      statement_generated: false, statement_sent: false, statement_overdue: false,
      reminder_created: false, reminder_sent: false, reminder_overdue: false,
      settings_updated: false, notification_email: '',
      daily_summary: false, weekly_summary: false,
      anomaly_alert: true,
    }),
    updateSetting: vi.fn().mockResolvedValue({}),
    updateNotificationSettings: vi.fn().mockResolvedValue({}),
    testEmailConfiguration: vi.fn().mockResolvedValue({}),
    testNotification: vi.fn().mockResolvedValue({}),
  },
  getErrorMessage: (error: unknown) => String(error),
}));

vi.mock('@/utils/auth', () => ({
  getCurrentUser: () => ({ email: 'admin@example.com' }),
}));

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NotificationsTab isAdmin={true} />
    </QueryClientProvider>,
  );
}

describe('NotificationsTab anomaly toggle', () => {
  it('renders the anomaly/fraud alerts toggle', async () => {
    renderTab();
    expect(await screen.findByText(/anomaly.*fraud alerts/i)).toBeInTheDocument();
  });
});
