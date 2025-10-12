import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { ApprovalActionButtons } from '../approvals/ApprovalActionButtons';
import { ExpenseApproval } from '@/types';

describe('ApprovalActionButtons', () => {
  const mockApproval: ExpenseApproval = {
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
  };

  const mockOnAction = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders approve and reject buttons', () => {
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    expect(screen.getByText('Approve')).toBeInTheDocument();
    expect(screen.getByText('Reject')).toBeInTheDocument();
  });

  it('opens approve dialog when approve button is clicked', async () => {
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    const approveButton = screen.getByText('Approve');
    await userEvent.click(approveButton);
    
    expect(screen.getByText('Approve Expense')).toBeInTheDocument();
    expect(screen.getByText('USD 150.00')).toBeInTheDocument();
    expect(screen.getByText('Travel')).toBeInTheDocument();
    expect(screen.getByText('Uber')).toBeInTheDocument();
  });

  it('opens reject dialog when reject button is clicked', async () => {
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    const rejectButton = screen.getByText('Reject');
    await userEvent.click(rejectButton);
    
    expect(screen.getByText('Reject Expense')).toBeInTheDocument();
    expect(screen.getByText('USD 150.00')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Please provide a reason for rejecting this expense...')).toBeInTheDocument();
  });

  it('handles approve action with notes', async () => {
    mockOnAction.mockResolvedValue(undefined);
    
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    // Open approve dialog
    const approveButton = screen.getByText('Approve');
    await userEvent.click(approveButton);
    
    // Add notes
    const notesTextarea = screen.getByPlaceholderText('Add any notes about this approval...');
    await userEvent.type(notesTextarea, 'Looks good to me');
    
    // Submit approval
    const submitButton = screen.getByText('Approve Expense');
    await userEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockOnAction).toHaveBeenCalledWith(1, 'approve', { notes: 'Looks good to me' });
    });
  });

  it('handles reject action with reason and notes', async () => {
    mockOnAction.mockResolvedValue(undefined);
    
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    // Open reject dialog
    const rejectButton = screen.getByText('Reject');
    await userEvent.click(rejectButton);
    
    // Add rejection reason
    const reasonTextarea = screen.getByPlaceholderText('Please provide a reason for rejecting this expense...');
    await userEvent.type(reasonTextarea, 'Missing receipt');
    
    // Add additional notes
    const notesTextarea = screen.getByPlaceholderText('Add any additional notes...');
    await userEvent.type(notesTextarea, 'Please resubmit with receipt');
    
    // Submit rejection
    const submitButton = screen.getByText('Reject Expense');
    await userEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockOnAction).toHaveBeenCalledWith(1, 'reject', { 
        reason: 'Missing receipt', 
        notes: 'Please resubmit with receipt' 
      });
    });
  });

  it('disables reject button when no reason is provided', async () => {
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    // Open reject dialog
    const rejectButton = screen.getByText('Reject');
    await userEvent.click(rejectButton);
    
    // Submit button should be disabled initially
    const submitButton = screen.getByText('Reject Expense');
    expect(submitButton).toBeDisabled();
    
    // Add reason
    const reasonTextarea = screen.getByPlaceholderText('Please provide a reason for rejecting this expense...');
    await userEvent.type(reasonTextarea, 'Missing receipt');
    
    // Submit button should now be enabled
    expect(submitButton).not.toBeDisabled();
  });

  it('shows loading state during approval', async () => {
    // Mock a delayed response
    mockOnAction.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));
    
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    // Open approve dialog
    const approveButton = screen.getByText('Approve');
    await userEvent.click(approveButton);
    
    // Submit approval
    const submitButton = screen.getByText('Approve Expense');
    await userEvent.click(submitButton);
    
    // Should show loading state
    expect(screen.getByText('Approving...')).toBeInTheDocument();
    
    // Wait for completion
    await waitFor(() => {
      expect(screen.queryByText('Approving...')).not.toBeInTheDocument();
    });
  });

  it('shows loading state during rejection', async () => {
    // Mock a delayed response
    mockOnAction.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));
    
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    // Open reject dialog
    const rejectButton = screen.getByText('Reject');
    await userEvent.click(rejectButton);
    
    // Add reason
    const reasonTextarea = screen.getByPlaceholderText('Please provide a reason for rejecting this expense...');
    await userEvent.type(reasonTextarea, 'Missing receipt');
    
    // Submit rejection
    const submitButton = screen.getByText('Reject Expense');
    await userEvent.click(submitButton);
    
    // Should show loading state
    expect(screen.getByText('Rejecting...')).toBeInTheDocument();
    
    // Wait for completion
    await waitFor(() => {
      expect(screen.queryByText('Rejecting...')).not.toBeInTheDocument();
    });
  });

  it('closes dialog after successful approval', async () => {
    mockOnAction.mockResolvedValue(undefined);
    
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    // Open approve dialog
    const approveButton = screen.getByText('Approve');
    await userEvent.click(approveButton);
    
    expect(screen.getByText('Approve Expense')).toBeInTheDocument();
    
    // Submit approval
    const submitButton = screen.getByText('Approve Expense');
    await userEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.queryByText('Approve Expense')).not.toBeInTheDocument();
    });
  });

  it('closes dialog after successful rejection', async () => {
    mockOnAction.mockResolvedValue(undefined);
    
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    // Open reject dialog
    const rejectButton = screen.getByText('Reject');
    await userEvent.click(rejectButton);
    
    expect(screen.getByText('Reject Expense')).toBeInTheDocument();
    
    // Add reason and submit
    const reasonTextarea = screen.getByPlaceholderText('Please provide a reason for rejecting this expense...');
    await userEvent.type(reasonTextarea, 'Missing receipt');
    
    const submitButton = screen.getByText('Reject Expense');
    await userEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.queryByText('Reject Expense')).not.toBeInTheDocument();
    });
  });

  it('handles action errors gracefully', async () => {
    mockOnAction.mockRejectedValue(new Error('API Error'));
    
    render(<ApprovalActionButtons approval={mockApproval} onAction={mockOnAction} />);
    
    // Open approve dialog
    const approveButton = screen.getByText('Approve');
    await userEvent.click(approveButton);
    
    // Submit approval
    const submitButton = screen.getByText('Approve Expense');
    await userEvent.click(submitButton);
    
    // Should handle error and reset loading state
    await waitFor(() => {
      expect(screen.queryByText('Approving...')).not.toBeInTheDocument();
      expect(screen.getByText('Approve Expense')).toBeInTheDocument(); // Dialog should remain open
    });
  });
});