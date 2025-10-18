/**
 * Event Callbacks Integration Example
 * 
 * This example demonstrates how to use event callbacks to integrate
 * the Cookie Consent Banner with your application's analytics and
 * user experience tracking.
 */

// Comprehensive event callback configuration
const cookieConsent = new CookieConsentBanner({
  primaryColor: '#007bff',
  darkMode: false,
  
  // Banner lifecycle callbacks
  onBannerShow: () => {
    console.log('Cookie banner displayed');
    
    // Track banner impression (without cookies)
    trackConsentEvent('banner_shown', {
      timestamp: Date.now(),
      page: window.location.pathname,
      user_agent: navigator.userAgent
    });
    
    // Optional: Pause auto-playing videos when banner shows
    pauseAutoplayingMedia();
  },
  
  onBannerHide: () => {
    console.log('Cookie banner hidden');
    
    // Resume auto-playing videos when banner hides
    resumeAutoplayingMedia();
    
    // Track banner dismissal
    trackConsentEvent('banner_hidden', {
      timestamp: Date.now(),
      method: 'consent_given' // or 'already_consented'
    });
  },
  
  // Preferences modal callbacks
  onPreferencesOpen: () => {
    console.log('Preferences modal opened');
    
    // Track preferences modal usage
    trackConsentEvent('preferences_opened', {
      timestamp: Date.now(),
      source: 'banner_button' // or 'settings_page'
    });
    
    // Optional: Blur background content
    document.body.classList.add('modal-open');
  },
  
  onPreferencesClose: (savedChanges = false) => {
    console.log('Preferences modal closed', { savedChanges });
    
    // Remove background blur
    document.body.classList.remove('modal-open');
    
    // Track modal closure
    trackConsentEvent('preferences_closed', {
      timestamp: Date.now(),
      changes_saved: savedChanges
    });
  },
  
  // Main consent change callback
  onConsentChange: (consentStatus, previousStatus, changedCategories = []) => {
    console.log('Consent changed:', {
      current: consentStatus,
      previous: previousStatus,
      changed: changedCategories
    });
    
    // Track consent changes
    trackConsentEvent('consent_changed', {
      status: consentStatus,
      previous_status: previousStatus,
      changed_categories: changedCategories,
      timestamp: Date.now()
    });
    
    // Handle specific consent scenarios
    handleConsentScenarios(consentStatus, previousStatus, changedCategories);
    
    // Sync with external systems
    syncConsentWithExternalSystems(consentStatus);
    
    // Update UI based on consent
    updateUIBasedOnConsent();
  },
  
  // Category-specific callbacks
  onCategoryChange: (category, enabled, previousState) => {
    console.log(`Category ${category} changed:`, { enabled, previousState });
    
    // Handle category-specific logic
    switch (category) {
      case 'analytics':
        handleAnalyticsConsentChange(enabled);
        break;
      case 'marketing':
        handleMarketingConsentChange(enabled);
        break;
      case 'essential':
        // Essential cookies can't be disabled, but track if attempted
        if (!enabled) {
          trackConsentEvent('essential_disable_attempted', {
            timestamp: Date.now()
          });
        }
        break;
    }
  },
  
  // Error handling callbacks
  onError: (error, context) => {
    console.error('Cookie consent error:', error, context);
    
    // Track errors for debugging
    trackConsentEvent('consent_error', {
      error_message: error.message,
      error_context: context,
      timestamp: Date.now(),
      user_agent: navigator.userAgent
    });
    
    // Optional: Show user-friendly error message
    showUserErrorMessage('There was an issue with cookie preferences. Please try again.');
  },
  
  // Storage callbacks
  onStorageError: (operation, error) => {
    console.error('Storage error during:', operation, error);
    
    // Handle localStorage unavailability
    if (error.name === 'QuotaExceededError') {
      showUserErrorMessage('Storage is full. Please clear some browser data and try again.');
    } else {
      showUserErrorMessage('Unable to save preferences. Please check your browser settings.');
    }
    
    // Track storage issues
    trackConsentEvent('storage_error', {
      operation: operation,
      error_type: error.name,
      timestamp: Date.now()
    });
  }
});

