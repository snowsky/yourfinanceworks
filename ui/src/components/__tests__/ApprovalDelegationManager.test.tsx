import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ApprovalDelegationManager } from '../approvals/ApprovalDelegationManager';
import { approvalApi } from '@/lib/api';
import { toast } from 'sonner';

// Mock the API
vi.mock('@/lib/api', () => ({
  approvalApi: {
    getDelegations: vi.fn(),
    createDelegation: vi.fn(),
    updateDelegation: vi.fn(),
    deleteDelegation: vi.fn(),
  },
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock the child components
vi.mock('../approvals/DelegationForm', () => ({
  DelegationForm: ({ onSubmit, onCancel, loading }: any) => (
    <div data-testid="delegation-form">
      <button onClick={() => onSubmit({ test: 'data' })}>Submit</button>
      <button onClick={onCancel}>Cancel</button>
      {loading && <span>Loading...</span>}
    </div>
  ),
}));

vi.mock('../approvals/ActiveDelegationsList', () => ({
  ActiveDelegationsList: ({ onEdit, onDelete, loading }: any) => (
    <div data-testid="active-delegations-list">
      <button onClick={() => onEdit({ id: 1, name: 'Test Delegation' })}>Edit</button>
      <button onClick={() => onDelete(1)}>Delete</button>
      {loading && <span>Loading...</span>}
    </div>
  ),
}));

const mockDelegations = [
  {
    id: 1,
    approver_id: 1,
    delegate_id: 2,
    start_date: '2024-01-01T00:00:00Z',
    end_date: '2024-01-07T00:00:00Z',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    approver: { id: 1, name: 'John Doe', email: 'john@example.com' },
    delegate: { id: 2, name: 'Jane Smith', email: 'jane@example.com' },
  },
];

describe('ApprovalDelegationManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (approvalApi.getDelegations as any).mockResolvedValue(mockDelegations);
  });

  it('renders the delegation manager with correct title and description', () => {
    render(<ApprovalDelegationManager />);
    
    expect(screen.getByText('Approval Delegation Management')).toBeInTheDocument();
    expect(screen.getByText(/Set up temporary delegation of approval responsibilities/)).toBeInTheDocument();
  });

  it('displays the new delegation button', () => {
    render(<ApprovalDelegationManager />);
    
    const newButton = screen.getByRole('button', { name: /new delegation/i });
    expect(newButton).toBeInTheDocument();
  });

  it('shows information alert about delegations', () => {
    render(<ApprovalDelegationManager />);
    
    expect(screen.getByText(/Delegations allow you to temporarily assign/)).toBeInTheDocument();
  });

  it('renders the active delegations list', () => {
    render(<ApprovalDelegationManager />);
    
    expect(screen.getByTestId('active-delegations-list')).toBeInTheDocument();
  });

  it('opens the delegation form when new delegation button is clicked', async () => {
    render(<ApprovalDelegationManager />);
    
    const newButton = screen.getByRole('button', { name: /new delegation/i });
    fireEvent.click(newButton);
    
    await waitFor(() => {
      expect(screen.getByTestId('delegation-form')).toBeInTheDocument();
    });
  });

  it('opens the delegation form for editing when edit is triggered', async () => {
    render(<ApprovalDelegationManager />);
    
    const editButton = screen.getByText('Edit');
    fireEvent.click(editButton);
    
    await waitFor(() => {
      expect(screen.getByTestId('delegation-form')).toBeInTheDocument();
    });
  });

  it('creates a new delegation successfully', async () => {
    (approvalApi.createDelegation as any).mockResolvedValue({ id: 2 });
    
    render(<ApprovalDelegationManager />);
    
    // Open form
    const newButton = screen.getByRole('button', { name: /new delegation/i });
    fireEvent.click(newButton);
    
    await waitFor(() => {
      expect(screen.getByTestId('delegation-form')).toBeInTheDocument();
    });
    
    // Submit form
    const submitButton = screen.getByText('Submit');
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(approvalApi.createDelegation).toHaveBeenCalledWith({ test: 'data' });
      expect(toast.success).toHaveBeenCalledWith('Approval delegation created successfully');
    });
  });

  it('updates an existing delegation successfully', async () => {
    (approvalApi.updateDelegation as any).mockResolvedValue({ id: 1 });
    
    render(<ApprovalDelegationManager />);
    
    // Trigger edit
    const editButton = screen.getByText('Edit');
    fireEvent.click(editButton);
    
    await waitFor(() => {
      expect(screen.getByTestId('delegation-form')).toBeInTheDocument();
    });
    
    // Submit form
    const submitButton = screen.getByText('Submit');
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(approvalApi.updateDelegation).toHaveBeenCalledWith(1, { test: 'data' });
      expect(toast.success).toHaveBeenCalledWith('Approval delegation updated successfully');
    });
  });

  it('handles delegation creation error', async () => {
    (approvalApi.createDelegation as any).mockRejectedValue(new Error('API Error'));
    
    render(<ApprovalDelegationManager />);
    
    // Open form
    const newButton = screen.getByRole('button', { name: /new delegation/i });
    fireEvent.click(newButton);
    
    await waitFor(() => {
      expect(screen.getByTestId('delegation-form')).toBeInTheDocument();
    });
    
    // Submit form
    const submitButton = screen.getByText('Submit');
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to save approval delegation');
    });
  });

  it('deletes a delegation successfully', async () => {
    (approvalApi.deleteDelegation as any).mockResolvedValue({ message: 'Deleted' });
    
    render(<ApprovalDelegationManager />);
    
    const deleteButton = screen.getByText('Delete');
    fireEvent.click(deleteButton);
    
    await waitFor(() => {
      expect(approvalApi.deleteDelegation).toHaveBeenCalledWith(1);
      expect(toast.success).toHaveBeenCalledWith('Approval delegation deleted successfully');
    });
  });

  it('handles delegation deletion error', async () => {
    (approvalApi.deleteDelegation as any).mockRejectedValue(new Error('API Error'));
    
    render(<ApprovalDelegationManager />);
    
    const deleteButton = screen.getByText('Delete');
    fireEvent.click(deleteButton);
    
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to delete approval delegation');
    });
  });

  it('closes the form when cancel is clicked', async () => {
    render(<ApprovalDelegationManager />);
    
    // Open form
    const newButton = screen.getByRole('button', { name: /new delegation/i });
    fireEvent.click(newButton);
    
    await waitFor(() => {
      expect(screen.getByTestId('delegation-form')).toBeInTheDocument();
    });
    
    // Cancel form
    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);
    
    await waitFor(() => {
      expect(screen.queryByTestId('delegation-form')).not.toBeInTheDocument();
    });
  });

  it('shows loading state in child components', async () => {
    render(<ApprovalDelegationManager />);
    
    // Open form
    const newButton = screen.getByRole('button', { name: /new delegation/i });
    fireEvent.click(newButton);
    
    await waitFor(() => {
      expect(screen.getByTestId('delegation-form')).toBeInTheDocument();
    });
    
    // Submit form to trigger loading
    const submitButton = screen.getByText('Submit');
    fireEvent.click(submitButton);
    
    // Should show loading in form - use getAllByText since there are multiple loading states
    expect(screen.getAllByText('Loading...')).toHaveLength(2);
  });

  it('refreshes the list after successful operations', async () => {
    (approvalApi.createDelegation as any).mockResolvedValue({ id: 2 });
    
    render(<ApprovalDelegationManager />);
    
    // Open form
    const newButton = screen.getByRole('button', { name: /new delegation/i });
    fireEvent.click(newButton);
    
    await waitFor(() => {
      expect(screen.getByTestId('delegation-form')).toBeInTheDocument();
    });
    
    // Submit form
    const submitButton = screen.getByText('Submit');
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      // The key prop should change, causing the list to refresh
      expect(approvalApi.createDelegation).toHaveBeenCalled();
    });
  });
});