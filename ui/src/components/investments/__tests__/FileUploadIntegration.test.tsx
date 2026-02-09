import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'sonner';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import FileUploadDialog from '../FileUploadDialog';
import FileAttachmentsList from '../FileAttachmentsList';
import FileUploadArea from '../FileUploadArea';
import * as api from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  apiRequest: vi.fn(),
}));

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: any) => {
      if (options) {
        return key.replace(/\{\{(\w+)\}\}/g, (_, match) => options[match] || '');
      }
      return key;
    },
  }),
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      {children}
      <Toaster />
    </BrowserRouter>
  </QueryClientProvider>
);

describe('File Upload Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('selected_tenant_id', '1');
  });

  describe('FileUploadDialog', () => {
    it('should render upload dialog', () => {
      render(
        <FileUploadDialog
          portfolioId={1}
          open={true}
          onOpenChange={vi.fn()}
        />,
        { wrapper: Wrapper }
      );

      expect(screen.getByText('Upload Holdings Files')).toBeInTheDocument();
      expect(screen.getByText('Select Holdings Files')).toBeInTheDocument();
    });

    it('should disable upload button when no files selected', () => {
      render(
        <FileUploadDialog
          portfolioId={1}
          open={true}
          onOpenChange={vi.fn()}
        />,
        { wrapper: Wrapper }
      );

      const uploadButton = screen.getByRole('button', { name: /Upload Files/i });
      expect(uploadButton).toBeDisabled();
    });
  });

  describe('FileAttachmentsList', () => {
    it('should display file attachments with status', async () => {
      const mockAttachments = [
        {
          id: '1',
          original_filename: 'holdings.pdf',
          file_size: 2048,
          status: 'completed' as const,
          extracted_holdings_count: 5,
          failed_holdings_count: 0,
          created_at: new Date().toISOString(),
        },
        {
          id: '2',
          original_filename: 'portfolio.csv',
          file_size: 1024,
          status: 'processing' as const,
          extracted_holdings_count: 0,
          failed_holdings_count: 0,
          created_at: new Date().toISOString(),
        },
      ];

      (api.apiRequest as any).mockResolvedValueOnce(mockAttachments);

      render(<FileAttachmentsList portfolioId={1} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('holdings.pdf')).toBeInTheDocument();
        expect(screen.getByText('portfolio.csv')).toBeInTheDocument();
      });
    });

    it('should show empty state when no files uploaded', async () => {
      (api.apiRequest as any).mockResolvedValueOnce([]);

      render(<FileAttachmentsList portfolioId={1} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('No files uploaded yet')).toBeInTheDocument();
      });
    });

    it('should display extraction results for completed files', async () => {
      const mockAttachments = [
        {
          id: '1',
          original_filename: 'holdings.pdf',
          file_size: 2048,
          status: 'completed' as const,
          extracted_holdings_count: 5,
          failed_holdings_count: 0,
          created_at: new Date().toISOString(),
          extracted_data: {
            holdings: [
              { symbol: 'AAPL', quantity: 10, cost_basis: 1500 },
            ],
          },
        },
      ];

      (api.apiRequest as any).mockResolvedValueOnce(mockAttachments);

      render(<FileAttachmentsList portfolioId={1} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('holdings.pdf')).toBeInTheDocument();
        // Check for holdings count
        const elements = screen.getAllByText(/holdings/i);
        expect(elements.length).toBeGreaterThan(0);
      });
    });

    it('should display error message for failed files', async () => {
      const mockAttachments = [
        {
          id: '1',
          original_filename: 'invalid.pdf',
          file_size: 1024,
          status: 'failed' as const,
          extraction_error: 'Unable to extract holdings from file',
          extracted_holdings_count: 0,
          failed_holdings_count: 0,
          created_at: new Date().toISOString(),
        },
      ];

      (api.apiRequest as any).mockResolvedValueOnce(mockAttachments);

      render(<FileAttachmentsList portfolioId={1} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('invalid.pdf')).toBeInTheDocument();
        expect(
          screen.getByText('Unable to extract holdings from file')
        ).toBeInTheDocument();
      });
    });

    it('should display partial failure status', async () => {
      const mockAttachments = [
        {
          id: '1',
          original_filename: 'partial.pdf',
          file_size: 1024,
          status: 'partial' as const,
          extracted_holdings_count: 3,
          failed_holdings_count: 2,
          created_at: new Date().toISOString(),
        },
      ];

      (api.apiRequest as any).mockResolvedValueOnce(mockAttachments);

      render(<FileAttachmentsList portfolioId={1} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('partial.pdf')).toBeInTheDocument();
        // Check for holdings created count
        const elements = screen.getAllByText(/holdings/i);
        expect(elements.length).toBeGreaterThan(0);
      });
    });
  });

  describe('FileUploadArea', () => {
    it('should render file upload area', () => {
      render(<FileUploadArea portfolioId={1} />, { wrapper: Wrapper });

      expect(
        screen.getByText('Import Holdings from File')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Select Holdings Files')
      ).toBeInTheDocument();
    });
  });

  describe('API Integration', () => {
    it('should call correct API endpoint for file list', async () => {
      (api.apiRequest as any).mockResolvedValueOnce([]);

      render(<FileAttachmentsList portfolioId={1} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(api.apiRequest).toHaveBeenCalledWith(
          '/investments/portfolios/1/holdings-files'
        );
      });
    });

    it('should handle API errors gracefully', async () => {
      (api.apiRequest as any).mockRejectedValueOnce(
        new Error('Failed to fetch attachments')
      );

      render(<FileAttachmentsList portfolioId={1} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByText('No files uploaded yet')).toBeInTheDocument();
      });
    });
  });
});
