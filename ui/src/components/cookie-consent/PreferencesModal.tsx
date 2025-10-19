// PreferencesModal component - detailed cookie preferences interface
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { PreferencesModalProps } from './types';

export const PreferencesModal: React.FC<PreferencesModalProps> = ({
  isOpen,
  onClose,
  onSave,
  currentPreferences,
  primaryColor = '#007bff',
  darkMode = false
}) => {
  const { t } = useTranslation();
  const modalRef = useRef<HTMLDivElement>(null);
  const firstFocusableRef = useRef<HTMLButtonElement>(null);
  const lastFocusableRef = useRef<HTMLButtonElement>(null);
  const [preferences, setPreferences] = useState(currentPreferences);

  // Focus trapping effect
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
        return;
      }

      if (event.key === 'Tab') {
        const focusableElements = modalRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        
        if (!focusableElements || focusableElements.length === 0) return;

        const firstElement = focusableElements[0] as HTMLElement;
        const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;

        if (event.shiftKey) {
          if (document.activeElement === firstElement) {
            event.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            event.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    
    // Focus the first focusable element when modal opens
    setTimeout(() => {
      firstFocusableRef.current?.focus();
    }, 100);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  // Handle backdrop click
  const handleBackdropClick = (event: React.MouseEvent) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  // Handle save preferences
  const handleSave = () => {
    try {
      // Update consent status to 'custom' when saving preferences
      const updatedPreferences = {
        ...preferences,
        timestamp: Date.now(),
        version: '1.0.0'
      };
      
      onSave(updatedPreferences);
      onClose();
    } catch (error) {
      console.error('Failed to save cookie preferences:', error);
      // In a real application, you might want to show an error message to the user
    }
  };

  // Handle cancel
  const handleCancel = () => {
    setPreferences(currentPreferences); // Reset to original preferences
    onClose();
  };

  // Reset preferences when modal opens with new currentPreferences
  useEffect(() => {
    setPreferences(currentPreferences);
  }, [currentPreferences, isOpen]);

  // Cleanup effect when modal closes
  useEffect(() => {
    if (!isOpen) {
      // Reset preferences to current when modal closes without saving
      setPreferences(currentPreferences);
    }
  }, [isOpen, currentPreferences]);

  if (!isOpen) return null;

  return (
    <div 
      className={`cookie-preferences-overlay ${darkMode ? 'cookie-preferences-overlay--dark' : ''}`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cookie-preferences-title"
      aria-describedby="cookie-preferences-description"
      data-testid="preferences-modal"
    >
      <div 
        ref={modalRef}
        className="cookie-preferences-modal"
        style={{ '--cookie-primary-color': primaryColor } as React.CSSProperties}
      >
        <div className="cookie-preferences-header">
          <h2 id="cookie-preferences-title" className="cookie-preferences-title">
            {t('cookieConsent.preferences.title')}
          </h2>
          <button
            ref={firstFocusableRef}
            className="cookie-preferences-close"
            onClick={onClose}
            aria-label={t('cookieConsent.preferences.closeAriaLabel')}
            type="button"
          >
            <span aria-hidden="true">&times;</span>
          </button>
        </div>

        <div className="cookie-preferences-content">
          <p id="cookie-preferences-description" className="cookie-preferences-description">
            {t('cookieConsent.preferences.description')}
          </p>

          <div className="cookie-categories">
            {/* Essential Cookies - Always enabled */}
            <div className="cookie-category">
              <div className="cookie-category-header">
                <h3 className="cookie-category-title">{t('cookieConsent.preferences.categories.essential.title')}</h3>
                <div className="cookie-category-toggle">
                  <input
                    type="checkbox"
                    id="essential-cookies"
                    checked={true}
                    disabled={true}
                    className="cookie-toggle-input"
                    aria-describedby="essential-description"
                  />
                  <label htmlFor="essential-cookies" className="cookie-toggle-label">
                    <span className="cookie-toggle-slider"></span>
                    <span className="sr-only">{t('cookieConsent.preferences.categories.essential.ariaLabel')}</span>
                  </label>
                  <span className="cookie-toggle-status">{t('cookieConsent.preferences.categories.essential.alwaysOn')}</span>
                </div>
              </div>
              <p id="essential-description" className="cookie-category-description">
                {t('cookieConsent.preferences.categories.essential.description')}
              </p>
            </div>

            {/* Analytics Cookies */}
            <div className="cookie-category">
              <div className="cookie-category-header">
                <h3 className="cookie-category-title">{t('cookieConsent.preferences.categories.analytics.title')}</h3>
                <div className="cookie-category-toggle">
                  <input
                    type="checkbox"
                    id="analytics-cookies"
                    checked={preferences.analytics}
                    onChange={(e) => setPreferences(prev => ({ ...prev, analytics: e.target.checked }))}
                    className="cookie-toggle-input"
                    aria-describedby="analytics-description"
                  />
                  <label htmlFor="analytics-cookies" className="cookie-toggle-label">
                    <span className="cookie-toggle-slider"></span>
                    <span className="sr-only">
                      {preferences.analytics ? t('cookieConsent.preferences.categories.analytics.disableAriaLabel') : t('cookieConsent.preferences.categories.analytics.enableAriaLabel')}
                    </span>
                  </label>
                  <span className="cookie-toggle-status">
                    {preferences.analytics ? t('cookieConsent.preferences.categories.analytics.on') : t('cookieConsent.preferences.categories.analytics.off')}
                  </span>
                </div>
              </div>
              <p id="analytics-description" className="cookie-category-description">
                {t('cookieConsent.preferences.categories.analytics.description')}
              </p>
            </div>

            {/* Marketing Cookies */}
            <div className="cookie-category">
              <div className="cookie-category-header">
                <h3 className="cookie-category-title">{t('cookieConsent.preferences.categories.marketing.title')}</h3>
                <div className="cookie-category-toggle">
                  <input
                    type="checkbox"
                    id="marketing-cookies"
                    checked={preferences.marketing}
                    onChange={(e) => setPreferences(prev => ({ ...prev, marketing: e.target.checked }))}
                    className="cookie-toggle-input"
                    aria-describedby="marketing-description"
                  />
                  <label htmlFor="marketing-cookies" className="cookie-toggle-label">
                    <span className="cookie-toggle-slider"></span>
                    <span className="sr-only">
                      {preferences.marketing ? t('cookieConsent.preferences.categories.marketing.disableAriaLabel') : t('cookieConsent.preferences.categories.marketing.enableAriaLabel')}
                    </span>
                  </label>
                  <span className="cookie-toggle-status">
                    {preferences.marketing ? t('cookieConsent.preferences.categories.marketing.on') : t('cookieConsent.preferences.categories.marketing.off')}
                  </span>
                </div>
              </div>
              <p id="marketing-description" className="cookie-category-description">
                {t('cookieConsent.preferences.categories.marketing.description')}
              </p>
            </div>
          </div>
        </div>

        <div className="cookie-preferences-footer">
          <button
            className="cookie-preferences-button cookie-preferences-button--secondary"
            onClick={handleCancel}
            type="button"
          >
            {t('cookieConsent.preferences.cancel')}
          </button>
          <button
            ref={lastFocusableRef}
            className="cookie-preferences-button cookie-preferences-button--primary"
            onClick={handleSave}
            type="button"
          >
            {t('cookieConsent.preferences.savePreferences')}
          </button>
        </div>
      </div>
    </div>
  );
};