import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ScheduledReportForm } from '../reports/ScheduledReportForm';
import { reportApi } from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  reportApi: {
    getTemplates: vi.fn(),
    createScheduledReport: vi.fn(),
    updateScheduledReport: vi.fn(),
  },
}));

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockTemplates = [
  {
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
  {
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
];

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
  recipients: ['user@example.com'],
  is_active: true,
  last_run: '2024-01-15T09:00:00Z',
  next_run: '2024-01-22T09:00:00Z',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  template: mockTemplates[0],
};

describe('ScheduledReportForm', () => {
  const mockOnSuccess = vi.fn();
  const mockOnCancel = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(reportApi.getTemplates).mockResolvedValue({
      templates: mockTemplates,
      total: 2,
    });
  });

  it('renders create form correctly', async () => {
    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('Schedule New Report')).toBeInTheDocument();
    expect(screen.getByText('Configure automated report generation and delivery')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Report Template')).toBeInTheDocument();
      expect(screen.getByText('Schedule Configuration')).toBeInTheDocument();
      expect(screen.getByText('Email Recipients')).toBeInTheDocument();
    });
  });

  it('renders edit form correctly', async () => {
    render(
      <ScheduledReportForm
        scheduledReport={mockScheduledReport}
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('Edit Scheduled Report')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByDisplayValue('user@example.com')).toBeInTheDocument();
    });
  });

  it('loads and displays templates', async () => {
    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(reportApi.getTemplates).toHaveBeenCalled();
    });

    // Click on template selector to see options
    const templateSelect = screen.getByRole('combobox');
    fireEvent.click(templateSelect);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sales Report')).toBeInTheDocument();
      expect(screen.getByText('Monthly Expense Report')).toBeInTheDocument();
    });
  });

  it('adds and removes recipients', async () => {
    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Enter email address')).toBeInTheDocument();
    });

    const emailInput = screen.getByPlaceholderText('Enter email address');
    const addButton = screen.getByRole('button', { name: '' }); // Plus button

    // Add a recipient
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText('test@example.com')).toBeInTheDocument();
      expect(screen.getByText('Recipients (1)')).toBeInTheDocument();
    });

    // Remove the recipient
    const removeButton = screen.getByRole('button', { name: '' }); // X button in badge
    fireEvent.click(removeButton);

    await waitFor(() => {
      expect(screen.queryByText('test@example.com')).not.toBeInTheDocument();
    });
  });

  it('validates email addresses', async () => {
    const { toast } = await import('sonner');

    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Enter email address')).toBeInTheDocument();
    });

    const emailInput = screen.getByPlaceholderText('Enter email address');
    const addButton = screen.getByRole('button', { name: '' }); // Plus button

    // Try to add invalid email
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Please enter a valid email address');
    });
  });

  it('prevents duplicate recipients', async () => {
    const { toast } = await import('sonner');

    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Enter email address')).toBeInTheDocument();
    });

    const emailInput = screen.getByPlaceholderText('Enter email address');
    const addButton = screen.getByRole('button', { name: '' }); // Plus button

    // Add first recipient
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(addButton);

    // Try to add same recipient again
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('This recipient is already added');
    });
  });

  it('updates schedule configuration based on frequency', async () => {
    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Frequency')).toBeInTheDocument();
    });

    // Change to monthly
    const frequencySelect = screen.getAllByRole('combobox')[1]; // Second combobox is frequency
    fireEvent.click(frequencySelect);
    
    await waitFor(() => {
      const monthlyOption = screen.getByText('Monthly');
      fireEvent.click(monthlyOption);
    });

    await waitFor(() => {
      expect(screen.getByText('Day of Month')).toBeInTheDocument();
    });

    // Change to yearly
    fireEvent.click(frequencySelect);
    
    await waitFor(() => {
      const yearlyOption = screen.getByText('Yearly');
      fireEvent.click(yearlyOption);
    });

    await waitFor(() => {
      expect(screen.getByText('Day of Month')).toBeInTheDocument();
      expect(screen.getByText('Month')).toBeInTheDocument();
    });
  });

  it('creates new scheduled report', async () => {
    const createdReport = { ...mockScheduledReport, id: 2 };
    vi.mocked(reportApi.createScheduledReport).mockResolvedValue(createdReport);

    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Report Template')).toBeInTheDocument();
    });

    // Select template
    const templateSelect = screen.getByRole('combobox');
    fireEvent.click(templateSelect);
    
    await waitFor(() => {
      const templateOption = screen.getByText('Weekly Sales Report');
      fireEvent.click(templateOption);
    });

    // Add recipient
    const emailInput = screen.getByPlaceholderText('Enter email address');
    const addButton = screen.getByRole('button', { name: '' }); // Plus button
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(addButton);

    // Submit form
    const submitButton = screen.getByText('Create Schedule');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(reportApi.createScheduledReport).toHaveBeenCalledWith({
        template_id: 1,
        schedule_config: expect.objectContaining({
          schedule_type: 'weekly',
        }),
        recipients: ['test@example.com'],
        is_active: true,
      });
      expect(mockOnSuccess).toHaveBeenCalledWith(createdReport);
    });
  });

  it('updates existing scheduled report', async () => {
    const updatedReport = { ...mockScheduledReport, recipients: ['updated@example.com'] };
    vi.mocked(reportApi.updateScheduledReport).mockResolvedValue(updatedReport);

    render(
      <ScheduledReportForm
        scheduledReport={mockScheduledReport}
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Edit Scheduled Report')).toBeInTheDocument();
    });

    // Submit form
    const submitButton = screen.getByText('Update Schedule');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(reportApi.updateScheduledReport).toHaveBeenCalledWith(1, {
        schedule_config: expect.objectContaining({
          schedule_type: 'weekly',
        }),
        recipients: ['user@example.com'],
        is_active: true,
      });
      expect(mockOnSuccess).toHaveBeenCalledWith(updatedReport);
    });
  });

  it('validates form before submission', async () => {
    const { toast } = await import('sonner');

    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Create Schedule')).toBeInTheDocument();
    });

    // Try to submit without template
    const submitButton = screen.getByText('Create Schedule');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Please select a template');
    });

    // Select template but no recipients
    const templateSelect = screen.getByRole('combobox');
    fireEvent.click(templateSelect);
    
    await waitFor(() => {
      const templateOption = screen.getByText('Weekly Sales Report');
      fireEvent.click(templateOption);
    });

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Please add at least one recipient');
    });
  });

  it('calls onCancel when cancel button is clicked', async () => {
    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);

    expect(mockOnCancel).toHaveBeenCalled();
  });

  it('calls onCancel when X button is clicked', async () => {
    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    const closeButton = screen.getByRole('button', { name: '' }); // X button in header
    fireEvent.click(closeButton);

    expect(mockOnCancel).toHaveBeenCalled();
  });

  it('toggles active status', async () => {
    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Active Status')).toBeInTheDocument();
    });

    const activeSwitch = screen.getByRole('switch');
    expect(activeSwitch).toBeChecked();

    fireEvent.click(activeSwitch);
    expect(activeSwitch).not.toBeChecked();
  });

  it('handles API errors gracefully', async () => {
    const { toast } = await import('sonner');
    vi.mocked(reportApi.createScheduledReport).mockRejectedValue(new Error('API Error'));

    render(
      <ScheduledReportForm
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Report Template')).toBeInTheDocument();
    });

    // Select template and add recipient
    const templateSelect = screen.getByRole('combobox');
    fireEvent.click(templateSelect);
    
    await waitFor(() => {
      const templateOption = screen.getByText('Weekly Sales Report');
      fireEvent.click(templateOption);
    });

    const emailInput = screen.getByPlaceholderText('Enter email address');
    const addButton = screen.getByRole('button', { name: '' }); // Plus button
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(addButton);

    // Submit form
    const submitButton = screen.getByText('Create Schedule');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to save scheduled report');
    });
  });
});