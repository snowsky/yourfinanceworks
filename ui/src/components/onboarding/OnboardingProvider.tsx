import React, { createContext, useContext, useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { APP_NAME } from '../../constants/app';

interface OnboardingStep {
  id: string;
  title: string;
  content: string;
  target: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
  action?: () => void;
}

interface OnboardingTour {
  id: string;
  name: string;
  steps: OnboardingStep[];
}

interface OnboardingContextType {
  isActive: boolean;
  currentTour: string | null;
  currentStep: number;
  tours: OnboardingTour[];
  startTour: (tourId: string) => void;
  nextStep: () => void;
  prevStep: () => void;
  skipTour: () => void;
  endTour: () => void;
  isFirstTime: boolean;
  showWelcome: boolean;
  setShowWelcome: (show: boolean) => void;
  markAsCompleted: (tourId: string) => void;
  getLastVisibleStep: () => number;
}

const OnboardingContext = createContext<OnboardingContextType | undefined>(undefined);

const TOURS: OnboardingTour[] = [
  {
    id: 'dashboard',
    name: 'Dashboard Overview',
    steps: [
      {
        id: 'welcome',
        title: 'Welcome to Invoice Manager!',
        content: 'Let\'s take a quick tour to get you started with managing your invoices and clients.',
        target: '[data-tour="dashboard-welcome"]',
        placement: 'bottom'
      },
      {
        id: 'header',
        title: 'Dashboard Header',
        content: 'This header shows your personalized welcome message and quick access to important actions.',
        target: '[data-tour="dashboard-header"]',
        placement: 'bottom'
      },
      {
        id: 'stats',
        title: 'Financial Overview',
        content: 'These cards show your key financial metrics - total income, pending amounts, client count, and overdue invoices.',
        target: '[data-tour="dashboard-stats"]',
        placement: 'bottom'
      },
      {
        id: 'chart',
        title: 'Revenue Trends',
        content: 'This chart visualizes your invoice trends over time to help you track your business performance.',
        target: '[data-tour="dashboard-revenue-chart"]',
        placement: 'top'
      },
      {
        id: 'recent',
        title: 'Recent Activity',
        content: 'Keep track of your latest invoices and their status at a glance.',
        target: '[data-tour="dashboard-recent"]',
        placement: 'top'
      },
      {
        id: 'quick-actions',
        title: 'Quick Actions',
        content: 'Access common tasks quickly from this section - create invoices, add clients, record payments, and more.',
        target: '[data-tour="dashboard-quick-actions"]',
        placement: 'top'
      },
      {
        id: 'payment-trends',
        title: 'Payment Trends',
        content: 'Monitor your payment performance with metrics like on-time payment rate, average payment time, and overdue rate.',
        target: '[data-tour="dashboard-payment-trends"]',
        placement: 'top'
      },
      {
        id: 'business-health',
        title: 'Business Health',
        content: 'Get a comprehensive view of your business metrics including monthly growth, active clients, and revenue trends.',
        target: '[data-tour="dashboard-business-health"]',
        placement: 'top'
      }
    ]
  },
  {
    id: 'navigation',
    name: 'Navigation Tour',
    steps: [
      {
        id: 'sidebar',
        title: 'Main Navigation',
        content: `Use this sidebar to navigate between different sections of your ${APP_NAME.toLowerCase()}.`,
        target: '[data-tour="sidebar"]',
        placement: 'right'
      },
      {
        id: 'dashboard',
        title: 'Dashboard',
        content: 'Your dashboard shows key financial metrics, recent activity, and business insights at a glance.',
        target: '[data-tour="nav-dashboard"]',
        placement: 'right'
      },
      {
        id: 'clients',
        title: 'Client Management',
        content: 'Manage your client information, contact details, and view their invoice history.',
        target: '[data-tour="nav-clients"]',
        placement: 'right'
      },
      {
        id: 'invoices',
        title: 'Invoices Section',
        content: 'Create, edit, and manage all your invoices here. You can also send them directly to clients.',
        target: '[data-tour="nav-invoices"]',
        placement: 'right'
      },
      {
        id: 'payments',
        title: 'Payment Management',
        content: 'Track and record payments from clients, view payment history, and manage outstanding balances.',
        target: '[data-tour="nav-payments"]',
        placement: 'right'
      },
      {
        id: 'expenses',
        title: 'Expense Tracking',
        content: 'Record business expenses, categorize costs, and link expenses to invoices for better financial tracking.',
        target: '[data-tour="nav-expenses"]',
        placement: 'right'
      },
      {
        id: 'approvals',
        title: 'Approval Workflows',
        content: 'Set up and manage expense approval processes to ensure proper authorization before processing expenses.',
        target: '[data-tour="nav-approvals"]',
        placement: 'right'
      },
      {
        id: 'inventory',
        title: 'Inventory Management',
        content: 'Track and manage your inventory items, stock levels, and inventory transactions.',
        target: '[data-tour="nav-inventory"]',
        placement: 'right'
      },
      {
        id: 'bank-statements',
        title: 'Statement Management',
        content: 'Import and manage bank statements to reconcile transactions and maintain accurate financial records.',
        target: '[data-tour="nav-statements"]',
        placement: 'right'
      },
      {
        id: 'reminders',
        title: 'Automated Reminders',
        content: 'Configure automated payment reminders and notifications for overdue invoices.',
        target: '[data-tour="nav-reminders"]',
        placement: 'right'
      },
      {
        id: 'reports',
        title: 'Reports & Analytics',
        content: 'Generate detailed reports and analytics to gain insights into your business performance.',
        target: '[data-tour="nav-reports"]',
        placement: 'right'
      },
      {
        id: 'settings',
        title: 'Settings & Configuration',
        content: 'Customize your experience, set up email delivery, and configure your business details.',
        target: '[data-tour="nav-settings"]',
        placement: 'right'
      },
      {
        id: 'users',
        title: 'User Management',
        content: 'Manage team members, assign roles, and control access permissions for your organization.',
        target: '[data-tour="nav-users"]',
        placement: 'right'
      },
      {
        id: 'audit-log',
        title: 'Audit Log',
        content: 'View a complete history of all system activities and changes for compliance and security.',
        target: '[data-tour="nav-audit-log"]',
        placement: 'right'
      },
      {
        id: 'analytics',
        title: 'Advanced Analytics',
        content: 'Access detailed analytics and reporting tools for deeper business insights.',
        target: '[data-tour="nav-analytics"]',
        placement: 'right'
      },
      {
        id: 'super-admin',
        title: 'Super Admin Panel',
        content: 'Access system-wide administration tools and settings.',
        target: '[data-tour="nav-super-admin"]',
        placement: 'right'
      }
    ]
  }
];

export function OnboardingProvider({ children }: { children: React.ReactNode }) {
  const [isActive, setIsActive] = useState(false);
  const [currentTour, setCurrentTour] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [completedTours, setCompletedTours] = useState<string[]>([]);
  const [isFirstTime, setIsFirstTime] = useState(false);
  const [showWelcome, setShowWelcome] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const completed = localStorage.getItem('onboarding-completed');
    const firstTime = localStorage.getItem('first-time-user');
    
    if (completed) {
      setCompletedTours(JSON.parse(completed));
    }
    
    if (!firstTime) {
      setIsFirstTime(true);
      setShowWelcome(true);
      localStorage.setItem('first-time-user', 'false');
    }
  }, []);

  const startTour = (tourId: string) => {
    // Check if we're on the dashboard page (either / or /dashboard)
    const isDashboardPage = location.pathname === '/' || location.pathname === '/dashboard';
    
    if (!isDashboardPage) {
      // If we're not on the dashboard, redirect to dashboard with tour parameter
      navigate(`/?tour=${tourId}`);
      return;
    }

    setCurrentTour(tourId);

    // Find the first available step (skip steps where target doesn't exist)
    const tour = TOURS.find(t => t.id === tourId);
    if (tour) {
      let firstAvailableStep = 0;
      while (firstAvailableStep < tour.steps.length) {
        const targetElement = document.querySelector(tour.steps[firstAvailableStep].target);
        if (targetElement) {
          break;
        }
        firstAvailableStep++;
      }
      setCurrentStep(firstAvailableStep);
    } else {
      setCurrentStep(0);
    }

    setIsActive(true);
  };

  const nextStep = () => {
    const tour = TOURS.find(t => t.id === currentTour);
    if (tour) {
      let nextStepIndex = currentStep + 1;

      // Skip steps where the target element doesn't exist (for role-based menu items)
      while (nextStepIndex < tour.steps.length) {
        const targetElement = document.querySelector(tour.steps[nextStepIndex].target);
        if (targetElement) {
          setCurrentStep(nextStepIndex);

          // If the target is a navigation link, click it to navigate to the page
          const link = targetElement.closest('a');
          if (link && link.href) {
            const href = link.getAttribute('href');
            if (href && !href.startsWith('http')) {
              // It's a relative link, navigate using React Router
              navigate(href);
            }
          }

          return;
        }
        nextStepIndex++;
      }

      // If we've gone through all remaining steps, end the tour
      endTour();
    }
  };

  const prevStep = () => {
    const tour = TOURS.find(t => t.id === currentTour);
    if (tour && currentStep > 0) {
      let prevStepIndex = currentStep - 1;

      // Skip steps where the target element doesn't exist (for role-based menu items)
      while (prevStepIndex >= 0) {
        const targetElement = document.querySelector(tour.steps[prevStepIndex].target);
        if (targetElement) {
          setCurrentStep(prevStepIndex);
          return;
        }
        prevStepIndex--;
      }
    }
  };

  const skipTour = () => {
    endTour();
  };

  const endTour = () => {
    if (currentTour) {
      markAsCompleted(currentTour);
    }
    setIsActive(false);
    setCurrentTour(null);
    setCurrentStep(0);
    // Navigate back to dashboard
    navigate('/');
  };

  const markAsCompleted = (tourId: string) => {
    const updated = [...completedTours, tourId];
    setCompletedTours(updated);
    localStorage.setItem('onboarding-completed', JSON.stringify(updated));
  };

  const getLastVisibleStep = () => {
    const tour = TOURS.find(t => t.id === currentTour);
    if (!tour) return 0;

    // Find the last step that has a visible target element
    for (let i = tour.steps.length - 1; i >= 0; i--) {
      const targetElement = document.querySelector(tour.steps[i].target);
      if (targetElement) {
        return i;
      }
    }
    return 0;
  };

  return (
    <OnboardingContext.Provider
      value={{
        isActive,
        currentTour,
        currentStep,
        tours: TOURS,
        startTour,
        nextStep,
        prevStep,
        skipTour,
        endTour,
        isFirstTime,
        showWelcome,
        setShowWelcome,
        markAsCompleted,
        getLastVisibleStep
      }}
    >
      {children}
    </OnboardingContext.Provider>
  );
}

export function useOnboarding() {
  const context = useContext(OnboardingContext);
  if (context === undefined) {
    throw new Error('useOnboarding must be used within an OnboardingProvider');
  }
  return context;
}