/**
 * Track consent-related events (without using cookies)
 * This function uses server-side tracking or localStorage for analytics
 */
function trackConsentEvent(eventName, properties = {}) {
  // Option 1: Send to server immediately (no cookies needed)
  fetch('/api/analytics/consent-events', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      event: eventName,
      properties: properties,
      session_id: getSessionId(), // Generate session ID without cookies
      timestamp: Date.now()
    })
  }).catch(error => {
    console.error('Failed to track consent event:', error);
  });
  
  // Option 2: Store in localStorage for later batch sending
  const events = JSON.parse(localStorage.getItem('consent_events') || '[]');
  events.push({
    event: eventName,
    properties: properties,
    timestamp: Date.now()
  });
  
  // Keep only last 100 events to prevent storage bloat
  if (events.length > 100) {
    events.splice(0, events.length - 100);
  }
  
  localStorage.setItem('consent_events', JSON.stringify(events));
}

/**
 * Handle different consent scenarios
 */
function handleConsentScenarios(current, previous, changed) {
  // First-time visitor accepting all cookies
  if (previous === null && current === 'accepted') {
    console.log('First-time visitor accepted all cookies');
    
    // Initialize all analytics and marketing tools
    initializeAllTrackingTools();
    
    // Show welcome message or onboarding
    showWelcomeMessage();
  }
  
  // User customizing preferences for the first time
  else if (previous === null && current === 'custom') {
    console.log('First-time visitor customized preferences');
    
    // Initialize only consented tools
    initializeConsentedTools();
    
    // Thank user for taking time to customize
    showCustomizationThankYou();
  }
  
  // User changing from accept all to custom
  else if (previous === 'accepted' && current === 'custom') {
    console.log('User switched from accept all to custom preferences');
    
    // Clean up any tools that are no longer consented
    cleanupNonConsentedTools(changed);
  }
  
  // User withdrawing consent entirely
  else if (previous !== null && current === null) {
    console.log('User withdrew all consent');
    
    // Clean up all non-essential tools
    cleanupAllNonEssentialTools();
    
    // Show privacy-focused message
    showPrivacyRespectedMessage();
  }
}

/**
 * Handle analytics consent changes
 */
function handleAnalyticsConsentChange(enabled) {
  if (enabled) {
    console.log('Analytics consent granted');
    
    // Initialize analytics tools
    initializeAnalytics();
    
    // Start performance monitoring
    startPerformanceMonitoring();
    
    // Enable heatmap tools if configured
    initializeHeatmapTools();
    
  } else {
    console.log('Analytics consent withdrawn');
    
    // Clean up analytics cookies and data
    cleanupAnalyticsData();
    
    // Stop performance monitoring
    stopPerformanceMonitoring();
    
    // Disable heatmap tools
    disableHeatmapTools();
  }
}

/**
 * Handle marketing consent changes
 */
function handleMarketingConsentChange(enabled) {
  if (enabled) {
    console.log('Marketing consent granted');
    
    // Initialize marketing pixels
    initializeMarketingPixels();
    
    // Enable personalization
    enablePersonalization();
    
    // Start A/B testing
    initializeABTesting();
    
  } else {
    console.log('Marketing consent withdrawn');
    
    // Clean up marketing cookies
    cleanupMarketingData();
    
    // Disable personalization
    disablePersonalization();
    
    // Stop A/B testing
    stopABTesting();
  }
}

/**
 * Sync consent with external systems
 */
function syncConsentWithExternalSystems(consentStatus) {
  const preferences = {
    essential: ConsentManager.getCategoryConsent('essential'),
    analytics: ConsentManager.getCategoryConsent('analytics'),
    marketing: ConsentManager.getCategoryConsent('marketing'),
    timestamp: Date.now()
  };
  
  // Sync with CRM system
  syncWithCRM(preferences);
  
  // Sync with email marketing platform
  syncWithEmailPlatform(preferences);
  
  // Sync with customer support system
  syncWithSupportSystem(preferences);
}

