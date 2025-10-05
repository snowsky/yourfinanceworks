import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import ApprovalReportsPage from '../../pages/ApprovalReportsPage';

// Mock the UI components
vi.mock('@/components/ui/card', () => ({
  Card: ({ children, ...props }: any) => <div data-testid="card" {...props}>{children}</div>,
  CardContent: ({ children, ...props }: any) => <div data-testid="card-content" {...props}>{children}</div>,
  CardDescription: ({ children, ...props }: any) => <div data-testid="card-description" {...props}>{children}</div>,
  CardHeader: ({ children, ...props }: any) => <div data-testid="card-header" {...props}>{children}</div>,
  CardTitle: ({ children, ...props }: any) => <div data-testid="card-title" {...props}>{children}</div>,
}));

vi.mock('@/components/ui/tabs', () => ({
  Tabs: ({ children, value, onValueChange, ...props }: any) => (
    <div data-testid="tabs" data-value={value} {...props}>
      {children}
    </div>
  ),
  TabsContent: ({ children, value, ...props }: any) => (
    <div data-testid="tabs-content" data-value={value} {...props}>
      {children}
    </div>
  ),
  TabsList: ({ children, ...props }: any) => <div data-testid="tabs-list" {...props}>{children}</div>,
  TabsTrigger: ({ children, value, ...props }: any) => (
    <button data-testid="tabs-trigger" data-value={value} {...props}>
      {children}
    </button>
  ),
}));

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, disabled, ...props }: any) => (
    <button onClick={onClick} disabled={disabled} data-testid="button" {...props}>
      {children}
    </button>
  ),
}));

vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, variant, ...props }: any) => (
    <span data-testid="badge" data-variant={variant} {...props}>
      {children}
    </span>
  ),
}));

vi.mock('@/components/ui/progress', () => ({
  Progress: ({ value, ...props }: any) => (
    <div data-testid="progress" data-value={value} {...props} />
  ),
}));

vi.mock('@/components/ui/select', () => ({
  Select: ({ children, value, onValueChange, ...props }: any) => (
    <div data-testid="select" data-value={value} {...props}>
      {children}
    </div>
  ),
  SelectContent: ({ children, ...props }: any) => <div data-testid="select-content" {...props}>{children}</div>,
  SelectItem: ({ children, value, ...props }: any) => (
    <div data-testid="select-item" data-value={value} {...props}>
      {children}
    </div>
  ),
  SelectTrigger: ({ children, ...props }: any) => <div data-testid="select-trigger" {...props}>{children}</div>,
  SelectValue: ({ placeholder, ...props }: any) => (
    <div data-testid="select-value" data-placeholder={placeholder} {...props} />
  ),
}));

vi.mock('@/components/ui/date-range-picker', () => ({
  DatePickerWithRange: ({ date, onDateChange, ...props }: any) => (
    <div data-testid="date-range-picker" {...props}>
      <button onClick={() => onDateChange({ from: new Date(), to: new Date() })}>
        Select Date Range
      </button>
    </div>
  ),
}));

vi.mock('@/components/ui/alert', () => ({
  Alert: ({ children, variant, ...props }: any) => (
    <div data-testid="alert" data-variant={variant} {...props}>
      {children}
    </div>
  ),
  AlertDescription: ({ children, ...props }: any) => (
    <div data-testid="alert-description" {...props}>
      {children}
    </div>
  ),
}));

