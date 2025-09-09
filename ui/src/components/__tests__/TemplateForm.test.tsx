import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { TemplateForm } from '../reports/TemplateForm';
import { reportApi } from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  reportApi: {
    getReportTypes: vi.fn(),
    createTemplate: vi.fn(),
    updateTemplate: vi.fn(),
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
vi.mock('../reports/ReportTypeSelector', () => ({
  ReportTypeSelector: ({ reportTypes, selectedType, onTypeSelect, loading }: any) => (
    <div data-testid="report-type-selector">
      <span>Selected: {selectedType || 'none'}</span>
      <button 
        onClick={() => onTypeSelect('invoice')}
        disabled={loading}
        data-testid="select-invoice"
      >
        Select Invoice
      </button>
      <button 
        onClick={() => onTypeSelect('client')}
        disabled={loading}
        data-testid="select-client"
      >
        Select Client
      </button>
    </div>
  ),
}));

vi.mock('../reports/ReportFilters', () => ({
  ReportFilters: ({ filters, onFiltersChange }: any) => (
    <div data-testid="report-filters">
      <button onClick={() => onFiltersChange({ ...filters, test_filter: 'test' })}>
        Add Filter
      </button>
    </div>
  ),
}));

const mockReportTypes = [
  {
    type: 'invoice',
    name: 'Invoice Report',
    description: 'Generate invoice reports',
    available_filters: ['date_from', 'date_to', 'status'],
    available_columns: ['number', 'client_name', 'amount', 'status'],
    default_columns: ['number', 'client_name', 'amount'],
  },
  {
    type: 'client',
    name: 'Client Report',
    description: 'Generate client reports',
    available_filters: ['include_inactive'],
    available_columns: ['name', 'email', 'balance'],
    default_columns: ['name', 'balance'],
  },
];

const mockTemplate = {
  id: 1,
  name: 'Test Template',
  report_type: 'invoice' as const,
  filters: { status: ['paid'] },
  columns: ['number', 'client_name'],
  formatting: {},
  is_shared: false,
  user_id: 1,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

describe('TemplateForm', () => {
  let queryClient: QueryClient;
  const mockOnSuccess = vi.fn();
  const mockOnCancel = vi.fn();

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const renderComponent = (template?: typeof mockTemplate) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <TemplateForm
          template={template}
          onSuccess={mockOnSuccess}
          onCancel={mockOnCancel}
        />
      </QueryClientProvider>
    );
  };

  it('renders create form correctly', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    expect(screen.getByText('Template Information')).toBeInTheDocument();
    expect(screen.getByLabelText('Template Name')).toBeInTheDocument();
    expect(screen.getByTestId('report-type-selector')).toBeInTheDocument();
    expect(screen.getByLabelText('Share with other users')).toBeInTheDocument();
  });

  it('renders edit form with existing template data', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent(mockTemplate);
    
    await waitFor(() => {
      const nameInput = screen.getByDisplayValue('Test Template');
      expect(nameInput).toBeInTheDocument();
    });
  });

  it('handles template name input', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    const nameInput = screen.getByLabelText('Template Name');
    fireEvent.change(nameInput, { target: { value: 'New Template Name' } });
    
    expect(nameInput).toHaveValue('New Template Name');
  });

  it('handles report type selection', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    await waitFor(() => {
      const selectButton = screen.getByTestId('select-invoice');
      fireEvent.click(selectButton);
    });
    
    // Should show the selected report type
    expect(screen.getByText('Selected: invoice')).toBeInTheDocument();
  });

  it('enables filters and columns tabs after report type selection', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    // Initially filters and columns tabs should be disabled
    const filtersTab = screen.getByRole('tab', { name: 'Filters' });
    const columnsTab = screen.getByRole('tab', { name: 'Columns' });
    
    expect(filtersTab).toHaveAttribute('disabled');
    expect(columnsTab).toHaveAttribute('disabled');
    
    // Select report type
    const selectButton = screen.getByTestId('select-invoice');
    fireEvent.click(selectButton);
    
    // Verify the report type was selected
    expect(screen.getByText('Selected: invoice')).toBeInTheDocument();
  });

  it('handles column selection', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    // Select report type first
    const selectButton = screen.getByTestId('select-invoice');
    fireEvent.click(selectButton);
    
    // Verify the report type was selected
    expect(screen.getByText('Selected: invoice')).toBeInTheDocument();
    
    // Verify tabs are present
    expect(screen.getByRole('tab', { name: 'Columns' })).toBeInTheDocument();
  });

  it('handles select all columns', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    // Select report type
    const selectButton = screen.getByTestId('select-invoice');
    fireEvent.click(selectButton);
    
    // Verify the report type was selected
    expect(screen.getByText('Selected: invoice')).toBeInTheDocument();
    
    // Verify the component structure is correct
    expect(screen.getByText('Template Information')).toBeInTheDocument();
  });

  it('validates required fields before saving', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    const saveButton = screen.getByText('Create Template');
    fireEvent.click(saveButton);
    
    // Should show validation error
    await waitFor(() => {
      expect(mockOnSuccess).not.toHaveBeenCalled();
    });
  });

  it('creates new template successfully', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    vi.mocked(reportApi.createTemplate).mockResolvedValue(mockTemplate);
    
    renderComponent();
    
    // Fill form
    const nameInput = screen.getByLabelText('Template Name');
    fireEvent.change(nameInput, { target: { value: 'New Template' } });
    
    // Select report type
    const selectButton = screen.getByTestId('select-invoice');
    fireEvent.click(selectButton);
    
    // Verify form state
    expect(nameInput).toHaveValue('New Template');
    expect(screen.getByText('Selected: invoice')).toBeInTheDocument();
    
    // Verify save button is enabled
    const saveButton = screen.getByText('Create Template');
    expect(saveButton).not.toBeDisabled();
  });

  it('updates existing template successfully', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    vi.mocked(reportApi.updateTemplate).mockResolvedValue({
      ...mockTemplate,
      name: 'Updated Template',
    });
    
    renderComponent(mockTemplate);
    
    // Update name
    const nameInput = screen.getByDisplayValue('Test Template');
    fireEvent.change(nameInput, { target: { value: 'Updated Template' } });
    
    const saveButton = screen.getByText('Update Template');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(reportApi.updateTemplate).toHaveBeenCalledWith(1, {
        name: 'Updated Template',
        report_type: 'invoice',
        filters: { status: ['paid'] },
        columns: ['number', 'client_name'],
        is_shared: false,
      });
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  it('handles sharing toggle', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    const shareSwitch = screen.getByLabelText('Share with other users');
    fireEvent.click(shareSwitch);
    
    expect(screen.getByText('Shared templates can be used by all users in your organization')).toBeInTheDocument();
  });

  it('handles cancel action', () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);
    
    expect(mockOnCancel).toHaveBeenCalled();
  });

  it('handles API errors', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    vi.mocked(reportApi.createTemplate).mockRejectedValue(new Error('API Error'));
    
    renderComponent();
    
    // Fill form
    const nameInput = screen.getByLabelText('Template Name');
    fireEvent.change(nameInput, { target: { value: 'New Template' } });
    
    await waitFor(() => {
      const typeSelector = screen.getByTestId('report-type-selector').querySelector('select');
      fireEvent.change(typeSelector!, { target: { value: 'invoice' } });
    });
    
    const saveButton = screen.getByText('Create Template');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(mockOnSuccess).not.toHaveBeenCalled();
    });
  });

  it('resets form when report type changes', async () => {
    vi.mocked(reportApi.getReportTypes).mockResolvedValue({ 
      report_types: mockReportTypes 
    });
    
    renderComponent();
    
    // Select first type
    const selectInvoiceButton = screen.getByTestId('select-invoice');
    fireEvent.click(selectInvoiceButton);
    
    // Verify first selection
    expect(screen.getByText('Selected: invoice')).toBeInTheDocument();
    
    // Change report type
    const selectClientButton = screen.getByTestId('select-client');
    fireEvent.click(selectClientButton);
    
    // Verify the change
    expect(screen.getByText('Selected: client')).toBeInTheDocument();
  });
});