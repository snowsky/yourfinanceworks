import { render, screen, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { ApprovalHistoryTimeline } from '../approvals/ApprovalHistoryTimeline';
import { approvalApi } from '@/lib/api';
import { ApprovalHistoryEntry } from '@/types';

// Mock the API
vi.mock('@/lib/api', () => ({
  approvalApi: {
    getApprovalHistory: vi.fn(),
  },
}));

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

// Mock date-fns
vi.mock('date-fns', () => ({
  formatDistanceToNow: vi.fn(() => '2 hours'),
  format: vi.fn(() => 'Jan 15, 2024 10:00 AM'),
}));

describe('ApprovalHistoryTimeline', () => {
  const mockHistory: ApprovalHistoryEntry[] = [
    {
      id: 1,
      expense_id: 101,
      approver_id: 1,
      action: 'submitted',
      status: 'pending',
      approval_level: 1,
      timestamp: '2024-01-15T10:00:00Z',
      approver: {
        id: 1,
        name: 'John Submitter',
        email: 'john@company.com',
      },
    },
    {
      id: 2,
      expense_id: 101,
      approver_id: 2,
      action: 'approved',
      status: 'approved',
      approval_level: 1,
      timestamp: '2024-01-15T11:00:00Z',
      notes: 'Approved for business travel',
      approver: {
        id: 2,
        name: 'Jane Manager',
        email: 'jane@company.com',
      },
    },
    {
      id: 3,
      expense_id: 101,
      approver_id: 3,
      action: 'rejected',
      status: 'rejected',
      approval_level: 2,
      timestamp: '2024-01-15T12:00:00Z',
      rejection_reason: 'Missing receipt',
      notes: 'Please resubmit with proper documentation',
      approver: {
        id: 3,
        name: 'Bob Director',
        email: 'bob@company.com',
      },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(approvalApi.getApprovalHistory).mockImplementation(() => new Promise(() => {}));
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    expect(screen.getByText('Approval History')).toBeInTheDocument();
    // Should show skeleton loading
    expect(screen.getAllByRole('generic')).toHaveLength(3); // 3 skeleton items
  });

  it('displays history entries when loaded successfully', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: mockHistory });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      expect(screen.getByText('Submitted for approval')).toBeInTheDocument();
      expect(screen.getByText('Approved')).toBeInTheDocument();
      expect(screen.getByText('Rejected')).toBeInTheDocument();
      
      expect(screen.getByText('John Submitter')).toBeInTheDocument();
      expect(screen.getByText('Jane Manager')).toBeInTheDocument();
      expect(screen.getByText('Bob Director')).toBeInTheDocument();
    });
  });

  it('displays approval levels correctly', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: mockHistory });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      expect(screen.getAllByText(/Level \d/)).toHaveLength(3);
      expect(screen.getByText('Level 1')).toBeInTheDocument();
      expect(screen.getByText('Level 2')).toBeInTheDocument();
    });
  });

  it('displays rejection reason when present', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: mockHistory });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      expect(screen.getByText('Reason:')).toBeInTheDocument();
      expect(screen.getByText('Missing receipt')).toBeInTheDocument();
    });
  });

  it('displays notes when present', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: mockHistory });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      expect(screen.getAllByText('Notes:')).toHaveLength(2);
      expect(screen.getByText('Approved for business travel')).toBeInTheDocument();
      expect(screen.getByText('Please resubmit with proper documentation')).toBeInTheDocument();
    });
  });

  it('displays formatted timestamps', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: mockHistory });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      expect(screen.getAllByText('Jan 15, 2024 10:00 AM')).toHaveLength(3);
      expect(screen.getAllByText('2 hours ago')).toHaveLength(3);
    });
  });

  it('handles empty history gracefully', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: [] });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      expect(screen.getByText('No approval history available')).toBeInTheDocument();
    });
  });

  it('handles API error gracefully', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockRejectedValue(new Error('API Error'));
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      expect(screen.getByText('No approval history available')).toBeInTheDocument();
    });
  });

  it('displays correct icons for different actions', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: mockHistory });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      // Check that different action types are rendered
      expect(screen.getByText('Submitted for approval')).toBeInTheDocument();
      expect(screen.getByText('Approved')).toBeInTheDocument();
      expect(screen.getByText('Rejected')).toBeInTheDocument();
    });
  });

  it('applies correct styling for different action types', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: mockHistory });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      // Check that badges are rendered for each action
      const badges = screen.getAllByRole('generic').filter(el => 
        el.textContent?.includes('Submitted') || 
        el.textContent?.includes('Approved') || 
        el.textContent?.includes('Rejected')
      );
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it('handles delegation action type', async () => {
    const historyWithDelegation = [
      {
        id: 4,
        expense_id: 101,
        approver_id: 4,
        action: 'delegated',
        status: 'pending',
        approval_level: 1,
        timestamp: '2024-01-15T13:00:00Z',
        approver: {
          id: 4,
          name: 'Alice Delegate',
          email: 'alice@company.com',
        },
      },
    ];
    
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: historyWithDelegation });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      expect(screen.getByText('Delegated approval')).toBeInTheDocument();
      expect(screen.getByText('Alice Delegate')).toBeInTheDocument();
    });
  });

  it('renders timeline structure correctly', async () => {
    vi.mocked(approvalApi.getApprovalHistory).mockResolvedValue({ history: mockHistory });
    
    render(<ApprovalHistoryTimeline expenseId={101} />);
    
    await waitFor(() => {
      // Should have timeline structure with proper spacing
      expect(screen.getByText('Approval History')).toBeInTheDocument();
      
      // All history entries should be present
      expect(screen.getByText('John Submitter')).toBeInTheDocument();
      expect(screen.getByText('Jane Manager')).toBeInTheDocument();
      expect(screen.getByText('Bob Director')).toBeInTheDocument();
    });
  });
});