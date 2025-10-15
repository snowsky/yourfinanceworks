import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { QuickActions } from '../QuickActions';

// Mock the API
vi.mock('@/lib/api', () => ({
  approvalApi: {
    getPendingApprovals: vi.fn().mockResolvedValue({
      approvals: [
        {
          id: 1,
          expense_id: 123,
          expense: { amount: 100 }
        }
      ],
      total: 1
    })
  }
}));

// Mock auth utilities
vi.mock('@/utils/auth', () => ({
  canPerformActions: vi.fn().mockReturnValue(true),
  getCurrentUser: vi.fn().mockReturnValue({
    id: 1,
    email: 'test@example.com',
    role: 'admin'
  })
}));

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate
  };
});

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue?: string) => defaultValue || key
  })
}));

// Mock sonner
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn()
  }
}));

const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {component}
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe('QuickActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders quick actions title and subtitle', async () => {
    renderWithProviders(<QuickActions />);
    
    await waitFor(() => {
      expect(screen.getByText('Quick Actions')).toBeInTheDocument();
      expect(screen.getByText('Common tasks and shortcuts')).toBeInTheDocument();
    });
  });

  it('renders primary action buttons', async () => {
    renderWithProviders(<QuickActions />);
    
    await waitFor(() => {
      expect(screen.getByText('New Expense')).toBeInTheDocument();
      expect(screen.getByText('Create Invoice')).toBeInTheDocument();
      expect(screen.getByText('Import Expenses')).toBeInTheDocument();
      expect(screen.getByText('Add Client')).toBeInTheDocument();
    });
  });

  it('renders secondary action buttons', async () => {
    renderWithProviders(<QuickActions />);
    
    await waitFor(() => {
      expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
      expect(screen.getByText('Inventory')).toBeInTheDocument();
      expect(screen.getByText('Generate Reports')).toBeInTheDocument();
      expect(screen.getByText('Reminders')).toBeInTheDocument();
    });
  });

  it('shows pending approvals badge when there are pending items', async () => {
    renderWithProviders(<QuickActions />);
    
    await waitFor(() => {
      // Should show badge with count of 1 (from mocked API response)
      expect(screen.getByText('1')).toBeInTheDocument();
    });
  });

  it('displays pending items section when there are pending approvals', async () => {
    renderWithProviders(<QuickActions />);
    
    await waitFor(() => {
      expect(screen.getByText('Needs Attention')).toBeInTheDocument();
      expect(screen.getByText('Expense #123')).toBeInTheDocument();
      expect(screen.getByText('$100')).toBeInTheDocument();
    });
  });

  it('handles action clicks correctly', async () => {
    renderWithProviders(<QuickActions />);
    
    await waitFor(() => {
      const newExpenseButton = screen.getByText('New Expense');
      fireEvent.click(newExpenseButton);
      expect(mockNavigate).toHaveBeenCalledWith('/expenses/new');
    });
  });

  it('shows loading state initially', () => {
    renderWithProviders(<QuickActions />);
    
    // Should show loading skeleton initially
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });
});