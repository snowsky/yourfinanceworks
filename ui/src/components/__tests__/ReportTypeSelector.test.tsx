import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ReportTypeSelector } from '../reports/ReportTypeSelector';
import { ReportType } from '@/lib/api';

const mockReportTypes: ReportType[] = [
  {
    type: 'client',
    name: 'Client Report',
    description: 'Comprehensive client analysis',
    available_filters: ['date_from', 'date_to'],
    available_columns: ['name', 'email', 'balance'],
    default_columns: ['name', 'email'],
  },
  {
    type: 'invoice',
    name: 'Invoice Report',
    description: 'Invoice performance analysis',
    available_filters: ['date_from', 'date_to', 'status'],
    available_columns: ['number', 'client_name', 'amount', 'status'],
    default_columns: ['number', 'client_name', 'amount'],
  },
];

describe('ReportTypeSelector', () => {
  const mockOnTypeSelect = vi.fn();

  beforeEach(() => {
    mockOnTypeSelect.mockClear();
  });

  it('renders report types correctly', () => {
    render(
      <ReportTypeSelector
        reportTypes={mockReportTypes}
        selectedType={null}
        onTypeSelect={mockOnTypeSelect}
      />
    );

    expect(screen.getByText('Select Report Type')).toBeInTheDocument();
    expect(screen.getByText('Client Report')).toBeInTheDocument();
    expect(screen.getByText('Invoice Report')).toBeInTheDocument();
    expect(screen.getByText('Comprehensive client analysis')).toBeInTheDocument();
    expect(screen.getByText('Invoice performance analysis')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(
      <ReportTypeSelector
        reportTypes={[]}
        selectedType={null}
        onTypeSelect={mockOnTypeSelect}
        loading={true}
      />
    );

    expect(screen.getByText('Select Report Type')).toBeInTheDocument();
    // Should show skeleton loading cards
    expect(document.querySelectorAll('.animate-pulse')).toHaveLength(5);
  });

  it('handles type selection', async () => {
    const user = userEvent.setup();
    
    render(
      <ReportTypeSelector
        reportTypes={mockReportTypes}
        selectedType={null}
        onTypeSelect={mockOnTypeSelect}
      />
    );

    await user.click(screen.getByText('Client Report'));
    expect(mockOnTypeSelect).toHaveBeenCalledWith('client');
  });

  it('highlights selected type', () => {
    render(
      <ReportTypeSelector
        reportTypes={mockReportTypes}
        selectedType="client"
        onTypeSelect={mockOnTypeSelect}
      />
    );

    const clientButton = screen.getByText('Client Report').closest('button');
    const invoiceButton = screen.getByText('Invoice Report').closest('button');

    // Selected button should have default variant (different styling)
    expect(clientButton).toHaveClass('bg-primary');
    expect(invoiceButton).not.toHaveClass('bg-primary');
  });

  it('renders with empty report types', () => {
    render(
      <ReportTypeSelector
        reportTypes={[]}
        selectedType={null}
        onTypeSelect={mockOnTypeSelect}
      />
    );

    expect(screen.getByText('Select Report Type')).toBeInTheDocument();
    expect(screen.queryByText('Client Report')).not.toBeInTheDocument();
  });
});