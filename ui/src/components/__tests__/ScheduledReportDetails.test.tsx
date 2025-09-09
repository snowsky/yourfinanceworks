import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';
import { ScheduledReportDetails } from '../reports/ScheduledReportDetails';

// Mock date-fns functions
vi.mock('date-fns', () => ({
  format: vi.fn((date, formatStr) => {
    if (formatStr === 'MMM d, yyyy h:mm a') {
      return 'Jan 15, 2024 9:00 AM';
    }
    return 'Jan 15, 2024 9:00 AM';
  }),
  formatDistanceToNow: vi.fn(() => '2 hours ago'),
}));

const mockScheduledReport = {
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
    filters: {
      date_from: '2024-01-01',
      status: ['paid', 'pending'],
    },
    columns: ['invoice_number', 'client_name', 'amount'],
    formatting: {},
    is_shared: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    user_id: 1,
  },
};

describe('ScheduledReportDetails', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders scheduled report details correctly', () => {
    render(
      <ScheduledReportDetails
        scheduledReport={mockScheduledReport}
        onClose={mockOnClose}
      />
    );

    // Check header
    expect(screen.getByText('Scheduled Report Details')).toBeInTheDocument();
    expect(screen.getByText('View configuration and status of this scheduled report')).toBeInTheDocument();

    // Check basic info
    expect(screen.getByText('Weekly Sales Report')).toBeInTheDocument();
    expect(screen.getByText('invoice report')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('displays schedule configuration correctly', () => {
    render(
      <ScheduledReportDetails
        scheduledReport={mockScheduledReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Schedule Configuration')).toBeInTheDocument();
    expect(screen.getByText('Every Monday at 9:00')).toBeInTheDocument();
    expect(screen.getByText('UTC')).toBeInTheDocument();
  });

  it('displays execution times when available', () => {
    render(
      <ScheduledReportDetails
        scheduledReport={mockScheduledReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Last Execution')).toBeInTheDocument();
    expect(screen.getByText('Next Execution')).toBeInTheDocument();
    expect(screen.getAllByText('Jan 15, 2024 9:00 AM')).toHaveLength(2);
    expect(screen.getAllByText('2 hours ago')).toHaveLength(2);
  });

  it('displays recipients correctly', () => {
    render(
      <ScheduledReportDetails
        scheduledReport={mockScheduledReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Email Recipients')).toBeInTheDocument();
    expect(screen.getByText('2 recipients')).toBeInTheDocument();
    expect(screen.getByText('user@example.com')).toBeInTheDocument();
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
  });

  it('displays template information correctly', () => {
    render(
      <ScheduledReportDetails
        scheduledReport={mockScheduledReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Template Information')).toBeInTheDocument();
    expect(screen.getByText('Template Name')).toBeInTheDocument();
    expect(screen.getByText('Weekly Sales Report')).toBeInTheDocument();
    expect(screen.getByText('Report Type')).toBeInTheDocument();
    expect(screen.getByText('invoice')).toBeInTheDocument();
  });

  it('displays applied filters when available', () => {
    render(
      <ScheduledReportDetails
        scheduledReport={mockScheduledReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Applied Filters')).toBeInTheDocument();
    expect(screen.getByText('date_from:')).toBeInTheDocument();
    expect(screen.getByText('2024-01-01')).toBeInTheDocument();
    expect(screen.getByText('status:')).toBeInTheDocument();
    expect(screen.getByText('paid, pending')).toBeInTheDocument();
  });

  it('displays metadata correctly', () => {
    render(
      <ScheduledReportDetails
        scheduledReport={mockScheduledReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Metadata')).toBeInTheDocument();
    expect(screen.getByText('Created')).toBeInTheDocument();
    expect(screen.getByText('Last Updated')).toBeInTheDocument();
  });

  it('handles different schedule types correctly', () => {
    const dailyReport = {
      ...mockScheduledReport,
      schedule_config: {
        schedule_type: 'daily' as const,
        hour: 10,
        minute: 30,
        timezone: 'America/New_York',
      },
    };

    render(
      <ScheduledReportDetails
        scheduledReport={dailyReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Every day at 10:30')).toBeInTheDocument();
    expect(screen.getByText('Eastern Time')).toBeInTheDocument();
  });

  it('handles monthly schedule type correctly', () => {
    const monthlyReport = {
      ...mockScheduledReport,
      schedule_config: {
        schedule_type: 'monthly' as const,
        day_of_month: 15,
        hour: 14,
        minute: 0,
        timezone: 'Europe/London',
      },
    };

    render(
      <ScheduledReportDetails
        scheduledReport={monthlyReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Every month on day 15 at 14:00')).toBeInTheDocument();
    expect(screen.getByText('London')).toBeInTheDocument();
  });

  it('handles yearly schedule type correctly', () => {
    const yearlyReport = {
      ...mockScheduledReport,
      schedule_config: {
        schedule_type: 'yearly' as const,
        month: 12,
        day_of_month: 31,
        hour: 23,
        minute: 59,
        timezone: 'Asia/Tokyo',
      },
    };

    render(
      <ScheduledReportDetails
        scheduledReport={yearlyReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Every year on December 31 at 23:59')).toBeInTheDocument();
    expect(screen.getByText('Tokyo')).toBeInTheDocument();
  });

  it('handles paused status correctly', () => {
    const pausedReport = {
      ...mockScheduledReport,
      is_active: false,
    };

    render(
      <ScheduledReportDetails
        scheduledReport={pausedReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Paused')).toBeInTheDocument();
  });

  it('handles single recipient correctly', () => {
    const singleRecipientReport = {
      ...mockScheduledReport,
      recipients: ['single@example.com'],
    };

    render(
      <ScheduledReportDetails
        scheduledReport={singleRecipientReport}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('1 recipient')).toBeInTheDocument();
    expect(screen.getByText('single@example.com')).toBeInTheDocument();
  });

  it('handles missing execution times gracefully', () => {
    const reportWithoutTimes = {
      ...mockScheduledReport,
      last_run: undefined,
      next_run: undefined,
    };

    render(
      <ScheduledReportDetails
        scheduledReport={reportWithoutTimes}
        onClose={mockOnClose}
      />
    );

    expect(screen.queryByText('Last Execution')).not.toBeInTheDocument();
    expect(screen.queryByText('Next Execution')).not.toBeInTheDocument();
  });

  it('handles missing template gracefully', () => {
    const reportWithoutTemplate = {
      ...mockScheduledReport,
      template: undefined,
    };

    render(
      <ScheduledReportDetails
        scheduledReport={reportWithoutTemplate}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Template 1')).toBeInTheDocument();
    expect(screen.queryByText('Template Information')).not.toBeInTheDocument();
  });

  it('handles empty filters gracefully', () => {
    const reportWithEmptyFilters = {
      ...mockScheduledReport,
      template: {
        ...mockScheduledReport.template!,
        filters: {},
      },
    };

    render(
      <ScheduledReportDetails
        scheduledReport={reportWithEmptyFilters}
        onClose={mockOnClose}
      />
    );

    expect(screen.queryByText('Applied Filters')).not.toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    render(
      <ScheduledReportDetails
        scheduledReport={mockScheduledReport}
        onClose={mockOnClose}
      />
    );

    const closeButton = screen.getByText('Close');
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('calls onClose when X button is clicked', () => {
    render(
      <ScheduledReportDetails
        scheduledReport={mockScheduledReport}
        onClose={mockOnClose}
      />
    );

    // Find the X button in the header
    const xButton = screen.getByRole('button', { name: '' }); // X button
    fireEvent.click(xButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('handles unknown timezone gracefully', () => {
    const reportWithUnknownTimezone = {
      ...mockScheduledReport,
      schedule_config: {
        ...mockScheduledReport.schedule_config,
        timezone: 'Unknown/Timezone',
      },
    };

    render(
      <ScheduledReportDetails
        scheduledReport={reportWithUnknownTimezone}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Unknown/Timezone')).toBeInTheDocument();
  });

  it('handles array filter values correctly', () => {
    const reportWithArrayFilters = {
      ...mockScheduledReport,
      template: {
        ...mockScheduledReport.template!,
        filters: {
          categories: ['office', 'travel', 'meals'],
          amount_min: 100,
        },
      },
    };

    render(
      <ScheduledReportDetails
        scheduledReport={reportWithArrayFilters}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('categories:')).toBeInTheDocument();
    expect(screen.getByText('office, travel, meals')).toBeInTheDocument();
    expect(screen.getByText('amount_min:')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });
});