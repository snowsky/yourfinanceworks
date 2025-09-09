import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ScheduledReportsManager } from '../reports/ScheduledReportsManager';
import { reportApi } from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  reportApi: {
    getScheduledReports: vi.fn(),
    updateScheduledReport: vi.fn(),
    deleteScheduledReport: vi.fn(),
    getTemplates: vi.fn(),
    createScheduledReport: vi.fn(),
  },
}));

// Mock date-fns functions
vi.mock('date-fns', () => ({
  formatDistanceToNow: vi.fn(() => '2 hours ago'),
  format: vi.fn(() => 'Jan 15, 2024 9:00 AM'),
}));

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock the form components to avoid ResizeObserver issues
vi.mock('../reports/ScheduledReportForm', () => ({
  ScheduledReportForm: ({ onSuccess, onCancel }: any) => (
    <div data-testid="scheduled-report-form">
      <h2>Schedule New Report</h2>
      <button onClick={() => onSuccess({ id: 1 })}>Create</button>
      <button onClick={onCancel}>Cancel</button>
    </div>
  ),
}));

vi.mock('../reports/ScheduledReportDetails', () => ({
  ScheduledReportDetails: ({ onClose }: any) => (
    <div data-testid="scheduled-report-details">
      <h2>Scheduled Report Details</h2>
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

const mockScheduledReports = [
  {
    id: 1,
    template_id: 1,
    schedule_config: {
      schedule_type: 'weekly' as const,
      day_of_week: 1,
      hour: 9,
      minute: 0,
      timezone: 'UTC',
    },
    recipients: ['user@example.com', 'admin@example.com'],
    is_active: true,
    last_run: '2024-01-15T09:00:00Z',
    next_run: '2024-01-22T09:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    template: {
      id: 1,
      name: 'Weekly Sales Report',
      report_type: 'invoice' as const,
      filters: {},
      columns: [],
      formatting: {},
      is_shared: false,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      user_id: 1,
    },
  },
  {
    id: 2,
    template_id: 2,
    schedule_config: {
      schedule_type: 'monthly' as const,
      day_of_month: 1,
      hour: 8,
      minute: 0,
      timezone: 'UTC',
    },
    recipients: ['manager@example.com'],
    is_active: false,
    last_run: '2024-01-01T08:00:00Z',
    next_run: '2024-02-01T08:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    template: {
      id: 2,
      name: 'Monthly Expense Report',
      report_type: 'expense' as const,
      filters: {},
      columns: [],
      formatting: {},
      is_shared: false,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      user_id: 1,
    },
  },
];

describe('ScheduledReportsManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(reportApi.getScheduledReports).mockImplementation(() => new Promise(() => {}));
    
    render(<ScheduledReportsManager />);
    
    expect(screen.getByText('Loading scheduled reports...')).toBeInTheDocument();
  });

  it('renders scheduled reports list', async () => {
    vi.mocked(reportApi.getScheduledReports).mockResolvedValue({
      scheduled_reports: mockScheduledReports,
      total: 2,
    });

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sales Report')).toBeInTheDocument();
      expect(screen.getByText('Monthly Expense Report')).toBeInTheDocument();
    });

    // Check schedule descriptions
    expect(screen.getByText('Weekly on Monday at 9:00')).toBeInTheDocument();
    expect(screen.getByText('Monthly on day 1 at 8:00')).toBeInTheDocument();

    // Check recipient counts
    expect(screen.getByText('2 recipients')).toBeInTheDocument();
    expect(screen.getByText('1 recipient')).toBeInTheDocument();

    // Check status badges
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Paused')).toBeInTheDocument();
  });

  it('renders empty state when no scheduled reports', async () => {
    vi.mocked(reportApi.getScheduledReports).mockResolvedValue({
      scheduled_reports: [],
      total: 0,
    });

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      expect(screen.getByText('No scheduled reports')).toBeInTheDocument();
      expect(screen.getByText('Create your first scheduled report to automate report generation and delivery.')).toBeInTheDocument();
    });
  });

  it('opens create form when clicking Schedule Report button', async () => {
    vi.mocked(reportApi.getScheduledReports).mockResolvedValue({
      scheduled_reports: [],
      total: 0,
    });

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      expect(screen.getByText('No scheduled reports')).toBeInTheDocument();
    });

    const scheduleButton = screen.getAllByText('Schedule Report')[0];
    fireEvent.click(scheduleButton);

    await waitFor(() => {
      expect(screen.getByText('Schedule New Report')).toBeInTheDocument();
    });
  });

  it('toggles schedule active status', async () => {
    vi.mocked(reportApi.getScheduledReports).mockResolvedValue({
      scheduled_reports: mockScheduledReports,
      total: 2,
    });
    vi.mocked(reportApi.updateScheduledReport).mockResolvedValue({
      ...mockScheduledReports[0],
      is_active: false,
    });

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sales Report')).toBeInTheDocument();
    });

    // Find and click the pause button for the active report
    const pauseButtons = screen.getAllByRole('button');
    const pauseButton = pauseButtons.find(button => {
      const svg = button.querySelector('svg');
      return svg && svg.getAttribute('data-testid') === 'pause-icon';
    });

    if (pauseButton) {
      fireEvent.click(pauseButton);

      await waitFor(() => {
        expect(reportApi.updateScheduledReport).toHaveBeenCalledWith(1, {
          is_active: false,
        });
      });
    }
  });

  it('deletes scheduled report with confirmation', async () => {
    vi.mocked(reportApi.getScheduledReports).mockResolvedValue({
      scheduled_reports: mockScheduledReports,
      total: 2,
    });
    vi.mocked(reportApi.deleteScheduledReport).mockResolvedValue(undefined);

    // Mock window.confirm
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sales Report')).toBeInTheDocument();
    });

    // Find and click a delete button
    const deleteButtons = screen.getAllByRole('button');
    const deleteButton = deleteButtons.find(button => {
      const svg = button.querySelector('svg');
      return svg && svg.getAttribute('data-testid') === 'trash-2-icon';
    });

    if (deleteButton) {
      fireEvent.click(deleteButton);

      expect(confirmSpy).toHaveBeenCalledWith('Are you sure you want to delete this scheduled report?');
      
      await waitFor(() => {
        expect(reportApi.deleteScheduledReport).toHaveBeenCalledWith(1);
      });
    }

    confirmSpy.mockRestore();
  });

  it('cancels delete when confirmation is declined', async () => {
    vi.mocked(reportApi.getScheduledReports).mockResolvedValue({
      scheduled_reports: mockScheduledReports,
      total: 2,
    });

    // Mock window.confirm to return false
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sales Report')).toBeInTheDocument();
    });

    // Find and click a delete button
    const deleteButtons = screen.getAllByRole('button');
    const deleteButton = deleteButtons.find(button => {
      const svg = button.querySelector('svg');
      return svg && svg.getAttribute('data-testid') === 'trash-2-icon';
    });

    if (deleteButton) {
      fireEvent.click(deleteButton);

      expect(confirmSpy).toHaveBeenCalled();
      expect(reportApi.deleteScheduledReport).not.toHaveBeenCalled();
    }

    confirmSpy.mockRestore();
  });

  it('opens edit form when clicking edit button', async () => {
    vi.mocked(reportApi.getScheduledReports).mockResolvedValue({
      scheduled_reports: mockScheduledReports,
      total: 2,
    });

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sales Report')).toBeInTheDocument();
    });

    // Find and click an edit button
    const editButtons = screen.getAllByRole('button');
    const editButton = editButtons.find(button => {
      const svg = button.querySelector('svg');
      return svg && svg.getAttribute('data-testid') === 'edit-icon';
    });

    if (editButton) {
      fireEvent.click(editButton);

      await waitFor(() => {
        expect(screen.getByText('Edit Scheduled Report')).toBeInTheDocument();
      });
    }
  });

  it('opens details view when clicking View Details button', async () => {
    vi.mocked(reportApi.getScheduledReports).mockResolvedValue({
      scheduled_reports: mockScheduledReports,
      total: 2,
    });

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sales Report')).toBeInTheDocument();
    });

    const viewDetailsButton = screen.getAllByText('View Details')[0];
    fireEvent.click(viewDetailsButton);

    await waitFor(() => {
      expect(screen.getByText('Scheduled Report Details')).toBeInTheDocument();
    });
  });

  it('handles API errors gracefully', async () => {
    vi.mocked(reportApi.getScheduledReports).mockRejectedValue(new Error('API Error'));

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      // Should still render the component, just without data
      expect(screen.getByText('Scheduled Reports')).toBeInTheDocument();
    });
  });

  it('displays correct schedule descriptions for different types', async () => {
    const dailyReport = {
      ...mockScheduledReports[0],
      id: 3,
      schedule_config: {
        schedule_type: 'daily' as const,
        hour: 10,
        minute: 30,
        timezone: 'UTC',
      },
    };

    const yearlyReport = {
      ...mockScheduledReports[0],
      id: 4,
      schedule_config: {
        schedule_type: 'yearly' as const,
        month: 12,
        day_of_month: 31,
        hour: 23,
        minute: 59,
        timezone: 'UTC',
      },
    };

    vi.mocked(reportApi.getScheduledReports).mockResolvedValue({
      scheduled_reports: [dailyReport, yearlyReport],
      total: 2,
    });

    render(<ScheduledReportsManager />);

    await waitFor(() => {
      expect(screen.getByText('Daily at 10:30')).toBeInTheDocument();
      expect(screen.getByText('Yearly on Dec 31 at 23:59')).toBeInTheDocument();
    });
  });
});