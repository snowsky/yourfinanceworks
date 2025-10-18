/**
 * Google Analytics Integration Example
 * 
 * This example shows how to integrate Google Analytics with the Cookie Consent Banner
 * to ensure analytics scripts only load when users have given consent.
 */

// Initialize the Cookie Consent Banner with Google Analytics configuration
const cookieConsent = new CookieConsentBanner({
  primaryColor: '#007bff',
  darkMode: false,
  message: 'We use cookies to improve your experience and analyze site usage.',
  
  // Google Analytics configuration
  analyticsConfig: {
    googleAnalytics: {
      trackingId: 'GA_MEASUREMENT_ID', // Replace with your GA4 Measurement ID
      enabled: true,
      config: {
        // Additional GA4 configuration options
        anonymize_ip: true,
        allow_google_signals: false,
        allow_ad_personalization_signals: false
      }
    }
  },
  
  // Handle consent changes
  onConsentChange: (consentStatus) => {
    console.log('Consent status changed:', consentStatus);
    
    // Check if analytics consent is given
    const analyticsConsent = ConsentManager.getCategoryConsent('analytics');
    
    if (analyticsConsent) {
      // Analytics consent given - GA will be loaded automatically
      console.log('Analytics tracking enabled');
      
      // Optional: Send custom events
      if (typeof gtag !== 'undefined') {
        gtag('event', 'consent_given', {
          event_category: 'privacy',
          event_label: 'analytics_consent'
        });
      }
    } else {
      // Analytics consent withdrawn
      console.log('Analytics tracking disabled');
      
      // Optional: Clear GA cookies if consent is withdrawn
      clearGoogleAnalyticsCookies();
    }
  }
});

/**
 * Function to clear Google Analytics cookies when consent is withdrawn
 */
function clearGoogleAnalyticsCookies() {
  // List of common GA cookie names
  const gaCookies = [
    '_ga',
    '_ga_' + 'GA_MEASUREMENT_ID'.replace('G-', ''),
    '_gid',
    '_gat',
    '_gat_gtag_' + 'GA_MEASUREMENT_ID',
    '__utma',
    '__utmb',
    '__utmc',
    '__utmt',
    '__utmz'
  ];
  
  // Clear each cookie
  gaCookies.forEach(cookieName => {
    document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.${window.location.hostname}`;
    document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
  });
}

/**
 * Manual consent checking for custom analytics events
 */
function trackCustomEvent(eventName, parameters = {}) {
  // Only track if analytics consent is given
  if (ConsentManager.getCategoryConsent('analytics')) {
    if (typeof gtag !== 'undefined') {
      gtag('event', eventName, parameters);
    }
  } else {
    console.log('Analytics event blocked - no consent:', eventName);
  }
}

// Example usage of custom event tracking
document.addEventListener('DOMContentLoaded', () => {
  // Track page view only if consent is given
  trackCustomEvent('page_view', {
    page_title: document.title,
    page_location: window.location.href
  });
  
  // Example: Track button clicks
  document.querySelectorAll('[data-track]').forEach(button => {
    button.addEventListener('click', () => {
      const eventName = button.dataset.track;
      trackCustomEvent('button_click', {
        button_name: eventName,
        page_location: window.location.href
      });
    });
  });
});

/**
 * Advanced: Server-side consent checking
 * Send consent status to your backend for server-side analytics
 */
function syncConsentWithServer() {
  const consentStatus = ConsentManager.getConsentStatus();
  const preferences = {
    essential: ConsentManager.getCategoryConsent('essential'),
    analytics: ConsentManager.getCategoryConsent('analytics'),
    marketing: ConsentManager.getCategoryConsent('marketing'),
    timestamp: Date.now()
  };
  
  // Send to your backend
  fetch('/api/consent', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      status: consentStatus,
      preferences: preferences
    })
  }).catch(error => {
    console.error('Failed to sync consent with server:', error);
  });
}

// Sync consent with server when it changes
cookieConsent.onConsentChange = (consentStatus) => {
  syncConsentWithServer();
};