/**
 * Update UI elements based on consent status
 */
function updateUIBasedOnConsent() {
  const analyticsConsent = ConsentManager.getCategoryConsent('analytics');
  const marketingConsent = ConsentManager.getCategoryConsent('marketing');
  
  // Show/hide analytics-dependent features
  const analyticsFeatures = document.querySelectorAll('[data-requires-analytics]');
  analyticsFeatures.forEach(element => {
    element.style.display = analyticsConsent ? 'block' : 'none';
  });
  
  // Show/hide marketing-dependent features
  const marketingFeatures = document.querySelectorAll('[data-requires-marketing]');
  marketingFeatures.forEach(element => {
    element.style.display = marketingConsent ? 'block' : 'none';
  });
  
  // Update consent status indicators
  updateConsentStatusIndicators();
}

/**
 * Utility functions for media control
 */
function pauseAutoplayingMedia() {
  document.querySelectorAll('video[autoplay], audio[autoplay]').forEach(media => {
    media.pause();
    media.dataset.wasAutoPlaying = 'true';
  });
}

function resumeAutoplayingMedia() {
  document.querySelectorAll('[data-was-auto-playing="true"]').forEach(media => {
    media.play().catch(() => {
      // Ignore autoplay failures due to browser policies
    });
    delete media.dataset.wasAutoPlaying;
  });
}

/**
 * Generate session ID without cookies
 */
function getSessionId() {
  let sessionId = sessionStorage.getItem('session_id');
  if (!sessionId) {
    sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    sessionStorage.setItem('session_id', sessionId);
  }
  return sessionId;
}

/**
 * User feedback functions
 */
function showUserErrorMessage(message) {
  // Create and show a user-friendly error notification
  const notification = document.createElement('div');
  notification.className = 'consent-error-notification';
  notification.textContent = message;
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.remove();
  }, 5000);
}

function showWelcomeMessage() {
  console.log('Showing welcome message for new user');
  // Implement welcome message logic
}

function showCustomizationThankYou() {
  console.log('Thanking user for customizing preferences');
  // Implement thank you message logic
}

function showPrivacyRespectedMessage() {
  console.log('Showing privacy respected message');
  // Implement privacy message logic
}

// Example: Advanced consent analytics dashboard
class ConsentAnalyticsDashboard {
  constructor() {
    this.events = [];
    this.loadStoredEvents();
  }
  
  loadStoredEvents() {
    const stored = localStorage.getItem('consent_events');
    if (stored) {
      this.events = JSON.parse(stored);
    }
  }
  
  getConsentMetrics() {
    return {
      totalEvents: this.events.length,
      bannerShows: this.events.filter(e => e.event === 'banner_shown').length,
      acceptAllRate: this.calculateAcceptAllRate(),
      customizationRate: this.calculateCustomizationRate(),
      mostRecentConsent: this.getMostRecentConsent()
    };
  }
  
  calculateAcceptAllRate() {
    const consentEvents = this.events.filter(e => e.event === 'consent_changed');
    const acceptAllEvents = consentEvents.filter(e => e.properties.status === 'accepted');
    return consentEvents.length > 0 ? (acceptAllEvents.length / consentEvents.length) * 100 : 0;
  }
  
  calculateCustomizationRate() {
    const consentEvents = this.events.filter(e => e.event === 'consent_changed');
    const customEvents = consentEvents.filter(e => e.properties.status === 'custom');
    return consentEvents.length > 0 ? (customEvents.length / consentEvents.length) * 100 : 0;
  }
  
  getMostRecentConsent() {
    const consentEvents = this.events.filter(e => e.event === 'consent_changed');
    return consentEvents.length > 0 ? consentEvents[consentEvents.length - 1] : null;
  }
}

// Initialize dashboard (for debugging/admin purposes)
const consentDashboard = new ConsentAnalyticsDashboard();

// Expose dashboard to console for debugging
window.consentDashboard = consentDashboard;