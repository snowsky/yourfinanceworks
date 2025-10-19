# Cookie Consent Banner

A GDPR-compliant cookie consent banner system that provides users with granular control over cookie preferences while maintaining a modern, accessible design. The system ensures no non-essential cookies are set until explicit consent is given.

## Features

- 🍪 **GDPR Compliant** - No non-essential cookies until explicit consent
- 🎨 **Modern Design** - Clean, professional interface with light/dark mode support
- ♿ **Fully Accessible** - Screen reader compatible with keyboard navigation
- 🔧 **Highly Customizable** - Configurable colors, themes, and messaging
- 📱 **Responsive** - Works seamlessly across all device sizes
- ⚡ **Framework Agnostic** - Works with React, Vue.js, or vanilla JavaScript
- 🔒 **Privacy First** - Granular control over cookie categories

## Configuration Options

### Basic Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `primaryColor` | string | `#007bff` | Primary color for buttons and accents |
| `darkMode` | boolean | `false` | Enable dark mode theme |
| `position` | string | `bottom` | Banner position (`bottom` or `top`) |
| `message` | string | Default message | Custom consent message text |
| `onConsentChange` | function | `null` | Callback when consent status changes |

### Analytics Configuration

```javascript
const analyticsConfig = {
  googleAnalytics: {
    trackingId: 'GA_TRACKING_ID',
    enabled: true
  },
  customProvider: {
    scriptUrl: 'https://example.com/analytics.js',
    initFunction: 'customAnalytics.init',
    consentCallback: (hasConsent) => {
      // Custom logic when consent changes
    }
  }
};
```

## GDPR Compliance Features

### Cookie Categories

The system manages three categories of cookies:

1. **Essential Cookies** - Always enabled, required for basic website functionality
2. **Analytics Cookies** - Optional, used for website performance monitoring
3. **Marketing Cookies** - Optional, used for advertising and personalization

### Compliance Requirements

- ✅ **No Pre-consent Loading** - Non-essential cookies are blocked until consent
- ✅ **Granular Control** - Users can choose specific cookie categories
- ✅ **Consent Withdrawal** - Users can change preferences at any time
- ✅ **Consent Persistence** - Preferences are stored locally with timestamps
- ✅ **Clear Information** - Detailed explanations for each cookie category

### Legal Compliance

The system helps meet GDPR requirements by:

- Obtaining explicit consent before setting non-essential cookies
- Providing clear information about cookie purposes
- Allowing easy consent withdrawal
- Maintaining consent records with timestamps
- Respecting user preferences across sessions

## Customization Guide

### Theme Customization

Override CSS custom properties to match your brand:

```css
:root {
  --cookie-primary-color: #your-brand-color;
  --cookie-bg-light: #ffffff;
  --cookie-bg-dark: #1a1a1a;
  --cookie-text-light: #333333;
  --cookie-text-dark: #ffffff;
  --cookie-border-radius: 8px;
  --cookie-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
```

### Message Customization

```javascript
const cookieConsent = new CookieConsentBanner({
  message: 'Your custom consent message here.',
  acceptAllText: 'Accept All Cookies',
  managePreferencesText: 'Cookie Settings',
  savePreferencesText: 'Save My Preferences',
  cancelText: 'Cancel'
});
```

### Advanced Styling

Add custom CSS classes for complete control:

```css
.cookie-banner {
  /* Custom banner styles */
}

.cookie-banner__button--primary {
  /* Custom primary button styles */
}

.preferences-modal {
  /* Custom modal styles */
}
```

## API Reference

### ConsentManager Methods

```javascript
// Check current consent status
const status = ConsentManager.getConsentStatus(); // 'accepted' | 'custom' | null

// Get specific category consent
const analyticsConsent = ConsentManager.getCategoryConsent('analytics');

// Set category consent
ConsentManager.setCategoryConsent('analytics', true);

// Clear all consent
ConsentManager.clearAllConsent();

// Check if consent is required
const required = ConsentManager.isConsentRequired();
```

### Event Callbacks

```javascript
const cookieConsent = new CookieConsentBanner({
  onConsentChange: (consentStatus) => {
    // Called when consent status changes
    console.log('New consent status:', consentStatus);
  },
  onBannerShow: () => {
    // Called when banner is displayed
    console.log('Banner shown');
  },
  onBannerHide: () => {
    // Called when banner is hidden
    console.log('Banner hidden');
  },
  onPreferencesOpen: () => {
    // Called when preferences modal opens
    console.log('Preferences opened');
  },
  onPreferencesClose: () => {
    // Called when preferences modal closes
    console.log('Preferences closed');
  }
});
```

## Browser Support

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+
- iOS Safari 12+
- Android Chrome 60+

## Performance

- **Bundle Size**: ~15KB minified + gzipped
- **Load Time**: <100ms initialization
- **Memory Usage**: <1MB runtime
- **No Dependencies**: Pure JavaScript implementation

## Troubleshooting

### Common Issues

**Banner not showing:**
- Check if consent is already stored in localStorage
- Verify CSS is properly loaded
- Ensure JavaScript is executed after DOM load

**Styles not applying:**
- Check CSS custom properties are supported
- Verify CSS file is loaded before component initialization
- Check for CSS conflicts with existing styles

**Analytics not loading:**
- Verify consent status is 'accepted' or analytics category is enabled
- Check analytics configuration is correct
- Ensure network requests are not blocked

### Debug Mode

Enable debug logging:

```javascript
const cookieConsent = new CookieConsentBanner({
  debug: true, // Enables console logging
  // other options...
});
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Check existing documentation
- Review the examples in the `/integrations` folder