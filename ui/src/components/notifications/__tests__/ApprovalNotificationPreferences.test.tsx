import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import ApprovalNotificationPreferences from '../ApprovalNotificationPreferences';
import { api } from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

const mockPreferences = {
  approval_notification_frequency: 'immediate',
  approval_reminder_frequency: 'daily',
  approval_notification_channels: ['email'],
  approval_events: {
    expense_submitted_for_approval: true,
    expense_approved: true,
    expense_rejected: true,
    expense_level_approved: true,
    expense_fully_approved: true,
    expense_auto_approved: true,
    approval_reminder: true,
    approval_escalation: true,
  },
};

describe('ApprovalNotificationPreferences', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    (api.get as any).mockImplementation(() => new Promise(() => {})); // Never resolves
    
    render(<ApprovalNotificationPreferences />);
    
    expect(screen.getByText('Loading notification preferences...')).toBeInTheDocument();
  });

  it('renders preferences after loading', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    expect(screen.getByText('Notification Frequency')).toBeInTheDocument();
    expect(screen.getByText('Notification Channels')).toBeInTheDocument();
    expect(screen.getByText('Event Notifications')).toBeInTheDocument();
  });

  it('displays current frequency settings', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Immediate - Send notifications as events occur')).toBeInTheDocument();
      expect(screen.getByText('Daily - Send reminders daily')).toBeInTheDocument();
    });
  });

  it('displays current channel settings', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      const emailCheckbox = screen.getByLabelText(/Email notifications/);
      const inAppCheckbox = screen.getByLabelText(/In-app notifications/);
      
      expect(emailCheckbox).toBeChecked();
      expect(inAppCheckbox).not.toBeChecked();
    });
  });

  it('displays current event settings', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      const expenseSubmittedSwitch = screen.getByLabelText('Expense submitted for approval');
      const expenseApprovedSwitch = screen.getByLabelText('Expense approved');
      
      expect(expenseSubmittedSwitch).toBeChecked();
      expect(expenseApprovedSwitch).toBeChecked();
    });
  });

  it('updates notification frequency', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    (api.put as any).mockResolvedValue({ data: { message: 'Success' } });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    // Change frequency to daily digest
    const frequencySelect = screen.getByText('Immediate - Send notifications as events occur');
    fireEvent.click(frequencySelect);
    
    const dailyDigestOption = screen.getByText('Daily Digest - Send a summary once per day');
    fireEvent.click(dailyDigestOption);
    
    // Save preferences
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/notifications/approval-preferences', 
        expect.objectContaining({
          approval_notification_frequency: 'daily_digest'
        })
      );
    });
  });

  it('updates notification channels', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    (api.put as any).mockResolvedValue({ data: { message: 'Success' } });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    // Enable in-app notifications
    const inAppCheckbox = screen.getByLabelText(/In-app notifications/);
    fireEvent.click(inAppCheckbox);
    
    // Save preferences
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/notifications/approval-preferences', 
        expect.objectContaining({
          approval_notification_channels: ['email', 'in_app']
        })
      );
    });
  });

  it('prevents disabling all channels', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    // Try to disable email (the only enabled channel)
    const emailCheckbox = screen.getByLabelText(/Email notifications/);
    fireEvent.click(emailCheckbox);
    
    // Email should still be checked (prevented from unchecking)
    expect(emailCheckbox).toBeChecked();
  });

  it('updates event preferences', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    (api.put as any).mockResolvedValue({ data: { message: 'Success' } });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    // Disable expense submitted notifications
    const expenseSubmittedSwitch = screen.getByLabelText('Expense submitted for approval');
    fireEvent.click(expenseSubmittedSwitch);
    
    // Save preferences
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/notifications/approval-preferences', 
        expect.objectContaining({
          approval_events: expect.objectContaining({
            expense_submitted_for_approval: false
          })
        })
      );
    });
  });

  it('sends test digest', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    (api.post as any).mockResolvedValue({ data: { message: 'Test digest sent successfully! Check your email.' } });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    const testDigestButton = screen.getByText('Send Test Digest');
    fireEvent.click(testDigestButton);
    
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/notifications/send-digest');
      expect(screen.getByText('Test digest sent successfully! Check your email.')).toBeInTheDocument();
    });
  });

  it('displays error message on API failure', async () => {
    (api.get as any).mockRejectedValue(new Error('API Error'));
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Failed to load notification preferences. Please try refreshing the page.')).toBeInTheDocument();
    });
  });

  it('displays success message after saving', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    (api.put as any).mockResolvedValue({ data: { message: 'Notification preferences updated successfully' } });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(screen.getByText('Notification preferences updated successfully')).toBeInTheDocument();
    });
  });

  it('displays error message on save failure', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    (api.put as any).mockRejectedValue(new Error('Save failed'));
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(screen.getByText('Failed to save notification preferences')).toBeInTheDocument();
    });
  });

  it('shows loading state while saving', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    (api.put as any).mockImplementation(() => new Promise(() => {})); // Never resolves
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);
    
    expect(saveButton).toBeDisabled();
    expect(screen.getByText('Save Preferences')).toBeInTheDocument(); // Button text changes when loading
  });

  it('validates frequency options', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    // Check that frequency options are available
    const frequencySelect = screen.getByText('Immediate - Send notifications as events occur');
    fireEvent.click(frequencySelect);
    
    expect(screen.getByText('Immediate - Send notifications as events occur')).toBeInTheDocument();
    expect(screen.getByText('Daily Digest - Send a summary once per day')).toBeInTheDocument();
  });

  it('validates reminder frequency options', async () => {
    (api.get as any).mockResolvedValue({ data: mockPreferences });
    
    render(<ApprovalNotificationPreferences />);
    
    await waitFor(() => {
      expect(screen.getByText('Approval Notification Preferences')).toBeInTheDocument();
    });
    
    // Check that reminder frequency options are available
    const reminderSelect = screen.getByText('Daily - Send reminders daily');
    fireEvent.click(reminderSelect);
    
    expect(screen.getByText('Daily - Send reminders daily')).toBeInTheDocument();
    expect(screen.getByText('Weekly - Send reminders weekly')).toBeInTheDocument();
    expect(screen.getByText('Disabled - No reminder notifications')).toBeInTheDocument();
  });
});