import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { TemplateBasedReportGenerator } from '../reports/TemplateBasedReportGenerator';
import { reportApi } from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  reportApi: {
    getTemplates: vi.fn(),
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

vi.mock('../reports/TemplateSharing', () => ({
  TemplateSharing: ({ template, trigger }: any) => (
    <div data-testid="template-sharing">
      {trigger}
      <span>Sharing for {template.name}</span>
    </div>
  ),
}));

const mockTemplates = [
  {
    id: 1,
    name: 'Monthly Invoice Report',
    report_type: 'invoice',
    filters: { date_from: '2024-01-01', status: ['paid'] },
    columns: ['number', 'client_name', 'amount'],
    formatting: {},
    is_shared: false,
    user_id: 1,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Client Summary',
    report_type: 'client',
    filters: { include_inactive: false },
    columns: ['name', 'balance'],
    formatting: {},
    is_shared: true,
    user_id: 1,
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
  {
    id: 3,
    name: 'Payment Analysis',
    report_type: 'payment',
    filters: { payment_methods: ['credit_card'] },
    columns: ['amount', 'payment_date'],
    formatting: {},
    is_shared: false,
    user_id: 1,
    created_at: '2024-01-03T00:00:00Z',
    updated_at: '2024-01-03T00:00:00Z',
  },
];

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
  ],
  metadata: {
    generated_at: '2024-01-01T00:00:00Z',
    generated_by: 1,
    export_format: 'json',
  },
  filters: { date_from: '2024-01-01', status: ['paid'] },
};

