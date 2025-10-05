import { render, screen, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { ApprovalDashboard } from '../approvals/ApprovalDashboard';
import { approvalApi } from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  approvalApi: {
    getDashboardStats: vi.fn(),
  },
}));

// Mock the child components
vi.mock('../approvals/PendingApprovalsList', () => ({
  PendingApprovalsList: ({ onApprovalAction }: { onApprovalAction: () => void }) => (
    <div data-testid="pending-approvals-list">
      <button onClick={onApprovalAction}>Mock Action</button>
    </div>
  ),
}));

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

describe('ApprovalDashboard', () => {
  const mockStats = {
    pending_count: 5,
    approved_today: 3,
    rejected_today: 1,
    overdue_count: 2,
    average_approval_time_hours: 24,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(approvalApi.getDashboardStats).mockImplementation(() => new Promise(() => {}));
    
    render(<ApprovalDashboard />);
    
    expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
    expect(screen.getByText('Approved Today')).toBeInTheDocument();
    expect(screen.getByText('Rejected Today')).toBeInTheDocument();
    expect(screen.getByText('Overdue')).toBeInTheDocument();
    expect(screen.getByText('Avg. Approval Time')).toBeInTheDocument();
  });

  it('displays stats when loaded successfully', async () => {
    vi.mocked(approvalApi.getDashboardStats).mockResolvedValue(mockStats);
    
    render(<ApprovalDashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument(); // pending_count
      expect(screen.getByText('3')).toBeInTheDocument(); // approved_today
      expect(screen.getByText('1')).toBeInTheDocument(); // rejected_today
      expect(screen.getByText('2')).toBeInTheDocument(); // overdue_count
      expect(screen.getByText('24h')).toBeInTheDocument(); // average_approval_time_hours
    });
  });

  it('handles API error gracefully', async () => {
    vi.mocked(approvalApi.getDashboardStats).mockRejectedValue(new Error('API Error'));
    
    render(<ApprovalDashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('0')).toBeInTheDocument(); // Should show 0 for all stats
    });
  });

  it('renders pending approvals list', () => {
    vi.mocked(approvalApi.getDashboardStats).mockResolvedValue(mockStats);
    
    render(<ApprovalDashboard />);
    
    expect(screen.getByTestId('pending-approvals-list')).toBeInTheDocument();
    expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
  });

  it('refreshes stats when approval action is triggered', async () => {
    vi.mocked(approvalApi.getDashboardStats).mockResolvedValue(mockStats);
    
    render(<ApprovalDashboard />);
    
    await waitFor(() => {
      expect(vi.mocked(approvalApi.getDashboardStats)).toHaveBeenCalledTimes(1);
    });

    // Trigger approval action
    const actionButton = screen.getByText('Mock Action');
    actionButton.click();

    await waitFor(() => {
      expect(vi.mocked(approvalApi.getDashboardStats)).toHaveBeenCalledTimes(2);
    });
  });

  it('applies correct variant styles based on stats', async () => {
    const statsWithWarnings = {
      ...mockStats,
      pending_count: 10,
      overdue_count: 5,
    };
    
    vi.mocked(approvalApi.getDashboardStats).mockResolvedValue(statsWithWarnings);
    
    render(<ApprovalDashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });
});