# Cookie Consent Integration Guide

This guide shows you how to integrate Analytics and Marketing cookies with the Cookie Consent Banner system.

## 🚀 Quick Start

### 1. Environment Setup

Create a `.env` file with your tracking IDs:

```bash
# Analytics
VITE_GA_MEASUREMENT_ID=G-XXXXXXXXXX

# Marketing
VITE_GOOGLE_ADS_ID=AW-XXXXXXXXX
VITE_FACEBOOK_PIXEL_ID=XXXXXXXXXXXXXXXXX
VITE_LINKEDIN_PARTNER_ID=XXXXXXX
```

### 2. Basic Usage

```tsx
import { useTracking, useBusinessTracking } from '@/hooks/useTracking';

function MyComponent() {
  const tracking = useTracking();
  const businessTracking = useBusinessTracking();

  const handleButtonClick = () => {
    // This respects user's cookie preferences
    tracking.trackEvent('button_click', {
      button_name: 'my_button',
      page: 'my_page'
    });
  };

  const handlePurchase = (amount: number, currency: string) => {
    // Only tracks if user consented to marketing cookies
    tracking.trackPurchase(amount, currency);
  };

  return (
    <button onClick={handleButtonClick}>
      Track This Click
    </button>
  );
}
```

## 📊 Analytics Integration

### Automatic Page Tracking

Page views are tracked automatically when you use the `useTracking` hook:

```tsx
function MyPage() {
  const tracking = useTracking(); // Automatically tracks page view
  
  return <div>My Page Content</div>;
}
```

### Custom Event Tracking

```tsx
// Basic event tracking
tracking.trackEvent('video_play', {
  video_id: 'intro_video',
  duration: 120
});

// User action tracking
tracking.trackUserAction('download', 'resources', 'user_guide.pdf');

// Error tracking
tracking.trackError('API request failed', 'user_dashboard');

// Performance tracking
tracking.trackTiming('page_load', 1250, 'Performance');
```

### Business Event Tracking

```tsx
// Invoice events
businessTracking.trackInvoiceCreated('INV-001', 1500.00, 'USD');
businessTracking.trackInvoicePaid('INV-001', 1500.00, 'USD');

// Client events
businessTracking.trackClientAdded('CLIENT-001');

// Feature usage
businessTracking.trackFeatureUsed('invoice_generator', 'dashboard');
```

## 🎯 Marketing Integration

### Conversion Tracking

```tsx
// Generic conversion
tracking.trackConversion('demo_request', {
  lead_source: 'website',
  campaign: 'summer_2024'
});

// Purchase tracking
tracking.trackPurchase(99.99, 'USD', 'ORDER-123');

// Signup tracking
tracking.trackSignup('email');

// Lead generation
tracking.trackLead('contact_form');
```

### E-commerce Tracking

```tsx
// Add to cart
tracking.trackAddToCart('product-123', 49.99);

// View product
tracking.trackViewContent('product', 'product-123');

// Remarketing audiences
tracking.addToRemarketingAudience('high_value_visitors', {
  page_value: 1000,
  user_type: 'premium'
});
```

## 🔄 Consent-Aware Behavior

### How It Works

The tracking system automatically respects user cookie preferences:

1. **No Consent**: Events are queued in memory
2. **Analytics Consent**: Analytics events are sent, marketing events queued
3. **Marketing Consent**: Marketing events are sent
4. **Full Consent**: All events are sent immediately
5. **Consent Withdrawn**: Tracking stops, cookies are cleared

### Event Queuing

```tsx
// This event will be queued if no consent is given
tracking.trackEvent('early_interaction', { timestamp: Date.now() });

// When user gives consent, all queued events are processed
// No additional code needed - it happens automatically
```

### Checking Consent Status

```tsx
function MyComponent() {
  const tracking = useTracking();

  if (tracking.analyticsEnabled) {
    // Show analytics-dependent features
  }

  if (tracking.marketingEnabled) {
    // Show marketing-dependent features
  }

  return <div>Content based on consent</div>;
}
```

## 🛠️ Advanced Configuration

### Custom Analytics Provider

```tsx
// In your analytics service
private loadCustomAnalytics() {
  // Load your custom analytics
  const script = document.createElement('script');
  script.src = 'https://your-analytics.com/script.js';
  document.head.appendChild(script);
  
  // Initialize with GDPR-compliant settings
  (window as any).yourAnalytics.init({
    anonymizeIP: true,
    respectDNT: true,
    cookieConsent: true
  });
}
```

