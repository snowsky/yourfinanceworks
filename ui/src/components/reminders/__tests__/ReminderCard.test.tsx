import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { ReminderCard } from '../ReminderCard';

const mockReminder = {
  id: 1,
  title: 'Test Reminder',
  description: 'Test description',
  due_date: '2024-01-15T10:00:00Z',
  priority: 'medium' as const,
  status: 'pending' as const,
  recurrence_pattern: 'none' as const,
  assigned_to: {
    id: 1,
    email: 'user@example.com',
    first_name: 'John',
    last_name: 'Doe'
  },
  created_by: {
    id: 1,
    email: 'user@example.com',
    first_name: 'John',
    last_name: 'Doe'
  },
  tags: ['work', 'important'],
  snooze_count: 0
};

const mockSnoozedReminder = {
  ...mockReminder,
  id: 2,
  status: 'snoozed' as const,
  snoozed_until: '2024-01-16T10:00:00Z',
  snooze_count: 2
};

const mockCompletedReminder = {
  ...mockReminder,
  id: 3,
  status: 'completed' as const,
  completed_at: '2024-01-14T10:00:00Z'
};

const mockOverdueReminder = {
  ...mockReminder,
  id: 4,
  due_date: '2024-01-10T10:00:00Z', // Past date
  priority: 'urgent' as const
};

