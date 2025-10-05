import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ApprovalRuleForm } from '../approvals/ApprovalRuleForm';
import { userApi } from '@/lib/api';
import { toast } from 'sonner';

// Mock the API modules
vi.mock('@/lib/api', () => ({
  userApi: {
    getUsers: vi.fn(),
  },
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

// Mock constants
vi.mock('@/constants/expenses', () => ({
  EXPENSE_CATEGORY_OPTIONS: ['Travel', 'Meals', 'Office Supplies', 'Software'],
}));

const mockUsers = [
  { id: 1, name: 'John Doe', email: 'john@example.com' },
  { id: 2, name: 'Jane Smith', email: 'jane@example.com' },
];

const mockRule = {
  id: 1,
  name: 'Manager Approval',
  min_amount: 100,
  max_amount: 1000,
  category_filter: '["Travel", "Meals"]',
  currency: 'USD',
  approval_level: 1,
  approver_id: 1,
  is_active: true,
  priority: 5,
  auto_approve_below: 50,
};

describe('ApprovalRuleForm', () => {
  const mockOnSubmit = vi.fn();
  const mockOnCancel = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(userApi.getUsers).mockResolvedValue(mockUsers);
  });

  it('renders create form correctly', async () => {
    render(
      <ApprovalRuleForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Create Approval Rule')).toBeInTheDocument();
    });

    expect(screen.getByLabelText('Rule Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Approver')).toBeInTheDocument();
    expect(screen.getByLabelText('Minimum Amount')).toBeInTheDocument();
    expect(screen.getByLabelText('Maximum Amount')).toBeInTheDocument();
    expect(screen.getByLabelText('Currency')).toBeInTheDocument();
    expect(screen.getByText('Create Rule')).toBeInTheDocument();
  });

  it('renders edit form with existing rule data', async () => {
    render(
      <ApprovalRuleForm
        rule={mockRule}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Edit Approval Rule')).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue('Manager Approval')).toBeInTheDocument();
    expect(screen.getByDisplayValue('100')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1000')).toBeInTheDocument();
    expect(screen.getByText('Update Rule')).toBeInTheDocument();
  });

  it('loads and displays users in approver dropdown', async () => {
    render(
      <ApprovalRuleForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(userApi.getUsers).toHaveBeenCalled();
    });

    // Click on approver dropdown
    fireEvent.click(screen.getByRole('combobox', { name: /approver/i }));

    await waitFor(() => {
      expect(screen.getByText('John Doe (john@example.com)')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith (jane@example.com)')).toBeInTheDocument();
    });
  });

  it('handles category selection and removal', async () => {
    render(
      <ApprovalRuleForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Add category filter')).toBeInTheDocument();
    });

    // Add a category
    fireEvent.click(screen.getByRole('combobox', { name: /add category filter/i }));
    fireEvent.click(screen.getByText('Travel'));

    expect(screen.getByText('Travel')).toBeInTheDocument();

    // Remove the category
    const removeButton = screen.getByRole('button', { name: /remove travel/i });
    fireEvent.click(removeButton);

    expect(screen.queryByText('Travel')).not.toBeInTheDocument();
  });

  it('validates form fields correctly', async () => {
    render(
      <ApprovalRuleForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Create Rule')).toBeInTheDocument();
    });

    // Try to submit without required fields
    fireEvent.click(screen.getByText('Create Rule'));

    await waitFor(() => {
      expect(screen.getByText('Rule name is required')).toBeInTheDocument();
    });
  });

  it('validates amount range correctly', async () => {
    render(
      <ApprovalRuleForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Rule Name')).toBeInTheDocument();
    });

    // Fill in form with invalid amount range
    fireEvent.change(screen.getByLabelText('Rule Name'), {
      target: { value: 'Test Rule' },
    });
    fireEvent.change(screen.getByLabelText('Minimum Amount'), {
      target: { value: '1000' },
    });
    fireEvent.change(screen.getByLabelText('Maximum Amount'), {
      target: { value: '500' },
    });

    fireEvent.click(screen.getByText('Create Rule'));

    await waitFor(() => {
      expect(screen.getByText('Maximum amount must be greater than minimum amount')).toBeInTheDocument();
    });
  });

  it('submits form with correct data', async () => {
    render(
      <ApprovalRuleForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Rule Name')).toBeInTheDocument();
    });

    // Fill in the form
    fireEvent.change(screen.getByLabelText('Rule Name'), {
      target: { value: 'Test Rule' },
    });
    fireEvent.change(screen.getByLabelText('Minimum Amount'), {
      target: { value: '100' },
    });
    fireEvent.change(screen.getByLabelText('Maximum Amount'), {
      target: { value: '1000' },
    });

    // Select approver
    fireEvent.click(screen.getByRole('combobox', { name: /approver/i }));
    fireEvent.click(screen.getByText('John Doe (john@example.com)'));

    fireEvent.click(screen.getByText('Create Rule'));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Test Rule',
          min_amount: 100,
          max_amount: 1000,
          approver_id: 1,
          currency: 'USD',
          approval_level: 1,
          is_active: true,
          priority: 0,
        })
      );
    });
  });

  it('calls onCancel when cancel button is clicked', async () => {
    render(
      <ApprovalRuleForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Cancel'));
    expect(mockOnCancel).toHaveBeenCalled();
  });

  it('shows loading state when loading prop is true', async () => {
    render(
      <ApprovalRuleForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        loading={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Saving...')).toBeInTheDocument();
    });
  });

  it('handles user loading error', async () => {
    vi.mocked(userApi.getUsers).mockRejectedValue(new Error('API Error'));

    render(
      <ApprovalRuleForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to load users');
    });
  });

  it('toggles active status correctly', async () => {
    render(
      <ApprovalRuleForm
        rule={mockRule}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('switch')).toBeInTheDocument();
    });

    const activeSwitch = screen.getByRole('switch');
    expect(activeSwitch).toBeChecked();

    fireEvent.click(activeSwitch);
    expect(activeSwitch).not.toBeChecked();
  });

  it('displays existing categories for edit mode', async () => {
    render(
      <ApprovalRuleForm
        rule={mockRule}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Travel')).toBeInTheDocument();
      expect(screen.getByText('Meals')).toBeInTheDocument();
    });
  });
});