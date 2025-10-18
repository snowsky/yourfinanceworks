import { ConsentManager } from '@/components/cookie-consent/services/ConsentManager';

// Marketing service that respects cookie consent
class MarketingService {
  private consentManager: ConsentManager;
  private isInitialized = false;
  private pendingEvents: Array<{ event: string; data: any }> = [];

  constructor() {
    this.consentManager = new ConsentManager();
    this.initializeMarketing();
    this.listenForConsentChanges();
  }

  private initializeMarketing() {
    // Check if marketing consent is already given
    if (this.consentManager.getCategoryConsent('marketing')) {
      this.loadMarketingScripts();
    }
  }

  private listenForConsentChanges() {
    // Listen for consent changes
    window.addEventListener('cookieConsentChange', (event: any) => {
      const { preferences } = event.detail;
      
      if (preferences.marketing && !this.isInitialized) {
        this.loadMarketingScripts();
        this.processPendingEvents();
      } else if (!preferences.marketing && this.isInitialized) {
        this.disableMarketing();
      }
    });
  }

  private loadMarketingScripts() {
    if (this.isInitialized) return;

    // Load marketing and advertising scripts
    this.loadGoogleAds();
    this.loadFacebookPixel();
    this.loadLinkedInInsight();
    this.loadCustomMarketing();
    
    this.isInitialized = true;
    console.log('🎯 Marketing tracking initialized with user consent');
  }

