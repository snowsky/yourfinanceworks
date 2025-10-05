import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ApprovalRulesList } from '../approvals/ApprovalRulesList';
import { approvalApi, userApi } from '@/lib/api';
import { toast } from 'sonner';

// Mock the API modules
vi.mock('@/lib/api', () => ({
  approvalApi: {
    getApprovalRules: vi.fn(),
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

const mockUsers = [
  { id: 1, name: 'John Doe', email: 'john@example.com' },
  { id: 2, name: 'Jane Smith', email: 'jane@example.com' },
];

const mockRules = [
  {
    id: 1,
    name: 'Manager Approval',
    min_amount: 100,
    max_amount: 1000,
    category_filter: '["Travel", "Meals"]',
    currency: 'USD',
    approval_level: 1,
    approver_id: 1,
    is_active: true,
    priority: 10,
    auto_approve_below: 50,
    approver: { id: 1, name: 'John Doe', email: 'john@example.com' },
  },
  {
    id: 2,
    name: 'Director Approval',
    min_amount: 1000,
    max_amount: undefined,
    category_filter: undefined,
    currency: 'USD',
    approval_level: 2,
    approver_id: 2,
    is_active: false,
    priority: 5,
    approver: { id: 2, name: 'Jane Smith', email: 'jane@example.com' },
  },
];

describe('ApprovalRulesList', () => {
  const mockOnEdit = vi.fn();
  const mockOnRefresh = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(approvalApi.getApprovalRules).mockResolvedValue(mockRules);
    vi.mocked(userApi.getUsers).mockResolvedValue(mockUsers);
  });

  it('renders approval rules list correctly', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
      expect(screen.getByText('Director Approval')).toBeInTheDocument();
    });

    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    vi.mocked(approvalApi.getApprovalRules).mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 100))
    );

    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('Loading approval rules...')).toBeInTheDocument();
  });

  it('handles API error gracefully', async () => {
    vi.mocked(approvalApi.getApprovalRules).mockRejectedValue(new Error('API Error'));

    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to load approval rules');
    });
  });

  it('filters rules by search term', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search rules or approvers...');
    fireEvent.change(searchInput, { target: { value: 'Manager' } });

    expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    expect(screen.queryByText('Director Approval')).not.toBeInTheDocument();
  });

  it('filters rules by status', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    // Filter by active status
    fireEvent.click(screen.getByRole('combobox', { name: /status/i }));
    fireEvent.click(screen.getByText('Active'));

    expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    expect(screen.queryByText('Director Approval')).not.toBeInTheDocument();
  });

  it('filters rules by approver', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    // Filter by approver
    fireEvent.click(screen.getByRole('combobox', { name: /approver/i }));
    fireEvent.click(screen.getByText('John Doe'));

    expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    expect(screen.queryByText('Director Approval')).not.toBeInTheDocument();
  });

  it('calls onEdit when edit button is clicked', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    // Click on the first rule's actions menu
    const actionButtons = screen.getAllByRole('button', { name: /more options/i });
    fireEvent.click(actionButtons[0]);

    // Click edit
    fireEvent.click(screen.getByText('Edit'));

    expect(mockOnEdit).toHaveBeenCalledWith(mockRules[0]);
  });

  it('toggles rule active status', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    const switches = screen.getAllByRole('switch');
    fireEvent.click(switches[0]);

    await waitFor(() => {
      expect(approvalApi.updateApprovalRule).toHaveBeenCalledWith(1, { is_active: false });
      expect(toast.success).toHaveBeenCalledWith('Rule deactivated successfully');
    });
  });

  it('handles delete rule with confirmation', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    // Click on the first rule's actions menu
    const actionButtons = screen.getAllByRole('button', { name: /more options/i });
    fireEvent.click(actionButtons[0]);

    // Click delete
    fireEvent.click(screen.getByText('Delete'));

    // Confirm deletion
    expect(screen.getByText('Delete Approval Rule')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Delete Rule'));

    await waitFor(() => {
      expect(approvalApi.deleteApprovalRule).toHaveBeenCalledWith(1);
      expect(toast.success).toHaveBeenCalledWith('Approval rule deleted successfully');
    });
  });

  it('handles priority changes', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    // Click priority up button for the second rule (Director Approval)
    const upButtons = screen.getAllByRole('button', { name: /move up/i });
    fireEvent.click(upButtons[1]);

    await waitFor(() => {
      expect(approvalApi.updateApprovalRulePriority).toHaveBeenCalledWith(2, 11);
      expect(toast.success).toHaveBeenCalledWith('Rule priority updated');
    });
  });

  it('displays rule information correctly', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    // Check amount range display
    expect(screen.getByText('$100.00 - $1000.00')).toBeInTheDocument();
    expect(screen.getByText('$1000.00 - No limit')).toBeInTheDocument();

    // Check currency display
    expect(screen.getAllByText('USD')).toHaveLength(2);

    // Check approval level badges
    expect(screen.getAllByText(/Level \d/)).toHaveLength(2);

    // Check priority badges
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();

    // Check status badges
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  it('displays categories correctly', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Travel, Meals')).toBeInTheDocument();
      expect(screen.getByText('All categories')).toBeInTheDocument();
    });
  });

  it('displays auto-approve information', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Auto-approve below $50')).toBeInTheDocument();
    });
  });

  it('shows empty state when no rules exist', async () => {
    vi.mocked(approvalApi.getApprovalRules).mockResolvedValue([]);

    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('No approval rules configured')).toBeInTheDocument();
    });
  });

  it('shows filtered empty state', async () => {
    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search rules or approvers...');
    fireEvent.change(searchInput, { target: { value: 'NonExistent' } });

    expect(screen.getByText('No rules match your filters')).toBeInTheDocument();
  });

  it('handles error when toggling rule status', async () => {
    vi.mocked(approvalApi.updateApprovalRule).mockRejectedValue(new Error('API Error'));

    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    const switches = screen.getAllByRole('switch');
    fireEvent.click(switches[0]);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to update rule status');
    });
  });

  it('handles error when deleting rule', async () => {
    vi.mocked(approvalApi.deleteApprovalRule).mockRejectedValue(new Error('API Error'));

    render(
      <ApprovalRulesList
        onEdit={mockOnEdit}
        onRefresh={mockOnRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Manager Approval')).toBeInTheDocument();
    });

    // Click on the first rule's actions menu
    const actionButtons = screen.getAllByRole('button', { name: /more options/i });
    fireEvent.click(actionButtons[0]);

    // Click delete
    fireEvent.click(screen.getByText('Delete'));

    // Confirm deletion
    fireEvent.click(screen.getByText('Delete Rule'));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to delete approval rule');
    });
  });
});