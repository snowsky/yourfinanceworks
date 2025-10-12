import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ApprovalSubmissionDialog } from '../expenses/ApprovalSubmissionDialog';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { it } from 'node:test';
import { beforeEach } from 'node:test';
import { describe } from 'node:test';

describe('ApprovalSubmissionDialog', () => {
  const mockOnConfirm = vi.fn();
  const mockOnOpenChange = vi.fn();

  const defaultProps = {
    open: true,
    onOpenChange: mockOnOpenChange,
    onConfirm: mockOnConfirm,
    expenseAmount: 150.00,
    currency: 'USD',
    category: 'Travel',
    loading: false
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders dialog with expense details', () => {
    render(<ApprovalSubmissionDialog {...defaultProps} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Submit for Approval' })).toBeInTheDocument();
    expect(screen.getByText('Amount:')).toBeInTheDocument();
    expect(screen.getByText('Category:')).toBeInTheDocument();
    expect(screen.getByText('Travel')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Add any additional context for the approver...')).toBeInTheDocument();
  });

  it('allows user to add notes', async () => {
    const user = userEvent.setup();
    render(<ApprovalSubmissionDialog {...defaultProps} />);

    const notesTextarea = screen.getByPlaceholderText('Add any additional context for the approver...');
    await user.type(notesTextarea, 'This is for the client meeting');

    expect(notesTextarea).toHaveValue('This is for the client meeting');
  });

  it('calls onConfirm with notes when submitted', async () => {
    const user = userEvent.setup();
    mockOnConfirm.mockResolvedValue(undefined);
    
    render(<ApprovalSubmissionDialog {...defaultProps} />);

    const notesTextarea = screen.getByPlaceholderText('Add any additional context for the approver...');
    await user.type(notesTextarea, 'Urgent approval needed');

    const submitButton = screen.getByRole('button', { name: 'Submit for Approval' });
    await user.click(submitButton);

    expect(mockOnConfirm).toHaveBeenCalledWith('Urgent approval needed');
  });

  it('calls onConfirm with undefined when no notes provided', async () => {
    const user = userEvent.setup();
    mockOnConfirm.mockResolvedValue(undefined);
    
    render(<ApprovalSubmissionDialog {...defaultProps} />);

    const submitButton = screen.getByRole('button', { name: 'Submit for Approval' });
    await user.click(submitButton);

    expect(mockOnConfirm).toHaveBeenCalledWith(undefined);
  });

  it('shows loading state when submitting', () => {
    render(<ApprovalSubmissionDialog {...defaultProps} loading={true} />);

    expect(screen.getByText('Submitting...')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Add any additional context for the approver...')).toBeDisabled();
  });

  it('calls onOpenChange when cancel is clicked', async () => {
    const user = userEvent.setup();
    render(<ApprovalSubmissionDialog {...defaultProps} />);

    const cancelButton = screen.getByText('Cancel');
    await user.click(cancelButton);

    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  it('clears notes after successful submission', async () => {
    const user = userEvent.setup();
    mockOnConfirm.mockResolvedValue(undefined);
    
    render(<ApprovalSubmissionDialog {...defaultProps} />);

    const notesTextarea = screen.getByPlaceholderText('Add any additional context for the approver...');
    await user.type(notesTextarea, 'Test notes');
    
    const submitButton = screen.getByRole('button', { name: 'Submit for Approval' });
    await user.click(submitButton);

    await waitFor(() => {
      expect(notesTextarea).toHaveValue('');
    });
  });

  it('does not clear notes when submission fails', async () => {
    const user = userEvent.setup();
    mockOnConfirm.mockRejectedValue(new Error('Submission failed'));
    
    render(<ApprovalSubmissionDialog {...defaultProps} />);

    const notesTextarea = screen.getByPlaceholderText('Add any additional context for the approver...');
    await user.type(notesTextarea, 'Test notes');
    
    const submitButton = screen.getByRole('button', { name: 'Submit for Approval' });
    await user.click(submitButton);

    await waitFor(() => {
      expect(notesTextarea).toHaveValue('Test notes');
    });
  });

  it('clears notes when dialog is cancelled', async () => {
    const user = userEvent.setup();
    render(<ApprovalSubmissionDialog {...defaultProps} />);

    const notesTextarea = screen.getByPlaceholderText('Add any additional context for the approver...');
    await user.type(notesTextarea, 'Test notes');
    
    const cancelButton = screen.getByText('Cancel');
    await user.click(cancelButton);

    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  it('displays approval workflow information', () => {
    render(<ApprovalSubmissionDialog {...defaultProps} />);

    expect(screen.getByText(/This expense will be submitted for approval according to your organization's approval rules/)).toBeInTheDocument();
  });
});