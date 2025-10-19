# Cookie Consent Banner Design

## Overview

The cookie consent system consists of three main components: a fixed bottom banner for initial consent, a detailed preferences modal for granular control, and a consent management service that handles localStorage operations and script loading. The design prioritizes accessibility, GDPR compliance, and seamless integration with existing applications.

## Architecture

### Component Structure
```
CookieConsentSystem/
├── CookieConsentBanner (Main container)
├── ConsentBanner (Fixed bottom bar)
├── PreferencesModal (Detailed settings)
├── ConsentManager (Service layer)
└── AnalyticsIntegration (Script loader)
```

### State Management
- **Consent State**: Tracks current consent status ('accepted', 'custom', null)
- **Preferences State**: Individual category toggles (essential, analytics, marketing)
- **UI State**: Banner visibility, modal open/closed, loading states
- **Theme State**: Light/dark mode support

## Components and Interfaces

### 1. CookieConsentBanner (Main Component)

**Props Interface:**
```typescript
interface CookieConsentProps {
  primaryColor?: string;
  darkMode?: boolean;
  position?: 'bottom' | 'top';
  message?: string;
  onConsentChange?: (consent: ConsentStatus) => void;
  analyticsConfig?: AnalyticsConfig;
}
```

**Key Methods:**
- `checkExistingConsent()`: Reads localStorage on mount
- `handleAcceptAll()`: Sets full consent and hides banner
- `handleManagePreferences()`: Opens preferences modal
- `updateConsentStatus()`: Manages consent state changes

### 2. ConsentBanner (Fixed Bar Component)

**Features:**
- Fixed positioning at bottom of viewport
- Responsive design with mobile-first approach
- Smooth slide-up animation on show/hide
- High contrast text and accessible button styling
- Keyboard navigation support

**CSS Classes:**
```css
.cookie-banner
.cookie-banner--visible
.cookie-banner--hidden
.cookie-banner__content
.cookie-banner__message
.cookie-banner__actions
.cookie-banner__button
.cookie-banner__button--primary
.cookie-banner__button--secondary
```

### 3. PreferencesModal (Detailed Settings)

**Features:**
- Modal overlay with focus trapping
- Three cookie categories with descriptions
- Toggle switches for analytics and marketing
- Save/Cancel actions
- Accessible modal implementation

**Cookie Categories:**
- **Essential**: Always enabled, required for basic functionality
- **Analytics**: Optional, for website performance monitoring
- **Marketing**: Optional, for advertising and personalization

### 4. ConsentManager (Service Layer)

**Core Functions:**
```typescript
class ConsentManager {
  getConsentStatus(): ConsentStatus
  setConsentStatus(status: ConsentStatus): void
  getCategoryConsent(category: CookieCategory): boolean
  setCategoryConsent(category: CookieCategory, enabled: boolean): void
  clearAllConsent(): void
  isConsentRequired(): boolean
}
```

**LocalStorage Keys:**
- `cookieConsent`: Main consent status
- `cookieConsent_essential`: Essential cookies (always true)
- `cookieConsent_analytics`: Analytics consent
- `cookieConsent_marketing`: Marketing consent
- `cookieConsent_timestamp`: Consent date for compliance

### 5. AnalyticsIntegration (Script Loader)

**Features:**
- Conditional script loading based on consent
- Support for Google Analytics, GTM, and custom providers
- Event tracking for consent changes
- Script cleanup on consent withdrawal

**Integration Example:**
```typescript
const analyticsConfig = {
  googleAnalytics: {
    trackingId: 'GA_TRACKING_ID',
    enabled: true
  },
  customProvider: {
    scriptUrl: 'https://example.com/analytics.js',
    initFunction: 'customAnalytics.init'
  }
};
```

## Data Models

### ConsentStatus Type
```typescript
type ConsentStatus = 'accepted' | 'custom' | null;
```

### CookieCategory Type
```typescript
type CookieCategory = 'essential' | 'analytics' | 'marketing';
```

### ConsentPreferences Interface
```typescript
interface ConsentPreferences {
  essential: boolean;
  analytics: boolean;
  marketing: boolean;
  timestamp: number;
  version: string;
}
```

## Error Handling

### LocalStorage Errors
- Graceful fallback when localStorage is unavailable
- Memory-based consent storage as backup
- User notification for storage issues

### Script Loading Errors
- Retry mechanism for failed analytics script loads
- Error logging without breaking main functionality
- Fallback analytics collection methods

### Modal Interaction Errors
- Keyboard trap error recovery
- Focus management error handling
- Modal state corruption prevention

## Testing Strategy

### Unit Tests
- ConsentManager localStorage operations
- Component prop validation and state changes
- Accessibility attribute verification
- Theme switching functionality

### Integration Tests
- Banner show/hide behavior based on consent status
- Modal opening and preference saving flow
- Analytics script loading based on consent
- Cross-browser localStorage compatibility

### Accessibility Tests
- Screen reader navigation testing
- Keyboard-only interaction verification
- Color contrast ratio validation
- Focus management testing

### GDPR Compliance Tests
- Verify no non-essential cookies before consent
- Test consent withdrawal functionality
- Validate consent persistence across sessions
- Check consent timestamp accuracy

## Implementation Notes

### CSS Custom Properties
```css
:root {
  --cookie-primary-color: #007bff;
  --cookie-bg-light: #ffffff;
  --cookie-bg-dark: #1a1a1a;
  --cookie-text-light: #333333;
  --cookie-text-dark: #ffffff;
  --cookie-border-radius: 8px;
  --cookie-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
```

### Responsive Breakpoints
- Mobile: < 768px (stacked buttons, full-width)
- Tablet: 768px - 1024px (horizontal layout)
- Desktop: > 1024px (optimized spacing)

### Animation Specifications
- Banner slide-in: 300ms ease-out
- Modal fade-in: 200ms ease-in-out
- Button hover transitions: 150ms ease

### Framework Integration Patterns

**React Integration:**
```typescript
// Hook-based approach
const { consentStatus, updateConsent } = useCookieConsent();

// Component integration
<CookieConsentBanner 
  onConsentChange={handleConsentChange}
  analyticsConfig={analyticsConfig}
/>
```

**Vue.js Integration:**
```typescript
// Composable approach
const { consentStatus, updateConsent } = useCookieConsent();

// Component integration
<CookieConsentBanner 
  @consent-change="handleConsentChange"
  :analytics-config="analyticsConfig"
/>
```

### Performance Considerations
- Lazy loading of modal component
- Debounced localStorage writes
- Minimal DOM manipulation
- Efficient event listener management
- CSS-based animations over JavaScript

### Security Considerations
- XSS prevention in dynamic content
- Secure localStorage key naming
- Script injection prevention
- Content Security Policy compatibility