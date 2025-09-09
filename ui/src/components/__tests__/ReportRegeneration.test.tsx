import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ReportRegeneration } from '../reports/ReportRegeneration';
import { reportApi } from '@/lib/api';
import { toast } from 'sonner';

// Mock dependencies
vi.mock('@/lib/api', () => ({
  reportApi: {
    generateReport: vi.fn(),
    downloadReport: vi.fn()
  }
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn()
  }
}));

const mockReport = {
  id: 1,
  report_type: 'client',
  status: 'completed',
  generated_at: '2024-01-15T10:30:00Z',
  expires_at: '2024-02-15T10:30:00Z',
  parameters: {
    export_format: 'pdf',
    filters: {
      client_name: 'Test Client',
      date_from: '2024-01-01T00:00:00Z',
      date_to: '2024-01-31T23:59:59Z'
    },
    columns: ['name', 'email', 'total']
  },
  template_id: 1
};

describe('ReportRegeneration', () => {
  const mockOnOpenChange = vi.fn();
  const mockOnRegenerated = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    (reportApi.generateReport as any).mockResolvedValue({
      success: true,
      report_id: 123
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders regeneration dialog when open', () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    expect(screen.getByText('Regenerate Report')).toBeInTheDocument();
    expect(screen.getByText('Generate a new version of this report with current data.')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={false}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    expect(screen.queryByText('Regenerate Report')).not.toBeInTheDocument();
  });

  it('displays original report information', () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    expect(screen.getByText('Original Report')).toBeInTheDocument();
    expect(screen.getByText('Client Report')).toBeInTheDocument();
    expect(screen.getByText('PDF')).toBeInTheDocument();
    expect(screen.getByText('Jan 15, 2024 10:30')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
  });

  it('shows applied filters', () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    expect(screen.getByText('Applied Filters')).toBeInTheDocument();
    expect(screen.getByText('Client name:')).toBeInTheDocument();
    expect(screen.getByText('Test Client')).toBeInTheDocument();
  });

  it('shows data changes notice', () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    expect(screen.getByText('Data Changes Notice')).toBeInTheDocument();
    expect(screen.getByText(/The regenerated report will use current data/)).toBeInTheDocument();
  });

  it('starts regeneration process', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(reportApi.generateReport).toHaveBeenCalledWith({
        report_type: 'client',
        filters: {
          client_name: 'Test Client',
          date_from: '2024-01-01T00:00:00Z',
          date_to: expect.any(String) // Current date
        },
        columns: ['name', 'email', 'total'],
        export_format: 'pdf',
        template_id: 1
      });
      expect(toast.success).toHaveBeenCalledWith('Report regeneration started');
    });
  });

  it('shows progress during regeneration', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText('Regeneration Status')).toBeInTheDocument();
    });

    // Advance timers to simulate progress
    vi.advanceTimersByTime(2000);

    await waitFor(() => {
      expect(screen.getByText('Validating Parameters')).toBeInTheDocument();
    });

    // Continue advancing through stages
    vi.advanceTimersByTime(2000);
    await waitFor(() => {
      expect(screen.getByText('Fetching Data')).toBeInTheDocument();
    });
  });

  it('shows progress bar during regeneration', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  it('shows estimated time remaining', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    vi.advanceTimersByTime(2000);

    await waitFor(() => {
      expect(screen.getByText(/remaining/)).toBeInTheDocument();
    });
  });

  it('completes regeneration successfully', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    // Fast forward through all stages
    vi.advanceTimersByTime(12000); // 6 stages * 2 seconds each

    await waitFor(() => {
      expect(screen.getByText('Report regenerated successfully')).toBeInTheDocument();
      expect(screen.getByText('Download')).toBeInTheDocument();
    });
  });

  it('handles regeneration API failure', async () => {
    (reportApi.generateReport as any).mockRejectedValue(new Error('API Error'));

    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to start regeneration');
      expect(screen.getByText('Regeneration failed')).toBeInTheDocument();
    });
  });

  it('shows error message on failure', async () => {
    (reportApi.generateReport as any).mockRejectedValue(new Error('Custom error message'));

    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText('Custom error message')).toBeInTheDocument();
    });
  });

  it('downloads regenerated report', async () => {
    const mockBlob = new Blob(['test content'], { type: 'application/pdf' });
    const mockResponse = {
      ok: true,
      blob: () => Promise.resolve(mockBlob)
    };
    (reportApi.downloadReport as any).mockResolvedValue(mockResponse);

    // Mock URL.createObjectURL
    global.URL.createObjectURL = vi.fn(() => 'mock-url');
    global.URL.revokeObjectURL = vi.fn();

    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    // Complete regeneration
    vi.advanceTimersByTime(12000);

    await waitFor(() => {
      expect(screen.getByText('Download')).toBeInTheDocument();
    });

    const downloadButton = screen.getByText('Download');
    fireEvent.click(downloadButton);

    await waitFor(() => {
      expect(reportApi.downloadReport).toHaveBeenCalled();
      expect(toast.success).toHaveBeenCalledWith('Regenerated report downloaded successfully');
    });
  });

  it('handles download failure', async () => {
    (reportApi.downloadReport as any).mockRejectedValue(new Error('Download failed'));

    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    // Complete regeneration
    vi.advanceTimersByTime(12000);

    await waitFor(() => {
      expect(screen.getByText('Download')).toBeInTheDocument();
    });

    const downloadButton = screen.getByText('Download');
    fireEvent.click(downloadButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to download regenerated report');
    });
  });

  it('closes dialog normally when not regenerating', () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const closeButton = screen.getByText('Close');
    fireEvent.click(closeButton);

    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  it('shows confirmation dialog when closing during regeneration', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText('Validating Parameters')).toBeInTheDocument();
    });

    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.getByText('Cancel Regeneration?')).toBeInTheDocument();
      expect(screen.getByText(/The report regeneration is currently in progress/)).toBeInTheDocument();
    });
  });

  it('allows force close during regeneration', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText('Validating Parameters')).toBeInTheDocument();
    });

    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.getByText('Close Anyway')).toBeInTheDocument();
    });

    const forceCloseButton = screen.getByText('Close Anyway');
    fireEvent.click(forceCloseButton);

    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  it('formats time remaining correctly', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    vi.advanceTimersByTime(2000);

    await waitFor(() => {
      // Should show time in seconds or minutes format
      expect(screen.getByText(/\d+[sm]/)).toBeInTheDocument();
    });
  });

  it('disables start button during regeneration', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.queryByText('Start Regeneration')).not.toBeInTheDocument();
    });
  });

  it('shows correct status icons', async () => {
    render(
      <ReportRegeneration
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
        onRegenerated={mockOnRegenerated}
      />
    );

    // Initially should show clock icon (ready state)
    expect(screen.getByText('Ready to regenerate')).toBeInTheDocument();

    const startButton = screen.getByText('Start Regeneration');
    fireEvent.click(startButton);

    // During regeneration should show spinning icon
    await waitFor(() => {
      expect(screen.getByText(/Validating Parameters|Fetching Data|Processing Data/)).toBeInTheDocument();
    });
  });
});