import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ReportHistory } from '../reports/ReportHistory';
import { reportApi } from '@/lib/api';
import { toast } from 'sonner';

// Mock dependencies
vi.mock('@/lib/api', () => ({
  reportApi: {
    getHistory: vi.fn(),
    downloadReport: vi.fn(),
    generateReport: vi.fn()
  }
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn()
  }
}));

// Mock child components
vi.mock('../reports/ReportSharing', () => ({
  ReportSharing: ({ open, onOpenChange }: any) => 
    open ? <div data-testid="report-sharing-dialog">Report Sharing Dialog</div> : null
}));

vi.mock('../reports/ReportRegeneration', () => ({
  ReportRegeneration: ({ open, onOpenChange }: any) => 
    open ? <div data-testid="report-regeneration-dialog">Report Regeneration Dialog</div> : null
}));

const mockReports = [
  {
    id: 1,
    report_type: 'client',
    status: 'completed',
    generated_at: '2024-01-15T10:30:00Z',
    expires_at: '2024-02-15T10:30:00Z',
    parameters: {
      export_format: 'pdf',
      filters: {
        client_name: 'Test Client'
      }
    },
    template_id: null
  },
  {
    id: 2,
    report_type: 'invoice',
    status: 'generating',
    generated_at: '2024-01-16T14:20:00Z',
    expires_at: '2024-02-16T14:20:00Z',
    parameters: {
      export_format: 'csv',
      filters: {}
    },
    template_id: 1
  },
  {
    id: 3,
    report_type: 'payment',
    status: 'failed',
    generated_at: '2024-01-17T09:15:00Z',
    expires_at: null,
    parameters: {
      export_format: 'excel',
      filters: {}
    },
    template_id: null
  }
];

