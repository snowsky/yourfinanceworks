// Main CookieConsentBanner component - orchestrates the entire consent system
import React, { useEffect, useState, useCallback, useRef, useImperativeHandle, forwardRef } from 'react';
import { ConsentBanner } from './ConsentBanner';
import { PreferencesModal } from './PreferencesModal';
import { ConsentManager } from './services/ConsentManager';
import { AnalyticsIntegration } from './services/AnalyticsIntegration';
import { getThemeClass, createThemeObserver } from './utils/theme';
import type { CookieConsentProps, ConsentStatus, ConsentPreferences } from './types';

// Ref interface for programmatic control
export interface CookieConsentRef {
  getConsentStatus: () => ConsentStatus;
  getPreferences: () => ConsentPreferences;
  acceptAll: () => void;
  openPreferences: () => void;
  clearConsent: () => void;
  updateAnalyticsConfig: (config: Partial<typeof analyticsConfig>) => void;
}
import './styles/cookie-consent.css';

export const CookieConsentBanner = forwardRef<CookieConsentRef, CookieConsentProps>(({
  primaryColor = '#007bff',
  darkMode,
  position = 'bottom',
  message = "We use cookies to improve your experience. By continuing, you agree to our use of cookies.",
  onConsentChange,
  analyticsConfig = {}
}, ref) => {
  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const themeObserverRef = useRef<MediaQueryList | null>(null);

  // State management
  const [consentStatus, setConsentStatus] = useState<ConsentStatus>(null);
  const [showBanner, setShowBanner] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [currentTheme, setCurrentTheme] = useState<string>(() => getThemeClass(darkMode));
  const [currentPreferences, setCurrentPreferences] = useState<ConsentPreferences>({
    essential: true,
    analytics: false,
    marketing: false,
    timestamp: Date.now(),
    version: '1.0.0'
  });

  // Service instances
  const [consentManager] = useState(() => new ConsentManager());
  const [analyticsIntegration] = useState(() => new AnalyticsIntegration(analyticsConfig));

  // Theme management effect
  useEffect(() => {
    if (darkMode === undefined) {
      // Auto-detect system preference and listen for changes
      themeObserverRef.current = createThemeObserver((isDark) => {
        const newTheme = isDark ? 'dark' : 'light';
        setCurrentTheme(newTheme);
      });
      
      // Set initial theme
      setCurrentTheme(getThemeClass(darkMode));
    } else {
      // Use explicit theme setting
      setCurrentTheme(darkMode ? 'dark' : 'light');
    }

    // Cleanup theme observer on unmount
    return () => {
      if (themeObserverRef.current) {
        themeObserverRef.current.removeEventListener('change', () => {});
      }
    };
  }, [darkMode]);

  // Apply theme and custom properties to container
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.setAttribute('data-theme', currentTheme);
      
      // Apply custom CSS properties for theming
      const customProperties = {
        '--cookie-primary-color': primaryColor,
        '--cookie-primary-hover': `${primaryColor}dd`,
        '--cookie-primary-active': `${primaryColor}bb`,
        '--cookie-position': position
      };

      Object.entries(customProperties).forEach(([property, value]) => {
        containerRef.current?.style.setProperty(property, value);
      });
    }
  }, [currentTheme, primaryColor, position]);

  // Check existing consent on mount
  useEffect(() => {
    const existingConsent = consentManager.getConsentStatus();
    const existingPreferences = consentManager.getConsentPreferences();
    
    setConsentStatus(existingConsent);
    setCurrentPreferences(existingPreferences);
    
    // Show banner only if consent is required
    if (consentManager.isConsentRequired()) {
      setShowBanner(true);
    } else {
      // Load analytics scripts if consent already exists
      analyticsIntegration.loadScripts(existingPreferences);
    }
  }, [consentManager, analyticsIntegration]);

  // Handle consent change notifications
  const handleConsentChange = useCallback((newStatus: ConsentStatus, preferences: ConsentPreferences) => {
    try {
      setConsentStatus(newStatus);
      setCurrentPreferences(preferences);
      
      // Notify parent component
      onConsentChange?.(newStatus);
      
      // Handle analytics integration
      analyticsIntegration.handleConsentChange(preferences);

      // Dispatch custom event for external listeners
      const consentEvent = new CustomEvent('cookieConsentChange', {
        detail: {
          status: newStatus,
          preferences,
          timestamp: Date.now()
        }
      });
      window.dispatchEvent(consentEvent);

    } catch (error) {
      console.error('Error handling consent change:', error);
    }
  }, [onConsentChange, analyticsIntegration]);

  // Handle "Accept All" button click
  const handleAcceptAll = useCallback(() => {
    try {
      const allAcceptedPreferences: ConsentPreferences = {
        essential: true,
        analytics: true,
        marketing: true,
        timestamp: Date.now(),
        version: '1.0.0'
      };

      // Update consent manager
      consentManager.setConsentStatus('accepted');
      consentManager.setConsentPreferences(allAcceptedPreferences);

      // Update state and hide banner
      handleConsentChange('accepted', allAcceptedPreferences);
      setShowBanner(false);

      // Announce to screen readers
      const announcement = document.createElement('div');
      announcement.setAttribute('aria-live', 'polite');
      announcement.setAttribute('aria-atomic', 'true');
      announcement.className = 'sr-only';
      announcement.textContent = 'All cookies have been accepted. Cookie preferences saved.';
      document.body.appendChild(announcement);
      setTimeout(() => {
        if (document.body.contains(announcement)) {
          document.body.removeChild(announcement);
        }
      }, 1000);

    } catch (error) {
      console.error('Error accepting all cookies:', error);
      // Could show user-facing error message here
    }
  }, [consentManager, handleConsentChange]);

  // Handle "Manage Preferences" button click
  const handleManagePreferences = useCallback(() => {
    setShowModal(true);
  }, []);

  // Handle modal close
  const handleModalClose = useCallback(() => {
    setShowModal(false);
  }, []);

  // Handle preference save from modal
  const handlePreferenceSave = useCallback((preferences: Partial<ConsentPreferences>) => {
    try {
      const updatedPreferences: ConsentPreferences = {
        ...currentPreferences,
        ...preferences,
        essential: true, // Always true
        timestamp: Date.now(),
        version: '1.0.0'
      };

      // Update consent manager
      consentManager.setConsentStatus('custom');
      consentManager.setConsentPreferences(updatedPreferences);

      // Update state and hide banner/modal
      handleConsentChange('custom', updatedPreferences);
      setShowBanner(false);
      setShowModal(false);

      // Announce to screen readers
      const announcement = document.createElement('div');
      announcement.setAttribute('aria-live', 'polite');
      announcement.setAttribute('aria-atomic', 'true');
      announcement.className = 'sr-only';
      announcement.textContent = 'Cookie preferences have been saved successfully.';
      document.body.appendChild(announcement);
      setTimeout(() => {
        if (document.body.contains(announcement)) {
          document.body.removeChild(announcement);
        }
      }, 1000);

    } catch (error) {
      console.error('Error saving cookie preferences:', error);
      // Could show user-facing error message here
    }
  }, [currentPreferences, consentManager, handleConsentChange]);

  // Programmatic control methods
  const clearConsent = useCallback(() => {
    try {
      consentManager.clearAllConsent();
      analyticsIntegration.cleanup();
      
      const defaultPreferences: ConsentPreferences = {
        essential: true,
        analytics: false,
        marketing: false,
        timestamp: Date.now(),
        version: '1.0.0'
      };

      setConsentStatus(null);
      setCurrentPreferences(defaultPreferences);
      setShowBanner(true);
      setShowModal(false);

      // Notify about consent clearing
      handleConsentChange(null, defaultPreferences);
    } catch (error) {
      console.error('Error clearing consent:', error);
    }
  }, [consentManager, analyticsIntegration, handleConsentChange]);

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    getConsentStatus: () => consentStatus,
    getPreferences: () => currentPreferences,
    acceptAll: handleAcceptAll,
    openPreferences: handleManagePreferences,
    clearConsent,
    updateAnalyticsConfig: (config) => {
      analyticsIntegration.updateConfig(config);
    }
  }), [consentStatus, currentPreferences, handleAcceptAll, handleManagePreferences, clearConsent, analyticsIntegration]);

  // Listen for custom events to open preferences
  useEffect(() => {
    const handleOpenPreferences = () => {
      setShowModal(true);
    };

    window.addEventListener('openCookiePreferences', handleOpenPreferences);
    window.addEventListener('openPreferences', handleOpenPreferences); // Legacy support

    return () => {
      window.removeEventListener('openCookiePreferences', handleOpenPreferences);
      window.removeEventListener('openPreferences', handleOpenPreferences);
    };
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      analyticsIntegration.cleanup();
    };
  }, [analyticsIntegration]);

  // Determine effective dark mode state
  const effectiveDarkMode = currentTheme === 'dark';

  return (
    <div 
      ref={containerRef}
      className={`cookie-consent-system cookie-consent-system--${position}`}
      data-testid="cookie-consent-banner"
      data-theme={currentTheme}
      data-position={position}
    >
      {/* Consent Banner */}
      <ConsentBanner
        message={message}
        primaryColor={primaryColor}
        darkMode={effectiveDarkMode}
        onAcceptAll={handleAcceptAll}
        onManagePreferences={handleManagePreferences}
        visible={showBanner}
      />

      {/* Preferences Modal */}
      <PreferencesModal
        isOpen={showModal}
        onClose={handleModalClose}
        onSave={handlePreferenceSave}
        currentPreferences={currentPreferences}
        primaryColor={primaryColor}
        darkMode={effectiveDarkMode}
      />
    </div>
  );
});

CookieConsentBanner.displayName = 'CookieConsentBanner';