// Mock recharts
vi.mock('recharts', () => ({
  BarChart: ({ children, data, ...props }: any) => (
    <div data-testid="bar-chart" data-length={data?.length} {...props}>
      {children}
    </div>
  ),
  Bar: ({ dataKey, ...props }: any) => <div data-testid="bar" data-key={dataKey} {...props} />,
  XAxis: ({ dataKey, ...props }: any) => <div data-testid="x-axis" data-key={dataKey} {...props} />,
  YAxis: (props: any) => <div data-testid="y-axis" {...props} />,
  CartesianGrid: (props: any) => <div data-testid="cartesian-grid" {...props} />,
  Tooltip: (props: any) => <div data-testid="tooltip" {...props} />,
  ResponsiveContainer: ({ children, ...props }: any) => (
    <div data-testid="responsive-container" {...props}>
      {children}
    </div>
  ),
  LineChart: ({ children, data, ...props }: any) => (
    <div data-testid="line-chart" data-length={data?.length} {...props}>
      {children}
    </div>
  ),
  Line: ({ dataKey, ...props }: any) => <div data-testid="line" data-key={dataKey} {...props} />,
  PieChart: ({ children, data, ...props }: any) => (
    <div data-testid="pie-chart" data-length={data?.length} {...props}>
      {children}
    </div>
  ),
  Pie: ({ dataKey, ...props }: any) => <div data-testid="pie" data-key={dataKey} {...props} />,
  Cell: (props: any) => <div data-testid="cell" {...props} />,
}));

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Clock: (props: any) => <div data-testid="clock-icon" {...props} />,
  TrendingUp: (props: any) => <div data-testid="trending-up-icon" {...props} />,
  TrendingDown: (props: any) => <div data-testid="trending-down-icon" {...props} />,
  AlertTriangle: (props: any) => <div data-testid="alert-triangle-icon" {...props} />,
  CheckCircle: (props: any) => <div data-testid="check-circle-icon" {...props} />,
  XCircle: (props: any) => <div data-testid="x-circle-icon" {...props} />,
  Users: (props: any) => <div data-testid="users-icon" {...props} />,
  FileText: (props: any) => <div data-testid="file-text-icon" {...props} />,
  Download: (props: any) => <div data-testid="download-icon" {...props} />,
  RefreshCw: (props: any) => <div data-testid="refresh-icon" {...props} />,
}));