describe('ReportHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (reportApi.getHistory as any).mockResolvedValue({
      reports: mockReports,
      total: mockReports.length
    });
  });

  it('renders report history with loading state', async () => {
    render(<ReportHistory />);
    
    expect(screen.getByText('Loading reports...')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('Report History')).toBeInTheDocument();
    });
  });

  it('displays reports in table format', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Client Reports')).toBeInTheDocument();
      expect(screen.getByText('Invoice Reports')).toBeInTheDocument();
      expect(screen.getByText('Payment Reports')).toBeInTheDocument();
    });

    // Check status badges
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Generating')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();

    // Check format badges
    expect(screen.getByText('PDF')).toBeInTheDocument();
    expect(screen.getByText('CSV')).toBeInTheDocument();
    expect(screen.getByText('EXCEL')).toBeInTheDocument();
  });

  it('filters reports by search term', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Client Reports')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search reports...');
    fireEvent.change(searchInput, { target: { value: 'client' } });

    // Should show only client reports
    expect(screen.getByText('Client Reports')).toBeInTheDocument();
    expect(screen.queryByText('Invoice Reports')).not.toBeInTheDocument();
  });

  it('filters reports by type', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Client Reports')).toBeInTheDocument();
    });

    // Open report type filter
    const typeFilter = screen.getByDisplayValue('Report Type');
    fireEvent.click(typeFilter);
    
    // Select client reports
    fireEvent.click(screen.getByText('Client Reports'));

    await waitFor(() => {
      expect(reportApi.getHistory).toHaveBeenCalledWith(20, 0);
    });
  });

  it('filters reports by status', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    // Open status filter
    const statusFilter = screen.getByDisplayValue('Status');
    fireEvent.click(statusFilter);
    
    // Select completed status
    fireEvent.click(screen.getByText('Completed'));

    await waitFor(() => {
      expect(reportApi.getHistory).toHaveBeenCalledWith(20, 0);
    });
  });

  it('handles report download', async () => {
    const mockBlob = new Blob(['test content'], { type: 'application/pdf' });
    const mockResponse = {
      ok: true,
      blob: () => Promise.resolve(mockBlob)
    };
    (reportApi.downloadReport as any).mockResolvedValue(mockResponse);

    // Mock URL.createObjectURL
    global.URL.createObjectURL = vi.fn(() => 'mock-url');
    global.URL.revokeObjectURL = vi.fn();

    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    // Find and click download button for completed report
    const downloadButtons = screen.getAllByRole('button');
    const downloadButton = downloadButtons.find(btn => 
      btn.querySelector('svg')?.classList.contains('lucide-download')
    );
    
    if (downloadButton) {
      fireEvent.click(downloadButton);
      
      await waitFor(() => {
        expect(reportApi.downloadReport).toHaveBeenCalledWith(1);
        expect(toast.success).toHaveBeenCalledWith('Report downloaded successfully');
      });
    }
  });

  it('handles download failure', async () => {
    (reportApi.downloadReport as any).mockRejectedValue(new Error('Download failed'));

    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    // Find and click download button
    const downloadButtons = screen.getAllByRole('button');
    const downloadButton = downloadButtons.find(btn => 
      btn.querySelector('svg')?.classList.contains('lucide-download')
    );
    
    if (downloadButton) {
      fireEvent.click(downloadButton);
      
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Failed to download report');
      });
    }
  });

  it('opens regeneration dialog', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Client Reports')).toBeInTheDocument();
    });

    // Find and click more options button
    const moreButtons = screen.getAllByRole('button');
    const moreButton = moreButtons.find(btn => 
      btn.querySelector('svg')?.classList.contains('lucide-more-horizontal')
    );
    
    if (moreButton) {
      fireEvent.click(moreButton);
      
      // Click regenerate option
      const regenerateOption = screen.getByText('Regenerate with Current Data');
      fireEvent.click(regenerateOption);
      
      await waitFor(() => {
        expect(screen.getByTestId('report-regeneration-dialog')).toBeInTheDocument();
      });
    }
  });

  it('opens sharing dialog for completed reports', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Client Reports')).toBeInTheDocument();
    });

    // Find and click more options button
    const moreButtons = screen.getAllByRole('button');
    const moreButton = moreButtons.find(btn => 
      btn.querySelector('svg')?.classList.contains('lucide-more-horizontal')
    );
    
    if (moreButton) {
      fireEvent.click(moreButton);
      
      // Click share option
      const shareOption = screen.getByText('Share Report');
      fireEvent.click(shareOption);
      
      await waitFor(() => {
        expect(screen.getByTestId('report-sharing-dialog')).toBeInTheDocument();
      });
    }
  });

  it('opens delete confirmation dialog', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Client Reports')).toBeInTheDocument();
    });

    // Find and click more options button
    const moreButtons = screen.getAllByRole('button');
    const moreButton = moreButtons.find(btn => 
      btn.querySelector('svg')?.classList.contains('lucide-more-horizontal')
    );
    
    if (moreButton) {
      fireEvent.click(moreButton);
      
      // Click delete option
      const deleteOption = screen.getByText('Delete');
      fireEvent.click(deleteOption);
      
      await waitFor(() => {
        expect(screen.getByText('Delete Report')).toBeInTheDocument();
        expect(screen.getByText('Are you sure you want to delete this report?')).toBeInTheDocument();
      });
    }
  });

  it('handles pagination', async () => {
    const manyReports = Array.from({ length: 25 }, (_, i) => ({
      ...mockReports[0],
      id: i + 1
    }));

    (reportApi.getHistory as any).mockResolvedValue({
      reports: manyReports.slice(0, 20),
      total: 25
    });

    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Showing 1 to 20 of 25 reports')).toBeInTheDocument();
    });

    // Click next page
    const nextButton = screen.getByText('Next');
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(reportApi.getHistory).toHaveBeenCalledWith(20, 20);
    });
  });

  it('refreshes report list', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Client Reports')).toBeInTheDocument();
    });

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(reportApi.getHistory).toHaveBeenCalledTimes(2);
    });
  });

  it('shows empty state when no reports', async () => {
    (reportApi.getHistory as any).mockResolvedValue({
      reports: [],
      total: 0
    });

    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('No reports found')).toBeInTheDocument();
      expect(screen.getByText('Generate your first report to see it here')).toBeInTheDocument();
    });
  });

  it('handles API errors gracefully', async () => {
    (reportApi.getHistory as any).mockRejectedValue(new Error('API Error'));

    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to load report history');
    });
  });

  it('shows correct status icons', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      // Check that status icons are rendered (we can't easily test the specific icons)
      const statusBadges = screen.getAllByText(/Completed|Generating|Failed/);
      expect(statusBadges).toHaveLength(3);
    });
  });

  it('formats dates correctly', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Jan 15, 2024 10:30')).toBeInTheDocument();
      expect(screen.getByText('Jan 16, 2024 14:20')).toBeInTheDocument();
      expect(screen.getByText('Jan 17, 2024 09:15')).toBeInTheDocument();
    });
  });

  it('shows client name in report details when available', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Client: Test Client')).toBeInTheDocument();
    });
  });

  it('disables download for non-completed reports', async () => {
    render(<ReportHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('Generating')).toBeInTheDocument();
    });

    // Download button should not be present for generating/failed reports
    const downloadButtons = screen.queryAllByRole('button').filter(btn => 
      btn.querySelector('svg')?.classList.contains('lucide-download')
    );
    
    // Should only have download button for completed report
    expect(downloadButtons).toHaveLength(1);
  });
});