import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { CookieConsentBanner } from '../../CookieConsentBanner';
import type { ConsentStatus, AnalyticsConfig } from '../../types';

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

// Mock matchMedia
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

describe('Cookie Consent Banner - End-to-End Tests', () => {
  let user: ReturnType<typeof userEvent.setup>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.getItem.mockReturnValue(null);
    user = userEvent.setup();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Complete User Flow - Accept All', () => {
    it('should complete full accept all flow from banner to consent storage', async () => {
      const onConsentChange = vi.fn();
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        }
      };

      render(
        <CookieConsentBanner 
          onConsentChange={onConsentChange}
          analyticsConfig={analyticsConfig}
        />
      );

      // Step 1: Verify banner is visible on first visit
      expect(screen.getByTestId('consent-banner')).toBeVisible();
      expect(screen.getByText(/We use cookies to improve your experience/)).toBeInTheDocument();

      // Step 2: Click Accept All button
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Step 3: Verify consent is stored
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_essential', 'true');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_marketing', 'true');
      });

      // Step 4: Verify callback is called
      expect(onConsentChange).toHaveBeenCalledWith('accepted');

      // Step 5: Verify banner is hidden
      await waitFor(() => {
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });

      // Step 6: Verify custom event is dispatched
      expect(window.dispatchEvent).toHaveBeenCalledWith(
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

    it('should not show banner on subsequent visits after accepting', () => {
      // Mock existing consent
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'true';
        return null;
      });

      render(<CookieConsentBanner />);

      // Banner should not be visible
      const banner = screen.queryByTestId('consent-banner');
      if (banner) {
        expect(banner).not.toBeVisible();
      } else {
        expect(banner).toBeNull();
      }
    });
  });

  describe('Complete User Flow - Custom Preferences', () => {
    it('should complete full custom preferences flow', async () => {
      const onConsentChange = vi.fn();

      render(<CookieConsentBanner onConsentChange={onConsentChange} />);

      // Step 1: Verify banner is visible
      expect(screen.getByTestId('consent-banner')).toBeVisible();

      // Step 2: Click Manage Preferences
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      // Step 3: Verify modal opens
      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Step 4: Verify modal content
      expect(screen.getByText('Cookie Preferences')).toBeInTheDocument();
      expect(screen.getByText('Essential Cookies')).toBeInTheDocument();
      expect(screen.getByText('Analytics Cookies')).toBeInTheDocument();
      expect(screen.getByText('Marketing Cookies')).toBeInTheDocument();

      // Step 5: Toggle analytics cookies on
      const analyticsToggle = screen.getByRole('checkbox', { name: /analytics cookies/i });
      await user.click(analyticsToggle);

      // Step 6: Keep marketing cookies off (default)
      const marketingToggle = screen.getByRole('checkbox', { name: /marketing cookies/i });
      expect(marketingToggle).not.toBeChecked();

      // Step 7: Save preferences
      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Step 8: Verify custom consent is stored
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'custom');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_marketing', 'false');
      });

      // Step 9: Verify callback is called
      expect(onConsentChange).toHaveBeenCalledWith('custom');

      // Step 10: Verify modal closes and banner hides
      await waitFor(() => {
        expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });
    });

    it('should handle modal cancellation correctly', async () => {
      render(<CookieConsentBanner />);

      // Open modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Toggle some preferences
      const analyticsToggle = screen.getByRole('checkbox', { name: /analytics cookies/i });
      await user.click(analyticsToggle);

      // Cancel instead of saving
      const cancelButton = screen.getByText('Cancel');
      await user.click(cancelButton);

      // Verify modal closes without saving
      await waitFor(() => {
        expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
      });

      // Verify no consent was stored
      expect(mockLocalStorage.setItem).not.toHaveBeenCalledWith('cookieConsent', 'custom');

      // Banner should still be visible
      expect(screen.getByTestId('consent-banner')).toBeVisible();
    });
  });

  describe('Keyboard Navigation Flow', () => {
    it('should support complete keyboard navigation', async () => {
      render(<CookieConsentBanner />);

      // Tab to Accept All button
      await user.tab();
      expect(screen.getByText('Accept All')).toHaveFocus();

      // Tab to Manage Preferences button
      await user.tab();
      expect(screen.getByText('Manage Preferences')).toHaveFocus();

      // Press Enter to open modal
      await user.keyboard('{Enter}');

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Tab through modal elements
      await user.tab(); // Should focus first toggle
      const analyticsToggle = screen.getByRole('checkbox', { name: /analytics cookies/i });
      expect(analyticsToggle).toHaveFocus();

      // Space to toggle
      await user.keyboard(' ');
      expect(analyticsToggle).toBeChecked();

      // Tab to next toggle
      await user.tab();
      const marketingToggle = screen.getByRole('checkbox', { name: /marketing cookies/i });
      expect(marketingToggle).toHaveFocus();

      // Tab to Save button
      await user.tab();
      await user.tab(); // Skip Cancel button
      const saveButton = screen.getByText('Save Preferences');
      expect(saveButton).toHaveFocus();

      // Press Enter to save
      await user.keyboard('{Enter}');

      // Verify preferences saved
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'custom');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      });
    });

    it('should trap focus within modal', async () => {
      render(<CookieConsentBanner />);

      // Open modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Tab through all focusable elements
      const focusableElements = [
        screen.getByRole('checkbox', { name: /analytics cookies/i }),
        screen.getByRole('checkbox', { name: /marketing cookies/i }),
        screen.getByText('Cancel'),
        screen.getByText('Save Preferences')
      ];

      // Tab through all elements
      for (const element of focusableElements) {
        await user.tab();
        expect(element).toHaveFocus();
      }

      // One more tab should cycle back to first element
      await user.tab();
      expect(focusableElements[0]).toHaveFocus();
    });
  });

  describe('Theme Switching Flow', () => {
    it('should handle theme changes during interaction', async () => {
      const { rerender } = render(<CookieConsentBanner darkMode={false} />);

      // Verify light theme
      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveAttribute('data-theme', 'light');

      // Switch to dark mode
      rerender(<CookieConsentBanner darkMode={true} />);
      expect(container).toHaveAttribute('data-theme', 'dark');

      // Open modal in dark mode
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        const modal = screen.getByTestId('preferences-modal');
        expect(modal).toBeInTheDocument();
        // Modal should inherit theme from container
        expect(container).toHaveAttribute('data-theme', 'dark');
      });
    });
  });

  describe('Analytics Integration Flow', () => {
    it('should handle analytics loading and consent changes', async () => {
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        },
        customProvider: {
          scriptUrl: 'https://example.com/analytics.js',
          initFunction: 'customAnalytics.init'
        }
      };

      const onConsentChange = vi.fn();

      render(
        <CookieConsentBanner 
          analyticsConfig={analyticsConfig}
          onConsentChange={onConsentChange}
        />
      );

      // Accept all cookies
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Verify analytics consent is granted
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      });

      // Now withdraw consent by opening preferences and disabling analytics
      // First, mock existing consent
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'true';
        return null;
      });

      // Re-render to simulate page reload with existing consent
      const { rerender } = render(
        <CookieConsentBanner 
          analyticsConfig={analyticsConfig}
          onConsentChange={onConsentChange}
        />
      );

      // Banner should not be visible initially
      const banner = screen.queryByTestId('consent-banner');
      if (banner) {
        expect(banner).not.toBeVisible();
      }

      // Use programmatic API to open preferences (simulating settings page)
      const container = screen.getByTestId('cookie-consent-banner');
      fireEvent(container, new CustomEvent('openPreferences'));

      // Modal should open
      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });
    });
  });

  describe('Error Recovery Flow', () => {
    it('should recover from localStorage errors gracefully', async () => {
      // Mock localStorage to throw errors
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });

      const onConsentChange = vi.fn();
      render(<CookieConsentBanner onConsentChange={onConsentChange} />);

      // Should still render banner
      expect(screen.getByTestId('consent-banner')).toBeVisible();

      // Accept all should not crash
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should still call callback even if storage fails
      await waitFor(() => {
        expect(onConsentChange).toHaveBeenCalledWith('accepted');
      });

      // Banner should still hide (using memory storage)
      await waitFor(() => {
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });
    });

    it('should handle modal interaction errors gracefully', async () => {
      render(<CookieConsentBanner />);

      // Open modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Simulate error during preference saving
      mockLocalStorage.setItem.mockImplementationOnce(() => {
        throw new Error('Storage error');
      });

      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Modal should still close gracefully
      await waitFor(() => {
        expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
      });
    });
  });

  describe('Multi-Session Flow', () => {
    it('should maintain consent across browser sessions', () => {
      // Simulate first session - accept cookies
      mockLocalStorage.getItem.mockReturnValue(null);
      
      const { unmount } = render(<CookieConsentBanner />);
      
      const acceptButton = screen.getByText('Accept All');
      fireEvent.click(acceptButton);

      // Verify consent was stored
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');

      unmount();

      // Simulate second session - consent should be remembered
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'true';
        return null;
      });

      render(<CookieConsentBanner />);

      // Banner should not be visible
      const banner = screen.queryByTestId('consent-banner');
      if (banner) {
        expect(banner).not.toBeVisible();
      } else {
        expect(banner).toBeNull();
      }
    });
  });
});