import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useAnalytics } from '@/services/analytics';
import { useMarketing } from '@/services/marketing';

// Unified tracking hook that combines analytics and marketing
export const useTracking = () => {
  const location = useLocation();
  const analytics = useAnalytics();
  const marketing = useMarketing();

  // Track page views automatically
  useEffect(() => {
    analytics.trackPageView(location.pathname);
    marketing.trackViewContent('page', location.pathname);
  }, [location.pathname, analytics, marketing]);

  return {
    // Analytics methods
    trackEvent: analytics.trackEvent,
    trackUserAction: analytics.trackUserAction,
    trackError: analytics.trackError,
    trackTiming: analytics.trackTiming,
    
    // Marketing methods
    trackConversion: marketing.trackConversion,
    trackPurchase: marketing.trackPurchase,
    trackSignup: marketing.trackSignup,
    trackLead: marketing.trackLead,
    trackAddToCart: marketing.trackAddToCart,
    addToRemarketingAudience: marketing.addToRemarketingAudience,
    
    // Status checks
    analyticsEnabled: analytics.isEnabled(),
    marketingEnabled: marketing.isEnabled(),
    
    // Convenience methods
    trackBusinessEvent: (eventName: string, data: Record<string, any> = {}) => {
      analytics.trackEvent(eventName, data);
      marketing.trackConversion(eventName, data);
    },
    
    trackUserEngagement: (action: string, category: string, value?: number) => {
      analytics.trackUserAction(action, category, undefined, value);
      if (marketing.isEnabled()) {
        marketing.addToRemarketingAudience('engaged_users', { action, category });
      }
    }
  };
};

// Hook for tracking specific business events
export const useBusinessTracking = () => {
  const tracking = useTracking();

  return {
    // Invoice-related tracking
    trackInvoiceCreated: (invoiceId: string, amount: number, currency: string) => {
      tracking.trackBusinessEvent('invoice_created', {
        invoice_id: invoiceId,
        value: amount,
        currency: currency
      });
    },

    trackInvoicePaid: (invoiceId: string, amount: number, currency: string) => {
      tracking.trackPurchase(amount, currency, invoiceId);
      tracking.trackBusinessEvent('invoice_paid', {
        invoice_id: invoiceId,
        value: amount,
        currency: currency
      });
    },

    // Client-related tracking
    trackClientAdded: (clientId: string) => {
      tracking.trackSignup('client_registration');
      tracking.trackBusinessEvent('client_added', { client_id: clientId });
    },

    // Expense-related tracking
    trackExpenseAdded: (expenseId: string, amount: number, category: string) => {
      tracking.trackBusinessEvent('expense_added', {
        expense_id: expenseId,
        value: amount,
        category: category
      });
    },

    // User engagement tracking
    trackFeatureUsed: (featureName: string, context?: string) => {
      tracking.trackUserEngagement('feature_used', featureName);
      tracking.trackEvent('feature_usage', {
        feature_name: featureName,
        context: context
      });
    },

    // Error tracking
    trackError: (error: string, context?: string) => {
      tracking.trackError(error, context);
    },

    // Performance tracking
    trackPerformance: (metric: string, value: number) => {
      tracking.trackTiming(metric, value, 'Performance');
    }
  };
};