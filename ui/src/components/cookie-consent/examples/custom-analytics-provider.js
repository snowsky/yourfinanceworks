/**
 * Custom Analytics Provider Integration Example
 * 
 * This example demonstrates how to integrate custom analytics providers
 * with the Cookie Consent Banner system.
 */

// Example: Mixpanel Integration
const mixpanelProvider = {
  name: 'mixpanel',
  scriptUrl: 'https://cdn.mxpnl.com/libs/mixpanel-2-latest.min.js',
  
  // Initialize the provider when consent is given
  init: (config) => {
    if (typeof mixpanel !== 'undefined') {
      mixpanel.init(config.token, {
        debug: config.debug || false,
        track_pageview: true,
        persistence: 'localStorage'
      });
      console.log('Mixpanel initialized');
    }
  },
  
  // Clean up when consent is withdrawn
  cleanup: () => {
    if (typeof mixpanel !== 'undefined') {
      mixpanel.reset();
      console.log('Mixpanel data cleared');
    }
  },
  
  // Track events
  track: (eventName, properties = {}) => {
    if (typeof mixpanel !== 'undefined') {
      mixpanel.track(eventName, properties);
    }
  }
};

// Example: Adobe Analytics Integration
const adobeAnalyticsProvider = {
  name: 'adobe',
  scriptUrl: 'https://assets.adobedtm.com/your-property-id.min.js',
  
  init: (config) => {
    // Adobe Analytics initialization
    if (typeof s !== 'undefined') {
      s.trackingServer = config.trackingServer;
      s.trackingServerSecure = config.trackingServerSecure;
      console.log('Adobe Analytics initialized');
    }
  },
  
  cleanup: () => {
    // Clear Adobe Analytics cookies
    const adobeCookies = ['s_cc', 's_sq', 's_vi', 's_fid'];
    adobeCookies.forEach(cookieName => {
      document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
    });
    console.log('Adobe Analytics data cleared');
  },
  
  track: (eventName, properties = {}) => {
    if (typeof s !== 'undefined') {
      s.linkTrackVars = 'events,eVar1,eVar2';
      s.events = eventName;
      Object.keys(properties).forEach((key, index) => {
        s[`eVar${index + 1}`] = properties[key];
      });
      s.tl(true, 'o', eventName);
    }
  }
};

// Custom Analytics Manager
class CustomAnalyticsManager {
  constructor() {
    this.providers = new Map();
    this.loadedProviders = new Set();
  }
  
  // Register a custom provider
  registerProvider(provider) {
    this.providers.set(provider.name, provider);
  }
  
  // Load provider script and initialize
  async loadProvider(providerName, config) {
    const provider = this.providers.get(providerName);
    if (!provider) {
      console.error(`Provider ${providerName} not found`);
      return;
    }
    
    try {
      // Load script if not already loaded
      if (!this.loadedProviders.has(providerName)) {
        await this.loadScript(provider.scriptUrl);
        this.loadedProviders.add(providerName);
      }
      
      // Initialize provider
      if (provider.init) {
        provider.init(config);
      }
    } catch (error) {
      console.error(`Failed to load provider ${providerName}:`, error);
    }
  }
  
  // Unload provider and clean up
  unloadProvider(providerName) {
    const provider = this.providers.get(providerName);
    if (provider && provider.cleanup) {
      provider.cleanup();
    }
  }
  
  // Track event across all loaded providers
  trackEvent(eventName, properties = {}) {
    this.providers.forEach((provider, name) => {
      if (this.loadedProviders.has(name) && provider.track) {
        provider.track(eventName, properties);
      }
    });
  }
  
  // Utility to load external scripts
  loadScript(url) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = url;
      script.async = true;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
}

// Initialize the analytics manager
const analyticsManager = new CustomAnalyticsManager();

// Register custom providers
analyticsManager.registerProvider(mixpanelProvider);
analyticsManager.registerProvider(adobeAnalyticsProvider);

// Configure the Cookie Consent Banner with custom providers
const cookieConsent = new CookieConsentBanner({
  primaryColor: '#007bff',
  darkMode: false,
  
  // Custom analytics configuration
  analyticsConfig: {
    mixpanel: {
      token: 'YOUR_MIXPANEL_TOKEN',
      debug: false
    },
    adobe: {
      trackingServer: 'your-tracking-server.com',
      trackingServerSecure: 'your-secure-tracking-server.com'
    }
  },
  
  // Handle consent changes
  onConsentChange: async (consentStatus) => {
    const analyticsConsent = ConsentManager.getCategoryConsent('analytics');
    
    if (analyticsConsent) {
      // Load and initialize analytics providers
      const config = cookieConsent.analyticsConfig;
      
      if (config.mixpanel) {
        await analyticsManager.loadProvider('mixpanel', config.mixpanel);
      }
      
      if (config.adobe) {
        await analyticsManager.loadProvider('adobe', config.adobe);
      }
      
      // Track consent given event
      analyticsManager.trackEvent('consent_given', {
        timestamp: Date.now(),
        categories: ['analytics']
      });
      
    } else {
      // Clean up providers when consent is withdrawn
      analyticsManager.unloadProvider('mixpanel');
      analyticsManager.unloadProvider('adobe');
    }
  }
});

// Example usage: Track custom events
function trackUserAction(action, details = {}) {
  // Only track if analytics consent is given
  if (ConsentManager.getCategoryConsent('analytics')) {
    analyticsManager.trackEvent(action, {
      ...details,
      timestamp: Date.now(),
      page: window.location.pathname
    });
  }
}

// Example event tracking
document.addEventListener('DOMContentLoaded', () => {
  // Track page views
  trackUserAction('page_view', {
    title: document.title,
    url: window.location.href
  });
  
  // Track form submissions
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', (e) => {
      trackUserAction('form_submit', {
        form_id: form.id || 'unknown',
        form_action: form.action
      });
    });
  });
  
  // Track downloads
  document.querySelectorAll('a[href$=".pdf"], a[href$=".doc"], a[href$=".zip"]').forEach(link => {
    link.addEventListener('click', (e) => {
      trackUserAction('file_download', {
        file_url: link.href,
        file_type: link.href.split('.').pop()
      });
    });
  });
});

// Advanced: Consent-aware A/B testing
class ConsentAwareABTesting {
  constructor() {
    this.experiments = new Map();
  }
  
  // Define an experiment
  defineExperiment(name, variants, config = {}) {
    this.experiments.set(name, {
      variants,
      config,
      assignment: null
    });
  }
  
  // Get variant assignment (only if analytics consent is given)
  getVariant(experimentName) {
    if (!ConsentManager.getCategoryConsent('analytics')) {
      return null; // No tracking without consent
    }
    
    const experiment = this.experiments.get(experimentName);
    if (!experiment) return null;
    
    // Assign variant if not already assigned
    if (!experiment.assignment) {
      const randomIndex = Math.floor(Math.random() * experiment.variants.length);
      experiment.assignment = experiment.variants[randomIndex];
      
      // Track assignment
      trackUserAction('ab_test_assignment', {
        experiment: experimentName,
        variant: experiment.assignment
      });
    }
    
    return experiment.assignment;
  }
}

// Example A/B testing usage
const abTesting = new ConsentAwareABTesting();

abTesting.defineExperiment('button_color', ['blue', 'green', 'red']);
abTesting.defineExperiment('headline_text', ['version_a', 'version_b']);

// Use in your application
const buttonVariant = abTesting.getVariant('button_color');
if (buttonVariant) {
  document.querySelector('#cta-button').className += ` variant-${buttonVariant}`;
}