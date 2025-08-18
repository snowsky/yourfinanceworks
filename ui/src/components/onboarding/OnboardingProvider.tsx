import React, { createContext, useContext, useState, useEffect } from 'react';

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
  markAsCompleted: (tourId: string) => void;
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
        id: 'stats',
        title: 'Financial Overview',
        content: 'These cards show your key financial metrics - total income, pending amounts, client count, and overdue invoices.',
        target: '[data-tour="dashboard-stats"]',
        placement: 'bottom'
      },
      {
        id: 'chart',
        title: 'Invoice Analytics',
        content: 'This chart visualizes your invoice trends over time to help you track your business performance.',
        target: '[data-tour="dashboard-chart"]',
        placement: 'top'
      },
      {
        id: 'recent',
        title: 'Recent Activity',
        content: 'Keep track of your latest invoices and their status at a glance.',
        target: '[data-tour="dashboard-recent"]',
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
        content: 'Use this sidebar to navigate between different sections of your invoice management system.',
        target: '[data-tour="sidebar"]',
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
        id: 'bank-statements',
        title: 'Bank Statement Management',
        content: 'Import and manage bank statements to reconcile transactions and maintain accurate financial records.',
        target: '[data-tour="nav-bank-statements"]',
        placement: 'right'
      },
      {
        id: 'settings',
        title: 'Settings & Configuration',
        content: 'Customize your experience, set up email delivery, and configure your business details.',
        target: '[data-tour="nav-settings"]',
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

  useEffect(() => {
    const completed = localStorage.getItem('onboarding-completed');
    const firstTime = localStorage.getItem('first-time-user');
    
    if (completed) {
      setCompletedTours(JSON.parse(completed));
    }
    
    if (!firstTime) {
      setIsFirstTime(true);
      localStorage.setItem('first-time-user', 'false');
    }
  }, []);

  const startTour = (tourId: string) => {
    setCurrentTour(tourId);
    setCurrentStep(0);
    setIsActive(true);
  };

  const nextStep = () => {
    const tour = TOURS.find(t => t.id === currentTour);
    if (tour && currentStep < tour.steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      endTour();
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
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
  };

  const markAsCompleted = (tourId: string) => {
    const updated = [...completedTours, tourId];
    setCompletedTours(updated);
    localStorage.setItem('onboarding-completed', JSON.stringify(updated));
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
        markAsCompleted
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