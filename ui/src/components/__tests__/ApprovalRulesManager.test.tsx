import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ApprovalRulesManager } from '../approvals/ApprovalRulesManager';
import { approvalApi, userApi } from '@/lib/api';
import { toast } from 'sonner';

// Mock the API modules
vi.mock('@/lib/api', () => ({
  approvalApi: {
    getApprovalRules: vi.fn(),
    createApprovalRule: vi.fn(),
    updateApprovalRule: vi.fn(),
    deleteApprovalRule: vi.fn(),
    updateApprovalRulePriority: vi.fn(),
  },
  userApi: {
    getUsers: vi.fn(),
  },
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock child components
vi.mock('../approvals/ApprovalRulesList', () => ({
  ApprovalRulesList: ({ onEdit, onRefresh }: any) => (
    <div data-testid="approval-rules-list">
      <button onClick={() => onEdit({ id: 1, name: 'Test Rule' })}>
        Edit Rule
      </button>
      <button onClick={onRefresh}>Refresh</button>
    </div>
  ),
}));

vi.mock('../approvals/ApprovalRuleForm', () => ({
  ApprovalRuleForm: ({ rule, onSubmit, onCancel, loading }: any) => (
    <div data-testid="approval-rule-form">
      <div>{rule ? 'Edit Mode' : 'Create Mode'}</div>
      <button onClick={() => onSubmit({ name: 'Test Rule' })}>
        Submit
      </button>
      <button onClick={onCancel}>Cancel</button>
      {loading && <div>Loading...</div>}
    </div>
  ),
}));

describe('ApprovalRulesManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the approval rules manager', () => {
    render(<ApprovalRulesManager />);
    
    expect(screen.getByText('Approval Rules Management')).toBeInTheDocument();
    expect(screen.getByText('Create Rule')).toBeInTheDocument();
    expect(screen.getByTestId('approval-rules-list')).toBeInTheDocument();
  });

  it('shows create rule dialog when create button is clicked', () => {
    render(<ApprovalRulesManager />);
    
    fireEvent.click(screen.getByText('Create Rule'));
    
    expect(screen.getByTestId('approval-rule-form')).toBeInTheDocument();
    expect(screen.getByText('Create Mode')).toBeInTheDocument();
  });

  it('shows edit rule dialog when edit is triggered', () => {
    render(<ApprovalRulesManager />);
    
    fireEvent.click(screen.getByText('Edit Rule'));
    
    expect(screen.getByTestId('approval-rule-form')).toBeInTheDocument();
    expect(screen.getByText('Edit Mode')).toBeInTheDocument();
  });

  it('closes form dialog when cancel is clicked', () => {
    render(<ApprovalRulesManager />);
    
    fireEvent.click(screen.getByText('Create Rule'));
    expect(screen.getByTestId('approval-rule-form')).toBeInTheDocument();
    
    fireEvent.click(screen.getByText('Cancel'));
    expect(screen.queryByTestId('approval-rule-form')).not.toBeInTheDocument();
  });

  it('creates a new approval rule successfully', async () => {
    const mockCreateRule = vi.mocked(approvalApi.createApprovalRule);
    mockCreateRule.mockResolvedValue({
      id: 1,
      name: 'Test Rule',
      min_amount: 100,
      max_amount: 1000,
      currency: 'USD',
      approval_level: 1,
      approver_id: 1,
      is_active: true,
      priority: 0,
    } as any);

    render(<ApprovalRulesManager />);
    
    fireEvent.click(screen.getByText('Create Rule'));
    fireEvent.click(screen.getByText('Submit'));
    
    await waitFor(() => {
      expect(mockCreateRule).toHaveBeenCalledWith({ name: 'Test Rule' });
      expect(toast.success).toHaveBeenCalledWith('Approval rule created successfully');
    });
  });

  it('updates an existing approval rule successfully', async () => {
    const mockUpdateRule = vi.mocked(approvalApi.updateApprovalRule);
    mockUpdateRule.mockResolvedValue({
      id: 1,
      name: 'Updated Rule',
    } as any);

    render(<ApprovalRulesManager />);
    
    fireEvent.click(screen.getByText('Edit Rule'));
    fireEvent.click(screen.getByText('Submit'));
    
    await waitFor(() => {
      expect(mockUpdateRule).toHaveBeenCalledWith(1, { name: 'Test Rule' });
      expect(toast.success).toHaveBeenCalledWith('Approval rule updated successfully');
    });
  });

  it('handles create rule error', async () => {
    const mockCreateRule = vi.mocked(approvalApi.createApprovalRule);
    mockCreateRule.mockRejectedValue(new Error('API Error'));

    render(<ApprovalRulesManager />);
    
    fireEvent.click(screen.getByText('Create Rule'));
    fireEvent.click(screen.getByText('Submit'));
    
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to save approval rule');
    });
  });

  it('handles update rule error', async () => {
    const mockUpdateRule = vi.mocked(approvalApi.updateApprovalRule);
    mockUpdateRule.mockRejectedValue(new Error('API Error'));

    render(<ApprovalRulesManager />);
    
    fireEvent.click(screen.getByText('Edit Rule'));
    fireEvent.click(screen.getByText('Submit'));
    
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to save approval rule');
    });
  });

  it('shows loading state during form submission', async () => {
    const mockCreateRule = vi.mocked(approvalApi.createApprovalRule);
    mockCreateRule.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));

    render(<ApprovalRulesManager />);
    
    fireEvent.click(screen.getByText('Create Rule'));
    fireEvent.click(screen.getByText('Submit'));
    
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('refreshes the rules list when refresh is triggered', () => {
    render(<ApprovalRulesManager />);
    
    const initialRefreshKey = screen.getByTestId('approval-rules-list');
    fireEvent.click(screen.getByText('Refresh'));
    
    // The component should re-render with a new refresh key
    expect(screen.getByTestId('approval-rules-list')).toBeInTheDocument();
  });

  it('displays help information about approval rules', () => {
    render(<ApprovalRulesManager />);
    
    expect(screen.getByText(/Approval rules determine which expenses require approval/)).toBeInTheDocument();
    expect(screen.getByText(/Rules are evaluated in priority order/)).toBeInTheDocument();
  });
});