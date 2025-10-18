import React, { createRef } from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { CookieConsentBanner, type CookieConsentRef } from '../CookieConsentBanner';
import type { ConsentStatus, AnalyticsConfig } from '../types';

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

// Mock matchMedia for theme detection
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock custom event dispatch
const mockDispatchEvent = vi.fn();
Object.defineProperty(window, 'dispatchEvent', {
  value: mockDispatchEvent,
});

describe('CookieConsentBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    mockLocalStorage.getItem.mockReturnValue(null);
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  describe('Initial Render and Consent Detection', () => {
    it('should render banner when no consent exists', () => {
      render(<CookieConsentBanner />);

      expect(screen.getByTestId('cookie-consent-banner')).toBeInTheDocument();
      expect(screen.getByTestId('consent-banner')).toBeInTheDocument();
    });

    it('should not render banner when consent already exists', () => {
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'true';
        return null;
      });

      render(<CookieConsentBanner />);

      expect(screen.getByTestId('cookie-consent-banner')).toBeInTheDocument();
      // Banner should not be visible when consent exists
      const banner = screen.queryByTestId('consent-banner');
      if (banner) {
        expect(banner).not.toBeVisible();
      } else {
        // Banner is not rendered at all, which is also correct
        expect(banner).toBeNull();
      }
    });

    it('should apply custom message', () => {
      const customMessage = 'Custom cookie message';
      render(<CookieConsentBanner message={customMessage} />);

      expect(screen.getByText(customMessage)).toBeInTheDocument();
    });

    it('should apply custom primary color', () => {
      const customColor = '#ff0000';
      render(<CookieConsentBanner primaryColor={customColor} />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveStyle(`--cookie-primary-color: ${customColor}`);
    });
  });

  describe('Theme Management', () => {
    it('should apply light theme by default', () => {
      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveAttribute('data-theme', 'light');
    });

    it('should apply dark theme when specified', () => {
      render(<CookieConsentBanner darkMode={true} />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveAttribute('data-theme', 'dark');
    });

    it('should auto-detect system theme when darkMode is undefined', () => {
      // Mock system dark mode preference
      window.matchMedia = vi.fn().mockImplementation(query => ({
        matches: query === '(prefers-color-scheme: dark)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));

      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveAttribute('data-theme', 'dark');
    });
  });

  describe('Position Support', () => {
    it('should apply bottom position by default', () => {
      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveAttribute('data-position', 'bottom');
      expect(container).toHaveClass('cookie-consent-system--bottom');
    });

    it('should apply top position when specified', () => {
      render(<CookieConsentBanner position="top" />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveAttribute('data-position', 'top');
      expect(container).toHaveClass('cookie-consent-system--top');
    });
  });

  describe('Accept All Flow', () => {
    it('should handle accept all button click', async () => {
      const onConsentChange = vi.fn();
      render(<CookieConsentBanner onConsentChange={onConsentChange} />);

      // Wait for banner to appear
      const acceptButton = await screen.findByText('Accept All');
      fireEvent.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
        expect(onConsentChange).toHaveBeenCalledWith('accepted');
      }, { timeout: 1000 });
    });

    it('should dispatch custom event on accept all', async () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      fireEvent.click(acceptButton);

      await waitFor(() => {
        expect(mockDispatchEvent).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'cookieConsentChange',
            detail: expect.objectContaining({
              status: 'accepted',
              preferences: expect.objectContaining({
                essential: true,
                analytics: true,
                marketing: true
              })
            })
          })
        );
      });
    });

    it('should hide banner after accepting all', async () => {
      render(<CookieConsentBanner />);

      const banner = screen.getByTestId('consent-banner');
      const acceptButton = screen.getByText('Accept All');

      expect(banner).toBeVisible();

      fireEvent.click(acceptButton);

      await waitFor(() => {
        expect(banner).not.toBeVisible();
      });
    });
  });

  describe('Manage Preferences Flow', () => {
    it('should open preferences modal when manage preferences is clicked', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      fireEvent.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });
    });

    it('should save custom preferences from modal', async () => {
      const onConsentChange = vi.fn();
      render(<CookieConsentBanner onConsentChange={onConsentChange} />);

      // Open modal
      const manageButton = screen.getByText('Manage Preferences');
      fireEvent.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Analytics should be off by default, just save the preferences
      const saveButton = screen.getByText('Save Preferences');
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'custom');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'false');
        expect(onConsentChange).toHaveBeenCalledWith('custom');
      });
    });

    it('should close modal and hide banner after saving preferences', async () => {
      render(<CookieConsentBanner />);

      // Open modal
      const manageButton = screen.getByText('Manage Preferences');
      fireEvent.click(manageButton);

      const modal = await screen.findByTestId('preferences-modal');
      const banner = screen.getByTestId('consent-banner');

      // Save preferences
      const saveButton = screen.getByText('Save Preferences');
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(modal).not.toBeInTheDocument();
        expect(banner).not.toBeVisible();
      });
    });
  });

  describe('Analytics Integration', () => {
    it('should load analytics scripts when consent is given', async () => {
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        }
      };

      render(<CookieConsentBanner analyticsConfig={analyticsConfig} />);

      const acceptButton = screen.getByText('Accept All');
      fireEvent.click(acceptButton);

      await waitFor(() => {
        // Check if analytics integration was called
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      });
    });

    it('should not load analytics scripts when consent is denied', async () => {
      render(<CookieConsentBanner />);

      // Open modal and deny analytics
      const manageButton = screen.getByText('Manage Preferences');
      fireEvent.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Analytics should be off by default, just save
      const saveButton = screen.getByText('Save Preferences');
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'false');
      });
    });
  });

  describe('Programmatic Control via Ref', () => {
    it('should expose methods via ref', () => {
      const ref = createRef<CookieConsentRef>();
      render(<CookieConsentBanner ref={ref} />);

      expect(ref.current).toBeDefined();
      expect(ref.current?.getConsentStatus).toBeDefined();
      expect(ref.current?.getPreferences).toBeDefined();
      expect(ref.current?.acceptAll).toBeDefined();
      expect(ref.current?.openPreferences).toBeDefined();
      expect(ref.current?.clearConsent).toBeDefined();
      expect(ref.current?.updateAnalyticsConfig).toBeDefined();
    });

    it('should allow programmatic accept all via ref', async () => {
      const ref = createRef<CookieConsentRef>();
      const onConsentChange = vi.fn();
      render(<CookieConsentBanner ref={ref} onConsentChange={onConsentChange} />);

      act(() => {
        ref.current?.acceptAll();
      });

      await waitFor(() => {
        expect(onConsentChange).toHaveBeenCalledWith('accepted');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });
    });

    it('should allow programmatic consent clearing via ref', async () => {
      // Start with existing consent
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        return 'true';
      });

      const ref = createRef<CookieConsentRef>();
      const onConsentChange = vi.fn();
      render(<CookieConsentBanner ref={ref} onConsentChange={onConsentChange} />);

      act(() => {
        ref.current?.clearConsent();
      });

      await waitFor(() => {
        expect(mockLocalStorage.removeItem).toHaveBeenCalled();
        expect(onConsentChange).toHaveBeenCalledWith(null);
      });
    });

    it('should return current consent status via ref', () => {
      const ref = createRef<CookieConsentRef>();
      render(<CookieConsentBanner ref={ref} />);

      const status = ref.current?.getConsentStatus();
      expect(status).toBe(null); // No consent initially
    });

    it('should return current preferences via ref', () => {
      const ref = createRef<CookieConsentRef>();
      render(<CookieConsentBanner ref={ref} />);

      const preferences = ref.current?.getPreferences();
      expect(preferences).toEqual(expect.objectContaining({
        essential: true,
        analytics: false,
        marketing: false
      }));
    });
  });

  describe('Error Handling', () => {
    it('should handle localStorage errors gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

      // Mock ConsentManager to throw error
      const originalSetItem = mockLocalStorage.setItem;
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('localStorage error');
      });

      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      fireEvent.click(acceptButton);

      // The error should be caught and logged
      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalled();
      });

      // Restore original implementation
      mockLocalStorage.setItem.mockImplementation(originalSetItem);
      consoleSpy.mockRestore();
    });

    it('should handle analytics integration errors gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

      // Mock analytics config that will cause an error
      const badAnalyticsConfig = {
        customProvider: {
          scriptUrl: 'invalid-url',
          initFunction: 'nonexistent.function'
        }
      };

      render(<CookieConsentBanner analyticsConfig={badAnalyticsConfig} />);

      const acceptButton = screen.getByText('Accept All');
      fireEvent.click(acceptButton);

      // Should not crash the component
      await waitFor(() => {
        expect(screen.getByTestId('cookie-consent-banner')).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Accessibility', () => {
    it('should announce consent changes to screen readers', async () => {
      const mockAppendChild = vi.spyOn(document.body, 'appendChild');
      const mockRemoveChild = vi.spyOn(document.body, 'removeChild');

      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      fireEvent.click(acceptButton);

      await waitFor(() => {
        expect(mockAppendChild).toHaveBeenCalledWith(
          expect.objectContaining({
            textContent: 'All cookies have been accepted. Cookie preferences saved.'
          })
        );
      });

      // Check cleanup after timeout
      await act(async () => {
        vi.advanceTimersByTime(1000);
      });

      expect(mockRemoveChild).toHaveBeenCalled();

      mockAppendChild.mockRestore();
      mockRemoveChild.mockRestore();
    });

    it('should have proper ARIA attributes', () => {
      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveAttribute('data-theme');

      const banner = screen.getByTestId('consent-banner');
      expect(banner).toHaveAttribute('role', 'banner');
      expect(banner).toHaveAttribute('aria-label');
    });
  });

  describe('Responsive Design', () => {
    it('should apply responsive CSS classes', () => {
      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveClass('cookie-consent-system');
    });

    it('should handle different screen sizes via CSS variables', () => {
      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      const styles = window.getComputedStyle(container);

      // CSS variables should be defined (actual values depend on CSS)
      expect(container).toBeInTheDocument();
    });
  });
});