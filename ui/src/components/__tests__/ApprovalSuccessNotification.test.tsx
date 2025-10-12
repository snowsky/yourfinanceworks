import { render, screen } from '@testing-library/react';
import { ApprovalSuccessNotification } from '../expenses/ApprovalSuccessNotification';

describe('ApprovalSuccessNotification', () => {
  const defaultProps = {
    expenseAmount: 250.75,
    currency: 'USD'
  };

  it('renders success message with expense amount', () => {
    render(<ApprovalSuccessNotification {...defaultProps} />);

    expect(screen.getByText('Expense submitted for approval successfully!')).toBeInTheDocument();
    expect(screen.getByText('Amount: USD 250.75')).toBeInTheDocument();
  });

  it('displays approver name when provided', () => {
    render(
      <ApprovalSuccessNotification 
        {...defaultProps} 
        approverName="John Smith" 
      />
    );

    expect(screen.getByText('Assigned to: John Smith')).toBeInTheDocument();
  });

  it('displays default estimated approval time', () => {
    render(<ApprovalSuccessNotification {...defaultProps} />);

    expect(screen.getByText('Expected approval time: 1-2 business days')).toBeInTheDocument();
  });

  it('displays custom estimated approval time when provided', () => {
    render(
      <ApprovalSuccessNotification 
        {...defaultProps} 
        estimatedApprovalTime="3-5 business days" 
      />
    );

    expect(screen.getByText('Expected approval time: 3-5 business days')).toBeInTheDocument();
  });

  it('renders with different currencies', () => {
    render(
      <ApprovalSuccessNotification 
        expenseAmount={100.50}
        currency="EUR"
      />
    );

    expect(screen.getByText('Amount: EUR 100.50')).toBeInTheDocument();
  });

  it('formats amount with two decimal places', () => {
    render(
      <ApprovalSuccessNotification 
        expenseAmount={42}
        currency="CAD"
      />
    );

    expect(screen.getByText('Amount: CAD 42.00')).toBeInTheDocument();
  });

  it('includes all visual elements', () => {
    render(
      <ApprovalSuccessNotification 
        {...defaultProps}
        approverName="Jane Doe"
        estimatedApprovalTime="24 hours"
      />
    );

    // Check for success icon (CheckCircle2)
    const successIcon = document.querySelector('svg');
    expect(successIcon).toBeInTheDocument();

    // Check for user icon
    expect(screen.getByText('Assigned to: Jane Doe')).toBeInTheDocument();
    
    // Check for clock icon
    expect(screen.getByText('Expected approval time: 24 hours')).toBeInTheDocument();
  });
});