### Custom Marketing Provider

```tsx
// In your marketing service
private loadCustomMarketing() {
  // Load your marketing tools
  const script = document.createElement('script');
  script.src = 'https://your-marketing.com/pixel.js';
  document.head.appendChild(script);
}
```

### Event Listeners

```tsx
// Listen for consent changes
window.addEventListener('cookieConsentChange', (event) => {
  const { status, preferences } = event.detail;
  
  if (preferences.analytics) {
    // Analytics consent given
    console.log('Analytics enabled');
  }
  
  if (preferences.marketing) {
    // Marketing consent given
    console.log('Marketing enabled');
  }
});
```

## 🔒 GDPR Compliance Features

### Automatic Cookie Clearing

When users withdraw consent, the system automatically:

- Stops sending tracking data
- Clears existing tracking cookies
- Disables tracking scripts
- Updates consent mode in Google Analytics

### Privacy-First Configuration

All tracking is configured with privacy-first settings:

```tsx
// Google Analytics with privacy settings
gtag('config', GA_MEASUREMENT_ID, {
  anonymize_ip: true,
  cookie_flags: 'SameSite=None;Secure',
  allow_google_signals: false,
  allow_ad_personalization_signals: false
});

// Consent mode
gtag('consent', 'default', {
  analytics_storage: 'denied',
  ad_storage: 'denied'
});
```

## 🧪 Testing Your Integration

### Development Testing

1. Open your browser's developer tools
2. Go to the Network tab
3. Clear your cookies and reload the page
4. Try the tracking buttons without giving consent - no requests should be sent
5. Give consent and try again - requests should now be sent

### Console Logging

The system logs all tracking activities to the console in development:

```
📊 Analytics initialized with user consent
🎯 Marketing tracking initialized with user consent
📄 Page view tracked: /dashboard
📊 Event tracked: button_click
🚫 Analytics disabled - user withdrew consent
```

### Testing Different Consent States

Use the Cookie Settings to test different scenarios:

1. **No Consent**: All tracking should be queued
2. **Analytics Only**: Only analytics events should fire
3. **Marketing Only**: Only marketing events should fire
4. **Full Consent**: All events should fire immediately

## 🚨 Common Issues

### "process is not defined" Error

If you see `Uncaught ReferenceError: process is not defined` in your browser console:

1. **Cause**: Using Node.js `process.env` in browser code
2. **Solution**: Use Vite's `import.meta.env` instead
3. **Environment Variables**: Ensure your `.env` file uses `VITE_` prefix:

```bash
# ✅ Correct (Vite)
VITE_GA_MEASUREMENT_ID=G-XXXXXXXXXX

# ❌ Incorrect (Node.js/React)
REACT_APP_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

4. **Code Update**: Replace `process.env.REACT_APP_*` with `import.meta.env.VITE_*`

### Events Not Firing

1. Check if user has given appropriate consent
2. Verify environment variables are set
3. Check browser console for errors
4. Ensure tracking IDs are valid

### Cookies Not Clearing

1. Check if consent withdrawal is properly detected
2. Verify cookie clearing logic includes all relevant cookies
3. Test across different domains/subdomains

### Performance Issues

1. Ensure scripts are loaded asynchronously
2. Queue events properly before consent
3. Avoid loading unnecessary tracking scripts

## 📈 Best Practices

### 1. Respect User Preferences
- Always check consent before tracking
- Queue events when no consent is given
- Clear data when consent is withdrawn

### 2. Minimize Data Collection
- Only track what you need
- Use privacy-friendly settings
- Anonymize IP addresses

### 3. Be Transparent
- Clearly explain what data you collect
- Provide easy consent management
- Honor user choices immediately

### 4. Test Thoroughly
- Test all consent scenarios
- Verify cookie clearing works
- Check cross-browser compatibility

### 5. Monitor Compliance
- Regularly audit your tracking
- Keep up with privacy regulations
- Update consent mechanisms as needed

## 🔗 Additional Resources

- [Google Analytics 4 Privacy Guide](https://support.google.com/analytics/answer/9019185)
- [Facebook Pixel GDPR Compliance](https://www.facebook.com/business/help/471978536642445)
- [GDPR Cookie Consent Requirements](https://gdpr.eu/cookies/)
- [Cookie Consent Banner Documentation](../README.md)