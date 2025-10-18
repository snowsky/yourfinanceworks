// ConsentBanner component - fixed bottom banner for initial consent
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ConsentBannerProps } from './types';

export const ConsentBanner: React.FC<ConsentBannerProps> = ({
  message,
  primaryColor,
  darkMode = false,
  onAcceptAll,
  onManagePreferences,
  visible
}) => {
  const { t } = useTranslation();
  const bannerRef = useRef<HTMLDivElement>(null);
  const acceptButtonRef = useRef<HTMLButtonElement>(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const [shouldRender, setShouldRender] = useState(visible);

  // Handle animation and visibility state
  useEffect(() => {
    if (visible && !shouldRender) {
      // Show animation: render first, then animate in
      setShouldRender(true);
      setIsAnimating(true);

      // Use requestAnimationFrame to ensure DOM is updated before animation
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setIsAnimating(false);
        });
      });
    } else if (!visible && shouldRender) {
      // Hide animation: animate out first, then stop rendering
      setIsAnimating(true);

      const timer = setTimeout(() => {
        setShouldRender(false);
        setIsAnimating(false);
      }, 300); // Match CSS transition duration

      return () => clearTimeout(timer);
    }
  }, [visible, shouldRender]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!visible) return;

      // Escape key to focus on manage preferences (less intrusive option)
      if (event.key === 'Escape') {
        const manageButton = bannerRef.current?.querySelector('[data-action="manage"]') as HTMLButtonElement;
        manageButton?.focus();
      }

      // Tab trapping within banner when focused
      if (event.key === 'Tab' && bannerRef.current?.contains(document.activeElement)) {
        const focusableElements = bannerRef.current.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );

        const firstElement = focusableElements[0] as HTMLElement;
        const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;

        if (event.shiftKey && document.activeElement === firstElement) {
          event.preventDefault();
          lastElement?.focus();
        } else if (!event.shiftKey && document.activeElement === lastElement) {
          event.preventDefault();
          firstElement?.focus();
        }
      }
    };

    if (visible) {
      document.addEventListener('keydown', handleKeyDown);
      // Auto-focus on the banner when it becomes visible for screen readers
      const focusTimer = setTimeout(() => {
        bannerRef.current?.focus();
      }, 350); // Wait for animation to complete

      return () => {
        document.removeEventListener('keydown', handleKeyDown);
        clearTimeout(focusTimer);
      };
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [visible]);

  if (!shouldRender) {
    return null;
  }

  const bannerStyle = primaryColor ? {
    '--cookie-primary-color': primaryColor,
    '--cookie-primary-hover': `${primaryColor}dd`,
    '--cookie-primary-active': `${primaryColor}bb`
  } as React.CSSProperties : {};

  const handleAcceptAll = () => {
    onAcceptAll();
    // Announce to screen readers
    const announcement = document.createElement('div');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.className = 'sr-only';
    announcement.textContent = t('cookieConsent.banner.acceptedAnnouncement');
    document.body.appendChild(announcement);
    setTimeout(() => document.body.removeChild(announcement), 1000);
  };

  const handleManagePreferences = () => {
    onManagePreferences();
    // Announce to screen readers
    const announcement = document.createElement('div');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.className = 'sr-only';
    announcement.textContent = t('cookieConsent.banner.preferencesAnnouncement');
    document.body.appendChild(announcement);
    setTimeout(() => document.body.removeChild(announcement), 1000);
  };

  const getAnimationClass = () => {
    if (!visible && isAnimating) return 'cookie-banner--hiding';
    if (visible && !isAnimating) return 'cookie-banner--visible';
    if (visible && isAnimating) return 'cookie-banner--showing';
    return 'cookie-banner--hidden';
  };

  return (
    <div
      ref={bannerRef}
      className={`cookie-banner ${getAnimationClass()}`}
      data-theme={darkMode ? 'dark' : 'light'}
      style={bannerStyle}
      data-testid="consent-banner"
      role="banner"
      aria-label={t('cookieConsent.banner.ariaLabel')}
      aria-describedby="cookie-message"
      tabIndex={-1}
      data-animating={isAnimating}
    >
      <div className="cookie-banner__content">
        <div className="cookie-banner__message">
          <p id="cookie-message" role="status" aria-live="polite">
            {message || t('cookieConsent.banner.message')}
          </p>
        </div>
        <div className="cookie-banner__actions" role="group" aria-label="Cookie consent actions">
          <button
            type="button"
            className="cookie-banner__button cookie-banner__button--secondary"
            onClick={handleManagePreferences}
            aria-label={t('cookieConsent.banner.manageAriaLabel')}
            aria-describedby="cookie-message"
            data-action="manage"
          >
            {t('cookieConsent.banner.managePreferences')}
          </button>
          <button
            ref={acceptButtonRef}
            type="button"
            className="cookie-banner__button cookie-banner__button--primary"
            onClick={handleAcceptAll}
            aria-label={t('cookieConsent.banner.acceptAriaLabel')}
            aria-describedby="cookie-message"
            data-action="accept"
          >
            {t('cookieConsent.banner.acceptAll')}
          </button>
        </div>
      </div>

      {/* Screen reader only instructions */}
      <div className="sr-only" aria-live="polite">
        {t('cookieConsent.banner.keyboardInstructions')}
      </div>
    </div>
  );
};