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
    name: 'Finance Command Center',
    steps: [
      {
        id: 'welcome',
        title: 'Welcome to Your Finance Platform',
        content: 'Let\'s take a brief tour of your new financial command center, designed to give you total clarity and control over your business growth.',
        target: '[data-tour="dashboard-welcome"]',
        placement: 'bottom'
      },
      {
        id: 'header',
        title: 'Personalized Overview',
        content: 'Your dashboard provides a high-level summary of your financial status and quick access to essential management tools.',
        target: '[data-tour="dashboard-header"]',
        placement: 'bottom'
      },
      {
        id: 'stats',
        title: 'Critical Metrics',
        content: 'Monitor your vital signs—total revenue, pending receivables, active client base, and overdue accounts—all in real-time.',
        target: '[data-tour="dashboard-stats"]',
        placement: 'bottom'
      },
      {
        id: 'chart',
        title: 'Performance Analytics',
        content: 'Visualize your revenue trends and business trajectory with high-fidelity charts, helping you make data-driven decisions.',
        target: '[data-tour="dashboard-revenue-chart"]',
        placement: 'top'
      },
      {
        id: 'recent',
        title: 'Real-time Activity',
        content: 'Stay informed with a live feed of your latest transactions, invoices, and financial events.',
        target: '[data-tour="dashboard-recent"]',
        placement: 'top'
      },
      {
        id: 'quick-actions',
        title: 'Efficiency Hub',
        content: 'Execute frequent tasks with precision—create invoices, log expenses, and record payments directly from here.',
        target: '[data-tour="dashboard-quick-actions"]',
        placement: 'top'
      },
      {
        id: 'payment-trends',
        title: 'Liquidity Insights',
        content: 'Analyze your cash flow health with deep-dive metrics on payment cycles and collection efficiency.',
        target: '[data-tour="dashboard-payment-trends"]',
        placement: 'top'
      },
      {
        id: 'business-health',
        title: 'Strategic Growth',
        content: 'Get a comprehensive view of your business health, including growth rates and client retention metrics.',
        target: '[data-tour="dashboard-business-health"]',
        placement: 'top'
      }
    ]
  },
  {
    id: 'navigation',
    name: 'Integrated Navigation',
    steps: [
      {
        id: 'sidebar',
        title: 'Unified Sidebar',
        content: `Access your entire suite of financial management tools from this centralized navigation hub.`,
        target: '[data-tour="sidebar"]',
        placement: 'right'
      },
      {
        id: 'dashboard',
        title: 'Insights Dashboard',
        content: 'Your primary workspace for financial intelligence and real-time performance monitoring.',
        target: '[data-tour="nav-dashboard"]',
        placement: 'right'
      },
      {
        id: 'clients',
        title: 'Client Capital',
        content: 'Manage your client ecosystem, track historical interactions, and optimize relationships.',
        target: '[data-tour="nav-clients"]',
        placement: 'right'
      },
      {
        id: 'invoices',
        title: 'Revenue Management',
        content: 'Generate professional invoices and manage your accounts receivable with ease.',
        target: '[data-tour="nav-invoices"]',
        placement: 'right'
      },
      {
        id: 'payments',
        title: 'Cash Flow Control',
        content: 'Track inbound payments, reconcile balances, and maintain a healthy cash position.',
        target: '[data-tour="nav-payments"]',
        placement: 'right'
      },
      {
        id: 'expenses',
        title: 'Outbound Optimization',
        content: 'Log business expenses and categorize costs to maximize tax efficiency and budget control.',
        target: '[data-tour="nav-expenses"]',
        placement: 'right'
      },
      {
        id: 'approvals',
        title: 'Governance & Compliance',
        content: 'Streamline your internal controls with automated expense approval workflows.',
        target: '[data-tour="nav-approvals"]',
        placement: 'right'
      },
      {
        id: 'inventory',
        title: 'Asset Management',
        content: 'Maintain precise inventory levels and track your physical assets across the enterprise.',
        target: '[data-tour="nav-inventory"]',
        placement: 'right'
      },
      {
        id: 'bank-statements',
        title: 'Bank Reconciliation',
        content: 'Seamlessly import and reconcile bank statements to ensure accounting accuracy.',
        target: '[data-tour="nav-statements"]',
        placement: 'right'
      },
      {
        id: 'reminders',
        title: 'Automated Outreach',
        content: 'Let the system handle payment reminders, ensuring you get paid faster without the manual effort.',
        target: '[data-tour="nav-reminders"]',
        placement: 'right'
      },
      {
        id: 'reports',
        title: 'Business Intelligence',
        content: 'Generate comprehensive financial reports and export data for accounting or auditing.',
        target: '[data-tour="nav-reports"]',
        placement: 'right'
      },
      {
        id: 'settings',
        title: 'Global Configuration',
        content: 'Customize the platform to fit your specific business requirements and branding.',
        target: '[data-tour="nav-settings"]',
        placement: 'right'
      },
      {
        id: 'users',
        title: 'Team Collaboration',
        content: 'Manage organizational access, roles, and permissions for your entire team.',
        target: '[data-tour="nav-users"]',
        placement: 'right'
      },
      {
        id: 'audit-log',
        title: 'System Transparency',
        content: 'Review a secure audit trail of all system activities for full accountability.',
        target: '[data-tour="nav-audit-log"]',
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

  const handleStepNavigation = (targetElement: HTMLElement) => {
    // If the target is a navigation link, click it to navigate to the page
    const link = targetElement.closest('a');
    if (link && link.href) {
      const href = link.getAttribute('href');
      if (href && !href.startsWith('http')) {
        // It's a relative link, navigate using React Router
        navigate(href);
      }
    }
  };

  const nextStep = () => {
    const tour = TOURS.find(t => t.id === currentTour);
    if (tour) {
      let nextStepIndex = currentStep + 1;

      // Skip steps where the target element doesn't exist (for role-based menu items)
      while (nextStepIndex < tour.steps.length) {
        const targetElement = document.querySelector(tour.steps[nextStepIndex].target) as HTMLElement;
        if (targetElement) {
          setCurrentStep(nextStepIndex);
          handleStepNavigation(targetElement);
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
        const targetElement = document.querySelector(tour.steps[prevStepIndex].target) as HTMLElement;
        if (targetElement) {
          setCurrentStep(prevStepIndex);
          handleStepNavigation(targetElement);
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