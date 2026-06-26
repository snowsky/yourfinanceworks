import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { InAppNotifications } from '../InAppNotifications';

// Mock the API the component fetches from so we can inject a notification.
vi.mock('@/lib/api', () => ({
  reminderApi: {
    getUnreadNotificationCount: vi.fn().mockResolvedValue({ count: 1 }),
    getRecentNotifications: vi.fn().mockResolvedValue({
      items: [
        {
          id: 1,
          notification_type: 'anomaly_alert',
          subject: 'High-risk anomaly on invoice #42',
          message: 'duplicate billing',
          is_read: false,
          scheduled_for: new Date().toISOString(),
        },
      ],
    }),
    markNotificationAsRead: vi.fn().mockResolvedValue({}),
    markAllNotificationsAsRead: vi.fn().mockResolvedValue({}),
    dismissNotification: vi.fn().mockResolvedValue({}),
  },
}));

describe('InAppNotifications anomaly routing', () => {
  beforeEach(() => {
    // jsdom: make window.location.href assignable and observable
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { href: '' },
    });
  });

  it('routes an anomaly_alert notification to the Slice-1 drawer', async () => {
    render(<InAppNotifications />);
    // Open the popover, then click the notification.
    fireEvent.click(await screen.findByRole('button'));
    const item = await screen.findByText(/duplicate billing/i);
    fireEvent.click(item);
    await waitFor(() => {
      expect(window.location.href).toBe('/anomalies?selected=42');
    });
  });
});