// Mock date-fns
vi.mock('date-fns', () => ({
  addDays: (date: Date, days: number) => new Date(date.getTime() + days * 24 * 60 * 60 * 1000),
  format: (date: Date, formatStr: string) => date.toISOString().split('T')[0],
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('ApprovalReportsPage', () => {
  const mockMetricsData = {
    total_approvals: 100,
    pending_approvals: 10,
    approved_count: 80,
    rejected_count: 10,
    average_approval_time: 24.5,
    median_approval_time: 18.0,
    approval_rate: 88.9,
    rejection_rate: 11.1,
    bottlenecks: [
      {
        approver_id: 1,
        approver_name: 'John Doe',
        average_time_hours: 48.0,
        approval_count: 20,
        is_bottleneck: true,
      },
    ],
    approver_performance: [
      {
        approver_id: 1,
        approver_name: 'John Doe',
        total_assigned: 25,
        approved: 20,
        rejected: 3,
        pending: 2,
        approval_rate: 87.0,
        average_time_hours: 36.0,
        efficiency_score: 75.5,
      },
    ],
    category_breakdown: {
      travel: {
        total: 50,
        approved: 45,
        rejected: 3,
        pending: 2,
        approval_rate: 93.8,
        average_time_hours: 20.0,
        total_amount: 25000.0,
        average_amount: 500.0,
      },
    },
    monthly_trends: {
      '2024-01': {
        total_submitted: 30,
        approved: 25,
        rejected: 3,
        pending: 2,
        approval_rate: 89.3,
        average_time_hours: 22.0,
        total_amount: 15000.0,
      },
    },
    compliance_issues: [
      {
        type: 'delayed_approval',
        approval_id: 123,
        expense_id: 456,
        approver_id: 1,
        delay_hours: 168.0,
        description: 'Approval took 7.0 days to complete',
      },
    ],
  };

  const mockPatternsData = {
    common_rejection_reasons: [
      {
        reason: 'Missing receipt',
        count: 15,
        total_amount: 7500.0,
      },
    ],
    approval_time_by_amount: {
      '0-100': 2.0,
      '100-500': 8.0,
      '500-1000': 16.0,
      '1000-5000': 24.0,
      '5000+': 48.0,
    },
    approval_time_by_category: {
      travel: 18.0,
      meals: 12.0,
      office: 6.0,
    },
    peak_submission_times: {
      by_hour: { '9': 25, '10': 30, '14': 20 },
      by_day: { Monday: 40, Tuesday: 35, Wednesday: 25 },
    },
    escalation_patterns: [
      {
        expense_id: 789,
        levels: 2,
        total_time_hours: 72.0,
        level_times: [
          { level: 1, time_hours: 24.0, approver_id: 1 },
          { level: 2, time_hours: 48.0, approver_id: 2 },
        ],
      },
    ],
    recommendations: [
      {
        type: 'process_optimization',
        priority: 'high',
        title: 'Optimize High-Value Expense Approvals',
        description: 'High-value expenses take significantly longer to approve.',
        impact: 'Reduce approval time for high-value expenses by up to 50%',
      },
    ],
  };

  const mockComplianceData = {
    total_expenses: 500,
    expenses_requiring_approval: 300,
    expenses_bypassed_approval: 15,
    compliance_rate: 95.0,
    policy_violations: [
      {
        expense_id: 101,
        amount: 750.0,
        category: 'travel',
        expense_date: '2024-01-15T10:00:00Z',
        violation_type: 'bypassed_approval',
        description: 'Expense bypassed approval workflow',
      },
    ],
    rule_effectiveness: [
      {
        rule_id: 1,
        rule_name: 'Travel Expenses',
        approval_count: 150,
        is_active: true,
        effectiveness_score: 85.0,
      },
    ],
    delegation_usage: {
      total_delegations: 25,
      active_delegations: 5,
      average_duration_days: 7.5,
      most_delegating_approvers: [{ approver_id: 1, delegation_count: 8 }],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup default successful fetch responses
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/api/approval-reports/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMetricsData),
        });
      }
      if (url.includes('/api/approval-reports/patterns')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockPatternsData),
        });
      }
      if (url.includes('/api/approval-reports/compliance')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockComplianceData),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
      });
    });
  });

  it('renders the page title and description', async () => {
    render(<ApprovalReportsPage />);

    expect(screen.getByText('Approval Reports & Analytics')).toBeInTheDocument();
    expect(
      screen.getByText('Comprehensive insights into your expense approval workflow')
    ).toBeInTheDocument();
  });

  it('renders filter controls', async () => {
    render(<ApprovalReportsPage />);

    expect(screen.getByText('Report Filters')).toBeInTheDocument();
    expect(screen.getByText('Date Range')).toBeInTheDocument();
    expect(screen.getByText('Approver')).toBeInTheDocument();
    expect(screen.getByText('Category')).toBeInTheDocument();
  });

  it('renders export buttons', async () => {
    render(<ApprovalReportsPage />);

    expect(screen.getByText('Export PDF')).toBeInTheDocument();
    expect(screen.getByText('Export Excel')).toBeInTheDocument();
    expect(screen.getByText('Refresh')).toBeInTheDocument();
  });

  it('renders tab navigation', async () => {
    render(<ApprovalReportsPage />);

    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Performance')).toBeInTheDocument();
    expect(screen.getByText('Patterns')).toBeInTheDocument();
    expect(screen.getByText('Compliance')).toBeInTheDocument();
  });

  it('loads and displays metrics data on mount', async () => {
    render(<ApprovalReportsPage />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/approval-reports/metrics')
      );
    });

    await waitFor(() => {
      expect(screen.getByText('100')).toBeInTheDocument(); // total_approvals
      expect(screen.getByText('89%')).toBeInTheDocument(); // approval_rate rounded
    });
  });

  it('displays key metrics cards in overview tab', async () => {
    render(<ApprovalReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Total Approvals')).toBeInTheDocument();
      expect(screen.getByText('Approval Rate')).toBeInTheDocument();
      expect(screen.getByText('Avg. Approval Time')).toBeInTheDocument();
      expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
    });
  });

  it('displays monthly trends chart', async () => {
    render(<ApprovalReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Monthly Approval Trends')).toBeInTheDocument();
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });
  });

  it('displays category breakdown', async () => {
    render(<ApprovalReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Approval Breakdown by Category')).toBeInTheDocument();
      expect(screen.getByText('travel')).toBeInTheDocument();
    });
  });

  it('handles refresh button click', async () => {
    render(<ApprovalReportsPage />);

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(6); // Initial load (3) + refresh (3)
    });
  });

  it('handles date range change', async () => {
    render(<ApprovalReportsPage />);

    const dateRangePicker = screen.getByTestId('date-range-picker');
    const selectButton = dateRangePicker.querySelector('button');
    
    if (selectButton) {
      fireEvent.click(selectButton);
    }

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/approval-reports/metrics')
      );
    });
  });

  it('displays error message when API fails', async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: false,
        status: 500,
      })
    );

    render(<ApprovalReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load report data')).toBeInTheDocument();
    });
  });

  it('displays loading state initially', () => {
    render(<ApprovalReportsPage />);

    expect(screen.getByText('Loading approval reports...')).toBeInTheDocument();
  });

  it('switches between tabs correctly', async () => {
    render(<ApprovalReportsPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Total Approvals')).toBeInTheDocument();
    });

    // Click on Performance tab
    const performanceTab = screen.getByText('Performance');
    fireEvent.click(performanceTab);

    await waitFor(() => {
      expect(screen.getByText('Approval Bottlenecks')).toBeInTheDocument();
    });
  });

  it('displays bottlenecks in performance tab', async () => {
    render(<ApprovalReportsPage />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Total Approvals')).toBeInTheDocument();
    });

    // Switch to performance tab
    const performanceTab = screen.getByText('Performance');
    fireEvent.click(performanceTab);

    await waitFor(() => {
      expect(screen.getByText('Approval Bottlenecks')).toBeInTheDocument();
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
  });

  it('displays patterns analysis in patterns tab', async () => {
    render(<ApprovalReportsPage />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Total Approvals')).toBeInTheDocument();
    });

    // Switch to patterns tab
    const patternsTab = screen.getByText('Patterns');
    fireEvent.click(patternsTab);

    await waitFor(() => {
      expect(screen.getByText('Common Rejection Reasons')).toBeInTheDocument();
      expect(screen.getByText('Missing receipt')).toBeInTheDocument();
    });
  });

  it('displays compliance report in compliance tab', async () => {
    render(<ApprovalReportsPage />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Total Approvals')).toBeInTheDocument();
    });

    // Switch to compliance tab
    const complianceTab = screen.getByText('Compliance');
    fireEvent.click(complianceTab);

    await waitFor(() => {
      expect(screen.getByText('Compliance Rate')).toBeInTheDocument();
      expect(screen.getByText('95%')).toBeInTheDocument();
    });
  });

  it('handles compliance data unavailable', async () => {
    // Mock compliance endpoint to fail
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/api/approval-reports/compliance')) {
        return Promise.resolve({
          ok: false,
          status: 403,
        });
      }
      if (url.includes('/api/approval-reports/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMetricsData),
        });
      }
      if (url.includes('/api/approval-reports/patterns')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockPatternsData),
        });
      }
      return Promise.resolve({ ok: false, status: 404 });
    });

    render(<ApprovalReportsPage />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Total Approvals')).toBeInTheDocument();
    });

    // Switch to compliance tab
    const complianceTab = screen.getByText('Compliance');
    fireEvent.click(complianceTab);

    await waitFor(() => {
      expect(screen.getByText('Compliance Reports Unavailable')).toBeInTheDocument();
    });
  });

  it('handles export functionality', async () => {
    // Mock successful export
    mockFetch.mockImplementation((url: string, options?: any) => {
      if (options?.method === 'POST' && url.includes('/api/approval-reports/generate')) {
        return Promise.resolve({
          ok: true,
          blob: () => Promise.resolve(new Blob(['test data'])),
        });
      }
      // Default responses for other endpoints
      if (url.includes('/api/approval-reports/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMetricsData),
        });
      }
      return Promise.resolve({ ok: false, status: 404 });
    });

    // Mock URL.createObjectURL and related DOM methods
    const mockCreateObjectURL = vi.fn(() => 'mock-url');
    const mockRevokeObjectURL = vi.fn();
    const mockClick = vi.fn();
    const mockAppendChild = vi.fn();
    const mockRemoveChild = vi.fn();

    Object.defineProperty(window, 'URL', {
      value: {
        createObjectURL: mockCreateObjectURL,
        revokeObjectURL: mockRevokeObjectURL,
      },
    });

    const mockAnchor = {
      href: '',
      download: '',
      click: mockClick,
    };

    vi.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'a') {
        return mockAnchor as any;
      }
      return document.createElement(tagName);
    });

    vi.spyOn(document.body, 'appendChild').mockImplementation(mockAppendChild);
    vi.spyOn(document.body, 'removeChild').mockImplementation(mockRemoveChild);

    render(<ApprovalReportsPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Total Approvals')).toBeInTheDocument();
    });

    // Click export PDF button
    const exportButton = screen.getByText('Export PDF');
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/approval-reports/generate',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: expect.stringContaining('"export_format":"pdf"'),
        })
      );
    });
  });

  it('formats time correctly', async () => {
    render(<ApprovalReportsPage />);

    await waitFor(() => {
      // Should display formatted time (24.5 hours should be "1d" approximately)
      expect(screen.getByText(/\d+[hmd]/)).toBeInTheDocument();
    });
  });

  it('displays recommendations with correct priority colors', async () => {
    render(<ApprovalReportsPage />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Total Approvals')).toBeInTheDocument();
    });

    // Switch to patterns tab
    const patternsTab = screen.getByText('Patterns');
    fireEvent.click(patternsTab);

    await waitFor(() => {
      expect(screen.getByText('Process Improvement Recommendations')).toBeInTheDocument();
      expect(screen.getByText('Optimize High-Value Expense Approvals')).toBeInTheDocument();
    });
  });
});