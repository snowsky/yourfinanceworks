import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import ExpensesNew from '../pages/ExpensesNew';
import ExpensesEdit from '../pages/ExpensesEdit';
import * as api from '../lib/api';

// Mock the API
vi.mock('../lib/api', () => ({
  expenseApi: {
    createExpense: vi.fn(),
    updateExpense: vi.fn(),
    getExpense: vi.fn(),
    listAttachments: vi.fn(),
    uploadReceipt: vi.fn(),
    submitForApproval: vi.fn(),
  },
  linkApi: {
    getInvoicesBasic: vi.fn(),
  }
}));

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: '123' }),
    useNavigate: () => vi.fn(),
  };
});

// Mock sonner
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: any) => options?.defaultValue || key,
  }),
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('Expense Approval Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.linkApi.getInvoicesBasic as any).mockResolvedValue([]);
    (api.expenseApi.createExpense as any).mockResolvedValue({ id: 123 });
    (api.expenseApi.updateExpense as any).mockResolvedValue({});
    (api.expenseApi.getExpense as any).mockResolvedValue({
      id: 123,
      amount: 100,
      currency: 'USD',
      category: 'Travel',
      status: 'recorded',
      expense_date: '2024-01-15',
    });
    (api.expenseApi.listAttachments as any).mockResolvedValue([]);
    (api.expenseApi.submitForApproval as any).mockResolvedValue([
      { id: 1, expense_id: 123, status: 'pending', approval_level: 1 }
    ]);
  });

  describe('ExpensesNew with Approval', () => {
    it('shows approval submission option', async () => {
      renderWithRouter(<ExpensesNew />);

      await waitFor(() => {
        expect(screen.getByText('Approval Workflow')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Submit this expense for approval after creation')).toBeInTheDocument();
    });

    it('creates expense and shows approval dialog when approval option is selected', async () => {
      const user = userEvent.setup();
      renderWithRouter(<ExpensesNew />);

      await waitFor(() => {
        expect(screen.getByText('Approval Workflow')).toBeInTheDocument();
      });

      // Fill in required fields
      const amountInput = screen.getByDisplayValue('0');
      await user.clear(amountInput);
      await user.type(amountInput, '150');

      // Select approval option
      const approvalCheckbox = screen.getByLabelText('Submit this expense for approval after creation');
      await user.click(approvalCheckbox);

      // Submit form
      const submitButton = screen.getByText('Create & Submit for Approval');
      await user.click(submitButton);

      // Wait for expense creation
      await waitFor(() => {
        expect(api.expenseApi.createExpense).toHaveBeenCalledWith(
          expect.objectContaining({
            amount: 150,
            status: 'draft'
          })
        );
      });

      // Check that approval dialog appears
      await waitFor(() => {
        expect(screen.getByText('Submit for Approval')).toBeInTheDocument();
      });
    });

    it('validates required fields before showing approval dialog', async () => {
      const user = userEvent.setup();
      renderWithRouter(<ExpensesNew />);

      await waitFor(() => {
        expect(screen.getByText('Approval Workflow')).toBeInTheDocument();
      });

      // Select approval option without filling required fields
      const approvalCheckbox = screen.getByLabelText('Submit this expense for approval after creation');
      await user.click(approvalCheckbox);

      // Try to submit form
      const submitButton = screen.getByText('Create & Submit for Approval');
      await user.click(submitButton);

      // Should not create expense or show dialog due to validation
      expect(api.expenseApi.createExpense).not.toHaveBeenCalled();
      expect(screen.queryByText('Submit for Approval')).not.toBeInTheDocument();
    });

    it('submits expense for approval with notes', async () => {
      const user = userEvent.setup();
      renderWithRouter(<ExpensesNew />);

      await waitFor(() => {
        expect(screen.getByText('Approval Workflow')).toBeInTheDocument();
      });

      // Fill in required fields
      const amountInput = screen.getByDisplayValue('0');
      await user.clear(amountInput);
      await user.type(amountInput, '200');

      // Select approval option
      const approvalCheckbox = screen.getByLabelText('Submit this expense for approval after creation');
      await user.click(approvalCheckbox);

      // Submit form
      const submitButton = screen.getByText('Create & Submit for Approval');
      await user.click(submitButton);

      // Wait for approval dialog
      await waitFor(() => {
        expect(screen.getByText('Submit for Approval')).toBeInTheDocument();
      });

      // Add notes in dialog
      const notesTextarea = screen.getByPlaceholderText('Add any additional context for the approver...');
      await user.type(notesTextarea, 'Urgent client meeting expense');

      // Submit for approval
      const approvalSubmitButton = screen.getByText('Submit for Approval');
      await user.click(approvalSubmitButton);

      // Check API calls
      await waitFor(() => {
        expect(api.expenseApi.submitForApproval).toHaveBeenCalledWith(123, 'Urgent client meeting expense');
      });
    });
  });

  describe('ExpensesEdit with Approval', () => {
    it('shows approval submission option for non-approved expenses', async () => {
      renderWithRouter(<ExpensesEdit />);

      await waitFor(() => {
        expect(screen.getByText('Approval Workflow')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Submit this expense for approval after saving changes')).toBeInTheDocument();
    });

    it('hides approval submission option for expenses already in approval workflow', async () => {
      (api.expenseApi.getExpense as any).mockResolvedValue({
        id: 123,
        amount: 100,
        currency: 'USD',
        category: 'Travel',
        status: 'pending_approval',
        expense_date: '2024-01-15',
      });

      renderWithRouter(<ExpensesEdit />);

      await waitFor(() => {
        expect(screen.queryByText('Approval Workflow')).not.toBeInTheDocument();
      });
    });

    it('updates expense and shows approval dialog when approval option is selected', async () => {
      const user = userEvent.setup();
      renderWithRouter(<ExpensesEdit />);

      await waitFor(() => {
        expect(screen.getByText('Approval Workflow')).toBeInTheDocument();
      });

      // Select approval option
      const approvalCheckbox = screen.getByLabelText('Submit this expense for approval after saving changes');
      await user.click(approvalCheckbox);

      // Save changes
      const saveButton = screen.getByText('Save & Submit for Approval');
      await user.click(saveButton);

      // Wait for expense update
      await waitFor(() => {
        expect(api.expenseApi.updateExpense).toHaveBeenCalledWith(
          123,
          expect.objectContaining({
            status: 'draft'
          })
        );
      });

      // Check that approval dialog appears
      await waitFor(() => {
        expect(screen.getByText('Submit for Approval')).toBeInTheDocument();
      });
    });

    it('validates inventory consumption items before approval submission', async () => {
      const user = userEvent.setup();
      renderWithRouter(<ExpensesEdit />);

      await waitFor(() => {
        expect(screen.getByText('Approval Workflow')).toBeInTheDocument();
      });

      // Enable inventory consumption
      const consumptionCheckbox = screen.getByLabelText('This expense is for consuming inventory items');
      await user.click(consumptionCheckbox);

      // Select approval option
      const approvalCheckbox = screen.getByLabelText('Submit this expense for approval after saving changes');
      await user.click(approvalCheckbox);

      // Try to save without consumption items
      const saveButton = screen.getByText('Save & Submit for Approval');
      await user.click(saveButton);

      // Should not update expense due to validation
      expect(api.expenseApi.updateExpense).not.toHaveBeenCalled();
      expect(screen.queryByText('Submit for Approval')).not.toBeInTheDocument();
    });
  });

  describe('Approval Dialog Interaction', () => {
    it('handles approval submission errors gracefully', async () => {
      const user = userEvent.setup();
      (api.expenseApi.submitForApproval as any).mockRejectedValue(new Error('Network error'));

      renderWithRouter(<ExpensesNew />);

      await waitFor(() => {
        expect(screen.getByText('Approval Workflow')).toBeInTheDocument();
      });

      // Fill form and trigger approval dialog
      const amountInput = screen.getByDisplayValue('0');
      await user.clear(amountInput);
      await user.type(amountInput, '100');

      const approvalCheckbox = screen.getByLabelText('Submit this expense for approval after creation');
      await user.click(approvalCheckbox);

      const submitButton = screen.getByText('Create & Submit for Approval');
      await user.click(submitButton);

      // Wait for approval dialog
      await waitFor(() => {
        expect(screen.getByText('Submit for Approval')).toBeInTheDocument();
      });

      // Submit for approval
      const approvalSubmitButton = screen.getByText('Submit for Approval');
      await user.click(approvalSubmitButton);

      // Dialog should remain open on error
      await waitFor(() => {
        expect(screen.getByText('Submit for Approval')).toBeInTheDocument();
      });
    });

    it('closes dialog and navigates on successful approval submission', async () => {
      const user = userEvent.setup();
      const mockNavigate = vi.fn();
      
      // Mock window.history.back for ExpensesNew
      Object.defineProperty(window, 'history', {
        value: { back: vi.fn() },
        writable: true
      });

      renderWithRouter(<ExpensesNew />);

      await waitFor(() => {
        expect(screen.getByText('Approval Workflow')).toBeInTheDocument();
      });

      // Fill form and trigger approval dialog
      const amountInput = screen.getByDisplayValue('0');
      await user.clear(amountInput);
      await user.type(amountInput, '100');

      const approvalCheckbox = screen.getByLabelText('Submit this expense for approval after creation');
      await user.click(approvalCheckbox);

      const submitButton = screen.getByText('Create & Submit for Approval');
      await user.click(submitButton);

      // Wait for approval dialog
      await waitFor(() => {
        expect(screen.getByText('Submit for Approval')).toBeInTheDocument();
      });

      // Submit for approval
      const approvalSubmitButton = screen.getByText('Submit for Approval');
      await user.click(approvalSubmitButton);

      // Check that navigation occurs
      await waitFor(() => {
        expect(window.history.back).toHaveBeenCalled();
      });
    });
  });
});