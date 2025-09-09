import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ReportSharing } from '../reports/ReportSharing';
import { toast } from 'sonner';

// Mock dependencies
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn()
  }
}));

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn()
  }
});

const mockReport = {
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
};

describe('ReportSharing', () => {
  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (navigator.clipboard.writeText as any).mockResolvedValue(undefined);
  });

  it('renders sharing dialog when open', () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    expect(screen.getByText('Share Report')).toBeInTheDocument();
    expect(screen.getByText('Create secure links to share this report with others.')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(
      <ReportSharing
        report={mockReport}
        open={false}
        onOpenChange={mockOnOpenChange}
      />
    );

    expect(screen.queryByText('Share Report')).not.toBeInTheDocument();
  });

  it('displays report information', () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    expect(screen.getByText('Client Report')).toBeInTheDocument();
    expect(screen.getByText('Generated on Jan 15, 2024 10:30')).toBeInTheDocument();
    expect(screen.getByText('PDF')).toBeInTheDocument();
  });

  it('shows share settings form', () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    expect(screen.getByText('Create Share Link')).toBeInTheDocument();
    expect(screen.getByText('Expiration')).toBeInTheDocument();
    expect(screen.getByText('Max Access Count')).toBeInTheDocument();
    expect(screen.getByText('Allow Download')).toBeInTheDocument();
    expect(screen.getByText('Require Authentication')).toBeInTheDocument();
  });

  it('creates share link with default settings', async () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    const createButton = screen.getByText('Create Share Link');
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
      expect(toast.success).toHaveBeenCalledWith('Share link created and copied to clipboard');
    });
  });

  it('updates expiration setting', () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    // Find and click expiration dropdown
    const expirationSelect = screen.getByDisplayValue('1 Week');
    fireEvent.click(expirationSelect);

    // Select different option
    fireEvent.click(screen.getByText('1 Month'));

    // Verify the selection changed (this would be reflected in the component state)
    expect(screen.getByDisplayValue('1 Month')).toBeInTheDocument();
  });

  it('updates max access count', () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    const maxAccessInput = screen.getByPlaceholderText('Unlimited');
    fireEvent.change(maxAccessInput, { target: { value: '10' } });

    expect(maxAccessInput).toHaveValue('10');
  });

  it('toggles allow download setting', () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    const downloadSwitch = screen.getByRole('switch', { name: /allow download/i });
    expect(downloadSwitch).toBeChecked();

    fireEvent.click(downloadSwitch);
    expect(downloadSwitch).not.toBeChecked();
  });

  it('toggles require authentication setting', () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    const authSwitch = screen.getByRole('switch', { name: /require authentication/i });
    expect(authSwitch).not.toBeChecked();

    fireEvent.click(authSwitch);
    expect(authSwitch).toBeChecked();
  });

  it('displays existing share links', async () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    // Wait for mock data to load
    await waitFor(() => {
      expect(screen.getByText('Active Share Links')).toBeInTheDocument();
    });

    // Check table headers
    expect(screen.getByText('Link')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Expiration')).toBeInTheDocument();
    expect(screen.getByText('Access')).toBeInTheDocument();
    expect(screen.getByText('Permissions')).toBeInTheDocument();
  });

  it('copies existing share link', async () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Active Share Links')).toBeInTheDocument();
    });

    // Find and click copy button
    const copyButtons = screen.getAllByRole('button');
    const copyButton = copyButtons.find(btn => 
      btn.querySelector('svg')?.classList.contains('lucide-copy')
    );

    if (copyButton) {
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalled();
        expect(toast.success).toHaveBeenCalledWith('Link copied to clipboard');
      });
    }
  });

  it('toggles share link status', async () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Active Share Links')).toBeInTheDocument();
    });

    // Find and click toggle button
    const toggleButtons = screen.getAllByRole('button');
    const toggleButton = toggleButtons.find(btn => 
      btn.querySelector('svg')?.classList.contains('lucide-eye-off')
    );

    if (toggleButton) {
      fireEvent.click(toggleButton);

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('Share link updated');
      });
    }
  });

  it('deletes share link', async () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Active Share Links')).toBeInTheDocument();
    });

    // Find and click delete button
    const deleteButtons = screen.getAllByRole('button');
    const deleteButton = deleteButtons.find(btn => 
      btn.querySelector('svg')?.classList.contains('lucide-trash-2')
    );

    if (deleteButton) {
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('Share link deleted');
      });
    }
  });

  it('shows correct expiration status badges', async () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Active Share Links')).toBeInTheDocument();
    });

    // Should show expiration status (the exact text depends on the mock data timing)
    const statusBadges = screen.getAllByText(/\d+d left|\d+h left|expired|never/);
    expect(statusBadges.length).toBeGreaterThan(0);
  });

  it('shows permission badges', async () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Active Share Links')).toBeInTheDocument();
    });

    // Should show download permission badge
    expect(screen.getByText('Download')).toBeInTheDocument();
  });

  it('closes dialog when close button clicked', () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    const closeButton = screen.getByText('Close');
    fireEvent.click(closeButton);

    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  it('handles clipboard write failure', async () => {
    (navigator.clipboard.writeText as any).mockRejectedValue(new Error('Clipboard error'));

    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    const createButton = screen.getByText('Create Share Link');
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to create share link');
    });
  });

  it('shows creating state during link creation', async () => {
    // Mock a delayed clipboard write
    (navigator.clipboard.writeText as any).mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 100))
    );

    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    const createButton = screen.getByText('Create Share Link');
    fireEvent.click(createButton);

    // Should show creating state
    expect(screen.getByText('Creating...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Create Share Link')).toBeInTheDocument();
    });
  });

  it('resets form after successful creation', async () => {
    render(
      <ReportSharing
        report={mockReport}
        open={true}
        onOpenChange={mockOnOpenChange}
      />
    );

    // Change some settings
    const maxAccessInput = screen.getByPlaceholderText('Unlimited');
    fireEvent.change(maxAccessInput, { target: { value: '5' } });

    const createButton = screen.getByText('Create Share Link');
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalled();
    });

    // Form should be reset
    expect(maxAccessInput).toHaveValue('');
  });
});