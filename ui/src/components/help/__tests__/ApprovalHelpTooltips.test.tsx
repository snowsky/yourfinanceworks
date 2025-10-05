import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ApprovalHelpTooltips, { HelpTooltip, QuickHelp } from '../ApprovalHelpTooltips';

describe('ApprovalHelpTooltips', () => {
  it('renders help toggle button', () => {
    render(
      <ApprovalHelpTooltips context="dashboard">
        <div>Test content</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    expect(helpButton).toBeInTheDocument();
  });

  it('starts tour when help button is clicked', async () => {
    render(
      <ApprovalHelpTooltips context="dashboard">
        <div>Test content</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    fireEvent.click(helpButton);

    await waitFor(() => {
      expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
      expect(screen.getByText('1 of 4')).toBeInTheDocument();
    });
  });

  it('navigates through tour steps', async () => {
    render(
      <ApprovalHelpTooltips context="dashboard">
        <div>Test content</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    fireEvent.click(helpButton);

    await waitFor(() => {
      expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
    });

    const nextButton = screen.getByText('Next');
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText('Filter & Sort')).toBeInTheDocument();
      expect(screen.getByText('2 of 4')).toBeInTheDocument();
    });
  });

  it('ends tour when finish is clicked', async () => {
    render(
      <ApprovalHelpTooltips context="dashboard">
        <div>Test content</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    fireEvent.click(helpButton);

    // Navigate to last step
    const nextButton = screen.getByText('Next');
    fireEvent.click(nextButton);
    fireEvent.click(nextButton);
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText('Finish')).toBeInTheDocument();
    });

    const finishButton = screen.getByText('Finish');
    fireEvent.click(finishButton);

    await waitFor(() => {
      expect(screen.queryByText('Delegation Active')).not.toBeInTheDocument();
    });
  });

  it('can navigate backwards in tour', async () => {
    render(
      <ApprovalHelpTooltips context="dashboard">
        <div>Test content</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    fireEvent.click(helpButton);

    const nextButton = screen.getByText('Next');
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText('Filter & Sort')).toBeInTheDocument();
    });

    const prevButton = screen.getByText('Previous');
    fireEvent.click(prevButton);

    await waitFor(() => {
      expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
      expect(screen.getByText('1 of 4')).toBeInTheDocument();
    });
  });
});

describe('HelpTooltip', () => {
  it('shows tooltip on hover', async () => {
    render(
      <HelpTooltip id="pending-count" context="dashboard">
        <button>Test Button</button>
      </HelpTooltip>
    );

    const button = screen.getByText('Test Button');
    fireEvent.mouseEnter(button);

    await waitFor(() => {
      expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
      expect(screen.getByText(/Number of expenses waiting/)).toBeInTheDocument();
    });
  });

  it('hides tooltip on mouse leave', async () => {
    render(
      <HelpTooltip id="pending-count" context="dashboard">
        <button>Test Button</button>
      </HelpTooltip>
    );

    const button = screen.getByText('Test Button');
    fireEvent.mouseEnter(button);

    await waitFor(() => {
      expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
    });

    fireEvent.mouseLeave(button);

    await waitFor(() => {
      expect(screen.queryByText('Pending Approvals')).not.toBeInTheDocument();
    });
  });

  it('renders children when tooltip data not found', () => {
    render(
      <HelpTooltip id="nonexistent" context="dashboard">
        <button>Test Button</button>
      </HelpTooltip>
    );

    expect(screen.getByText('Test Button')).toBeInTheDocument();
  });
});

describe('QuickHelp', () => {
  it('renders quick help button', () => {
    render(<QuickHelp context="dashboard" />);

    expect(screen.getByText('Quick Help')).toBeInTheDocument();
  });

  it('shows help panel when clicked', async () => {
    render(<QuickHelp context="dashboard" />);

    const quickHelpButton = screen.getByText('Quick Help');
    fireEvent.click(quickHelpButton);

    await waitFor(() => {
      expect(screen.getByText('Quick Tips')).toBeInTheDocument();
      expect(screen.getByText(/Use filters to prioritize/)).toBeInTheDocument();
    });
  });

  it('hides help panel when close button is clicked', async () => {
    render(<QuickHelp context="dashboard" />);

    const quickHelpButton = screen.getByText('Quick Help');
    fireEvent.click(quickHelpButton);

    await waitFor(() => {
      expect(screen.getByText('Quick Tips')).toBeInTheDocument();
    });

    const closeButton = screen.getByRole('button', { name: '' }); // X button
    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByText('Quick Tips')).not.toBeInTheDocument();
    });
  });

  it('displays context-specific tips', () => {
    render(<QuickHelp context="submission" />);

    const quickHelpButton = screen.getByText('Quick Help');
    fireEvent.click(quickHelpButton);

    expect(screen.getByText(/Ensure all required fields/)).toBeInTheDocument();
    expect(screen.getByText(/Upload clear, legible receipts/)).toBeInTheDocument();
  });
});

describe('Context-specific content', () => {
  it('shows submission context tooltips', () => {
    render(
      <ApprovalHelpTooltips context="submission">
        <div>Submission form</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    fireEvent.click(helpButton);

    expect(screen.getByText('Submit for Approval')).toBeInTheDocument();
  });

  it('shows approval context tooltips', () => {
    render(
      <ApprovalHelpTooltips context="approval">
        <div>Approval form</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    fireEvent.click(helpButton);

    expect(screen.getByText('Approve Expense')).toBeInTheDocument();
  });

  it('shows rules context tooltips', () => {
    render(
      <ApprovalHelpTooltips context="rules">
        <div>Rules configuration</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    fireEvent.click(helpButton);

    expect(screen.getByText('Rule Priority')).toBeInTheDocument();
  });

  it('shows delegation context tooltips', () => {
    render(
      <ApprovalHelpTooltips context="delegation">
        <div>Delegation setup</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    fireEvent.click(helpButton);

    expect(screen.getByText('Choose Delegate')).toBeInTheDocument();
  });
});

describe('Accessibility', () => {
  it('has proper ARIA labels and roles', () => {
    render(
      <ApprovalHelpTooltips context="dashboard">
        <div>Test content</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    expect(helpButton).toHaveAttribute('title');
  });

  it('supports keyboard navigation', async () => {
    render(
      <ApprovalHelpTooltips context="dashboard">
        <div>Test content</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    helpButton.focus();
    fireEvent.keyDown(helpButton, { key: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
    });
  });

  it('provides proper focus management in tour', async () => {
    render(
      <ApprovalHelpTooltips context="dashboard">
        <div>Test content</div>
      </ApprovalHelpTooltips>
    );

    const helpButton = screen.getByTitle('Show Help');
    fireEvent.click(helpButton);

    await waitFor(() => {
      const nextButton = screen.getByText('Next');
      expect(nextButton).toBeInTheDocument();
    });
  });
});