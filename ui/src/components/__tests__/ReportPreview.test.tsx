import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ReportPreview } from '../reports/ReportPreview';
import { ReportData } from '@/lib/api';

const mockReportData: ReportData = {
  report_type: 'invoice',
  summary: {
    total_records: 25,
    total_amount: 15000,
    currency: 'USD',
    date_range: {
      date_from: '2024-01-01',
      date_to: '2024-01-31',
    },
    key_metrics: {
      average_amount: 600,
      paid_invoices: 20,
      pending_invoices: 5,
    },
  },
  data: [
    {
      id: 1,
      number: 'INV-001',
      client_name: 'Client A',
      amount: 1000,
      status: 'paid',
      date: '2024-01-15',
    },
    {
      id: 2,
      number: 'INV-002',
      client_name: 'Client B',
      amount: 1500,
      status: 'pending',
      date: '2024-01-20',
    },
  ],
  metadata: {
    generated_at: '2024-01-31T10:00:00Z',
    generated_by: 1,
    export_format: 'json',
    generation_time: 2.5,
  },
  filters: {
    date_from: '2024-01-01',
    date_to: '2024-01-31',
  },
};

describe('ReportPreview', () => {
  const mockOnRefresh = vi.fn();

  beforeEach(() => {
    mockOnRefresh.mockClear();
  });

  it('renders loading state', () => {
    render(
      <ReportPreview
        reportData={null}
        loading={true}
        error={null}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('Generating Preview...')).toBeInTheDocument();
    expect(screen.getByText('Please wait while we generate your report preview')).toBeInTheDocument();
    // Check for loading spinner by class
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('renders error state', async () => {
    const user = userEvent.setup();
    
    render(
      <ReportPreview
        reportData={null}
        loading={false}
        error="Failed to generate preview"
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('Preview Error')).toBeInTheDocument();
    expect(screen.getByText('Failed to generate preview')).toBeInTheDocument();
    
    const tryAgainButton = screen.getByText('Try Again');
    await user.click(tryAgainButton);
    
    expect(mockOnRefresh).toHaveBeenCalledTimes(1);
  });

  it('renders empty state', () => {
    render(
      <ReportPreview
        reportData={null}
        loading={false}
        error={null}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('Report Preview')).toBeInTheDocument();
    expect(screen.getByText('Configure your filters and click preview to see a sample of your report')).toBeInTheDocument();
    expect(screen.getByText('No preview available. Please configure your filters and generate a preview.')).toBeInTheDocument();
  });

  it('renders report data correctly', () => {
    render(
      <ReportPreview
        reportData={mockReportData}
        loading={false}
        error={null}
        onRefresh={mockOnRefresh}
      />
    );

    // Check summary statistics
    expect(screen.getByText('25')).toBeInTheDocument(); // Total records
    expect(screen.getByText('Total Records')).toBeInTheDocument();
    expect(screen.getByText('$15,000.00')).toBeInTheDocument(); // Total amount
    expect(screen.getByText('Total Amount')).toBeInTheDocument();

    // Check date range (dates might be formatted differently)
    expect(screen.getByText('Date Range')).toBeInTheDocument();
    // Check for date components separately since formatting might vary
    expect(screen.getAllByText(/2024/).length).toBeGreaterThan(0);

    // Check key metrics
    expect(screen.getByText('Average Amount')).toBeInTheDocument();
    expect(screen.getByText('Paid Invoices')).toBeInTheDocument();
    expect(screen.getByText('Pending Invoices')).toBeInTheDocument();
  });

  it('renders data table with formatted values', () => {
    render(
      <ReportPreview
        reportData={mockReportData}
        loading={false}
        error={null}
        onRefresh={mockOnRefresh}
      />
    );

    // Check table headers
    expect(screen.getByText('Number')).toBeInTheDocument();
    expect(screen.getByText('Client Name')).toBeInTheDocument();
    expect(screen.getByText('Amount')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();

    // Check table data
    expect(screen.getByText('INV-001')).toBeInTheDocument();
    expect(screen.getByText('Client A')).toBeInTheDocument();
    expect(screen.getByText('$1,000.00')).toBeInTheDocument();
    
    // Check status badges
    expect(screen.getByText('PAID')).toBeInTheDocument();
    expect(screen.getByText('PENDING')).toBeInTheDocument();
  });

  it('shows record count badge', () => {
    render(
      <ReportPreview
        reportData={mockReportData}
        loading={false}
        error={null}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('Showing 2 of 25 records')).toBeInTheDocument();
  });

  it('handles empty data', () => {
    const emptyReportData: ReportData = {
      ...mockReportData,
      data: [],
      summary: {
        ...mockReportData.summary,
        total_records: 0,
      },
    };

    render(
      <ReportPreview
        reportData={emptyReportData}
        loading={false}
        error={null}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('No data found matching your filters.')).toBeInTheDocument();
  });

  it('formats dates correctly', () => {
    render(
      <ReportPreview
        reportData={mockReportData}
        loading={false}
        error={null}
        onRefresh={mockOnRefresh}
      />
    );

    // Check formatted dates in the table (dates might be formatted differently)
    expect(screen.getAllByText(/Jan \d+, 2024/).length).toBeGreaterThan(0);
  });

  it('handles null values in data', () => {
    const dataWithNulls: ReportData = {
      ...mockReportData,
      data: [
        {
          id: 1,
          number: 'INV-001',
          client_name: null,
          amount: 1000,
          status: 'paid',
          date: '2024-01-15',
        },
      ],
    };

    render(
      <ReportPreview
        reportData={dataWithNulls}
        loading={false}
        error={null}
        onRefresh={mockOnRefresh}
      />
    );

    // Should show dash for null values
    expect(screen.getByText('-')).toBeInTheDocument();
  });
});