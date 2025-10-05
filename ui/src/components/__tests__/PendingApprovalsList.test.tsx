import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { PendingApprovalsList } from '../approvals/PendingApprovalsList';
import { approvalApi } from '@/lib/api';
import { ExpenseApproval } from '@/types';

// Mock the API
vi.mock('@/lib/api', () => ({
  approvalApi: {
    getPendingApprovals: vi.fn(),
    approveExpense: vi.fn(),
    rejectExpense: vi.fn(),
  },
}));

// Mock child components
vi.mock('../approvals/ApprovalActionButtons', () => ({
  ApprovalActionButtons: ({ approval, onAction }: { approval: ExpenseApproval; onAction: Function }) => (
    <div data-testid={`action-buttons-${approval.id}`}>
      <button onClick={() => onAction(approval.id, 'approve', { notes: 'test' })}>
        Approve
      </button>
      <button onClick={() => onAction(approval.id, 'reject', { reason: 'test reason' })}>
        Reject
      </button>
    </div>
  ),
}));

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

// Mock date-fns
vi.mock('date-fns', () => ({
  formatDistanceToNow: vi.fn(() => '2 hours'),
}));

describe('PendingApprovalsList', () => {
  const mockApprovals: ExpenseApproval[] = [
    {
      id: 1,
      expense_id: 101,
      approver_id: 1,
      status: 'pending',
      submitted_at: '2024-01-15T10:00:00Z',
      approval_level: 1,
      is_current_level: true,
      expense: {
        id: 101,
        amount: 150.00,
        currency: 'USD',
        expense_date: '2024-01-14',
        category: 'Travel',
        vendor: 'Uber',
        status: 'pending_approval',
        notes: 'Business trip to client meeting',
      },
      approver: {
        id: 1,
        name: 'John Manager',
        email: 'john@company.com',
      },
    },
    {
      id: 2,
      expense_id: 102,
      approver_id: 1,
      status: 'pending',
      submitted_at: '2024-01-15T09:00:00Z',
      approval_level: 1,
      is_current_level: true,
      expense: {
        id: 102,
        amount: 75.50,
        currency: 'USD',
        expense_date: '2024-01-13',
        category: 'Meals',
        vendor: 'Restaurant ABC',
        status: 'pending_approval',
      },
    },
  ];

  const mockApiResponse = {
    approvals: mockApprovals,
    total: 2,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(approvalApi.getPendingApprovals).mockImplementation(() => new Promise(() => {}));
    
    render(<PendingApprovalsList />);
    
    // Should show skeleton loading
    expect(screen.getAllByRole('generic')).toHaveLength(3); // 3 skeleton cards
  });

  it('displays approvals when loaded successfully', async () => {
    vi.mocked(approvalApi.getPendingApprovals).mockResolvedValue(mockApiResponse);
    
    render(<PendingApprovalsList />);
    
    await waitFor(() => {
      expect(screen.getByText('USD 150.00')).toBeInTheDocument();
      expect(screen.getByText('Travel')).toBeInTheDocument();
      expect(screen.getByText('Uber')).toBeInTheDocument();
      expect(screen.getByText('Business trip to client meeting')).toBeInTheDocument();
      
      expect(screen.getByText('USD 75.50')).toBeInTheDocument();
      expect(screen.getByText('Meals')).toBeInTheDocument();
      expect(screen.getByText('Restaurant ABC')).toBeInTheDocument();
    });
  });

  it('handles search functionality', async () => {
    vi.mocked(approvalApi.getPendingApprovals).mockResolvedValue(mockApiResponse);
    
    render(<PendingApprovalsList />);
    
    await waitFor(() => {
      expect(screen.getByText('Uber')).toBeInTheDocument();
      expect(screen.getByText('Restaurant ABC')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search by vendor, category, or notes...');
    await userEvent.type(searchInput, 'Uber');

    // Should filter to show only Uber expense
    expect(screen.getByText('Uber')).toBeInTheDocument();
    expect(screen.queryByText('Restaurant ABC')).not.toBeInTheDocument();
  });

  it('handles sorting functionality', async () => {
    vi.mocked(approvalApi.getPendingApprovals).mockResolvedValue(mockApiResponse);
    
    render(<PendingApprovalsList />);
    
    await waitFor(() => {
      expect(screen.getByDisplayValue('Date Submitted')).toBeInTheDocument();
    });

    // Change sort to amount
    const sortSelect = screen.getByDisplayValue('Date Submitted');
    await userEvent.click(sortSelect);
    await userEvent.click(screen.getByText('Amount'));

    await waitFor(() => {
      expect(vi.mocked(approvalApi.getPendingApprovals)).toHaveBeenCalledWith(
        expect.objectContaining({
          sort_by: 'amount',
          sort_order: 'asc',
        })
      );
    });
  });

  it('handles filter functionality', async () => {
    vi.mocked(approvalApi.getPendingApprovals).mockResolvedValue(mockApiResponse);
    
    render(<PendingApprovalsList />);
    
    await waitFor(() => {
      expect(screen.getByText('Filters')).toBeInTheDocument();
    });

    // Open filters
    const filtersButton = screen.getByText('Filters');
    await userEvent.click(filtersButton);

    // Set category filter
    const categoryInput = screen.getByPlaceholderText('Filter by category');
    await userEvent.type(categoryInput, 'Travel');

    await waitFor(() => {
      expect(vi.mocked(approvalApi.getPendingApprovals)).toHaveBeenCalledWith(
        expect.objectContaining({
          category: 'Travel',
        })
      );
    });
  });

  it('handles approval action successfully', async () => {
    vi.mocked(approvalApi.getPendingApprovals).mockResolvedValue(mockApiResponse);
    vi.mocked(approvalApi.approveExpense).mockResolvedValue({ success: true, message: 'Approved' });
    
    const onApprovalAction = vi.fn();
    render(<PendingApprovalsList onApprovalAction={onApprovalAction} />);
    
    await waitFor(() => {
      expect(screen.getByTestId('action-buttons-1')).toBeInTheDocument();
    });

    const approveButton = screen.getByText('Approve');
    await userEvent.click(approveButton);

    await waitFor(() => {
      expect(vi.mocked(approvalApi.approveExpense)).toHaveBeenCalledWith(1, 'test');
      expect(onApprovalAction).toHaveBeenCalled();
    });
  });

  it('handles rejection action successfully', async () => {
    vi.mocked(approvalApi.getPendingApprovals).mockResolvedValue(mockApiResponse);
    vi.mocked(approvalApi.rejectExpense).mockResolvedValue({ success: true, message: 'Rejected' });
    
    const onApprovalAction = vi.fn();
    render(<PendingApprovalsList onApprovalAction={onApprovalAction} />);
    
    await waitFor(() => {
      expect(screen.getByTestId('action-buttons-1')).toBeInTheDocument();
    });

    const rejectButton = screen.getByText('Reject');
    await userEvent.click(rejectButton);

    await waitFor(() => {
      expect(vi.mocked(approvalApi.rejectExpense)).toHaveBeenCalledWith(1, 'test reason', undefined);
      expect(onApprovalAction).toHaveBeenCalled();
    });
  });

  it('displays empty state when no approvals', async () => {
    vi.mocked(approvalApi.getPendingApprovals).mockResolvedValue({ approvals: [], total: 0 });
    
    render(<PendingApprovalsList />);
    
    await waitFor(() => {
      expect(screen.getByText('No pending approvals')).toBeInTheDocument();
    });
  });

  it('handles pagination correctly', async () => {
    const largeResponse = {
      approvals: mockApprovals,
      total: 25, // More than page size
    };
    vi.mocked(approvalApi.getPendingApprovals).mockResolvedValue(largeResponse);
    
    render(<PendingApprovalsList />);
    
    await waitFor(() => {
      expect(screen.getByText('Showing 1 to 10 of 25 approvals')).toBeInTheDocument();
      expect(screen.getByText('Next')).toBeInTheDocument();
    });

    const nextButton = screen.getByText('Next');
    await userEvent.click(nextButton);

    await waitFor(() => {
      expect(vi.mocked(approvalApi.getPendingApprovals)).toHaveBeenCalledWith(
        expect.objectContaining({
          offset: 10,
        })
      );
    });
  });

  it('handles API error gracefully', async () => {
    vi.mocked(approvalApi.getPendingApprovals).mockRejectedValue(new Error('API Error'));
    
    render(<PendingApprovalsList />);
    
    await waitFor(() => {
      expect(screen.getByText('No pending approvals')).toBeInTheDocument();
    });
  });
});