describe('TemplateBasedReportGenerator', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <TemplateBasedReportGenerator />
      </QueryClientProvider>
    );
  };

  it('renders loading state initially', () => {
    vi.mocked(reportApi.getTemplates).mockImplementation(() => new Promise(() => {}));
    
    renderComponent();
    
    expect(screen.getByText('Template-Based Reports')).toBeInTheDocument();
    expect(screen.getByText('Loading templates...')).toBeInTheDocument();
  });

  it('renders empty state when no templates exist', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ templates: [], total: 0 });
    
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('No templates available')).toBeInTheDocument();
      expect(screen.getByText('Create your first template to get started with template-based reporting')).toBeInTheDocument();
      expect(screen.getByText('Manage Templates')).toBeInTheDocument();
    });
  });

  it('renders templates when they exist', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Monthly Invoice Report')).toBeInTheDocument();
      expect(screen.getByText('Client Summary')).toBeInTheDocument();
      expect(screen.getByText('Payment Analysis')).toBeInTheDocument();
    });
  });

  it('groups templates by type in selector', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    
    renderComponent();
    
    await waitFor(() => {
      const selector = screen.getByRole('combobox');
      fireEvent.click(selector);
    });
    
    expect(screen.getByText('Invoice Report')).toBeInTheDocument();
    expect(screen.getByText('Client Report')).toBeInTheDocument();
    expect(screen.getByText('Payment Report')).toBeInTheDocument();
  });

  it('handles template selection from dropdown', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    await waitFor(() => {
      const selector = screen.getByRole('combobox');
      fireEvent.click(selector);
    });
    
    const templateOption = screen.getByText('Monthly Invoice Report');
    fireEvent.click(templateOption);
    
    await waitFor(() => {
      expect(screen.getByText('Continue with "Monthly Invoice Report"')).toBeInTheDocument();
    });
  });

  it('handles template selection from grid', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    await waitFor(() => {
      const templateCards = screen.getAllByText('Monthly Invoice Report');
      fireEvent.click(templateCards[1]); // Click the card, not the dropdown option
    });
    
    // Should auto-preview when template is selected
    await waitFor(() => {
      expect(reportApi.previewReport).toHaveBeenCalledWith({
        report_type: 'invoice',
        filters: { date_from: '2024-01-01', status: ['paid'] },
        limit: 10,
      });
    });
  });

  it('navigates to preview tab after template selection', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    await waitFor(() => {
      const selector = screen.getByRole('combobox');
      fireEvent.click(selector);
    });
    
    const templateOption = screen.getByText('Monthly Invoice Report');
    fireEvent.click(templateOption);
    
    const continueButton = screen.getByText('Continue with "Monthly Invoice Report"');
    fireEvent.click(continueButton);
    
    expect(screen.getByRole('tab', { name: 'Preview & Generate' })).toHaveAttribute('data-state', 'active');
  });

  it('displays template details in preview tab', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    // Select template and go to preview
    await waitFor(() => {
      const templateCards = screen.getAllByText('Monthly Invoice Report');
      fireEvent.click(templateCards[1]);
    });
    
    const previewTab = screen.getByRole('tab', { name: 'Preview & Generate' });
    fireEvent.click(previewTab);
    
    expect(screen.getByText('Active Filters')).toBeInTheDocument();
    expect(screen.getByText('Date From:')).toBeInTheDocument();
    expect(screen.getByText('Status:')).toBeInTheDocument();
    expect(screen.getByText('Custom Columns (3)')).toBeInTheDocument();
  });

  it('handles export format selection', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    // Select template
    await waitFor(() => {
      const templateCards = screen.getAllByText('Monthly Invoice Report');
      fireEvent.click(templateCards[1]);
    });
    
    const previewTab = screen.getByRole('tab', { name: 'Preview & Generate' });
    fireEvent.click(previewTab);
    
    const formatSelector = screen.getByTestId('export-format-selector').querySelector('select');
    fireEvent.change(formatSelector!, { target: { value: 'csv' } });
    
    expect(formatSelector).toHaveValue('csv');
  });

  it('handles report generation', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    vi.mocked(reportApi.generateReport).mockResolvedValue({
      success: true,
      report_id: 123,
      download_url: 'https://example.com/download/123',
    });
    
    const mockOpen = vi.fn();
    Object.defineProperty(window, 'open', { value: mockOpen });
    
    renderComponent();
    
    // Select template
    await waitFor(() => {
      const templateCards = screen.getAllByText('Monthly Invoice Report');
      fireEvent.click(templateCards[1]);
    });
    
    const previewTab = screen.getByRole('tab', { name: 'Preview & Generate' });
    fireEvent.click(previewTab);
    
    const exportButton = screen.getByText('Export');
    fireEvent.click(exportButton);
    
    await waitFor(() => {
      expect(reportApi.generateReport).toHaveBeenCalledWith({
        report_type: 'invoice',
        filters: { date_from: '2024-01-01', status: ['paid'] },
        columns: ['number', 'client_name', 'amount'],
        export_format: 'pdf',
        template_id: 1,
      });
      expect(mockOpen).toHaveBeenCalledWith('https://example.com/download/123', '_blank');
    });
  });

  it('handles preview refresh', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    // Select template
    await waitFor(() => {
      const templateCards = screen.getAllByText('Monthly Invoice Report');
      fireEvent.click(templateCards[1]);
    });
    
    const previewTab = screen.getByRole('tab', { name: 'Preview & Generate' });
    fireEvent.click(previewTab);
    
    const refreshButton = screen.getByText('Refresh Preview');
    fireEvent.click(refreshButton);
    
    await waitFor(() => {
      expect(reportApi.previewReport).toHaveBeenCalledTimes(2); // Once on selection, once on refresh
    });
  });

  it('shows shared badge for shared templates', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    
    renderComponent();
    
    await waitFor(() => {
      const sharedBadges = screen.getAllByText('Shared');
      expect(sharedBadges).toHaveLength(1); // Only Client Summary is shared
    });
  });

  it('displays template metadata correctly', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('1 filters • 3 columns')).toBeInTheDocument();
      expect(screen.getByText('1 filters • 2 columns')).toBeInTheDocument();
      expect(screen.getByText('Created 1/1/2024')).toBeInTheDocument();
      expect(screen.getByText('Created 1/2/2024')).toBeInTheDocument();
    });
  });

  it('handles templates with no filters', async () => {
    const templatesWithoutFilters = [
      {
        ...mockTemplates[0],
        filters: {},
      },
    ];
    
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: templatesWithoutFilters, 
      total: 1 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    await waitFor(() => {
      const templateCards = screen.getAllByText('Monthly Invoice Report');
      fireEvent.click(templateCards[1]);
    });
    
    const previewTab = screen.getByRole('tab', { name: 'Preview & Generate' });
    fireEvent.click(previewTab);
    
    expect(screen.queryByText('Active Filters')).not.toBeInTheDocument();
  });

  it('handles templates with no custom columns', async () => {
    const templatesWithoutColumns = [
      {
        ...mockTemplates[0],
        columns: undefined,
      },
    ];
    
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: templatesWithoutColumns, 
      total: 1 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    await waitFor(() => {
      const templateCards = screen.getAllByText('Monthly Invoice Report');
      fireEvent.click(templateCards[1]);
    });
    
    const previewTab = screen.getByRole('tab', { name: 'Preview & Generate' });
    fireEvent.click(previewTab);
    
    expect(screen.queryByText('Custom Columns')).not.toBeInTheDocument();
  });

  it('handles API errors gracefully', async () => {
    vi.mocked(reportApi.getTemplates).mockRejectedValue(new Error('API Error'));
    
    renderComponent();
    
    // Component should still render without crashing
    expect(screen.getByText('Template-Based Reports')).toBeInTheDocument();
  });

  it('formats filter values correctly', async () => {
    const templateWithComplexFilters = [
      {
        ...mockTemplates[0],
        filters: {
          status: ['paid', 'pending', 'overdue'],
          include_items: true,
          amount_min: 100,
        },
      },
    ];
    
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: templateWithComplexFilters, 
      total: 1 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    await waitFor(() => {
      const templateCards = screen.getAllByText('Monthly Invoice Report');
      fireEvent.click(templateCards[1]);
    });
    
    const previewTab = screen.getByRole('tab', { name: 'Preview & Generate' });
    fireEvent.click(previewTab);
    
    expect(screen.getByText('paid, pending +1 more')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('shows template sharing component for shared templates', async () => {
    vi.mocked(reportApi.getTemplates).mockResolvedValue({ 
      templates: mockTemplates, 
      total: mockTemplates.length 
    });
    vi.mocked(reportApi.previewReport).mockResolvedValue(mockPreviewData);
    
    renderComponent();
    
    // Select shared template
    await waitFor(() => {
      const templateCards = screen.getAllByText('Client Summary');
      fireEvent.click(templateCards[1]);
    });
    
    const previewTab = screen.getByRole('tab', { name: 'Preview & Generate' });
    fireEvent.click(previewTab);
    
    expect(screen.getByTestId('template-sharing')).toBeInTheDocument();
    expect(screen.getByText('Sharing for Client Summary')).toBeInTheDocument();
  });
});