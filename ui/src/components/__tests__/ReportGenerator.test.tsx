import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReportGenerator } from '../reports/ReportGenerator';
import { ReportType, ReportData } from '@/lib/api';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { beforeEach } from 'node:test';
import { describe } from 'node:test';

// Mock the API
vi.mock('@/lib/api', () => ({
  reportApi: {
    getReportTypes: vi.fn().mockResolvedValue({ 
      report_types: [
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
      ]
    }),
    previewReport: vi.fn().mockResolvedValue({
      report_type: 'client',
      summary: {
        total_records: 10,
        total_amount: 5000,
        currency: 'USD',
        key_metrics: {},
      },
      data: [
        { id: 1, name: 'Client A', email: 'clienta@example.com', balance: 1000 },
        { id: 2, name: 'Client B', email: 'clientb@example.com', balance: 2000 },
      ],
      metadata: {
        generated_at: '2024-01-31T10:00:00Z',
        generated_by: 1,
        export_format: 'json',
      },
      filters: {},
    }),
    generateReport: vi.fn().mockResolvedValue({
      success: true,
      report_id: 1,
      download_url: 'http://example.com/report.pdf',
    }),
    downloadReport: vi.fn().mockResolvedValue(new Response()),
  },
  clientApi: {
    getClients: vi.fn().mockResolvedValue([]),
  },
  currencyApi: {
    getSupportedCurrencies: vi.fn().mockResolvedValue({ currencies: [] }),
  },
}));

vi.mock('@/constants/expenses', () => ({
  EXPENSE_CATEGORY_OPTIONS: [],
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('ReportGenerator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the main interface', async () => {
    render(<ReportGenerator />, { wrapper: createWrapper() });

    expect(screen.getByText('Report Generator')).toBeInTheDocument();
    expect(screen.getByText('Generate comprehensive reports for your business data')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Select Report Type')).toBeInTheDocument();
    });
  });

  it('loads and displays report types', async () => {
    render(<ReportGenerator />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Client Report')).toBeInTheDocument();
      expect(screen.getByText('Invoice Report')).toBeInTheDocument();
    });
  });

  it('shows filters and preview after selecting report type', async () => {
    const user = userEvent.setup();
    
    render(<ReportGenerator />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Client Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Client Report'));

    await waitFor(() => {
      expect(screen.getByText('Report Filters')).toBeInTheDocument();
      expect(screen.getByText('Report Preview')).toBeInTheDocument();
      expect(screen.getByText('Export Format')).toBeInTheDocument();
    });
  });

  it('handles preview generation', async () => {
    const user = userEvent.setup();
    
    render(<ReportGenerator />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Client Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Client Report'));

    await waitFor(() => {
      expect(screen.getByText('Preview Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Preview Report'));

    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument(); // Total records
      expect(screen.getByText('Client A')).toBeInTheDocument();
    });
  });

  it('provides quick action buttons', async () => {
    const user = userEvent.setup();
    
    render(<ReportGenerator />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Client Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Client Report'));

    await waitFor(() => {
      expect(screen.getByText('Quick Actions')).toBeInTheDocument();
      expect(screen.getByText('This Month')).toBeInTheDocument();
      expect(screen.getByText('Last Month')).toBeInTheDocument();
      expect(screen.getByText('Year to Date')).toBeInTheDocument();
      expect(screen.getByText('Clear Filters')).toBeInTheDocument();
    });
  });

  it('handles quick action - This Month', async () => {
    const user = userEvent.setup();
    
    render(<ReportGenerator />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Client Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Client Report'));

    await waitFor(() => {
      expect(screen.getByText('This Month')).toBeInTheDocument();
    });

    await user.click(screen.getByText('This Month'));

    // Should trigger preview with current month dates
    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument(); // Preview should load
    });
  });

  it('handles export functionality', async () => {
    const user = userEvent.setup();
    
    render(<ReportGenerator />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Client Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Client Report'));

    // First generate a preview
    await waitFor(() => {
      expect(screen.getByText('Preview Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Preview Report'));

    await waitFor(() => {
      expect(screen.getByText('Export as PDF')).toBeInTheDocument();
    });

    // Export should be enabled after preview
    const exportButton = screen.getByText('Export as PDF');
    expect(exportButton).not.toBeDisabled();

    await user.click(exportButton);

    // Should call the export API
    await waitFor(() => {
      expect(vi.mocked(require('@/lib/api').reportApi.generateReport)).toHaveBeenCalled();
    });
  });

  it('disables export when no preview data', async () => {
    const user = userEvent.setup();
    
    render(<ReportGenerator />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Client Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Client Report'));

    await waitFor(() => {
      expect(screen.getByText('Export as PDF')).toBeInTheDocument();
    });

    // Export should be disabled without preview
    const exportButton = screen.getByText('Export as PDF');
    expect(exportButton).toBeDisabled();
  });

  it('handles format selection', async () => {
    const user = userEvent.setup();
    
    render(<ReportGenerator />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Client Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Client Report'));

    await waitFor(() => {
      expect(screen.getByText('Excel')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Excel'));

    await waitFor(() => {
      expect(screen.getByText('Export as Excel')).toBeInTheDocument();
    });
  });

  it('resets state when changing report type', async () => {
    const user = userEvent.setup();
    
    render(<ReportGenerator />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Client Report')).toBeInTheDocument();
    });

    // Select first report type and generate preview
    await user.click(screen.getByText('Client Report'));
    
    await waitFor(() => {
      expect(screen.getByText('Preview Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Preview Report'));

    await waitFor(() => {
      expect(screen.getByText('Client A')).toBeInTheDocument();
    });

    // Change to different report type
    await user.click(screen.getByText('Invoice Report'));

    // Preview should be reset
    await waitFor(() => {
      expect(screen.queryByText('Client A')).not.toBeInTheDocument();
      expect(screen.getByText('No preview available')).toBeInTheDocument();
    });
  });
});