  private loadGoogleAds() {
    const GOOGLE_ADS_ID = import.meta.env.VITE_GOOGLE_ADS_ID;
    if (!GOOGLE_ADS_ID) return;

    // Load Google Ads conversion tracking
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${GOOGLE_ADS_ID}`;
    document.head.appendChild(script);

    // Initialize Google Ads tracking
    (window as any).dataLayer = (window as any).dataLayer || [];
    function gtag(...args: any[]) {
      (window as any).dataLayer.push(args);
    }
    (window as any).gtag = gtag;

    gtag('config', GOOGLE_ADS_ID);
    
    // Update consent for advertising
    gtag('consent', 'update', {
      ad_storage: 'granted',
      ad_user_data: 'granted',
      ad_personalization: 'granted'
    });
  }

  private loadFacebookPixel() {
    const FACEBOOK_PIXEL_ID = import.meta.env.VITE_FACEBOOK_PIXEL_ID;
    if (!FACEBOOK_PIXEL_ID) return;

    // Facebook Pixel Code
    (function(f: any, b: any, e: string, v: string) {
      let n: any, t: any, s: any;
      if (f.fbq) return;
      n = f.fbq = function() {
        n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
      };
      if (!f._fbq) f._fbq = n;
      n.push = n;
      n.loaded = !0;
      n.version = '2.0';
      n.queue = [];
      t = b.createElement(e);
      t.async = !0;
      t.src = v;
      s = b.getElementsByTagName(e)[0];
      s.parentNode!.insertBefore(t, s);
    })(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');

    (window as any).fbq('init', FACEBOOK_PIXEL_ID);
    (window as any).fbq('track', 'PageView');
  }

  private loadLinkedInInsight() {
    const LINKEDIN_PARTNER_ID = import.meta.env.VITE_LINKEDIN_PARTNER_ID;
    if (!LINKEDIN_PARTNER_ID) return;

    // LinkedIn Insight Tag
    (window as any)._linkedin_partner_id = LINKEDIN_PARTNER_ID;
    (window as any)._linkedin_data_partner_ids = (window as any)._linkedin_data_partner_ids || [];
    (window as any)._linkedin_data_partner_ids.push((window as any)._linkedin_partner_id);

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.async = true;
    script.src = 'https://snap.licdn.com/li.lms-analytics/insight.min.js';
    document.head.appendChild(script);
  }

  private loadCustomMarketing() {
    // Load your custom marketing tools
    // Example: Customer.io, Intercom, etc.
    console.log('🔧 Custom marketing tools initialized');
  }

  private disableMarketing() {
    if (!this.isInitialized) return;

    // Disable Google Ads
    if ((window as any).gtag) {
      (window as any).gtag('consent', 'update', {
        ad_storage: 'denied',
        ad_user_data: 'denied',
        ad_personalization: 'denied'
      });
    }

    // Clear marketing cookies
    this.clearMarketingCookies();
    
    this.isInitialized = false;
    console.log('🚫 Marketing tracking disabled - user withdrew consent');
  }

  private clearMarketingCookies() {
    // Clear various marketing cookies
    const marketingCookies = [
      '_fbp', '_fbc', // Facebook
      'fr', // Facebook
      'li_gc', // LinkedIn
      '_gcl_au', '_gcl_aw', // Google Ads
      'IDE', 'DSID', // Google DoubleClick
      '_uetsid', '_uetvid' // Microsoft Bing
    ];

    marketingCookies.forEach(cookieName => {
      document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
      document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.${window.location.hostname};`;
    });
  }

  private processPendingEvents() {
    // Process any events that were queued before consent was given
    this.pendingEvents.forEach(({ event, data }) => {
      this.trackConversion(event, data);
    });
    this.pendingEvents = [];
  }

  // Public methods for marketing tracking
  public trackConversion(eventName: string, parameters: Record<string, any> = {}) {
    if (!this.consentManager.getCategoryConsent('marketing')) {
      // Queue the event if no consent yet
      this.pendingEvents.push({ event: eventName, data: parameters });
      return;
    }

    if (!this.isInitialized) return;

    // Google Ads conversion tracking
    if ((window as any).gtag) {
      (window as any).gtag('event', 'conversion', {
        send_to: import.meta.env.VITE_GOOGLE_ADS_CONVERSION_ID,
        event_category: 'engagement',
        event_label: eventName,
        ...parameters
      });
    }

    // Facebook Pixel tracking
    if ((window as any).fbq) {
      (window as any).fbq('track', eventName, parameters);
    }

    // LinkedIn conversion tracking
    if ((window as any).lintrk) {
      (window as any).lintrk('track', { conversion_id: eventName });
    }

    console.log('🎯 Conversion tracked:', eventName, parameters);
  }

  public trackPurchase(value: number, currency: string = 'USD', transactionId?: string) {
    const purchaseData = {
      value: value,
      currency: currency,
      transaction_id: transactionId
    };

    this.trackConversion('Purchase', purchaseData);
  }

  public trackSignup(method?: string) {
    this.trackConversion('CompleteRegistration', {
      content_name: 'signup',
      method: method || 'email'
    });
  }

  public trackLead(leadType?: string) {
    this.trackConversion('Lead', {
      content_category: leadType || 'general'
    });
  }

  public trackAddToCart(itemId: string, value?: number) {
    this.trackConversion('AddToCart', {
      content_ids: [itemId],
      content_type: 'product',
      value: value
    });
  }

  public trackViewContent(contentType: string, contentId?: string) {
    this.trackConversion('ViewContent', {
      content_type: contentType,
      content_ids: contentId ? [contentId] : undefined
    });
  }

  // Remarketing audience building
  public addToRemarketingAudience(audienceType: string, parameters: Record<string, any> = {}) {
    if (!this.consentManager.getCategoryConsent('marketing')) {
      this.pendingEvents.push({ event: 'remarketing', data: { audienceType, parameters } });
      return;
    }

    if (!this.isInitialized) return;

    // Google Ads remarketing
    if ((window as any).gtag) {
      (window as any).gtag('event', 'page_view', {
        custom_map: { custom_parameter: audienceType },
        ...parameters
      });
    }

    // Facebook Custom Audience
    if ((window as any).fbq) {
      (window as any).fbq('track', 'CustomEvent', {
        audience_type: audienceType,
        ...parameters
      });
    }

    console.log('👥 Added to remarketing audience:', audienceType, parameters);
  }

  // Check if marketing is enabled
  public isEnabled(): boolean {
    return this.consentManager.getCategoryConsent('marketing') && this.isInitialized;
  }
}

// Create singleton instance
export const marketing = new MarketingService();

// React hook for marketing
export const useMarketing = () => {
  return {
    trackConversion: marketing.trackConversion.bind(marketing),
    trackPurchase: marketing.trackPurchase.bind(marketing),
    trackSignup: marketing.trackSignup.bind(marketing),
    trackLead: marketing.trackLead.bind(marketing),
    trackAddToCart: marketing.trackAddToCart.bind(marketing),
    trackViewContent: marketing.trackViewContent.bind(marketing),
    addToRemarketingAudience: marketing.addToRemarketingAudience.bind(marketing),
    isEnabled: marketing.isEnabled.bind(marketing)
  };
};