import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { TemplateGenerateDialog } from '../reports/TemplateGenerateDialog';
import { reportApi } from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  reportApi: {
    previewReport: vi.fn(),
    generateReport: vi.fn(),
    downloadReport: vi.fn(),
  },
}));

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock child components
vi.mock('../reports/ExportFormatSelector', () => ({
  ExportFormatSelector: ({ selectedFormat, onFormatChange, onExport, loading, disabled }: any) => (
    <div data-testid="export-format-selector">
      <select value={selectedFormat} onChange={(e) => onFormatChange(e.target.value)}>
        <option value="pdf">PDF</option>
        <option value="csv">CSV</option>
        <option value="excel">Excel</option>
        <option value="json">JSON</option>
      </select>
      <button onClick={onExport} disabled={loading || disabled}>
        Export
      </button>
    </div>
  ),
}));

vi.mock('../reports/ReportPreview', () => ({
  ReportPreview: ({ reportData, loading, error, onRefresh }: any) => (
    <div data-testid="report-preview">
      {loading && <span>Loading preview...</span>}
      {error && <span>Error: {error}</span>}
      {reportData && <span>Preview data loaded</span>}
      <button onClick={onRefresh}>Refresh</button>
    </div>
  ),
}));

const mockTemplate = {
  id: 1,
  name: 'Monthly Invoice Report',
  report_type: 'invoice' as const,
  filters: { 
    date_from: '2024-01-01', 
    date_to: '2024-01-31',
    status: ['paid', 'pending'] 
  },
  columns: ['number', 'client_name', 'amount', 'status'],
  formatting: {},
  is_shared: true,
  user_id: 1,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockPreviewData = {
  report_type: 'invoice',
  summary: {
    total_records: 10,
    total_amount: 5000,
    currency: 'USD',
    date_range: { date_from: '2024-01-01', date_to: '2024-01-31' },
    key_metrics: { avg_amount: 500 },
  },
  data: [
    { number: 'INV-001', client_name: 'Client A', amount: 1000, status: 'paid' },
    { number: 'INV-002', client_name: 'Client B', amount: 1500, status: 'pending' },
  ],
  metadata: {
    generated_at: '2024-01-01T00:00:00Z',
    generated_by: 1,
    export_format: 'json',
  },
  filters: mockTemplate.filters,
};

describe('TemplateGenerateDialog', () => {
  let queryClient: QueryClient;
  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const renderComponent = (open = true) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <TemplateGenerateDialog
          template={mockTemplate}
          open={open}
          onOpenChange={mockOnOpenChange}
        />
      </QueryClientProvider>
    );
  };

  it('renders dialog when open', () => {
    renderComponent(true);
    
    expect(screen.getByText('Generate Report: Monthly Invoice Report')).toBeInTheDocument();
    expect(screen.getByText('Generate a report using this template with current data')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    renderComponent(false);
    
    expect(screen.queryByText('Generate Report: Monthly Invoice Report')).not.toBeInTheDocument();
  });

  it('displays template overview correctly', () => {
    renderComponent();
    
    expect(screen.getByText('Template Overview')).toBeInTheDocument();
    expect(screen.getByText('Invoice Report')).toBeInTheDocument();
    expect(screen.getByText('Shared')).toBeInTheDocument();
    expect(screen.getByText('Active Filters')).toBeInTheDocument();
    expect(screen.getByText('Custom Columns (4)')).toBeInTheDocument();
  });

  it('displays filter information correctly', () => {
    renderComponent();
    
    expect(screen.getByText('Date From:')).toBeInTheDocument();
    expect(screen.getByText('1/1/2024')).toBeInTheDocument();
    expect(screen.getByText('Date To:')).toBeInTheDocument();
    expect(screen.getByText('1/31/2024')).toBeInTheDocument();
    expect(screen.getByText('Status:')).toBeInTheDocument();
    expect(screen.getByText('paid, pending')).toBeInTheDocument();
  });

  it('displays column information correctly', () => {
    renderComponent();
    
    expect(screen.getByText('Number')).toBeInTheDocument();
    expect(screen.getByText('Client Name')).toBeInTheDocument();
    expect(screen.getByText('Amount')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
  });

  it('handles preview generation', async () => {
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    const previewButton = screen.getByText('Preview Report');
    fireEvent.click(previewButton);
    
    await waitFor(() => {
      expect(reportApi.previewReport).toHaveBeenCalledWith({
        report_type: 'invoice',
        filters: mockTemplate.filters,
        limit: 10,
      });
    });
    
    expect(screen.getByText('Preview data loaded')).toBeInTheDocument();
  });

  it('handles preview errors', async () => {
    vi.mocked(reportApi.previewReport).mockRejectedValue(new Error('Preview failed'));
    
    renderComponent();
    
    const previewButton = screen.getByText('Preview Report');
    fireEvent.click(previewButton);
    
    await waitFor(() => {
      expect(screen.getByText('Error: Preview failed')).toBeInTheDocument();
    });
  });

  it('handles export format selection', () => {
    renderComponent();
    
    const formatSelector = screen.getByTestId('export-format-selector').querySelector('select');
    fireEvent.change(formatSelector!, { target: { value: 'csv' } });
    
    expect(formatSelector).toHaveValue('csv');
  });

  it('handles report generation with download URL', async () => {
    vi.mocked(reportApi.generateReport).mockResolvedValue({
      success: true,
      report_id: 123,
      download_url: 'https://example.com/download/123',
    });
    
    // Mock window.open
    const mockOpen = vi.fn();
    Object.defineProperty(window, 'open', { value: mockOpen });
    
    renderComponent();
    
    const exportButton = screen.getByText('Export');
    fireEvent.click(exportButton);
    
    await waitFor(() => {
      expect(reportApi.generateReport).toHaveBeenCalledWith({
        report_type: 'invoice',
        filters: mockTemplate.filters,
        columns: mockTemplate.columns,
        export_format: 'pdf',
        template_id: 1,
      });
      expect(mockOpen).toHaveBeenCalledWith('https://example.com/download/123', '_blank');
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it('handles report generation with file download', async () => {
    vi.mocked(reportApi.generateReport).mockResolvedValue({
      success: true,
      report_id: 123,
      file_path: '/reports/123.pdf',
    });
    
    const mockBlob = new Blob(['test'], { type: 'application/pdf' });
    const mockResponse = {
      ok: true,
      blob: () => Promise.resolve(mockBlob),
    } as Response;
    vi.mocked(reportApi.downloadReport).mockResolvedValue(mockResponse);
    
    // Mock DOM methods
    const mockCreateElement = vi.fn();
    const mockAppendChild = vi.fn();
    const mockRemoveChild = vi.fn();
    const mockClick = vi.fn();
    const mockCreateObjectURL = vi.fn(() => 'blob:url');
    const mockRevokeObjectURL = vi.fn();
    
    const mockAnchor = {
      href: '',
      download: '',
      click: mockClick,
    };
    
    mockCreateElement.mockReturnValue(mockAnchor);
    
    Object.defineProperty(document, 'createElement', { value: mockCreateElement });
    Object.defineProperty(document.body, 'appendChild', { value: mockAppendChild });
    Object.defineProperty(document.body, 'removeChild', { value: mockRemoveChild });
    Object.defineProperty(window.URL, 'createObjectURL', { value: mockCreateObjectURL });
    Object.defineProperty(window.URL, 'revokeObjectURL', { value: mockRevokeObjectURL });
    
    renderComponent();
    
    const exportButton = screen.getByText('Export');
    fireEvent.click(exportButton);
    
    await waitFor(() => {
      expect(reportApi.downloadReport).toHaveBeenCalledWith(123);
      expect(mockClick).toHaveBeenCalled();
      expect(mockAnchor.download).toBe('Monthly Invoice Report-123.pdf');
    });
  });

  it('handles report generation errors', async () => {
    vi.mocked(reportApi.generateReport).mockResolvedValue({
      success: false,
      error_message: 'Generation failed',
    });
    
    renderComponent();
    
    const exportButton = screen.getByText('Export');
    fireEvent.click(exportButton);
    
    await waitFor(() => {
      expect(mockOnOpenChange).not.toHaveBeenCalledWith(false);
    });
  });

  it('shows loading states correctly', async () => {
    vi.mocked(reportApi.previewReport).mockImplementation(() => new Promise(() => {}));
    
    renderComponent();
    
    const previewButton = screen.getByText('Preview Report');
    fireEvent.click(previewButton);
    
    expect(screen.getByText('Generating Preview...')).toBeInTheDocument();
    expect(screen.getByText('Loading preview...')).toBeInTheDocument();
  });

  it('handles dialog close', () => {
    renderComponent();
    
    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);
    
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  it('formats filter values correctly', () => {
    const templateWithComplexFilters = {
      ...mockTemplate,
      filters: {
        date_from: '2024-01-01',
        status: ['paid', 'pending', 'overdue', 'draft'],
        include_items: true,
        amount_min: 100,
      },
    };
    
    render(
      <QueryClientProvider client={queryClient}>
        <TemplateGenerateDialog
          template={templateWithComplexFilters}
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      </QueryClientProvider>
    );
    
    expect(screen.getByText('paid, pending, overdue +1 more')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('shows template metadata correctly', () => {
    renderComponent();
    
    expect(screen.getByText('Created 1/1/2024')).toBeInTheDocument();
  });

  it('handles templates with no filters', () => {
    const templateWithoutFilters = {
      ...mockTemplate,
      filters: {},
    };
    
    render(
      <QueryClientProvider client={queryClient}>
        <TemplateGenerateDialog
          template={templateWithoutFilters}
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      </QueryClientProvider>
    );
    
    expect(screen.queryByText('Active Filters')).not.toBeInTheDocument();
  });

  it('handles templates with no custom columns', () => {
    const templateWithoutColumns = {
      ...mockTemplate,
      columns: undefined,
    };
    
    render(
      <QueryClientProvider client={queryClient}>
        <TemplateGenerateDialog
          template={templateWithoutColumns}
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      </QueryClientProvider>
    );
    
    expect(screen.queryByText('Custom Columns')).not.toBeInTheDocument();
  });
});