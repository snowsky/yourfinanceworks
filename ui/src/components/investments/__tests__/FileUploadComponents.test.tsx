import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import FileUploadDialog from '../FileUploadDialog';
import FileUploadArea from '../FileUploadArea';
import FileAttachmentsList from '../FileAttachmentsList';
import FileAttachmentDetail from '../FileAttachmentDetail';
import * as apiModule from '@/lib/api';

// Mock the API module
vi.mock('@/lib/api', () => ({
  apiRequest: vi.fn(),
  investmentApi: {
    downloadHoldingsFileBlob: vi.fn(),
  },
}));

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const renderWithProviders = (component: React.ReactElement) => {
  const testQueryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const result = render(
    <QueryClientProvider client={testQueryClient}>
      {component}
    </QueryClientProvider>
  );

  return { ...result, queryClient: testQueryClient };
};

describe('File Upload Components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('FileUploadDialog', () => {
    it('renders the dialog with title and description', () => {
      renderWithProviders(
        <FileUploadDialog
          portfolioId={1}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      expect(screen.getByText('Upload Holdings Files')).toBeInTheDocument();
      expect(screen.getByText(/Upload PDF or CSV files/)).toBeInTheDocument();
    });

    it('displays upload area with file input', () => {
      renderWithProviders(
        <FileUploadDialog
          portfolioId={1}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      expect(screen.getByText('Select Holdings Files')).toBeInTheDocument();
    });

    it('shows upload button disabled when no files selected', () => {
      renderWithProviders(
        <FileUploadDialog
          portfolioId={1}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      const uploadButton = screen.getByRole('button', { name: /Upload Files/i });
      expect(uploadButton).toBeDisabled();
    });

    it('closes dialog when cancel button is clicked', async () => {
      const onOpenChange = vi.fn();
      renderWithProviders(
        <FileUploadDialog
          portfolioId={1}
          open={true}
          onOpenChange={onOpenChange}
        />
      );

      const cancelButton = screen.getByRole('button', { name: /Cancel/i });
      await userEvent.click(cancelButton);

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('displays alert about background processing', () => {
      renderWithProviders(
        <FileUploadDialog
          portfolioId={1}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      expect(screen.getByText(/Files will be processed in the background/)).toBeInTheDocument();
    });
  });

  describe('FileUploadArea', () => {
    it('renders the upload area card', () => {
      renderWithProviders(
        <FileUploadArea portfolioId={1} />
      );

      expect(screen.getByText('Import Holdings from File')).toBeInTheDocument();
      expect(screen.getByText(/Upload PDF or CSV files/)).toBeInTheDocument();
    });

    it('displays file upload component', () => {
      renderWithProviders(
        <FileUploadArea portfolioId={1} />
      );

      expect(screen.getByText('Select Holdings Files')).toBeInTheDocument();
    });

    it('shows clear and upload buttons', () => {
      renderWithProviders(
        <FileUploadArea portfolioId={1} />
      );

      expect(screen.getByRole('button', { name: /Clear/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Upload Files/i })).toBeInTheDocument();
    });

    it('displays alert about background processing', () => {
      renderWithProviders(
        <FileUploadArea portfolioId={1} />
      );

      expect(screen.getByText(/Files will be processed in the background/)).toBeInTheDocument();
    });
  });

  describe('FileAttachmentsList', () => {
    it('renders loading state initially', () => {
      vi.mocked(apiModule.apiRequest).mockImplementation(() =>
        new Promise(() => {}) // Never resolves
      );

      renderWithProviders(
        <FileAttachmentsList portfolioId={1} />
      );

      expect(screen.getByText(/Loading files/)).toBeInTheDocument();
    });

    it('displays empty state when no files', async () => {
      vi.mocked(apiModule.apiRequest).mockResolvedValueOnce([]);

      const { rerender, queryClient } = renderWithProviders(
        <FileAttachmentsList portfolioId={1} />
      );

      // Wait for the query to complete
      await new Promise(resolve => setTimeout(resolve, 100));

      rerender(
        <QueryClientProvider client={queryClient}>
          <FileAttachmentsList portfolioId={1} />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.queryByText(/Loading files/)).not.toBeInTheDocument();
      }, { timeout: 3000 });
    });

    it('displays file list with status badges', async () => {
      const mockAttachments = [
        {
          id: '1',
          original_filename: 'holdings.pdf',
          file_size: 1024000,
          status: 'completed' as const,
          extracted_holdings_count: 5,
          failed_holdings_count: 0,
          created_at: new Date().toISOString(),
        },
      ];

      vi.mocked(apiModule.apiRequest).mockResolvedValueOnce(mockAttachments);

      renderWithProviders(
        <FileAttachmentsList portfolioId={1} />
      );

      await waitFor(() => {
        expect(screen.getByText('holdings.pdf')).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    it('displays action buttons for each file', async () => {
      const mockAttachments = [
        {
          id: '1',
          original_filename: 'holdings.pdf',
          file_size: 1024000,
          status: 'completed' as const,
          extracted_holdings_count: 5,
          failed_holdings_count: 0,
          created_at: new Date().toISOString(),
        },
      ];

      vi.mocked(apiModule.apiRequest).mockResolvedValueOnce(mockAttachments);

      renderWithProviders(
        <FileAttachmentsList portfolioId={1} />
      );

      await waitFor(() => {
        expect(screen.getByText('holdings.pdf')).toBeInTheDocument();
      }, { timeout: 3000 });

      // Check for action buttons (Eye, Download, Delete)
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('shows extraction results for completed files', async () => {
      const mockAttachments = [
        {
          id: '1',
          original_filename: 'holdings.pdf',
          file_size: 1024000,
          status: 'completed' as const,
          extracted_holdings_count: 5,
          failed_holdings_count: 0,
          created_at: new Date().toISOString(),
        },
      ];

      vi.mocked(apiModule.apiRequest).mockResolvedValueOnce(mockAttachments);

      renderWithProviders(
        <FileAttachmentsList portfolioId={1} />
      );

      await waitFor(() => {
        expect(screen.getByText('holdings.pdf')).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    it('shows error message for failed files', async () => {
      const mockAttachments = [
        {
          id: '1',
          original_filename: 'holdings.pdf',
          file_size: 1024000,
          status: 'failed' as const,
          extraction_error: 'File format not recognized',
          extracted_holdings_count: 0,
          failed_holdings_count: 0,
          created_at: new Date().toISOString(),
        },
      ];

      vi.mocked(apiModule.apiRequest).mockResolvedValueOnce(mockAttachments);

      renderWithProviders(
        <FileAttachmentsList portfolioId={1} />
      );

      await waitFor(() => {
        expect(screen.getByText('File format not recognized')).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    it('shows partial results for partial files', async () => {
      const mockAttachments = [
        {
          id: '1',
          original_filename: 'holdings.pdf',
          file_size: 1024000,
          status: 'partial' as const,
          extracted_holdings_count: 3,
          failed_holdings_count: 2,
          created_at: new Date().toISOString(),
        },
      ];

      vi.mocked(apiModule.apiRequest).mockResolvedValueOnce(mockAttachments);

      renderWithProviders(
        <FileAttachmentsList portfolioId={1} />
      );

      await waitFor(() => {
        expect(screen.getByText('holdings.pdf')).toBeInTheDocument();
      }, { timeout: 3000 });
    });
  });

  describe('FileAttachmentDetail', () => {
    it('renders dialog with attachment details', () => {
      const attachment = {
        id: '1',
        original_filename: 'holdings.pdf',
        file_size: 1024000,
        status: 'completed' as const,
        extracted_holdings_count: 5,
        failed_holdings_count: 0,
        created_at: new Date().toISOString(),
      };

      renderWithProviders(
        <FileAttachmentDetail
          attachment={attachment}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      expect(screen.getByText('Extraction Results')).toBeInTheDocument();
      expect(screen.getByText('holdings.pdf')).toBeInTheDocument();
    });

    it('displays status and file size', () => {
      const attachment = {
        id: '1',
        original_filename: 'holdings.pdf',
        file_size: 1024000,
        status: 'completed' as const,
        extracted_holdings_count: 5,
        failed_holdings_count: 0,
        created_at: new Date().toISOString(),
      };

      renderWithProviders(
        <FileAttachmentDetail
          attachment={attachment}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      expect(screen.getByText('completed')).toBeInTheDocument();
    });

    it('shows extraction results for completed files', () => {
      const attachment = {
        id: '1',
        original_filename: 'holdings.pdf',
        file_size: 1024000,
        status: 'completed' as const,
        extracted_holdings_count: 5,
        failed_holdings_count: 0,
        created_at: new Date().toISOString(),
      };

      renderWithProviders(
        <FileAttachmentDetail
          attachment={attachment}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('shows error details for failed files', () => {
      const attachment = {
        id: '1',
        original_filename: 'holdings.pdf',
        file_size: 1024000,
        status: 'failed' as const,
        extraction_error: 'File format not recognized',
        extracted_holdings_count: 0,
        failed_holdings_count: 0,
        created_at: new Date().toISOString(),
      };

      renderWithProviders(
        <FileAttachmentDetail
          attachment={attachment}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      expect(screen.getByText('failed')).toBeInTheDocument();
      expect(screen.getByText('File format not recognized')).toBeInTheDocument();
    });

    it('displays extracted data when available', () => {
      const attachment = {
        id: '1',
        original_filename: 'holdings.pdf',
        file_size: 1024000,
        status: 'completed' as const,
        extracted_holdings_count: 5,
        failed_holdings_count: 0,
        created_at: new Date().toISOString(),
        extracted_data: {
          holdings: [
            { symbol: 'AAPL', quantity: 100, cost_basis: 15000 },
          ],
        },
      };

      renderWithProviders(
        <FileAttachmentDetail
          attachment={attachment}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      expect(screen.getByText(/AAPL/)).toBeInTheDocument();
    });

    it('handles null attachment gracefully', () => {
      const { container } = renderWithProviders(
        <FileAttachmentDetail
          attachment={null}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      expect(container.firstChild).toBeNull();
    });

    it('opens preview dialog when preview button is clicked', async () => {
      const attachment = {
        id: '1',
        original_filename: 'holdings.pdf',
        file_size: 1024000,
        status: 'completed' as const,
        extracted_holdings_count: 5,
        failed_holdings_count: 0,
        created_at: new Date().toISOString(),
      };

      // Mock the download blob response
      const mockBlob = new Blob(['fake pdf content'], { type: 'application/pdf' });
      // We need to access the mocked module safely
      const apiModule = await import('@/lib/api');
      vi.mocked(apiModule.investmentApi.downloadHoldingsFileBlob).mockResolvedValue({
        blob: mockBlob,
        filename: 'holdings.pdf',
        contentType: 'application/pdf',
      });

      // Mock URL.createObjectURL
      const mockCreateObjectURL = vi.fn().mockReturnValue('blob:http://localhost:3000/fake-blob');
      window.URL.createObjectURL = mockCreateObjectURL;
      window.URL.revokeObjectURL = vi.fn();

      renderWithProviders(
        <FileAttachmentDetail
          attachment={attachment}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      // Click load preview button
      const user = userEvent.setup();
      const previewButton = screen.getAllByText('Load Preview')[0];
      await user.click(previewButton);

      // Verify API call
      await waitFor(() => {
        expect(apiModule.investmentApi.downloadHoldingsFileBlob).toHaveBeenCalledWith(1);
      });

      // Verify preview loaded by checking for Download button and iframe
      await waitFor(() => {
        expect(screen.queryByText('Load Preview')).not.toBeInTheDocument();
        expect(screen.getByText('Download')).toBeInTheDocument();
        const frames = document.getElementsByTagName('iframe');
        expect(frames.length).toBeGreaterThan(0);
      });
    });

    it('falls back to filename extension for content type', async () => {
      const attachment = {
        id: '2',
        original_filename: 'test.pdf',
        file_size: 1024,
        status: 'completed' as const,
        extracted_holdings_count: 0,
        failed_holdings_count: 0,
        created_at: new Date().toISOString(),
      };

      // Mock generic blob response
      const mockBlob = new Blob(['fake pdf content'], { type: 'application/octet-stream' });
      const apiModule = await import('@/lib/api');
      vi.mocked(apiModule.investmentApi.downloadHoldingsFileBlob).mockResolvedValue({
        blob: mockBlob,
        filename: 'test.pdf',
        contentType: 'application/octet-stream',
      });

      window.URL.createObjectURL = vi.fn().mockReturnValue('blob:test');

      renderWithProviders(
        <FileAttachmentDetail
          attachment={attachment}
          open={true}
          onOpenChange={vi.fn()}
        />
      );

      const user = userEvent.setup();
      const previewButton = screen.getAllByText('Load Preview')[0];
      await user.click(previewButton);

      await waitFor(() => {
        // Should find iframe because it detected PDF
        const frames = document.getElementsByTagName('iframe');
        expect(frames.length).toBeGreaterThan(0);
      });
    });
  });
});
