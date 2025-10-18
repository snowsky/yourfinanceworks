import { ConsentManager } from '@/components/cookie-consent/services/ConsentManager';

// Analytics service that respects cookie consent
class AnalyticsService {
  private consentManager: ConsentManager;
  private isInitialized = false;
  private pendingEvents: Array<{ event: string; data: any }> = [];

  constructor() {
    this.consentManager = new ConsentManager();
    this.initializeAnalytics();
    this.listenForConsentChanges();
  }

  private initializeAnalytics() {
    // Check if analytics consent is already given
    if (this.consentManager.getCategoryConsent('analytics')) {
      this.loadAnalyticsScripts();
    }
  }

  private listenForConsentChanges() {
    // Listen for consent changes
    window.addEventListener('cookieConsentChange', (event: any) => {
      const { preferences } = event.detail;
      
      if (preferences.analytics && !this.isInitialized) {
        this.loadAnalyticsScripts();
        this.processPendingEvents();
      } else if (!preferences.analytics && this.isInitialized) {
        this.disableAnalytics();
      }
    });
  }

  private loadAnalyticsScripts() {
    if (this.isInitialized) return;

    // Load Google Analytics 4
    this.loadGoogleAnalytics();
    
    // Load other analytics providers
    this.loadCustomAnalytics();
    
    this.isInitialized = true;
    console.log('📊 Analytics initialized with user consent');
  }

  private loadGoogleAnalytics() {
    const GA_MEASUREMENT_ID = import.meta.env.VITE_GA_MEASUREMENT_ID || 'G-XXXXXXXXXX';
    
    // Create and load gtag script
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`;
    document.head.appendChild(script);

    // Initialize gtag
    (window as any).dataLayer = (window as any).dataLayer || [];
    function gtag(...args: any[]) {
      (window as any).dataLayer.push(args);
    }
    (window as any).gtag = gtag;

    gtag('js', new Date());
    gtag('config', GA_MEASUREMENT_ID, {
      // GDPR-compliant settings
      anonymize_ip: true,
      cookie_flags: 'SameSite=None;Secure',
      allow_google_signals: false, // Disable advertising features by default
      allow_ad_personalization_signals: false
    });

    // Set consent mode
    gtag('consent', 'default', {
      analytics_storage: 'granted',
      ad_storage: this.consentManager.getCategoryConsent('marketing') ? 'granted' : 'denied'
    });
  }

  private loadCustomAnalytics() {
    // Example: Load your own analytics or third-party analytics
    // Replace with your actual analytics provider
    
    // Example: Mixpanel
    // this.loadMixpanel();
    
    // Example: Hotjar
    // this.loadHotjar();
    
    // Example: Custom analytics
    this.initializeCustomTracking();
  }

  private initializeCustomTracking() {
    // Your custom analytics implementation
    console.log('🔧 Custom analytics tracking initialized');
    
    // Example: Send page view
    this.trackPageView(window.location.pathname);
  }

  private disableAnalytics() {
    if (!this.isInitialized) return;

    // Disable Google Analytics
    if ((window as any).gtag) {
      (window as any).gtag('consent', 'update', {
        analytics_storage: 'denied'
      });
    }

    // Clear analytics cookies
    this.clearAnalyticsCookies();
    
    this.isInitialized = false;
    console.log('🚫 Analytics disabled - user withdrew consent');
  }

  private clearAnalyticsCookies() {
    // Clear Google Analytics cookies
    const gaCookies = ['_ga', '_ga_', '_gid', '_gat', '_gtag'];
    gaCookies.forEach(cookieName => {
      document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
      document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.${window.location.hostname};`;
    });
  }

  private processPendingEvents() {
    // Process any events that were queued before consent was given
    this.pendingEvents.forEach(({ event, data }) => {
      this.trackEvent(event, data);
    });
    this.pendingEvents = [];
  }

  // Public methods for tracking
  public trackPageView(path: string, title?: string) {
    if (!this.consentManager.getCategoryConsent('analytics')) {
      // Queue the event if no consent yet
      this.pendingEvents.push({ event: 'page_view', data: { path, title } });
      return;
    }

    if (this.isInitialized && (window as any).gtag) {
      (window as any).gtag('config', import.meta.env.VITE_GA_MEASUREMENT_ID, {
        page_path: path,
        page_title: title || document.title
      });
    }

    // Custom analytics tracking
    console.log('📄 Page view tracked:', { path, title });
  }

  public trackEvent(eventName: string, parameters: Record<string, any> = {}) {
    if (!this.consentManager.getCategoryConsent('analytics')) {
      // Queue the event if no consent yet
      this.pendingEvents.push({ event: eventName, data: parameters });
      return;
    }

    if (this.isInitialized && (window as any).gtag) {
      (window as any).gtag('event', eventName, parameters);
    }

    // Custom analytics tracking
    console.log('📊 Event tracked:', eventName, parameters);
  }

  public trackUserAction(action: string, category: string, label?: string, value?: number) {
    this.trackEvent('user_action', {
      event_category: category,
      event_label: label,
      value: value,
      action: action
    });
  }

  public trackError(error: string, context?: string) {
    this.trackEvent('error', {
      error_message: error,
      error_context: context,
      page_path: window.location.pathname
    });
  }

  public trackTiming(name: string, value: number, category?: string) {
    this.trackEvent('timing_complete', {
      name: name,
      value: value,
      event_category: category || 'Performance'
    });
  }

  // Check if analytics is enabled
  public isEnabled(): boolean {
    return this.consentManager.getCategoryConsent('analytics') && this.isInitialized;
  }
}

// Create singleton instance
export const analytics = new AnalyticsService();

// React hook for analytics
export const useAnalytics = () => {
  return {
    trackPageView: analytics.trackPageView.bind(analytics),
    trackEvent: analytics.trackEvent.bind(analytics),
    trackUserAction: analytics.trackUserAction.bind(analytics),
    trackError: analytics.trackError.bind(analytics),
    trackTiming: analytics.trackTiming.bind(analytics),
    isEnabled: analytics.isEnabled.bind(analytics)
  };
};