describe('ReminderCard', () => {
  const mockProps = {
    currentUserId: 1,
    onEdit: vi.fn(),
    onComplete: vi.fn(),
    onSnooze: vi.fn(),
    onUnsnooze: vi.fn(),
    onDelete: vi.fn()
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock current date to ensure consistent testing
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Basic Rendering', () => {
    it('renders reminder title and description', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByText('Test Reminder')).toBeInTheDocument();
      expect(screen.getByText('Test description')).toBeInTheDocument();
    });

    it('displays priority badge', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByText('medium')).toBeInTheDocument();
    });

    it('displays status badge', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByText('pending')).toBeInTheDocument();
    });

    it('displays assigned user information', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByText('You')).toBeInTheDocument();
    });

    it('displays tags when present', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByText('work')).toBeInTheDocument();
      expect(screen.getByText('important')).toBeInTheDocument();
    });

    it('displays recurrence pattern when not none', () => {
      const recurringReminder = { ...mockReminder, recurrence_pattern: 'weekly' as const };
      render(<ReminderCard reminder={recurringReminder} {...mockProps} />);
      
      expect(screen.getByText('Weekly')).toBeInTheDocument();
    });
  });

  describe('Date Formatting', () => {
    it('shows "Today at" for due date today', () => {
      const todayReminder = { ...mockReminder, due_date: '2024-01-15T14:00:00Z' };
      render(<ReminderCard reminder={todayReminder} {...mockProps} />);
      
      expect(screen.getByText(/Today at/)).toBeInTheDocument();
    });

    it('shows "Tomorrow at" for due date tomorrow', () => {
      const tomorrowReminder = { ...mockReminder, due_date: '2024-01-16T14:00:00Z' };
      render(<ReminderCard reminder={tomorrowReminder} {...mockProps} />);
      
      expect(screen.getByText(/Tomorrow at/)).toBeInTheDocument();
    });

    it('shows full date for other dates', () => {
      const futureReminder = { ...mockReminder, due_date: '2024-01-20T14:00:00Z' };
      render(<ReminderCard reminder={futureReminder} {...mockProps} />);
      
      expect(screen.getByText(/Jan 20, 2024/)).toBeInTheDocument();
    });
  });

  describe('Visual States', () => {
    it('applies overdue styling for past due reminders', () => {
      const { container } = render(<ReminderCard reminder={mockOverdueReminder} {...mockProps} />);
      
      expect(container.firstChild).toHaveClass('border-red-300', 'bg-red-50');
      expect(screen.getByRole('img', { hidden: true })).toBeInTheDocument(); // AlertCircle icon
    });

    it('applies today styling for reminders due today', () => {
      const todayReminder = { ...mockReminder, due_date: '2024-01-15T14:00:00Z' };
      const { container } = render(<ReminderCard reminder={todayReminder} {...mockProps} />);
      
      expect(container.firstChild).toHaveClass('border-orange-300', 'bg-orange-50');
    });

    it('applies completed styling for completed reminders', () => {
      const { container } = render(<ReminderCard reminder={mockCompletedReminder} {...mockProps} />);
      
      expect(container.firstChild).toHaveClass('opacity-75');
    });
  });

  describe('Pending Reminder Actions', () => {
    it('shows Complete and Snooze buttons for pending reminders assigned to current user', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByText('Complete')).toBeInTheDocument();
      expect(screen.getByText('Snooze')).toBeInTheDocument();
    });

    it('calls onComplete when Complete button is clicked', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      fireEvent.click(screen.getByText('Complete'));
      expect(mockProps.onComplete).toHaveBeenCalledWith(1);
    });

    it('calls onSnooze when Snooze button is clicked', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      fireEvent.click(screen.getByText('Snooze'));
      expect(mockProps.onSnooze).toHaveBeenCalledWith(1, expect.any(Date));
    });

    it('does not show action buttons for reminders not assigned to current user', () => {
      const otherUserReminder = {
        ...mockReminder,
        assigned_to: { id: 2, email: 'other@example.com', first_name: 'Jane', last_name: 'Smith' }
      };
      render(<ReminderCard reminder={otherUserReminder} {...mockProps} />);
      
      expect(screen.queryByText('Complete')).not.toBeInTheDocument();
      expect(screen.queryByText('Snooze')).not.toBeInTheDocument();
    });
  });

  describe('Snoozed Reminder Actions', () => {
    it('shows Complete and Unsnooze buttons for snoozed reminders', () => {
      render(<ReminderCard reminder={mockSnoozedReminder} {...mockProps} />);
      
      expect(screen.getByText('Complete')).toBeInTheDocument();
      expect(screen.getByText('Unsnooze')).toBeInTheDocument();
    });

    it('displays snoozed until information', () => {
      render(<ReminderCard reminder={mockSnoozedReminder} {...mockProps} />);
      
      expect(screen.getByText(/Snoozed until/)).toBeInTheDocument();
      expect(screen.getByText(/Jan 16, 2024/)).toBeInTheDocument();
    });

    it('displays snooze count when greater than 0', () => {
      render(<ReminderCard reminder={mockSnoozedReminder} {...mockProps} />);
      
      expect(screen.getByText('Snoozed 2x')).toBeInTheDocument();
    });

    it('calls onUnsnooze when Unsnooze button is clicked', () => {
      render(<ReminderCard reminder={mockSnoozedReminder} {...mockProps} />);
      
      fireEvent.click(screen.getByText('Unsnooze'));
      expect(mockProps.onUnsnooze).toHaveBeenCalledWith(2);
    });

    it('applies blue styling to Unsnooze button', () => {
      render(<ReminderCard reminder={mockSnoozedReminder} {...mockProps} />);
      
      const unsnoozeButton = screen.getByText('Unsnooze').closest('button');
      expect(unsnoozeButton).toHaveClass('text-blue-600', 'hover:text-blue-700');
    });
  });

  describe('Completed Reminder Display', () => {
    it('displays completion information', () => {
      render(<ReminderCard reminder={mockCompletedReminder} {...mockProps} />);
      
      expect(screen.getByText(/Completed on/)).toBeInTheDocument();
      expect(screen.getByText(/Jan 14, 2024/)).toBeInTheDocument();
    });

    it('does not show action buttons for completed reminders', () => {
      render(<ReminderCard reminder={mockCompletedReminder} {...mockProps} />);
      
      expect(screen.queryByText('Complete')).not.toBeInTheDocument();
      expect(screen.queryByText('Snooze')).not.toBeInTheDocument();
      expect(screen.queryByText('Unsnooze')).not.toBeInTheDocument();
    });
  });

  describe('Edit and Delete Actions', () => {
    it('shows Edit button for users who can edit', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByText('Edit')).toBeInTheDocument();
    });

    it('shows Delete button for creators', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });

    it('calls onEdit when Edit button is clicked', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      fireEvent.click(screen.getByText('Edit'));
      expect(mockProps.onEdit).toHaveBeenCalledWith(mockReminder);
    });

    it('calls onDelete when Delete button is clicked', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      fireEvent.click(screen.getByText('Delete'));
      expect(mockProps.onDelete).toHaveBeenCalledWith(1);
    });

    it('does not show Delete button for non-creators', () => {
      const otherUserReminder = {
        ...mockReminder,
        created_by: { id: 2, email: 'other@example.com', first_name: 'Jane', last_name: 'Smith' }
      };
      render(<ReminderCard reminder={otherUserReminder} {...mockProps} />);
      
      expect(screen.queryByText('Delete')).not.toBeInTheDocument();
    });
  });

  describe('Priority Colors', () => {
    it('applies correct color for urgent priority', () => {
      const urgentReminder = { ...mockReminder, priority: 'urgent' as const };
      render(<ReminderCard reminder={urgentReminder} {...mockProps} />);
      
      const priorityBadge = screen.getByText('urgent').closest('div');
      expect(priorityBadge).toHaveClass('bg-red-500', 'text-white');
    });

    it('applies correct color for high priority', () => {
      const highReminder = { ...mockReminder, priority: 'high' as const };
      render(<ReminderCard reminder={highReminder} {...mockProps} />);
      
      const priorityBadge = screen.getByText('high').closest('div');
      expect(priorityBadge).toHaveClass('bg-orange-500', 'text-white');
    });

    it('applies correct color for medium priority', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      const priorityBadge = screen.getByText('medium').closest('div');
      expect(priorityBadge).toHaveClass('bg-yellow-500', 'text-white');
    });

    it('applies correct color for low priority', () => {
      const lowReminder = { ...mockReminder, priority: 'low' as const };
      render(<ReminderCard reminder={lowReminder} {...mockProps} />);
      
      const priorityBadge = screen.getByText('low').closest('div');
      expect(priorityBadge).toHaveClass('bg-green-500', 'text-white');
    });
  });

  describe('Status Colors', () => {
    it('applies correct color for completed status', () => {
      render(<ReminderCard reminder={mockCompletedReminder} {...mockProps} />);
      
      const statusBadge = screen.getByText('completed').closest('div');
      expect(statusBadge).toHaveClass('bg-green-100', 'text-green-800', 'border-green-200');
    });

    it('applies correct color for snoozed status', () => {
      render(<ReminderCard reminder={mockSnoozedReminder} {...mockProps} />);
      
      const statusBadge = screen.getByText('snoozed').closest('div');
      expect(statusBadge).toHaveClass('bg-blue-100', 'text-blue-800', 'border-blue-200');
    });

    it('applies correct color for pending status', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      const statusBadge = screen.getByText('pending').closest('div');
      expect(statusBadge).toHaveClass('bg-yellow-100', 'text-yellow-800', 'border-yellow-200');
    });
  });

  describe('User Display Names', () => {
    it('displays full name when available', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByText('You')).toBeInTheDocument();
    });

    it('displays email when name is not available', () => {
      const noNameReminder = {
        ...mockReminder,
        assigned_to: { id: 2, email: 'test@example.com' },
        created_by: { id: 2, email: 'test@example.com' }
      };
      render(<ReminderCard reminder={noNameReminder} {...mockProps} currentUserId={1} />);
      
      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });

    it('displays first name only when last name is not available', () => {
      const firstNameOnlyReminder = {
        ...mockReminder,
        assigned_to: { id: 2, email: 'test@example.com', first_name: 'Jane' },
        created_by: { id: 2, email: 'test@example.com', first_name: 'Jane' }
      };
      render(<ReminderCard reminder={firstNameOnlyReminder} {...mockProps} currentUserId={1} />);
      
      expect(screen.getByText('Jane')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper button labels', () => {
      render(<ReminderCard reminder={mockReminder} {...mockProps} />);
      
      expect(screen.getByRole('button', { name: /Complete/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Snooze/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Edit/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Delete/ })).toBeInTheDocument();
    });

    it('has proper button labels for snoozed reminders', () => {
      render(<ReminderCard reminder={mockSnoozedReminder} {...mockProps} />);
      
      expect(screen.getByRole('button', { name: /Complete/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Unsnooze/ })).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles reminder without description', () => {
      const noDescReminder = { ...mockReminder, description: undefined };
      render(<ReminderCard reminder={noDescReminder} {...mockProps} />);
      
      expect(screen.getByText('Test Reminder')).toBeInTheDocument();
      expect(screen.queryByText('Test description')).not.toBeInTheDocument();
    });

    it('handles reminder without tags', () => {
      const noTagsReminder = { ...mockReminder, tags: undefined };
      render(<ReminderCard reminder={noTagsReminder} {...mockProps} />);
      
      expect(screen.getByText('Test Reminder')).toBeInTheDocument();
      expect(screen.queryByText('work')).not.toBeInTheDocument();
    });

    it('handles reminder without snooze count', () => {
      const noSnoozeCountReminder = { ...mockSnoozedReminder, snooze_count: undefined };
      render(<ReminderCard reminder={noSnoozeCountReminder} {...mockProps} />);
      
      expect(screen.queryByText(/Snoozed \dx/)).not.toBeInTheDocument();
    });

    it('handles missing callback functions gracefully', () => {
      const minimalProps = { currentUserId: 1 };
      
      expect(() => {
        render(<ReminderCard reminder={mockReminder} {...minimalProps} />);
      }).not.toThrow();
    });
  });

  describe('Custom Styling', () => {
    it('applies custom className when provided', () => {
      const { container } = render(
        <ReminderCard reminder={mockReminder} {...mockProps} className="custom-class" />
      );
      
      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('maintains default classes with custom className', () => {
      const { container } = render(
        <ReminderCard reminder={mockReminder} {...mockProps} className="custom-class" />
      );
      
      expect(container.firstChild).toHaveClass('transition-all', 'duration-200', 'hover:shadow-md', 'custom-class');
    });
  });
});