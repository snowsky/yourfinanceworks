import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ExpenseApprovalStatus } from '../approvals/ExpenseApprovalStatus';
import type { ExpenseApproval } from '@/types';

// Mock the date-fns format function
vi.mock('date-fns', () => ({
  format: vi.fn((date, formatStr) => {
    if (formatStr === 'MMM d, yyyy HH:mm') {
      return 'Jan 15, 2024 10:30';
    }
    if (formatStr === 'MMM d') {
      return 'Jan 15';
    }
    return 'Jan 15, 2024';
  }),
}));

describe('ExpenseApprovalStatus', () => {
  const mockExpense = {
    id: 1,
    amount: 100,
    currency: 'USD',
    status: 'pending_approval',
  };

  const mockApprovals: ExpenseApproval[] = [
    {
      id: 1,
      expense_id: 1,
      approver_id: 1,
      status: 'pending',
      submitted_at: '2024-01-15T10:30:00Z',
      approval_level: 1,
      is_current_level: true,
      approver: {
        id: 1,
        name: 'John Manager',
        email: 'john@example.com',
      },
    },
  ];

  it('renders nothing for non-approval expenses', () => {
    const { container } = render(
      <ExpenseApprovalStatus 
        expense={{ ...mockExpense, status: 'recorded' }} 
        approvals={[]} 
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders pending approval badge', () => {
    render(
      <ExpenseApprovalStatus 
        expense={mockExpense} 
        approvals={mockApprovals} 
      />
    );
    
    expect(screen.getByText('Pending Approval')).toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveAttribute('data-state', 'closed');
  });

  it('renders approved badge', () => {
    render(
      <ExpenseApprovalStatus 
        expense={{ ...mockExpense, status: 'approved' }} 
        approvals={[]} 
      />
    );
    
    expect(screen.getByText('Approved')).toBeInTheDocument();
  });

  it('renders rejected badge', () => {
    render(
      <ExpenseApprovalStatus 
        expense={{ ...mockExpense, status: 'rejected' }} 
        approvals={[]} 
      />
    );
    
    expect(screen.getByText('Rejected')).toBeInTheDocument();
  });

  it('renders resubmitted badge', () => {
    render(
      <ExpenseApprovalStatus 
        expense={{ ...mockExpense, status: 'resubmitted' }} 
        approvals={[]} 
      />
    );
    
    expect(screen.getByText('Resubmitted')).toBeInTheDocument();
  });

  it('shows approval progress for multi-level approvals', () => {
    const multiLevelApprovals: ExpenseApproval[] = [
      {
        id: 1,
        expense_id: 1,
        approver_id: 1,
        status: 'approved',
        submitted_at: '2024-01-15T10:30:00Z',
        decided_at: '2024-01-15T11:00:00Z',
        approval_level: 1,
        is_current_level: false,
        approver: { id: 1, name: 'John Manager', email: 'john@example.com' },
      },
      {
        id: 2,
        expense_id: 1,
        approver_id: 2,
        status: 'pending',
        submitted_at: '2024-01-15T11:00:00Z',
        approval_level: 2,
        is_current_level: true,
        approver: { id: 2, name: 'Jane Director', email: 'jane@example.com' },
      },
    ];

    render(
      <ExpenseApprovalStatus 
        expense={mockExpense} 
        approvals={multiLevelApprovals} 
      />
    );
    
    expect(screen.getByText('1/2')).toBeInTheDocument();
  });

  it('shows tooltip with current approver information on hover', async () => {
    render(
      <ExpenseApprovalStatus 
        expense={mockExpense} 
        approvals={mockApprovals} 
      />
    );
    
    const trigger = screen.getByRole('button');
    fireEvent.mouseEnter(trigger);
    
    await waitFor(() => {
      expect(screen.getByText('Current approver: John Manager')).toBeInTheDocument();
      expect(screen.getByText('Submitted: Jan 15, 2024 10:30')).toBeInTheDocument();
    });
  });

  it('shows rejection reason in tooltip for rejected expenses', async () => {
    const rejectedApprovals: ExpenseApproval[] = [
      {
        id: 1,
        expense_id: 1,
        approver_id: 1,
        status: 'rejected',
        rejection_reason: 'Missing receipt',
        submitted_at: '2024-01-15T10:30:00Z',
        decided_at: '2024-01-15T11:00:00Z',
        approval_level: 1,
        is_current_level: false,
        approver: { id: 1, name: 'John Manager', email: 'john@example.com' },
      },
    ];

    render(
      <ExpenseApprovalStatus 
        expense={{ ...mockExpense, status: 'rejected' }} 
        approvals={rejectedApprovals} 
      />
    );
    
    const trigger = screen.getByRole('button');
    fireEvent.mouseEnter(trigger);
    
    await waitFor(() => {
      expect(screen.getByText('Rejection reason:')).toBeInTheDocument();
      expect(screen.getByText('Missing receipt')).toBeInTheDocument();
    });
  });

  it('shows approval history for multi-level approvals in tooltip', async () => {
    const multiLevelApprovals: ExpenseApproval[] = [
      {
        id: 1,
        expense_id: 1,
        approver_id: 1,
        status: 'approved',
        submitted_at: '2024-01-15T10:30:00Z',
        decided_at: '2024-01-15T11:00:00Z',
        approval_level: 1,
        is_current_level: false,
        approver: { id: 1, name: 'John Manager', email: 'john@example.com' },
      },
      {
        id: 2,
        expense_id: 1,
        approver_id: 2,
        status: 'pending',
        submitted_at: '2024-01-15T11:00:00Z',
        approval_level: 2,
        is_current_level: true,
        approver: { id: 2, name: 'Jane Director', email: 'jane@example.com' },
      },
    ];

    render(
      <ExpenseApprovalStatus 
        expense={mockExpense} 
        approvals={multiLevelApprovals} 
      />
    );
    
    const trigger = screen.getByRole('button');
    fireEvent.mouseEnter(trigger);
    
    await waitFor(() => {
      expect(screen.getByText('Approval History:')).toBeInTheDocument();
      expect(screen.getByText(/Level 1: approved by John Manager/)).toBeInTheDocument();
      expect(screen.getByText(/Level 2: pending by Jane Director/)).toBeInTheDocument();
    });
  });

  it('applies custom className', () => {
    const { container } = render(
      <ExpenseApprovalStatus 
        expense={mockExpense} 
        approvals={mockApprovals} 
        className="custom-class" 
      />
    );
    
    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('handles empty approvals array gracefully', () => {
    render(
      <ExpenseApprovalStatus 
        expense={mockExpense} 
        approvals={[]} 
      />
    );
    
    expect(screen.getByText('Pending Approval')).toBeInTheDocument();
  });
});