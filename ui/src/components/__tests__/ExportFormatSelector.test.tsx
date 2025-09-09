import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ExportFormatSelector } from '../reports/ExportFormatSelector';

describe('ExportFormatSelector', () => {
  const mockOnFormatChange = vi.fn();
  const mockOnExport = vi.fn();

  beforeEach(() => {
    mockOnFormatChange.mockClear();
    mockOnExport.mockClear();
  });

  it('renders all export format options', () => {
    render(
      <ExportFormatSelector
        selectedFormat="pdf"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    expect(screen.getByText('Export Format')).toBeInTheDocument();
    expect(screen.getByText('PDF')).toBeInTheDocument();
    expect(screen.getByText('Excel')).toBeInTheDocument();
    expect(screen.getByText('CSV')).toBeInTheDocument();
    expect(screen.getByText('JSON')).toBeInTheDocument();
  });

  it('shows recommended badge for PDF', () => {
    render(
      <ExportFormatSelector
        selectedFormat="pdf"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    expect(screen.getByText('Recommended')).toBeInTheDocument();
  });

  it('handles format selection', async () => {
    const user = userEvent.setup();
    
    render(
      <ExportFormatSelector
        selectedFormat="pdf"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    await user.click(screen.getByText('Excel'));
    expect(mockOnFormatChange).toHaveBeenCalledWith('excel');
  });

  it('highlights selected format', () => {
    render(
      <ExportFormatSelector
        selectedFormat="excel"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    const pdfButton = screen.getByText('PDF').closest('button');
    const excelButton = screen.getByText('Excel').closest('button');

    expect(pdfButton).not.toHaveClass('bg-primary');
    expect(excelButton).toHaveClass('bg-primary');
  });

  it('shows format-specific details', () => {
    render(
      <ExportFormatSelector
        selectedFormat="pdf"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    expect(screen.getByText('PDF Format')).toBeInTheDocument();
    expect(screen.getByText('✓ Professional formatting')).toBeInTheDocument();
    expect(screen.getByText('✓ Company branding')).toBeInTheDocument();
    expect(screen.getByText('✓ Print-ready layout')).toBeInTheDocument();
  });

  it('shows Excel-specific details when Excel is selected', () => {
    render(
      <ExportFormatSelector
        selectedFormat="excel"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    expect(screen.getByText('Excel Format')).toBeInTheDocument();
    expect(screen.getByText('✓ Multiple worksheets')).toBeInTheDocument();
    expect(screen.getByText('✓ Formatted cells')).toBeInTheDocument();
    expect(screen.getByText('✓ Charts and graphs')).toBeInTheDocument();
  });

  it('handles export button click', async () => {
    const user = userEvent.setup();
    
    render(
      <ExportFormatSelector
        selectedFormat="pdf"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    await user.click(screen.getByText('Export as PDF'));
    expect(mockOnExport).toHaveBeenCalledTimes(1);
  });

  it('shows loading state', () => {
    render(
      <ExportFormatSelector
        selectedFormat="pdf"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={true}
      />
    );

    expect(screen.getByText('Generating Report...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generating report/i })).toBeDisabled();
  });

  it('disables components when disabled prop is true', () => {
    render(
      <ExportFormatSelector
        selectedFormat="pdf"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
        disabled={true}
      />
    );

    const pdfButton = screen.getByText('PDF').closest('button');
    const exportButton = screen.getByText('Export as PDF');

    expect(pdfButton).toBeDisabled();
    expect(exportButton).toBeDisabled();
  });

  it('shows export tips', () => {
    render(
      <ExportFormatSelector
        selectedFormat="pdf"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    expect(screen.getByText(/PDF format is recommended for sharing/)).toBeInTheDocument();
    expect(screen.getByText(/Use Excel or CSV for further data analysis/)).toBeInTheDocument();
  });

  it('updates export button text based on selected format', () => {
    const { rerender } = render(
      <ExportFormatSelector
        selectedFormat="pdf"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    expect(screen.getByText('Export as PDF')).toBeInTheDocument();

    rerender(
      <ExportFormatSelector
        selectedFormat="csv"
        onFormatChange={mockOnFormatChange}
        onExport={mockOnExport}
        loading={false}
      />
    );

    expect(screen.getByText('Export as CSV')).toBeInTheDocument();
  });
});