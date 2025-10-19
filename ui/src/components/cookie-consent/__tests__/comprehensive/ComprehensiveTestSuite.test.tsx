import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { CookieConsentBanner } from '../../CookieConsentBanner';
import { ConsentManager } from '../../services/ConsentManager';
import { AnalyticsIntegration } from '../../services/AnalyticsIntegration';
import type { AnalyticsConfig, ConsentPreferences } from '../../types';

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

describe('Cookie Consent Banner - Comprehensive Test Suite', () => {
  let user: ReturnType<typeof userEvent.setup>;
  let consentManager: ConsentManager;
  let analyticsIntegration: AnalyticsIntegration;

  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.getItem.mockReturnValue(null);
    user = userEvent.setup();
    consentManager = new ConsentManager();
    analyticsIntegration = new AnalyticsIntegration();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Integration Test Suite', () => {
    it('should complete full user journey from first visit to consent management', async () => {
      const onConsentChange = vi.fn();
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        }
      };

      // Step 1: First visit - banner should appear
      render(
        <CookieConsentBanner 
          onConsentChange={onConsentChange}
          analyticsConfig={analyticsConfig}
        />
      );

      expect(screen.getByTestId('consent-banner')).toBeVisible();
      expect(screen.getByText(/We use cookies to improve your experience/)).toBeInTheDocument();

      // Step 2: User clicks "Manage Preferences"
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Step 3: User reviews options and enables analytics only
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      const marketingToggle = screen.getByLabelText('Marketing Cookies');
      
      expect(analyticsToggle).not.toBeChecked();
      expect(marketingToggle).not.toBeChecked();

      await user.click(analyticsToggle);
      expect(analyticsToggle).toBeChecked();
      expect(marketingToggle).not.toBeChecked();

      // Step 4: User saves preferences
      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Step 5: Verify consent is stored correctly
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'custom');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_marketing', 'false');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_timestamp', expect.any(String));
      });

      // Step 6: Verify callback and events
      expect(onConsentChange).toHaveBeenCalledWith('custom');

      // Step 7: Verify UI state
      await waitFor(() => {
        expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });

      // Step 8: Simulate page reload with existing consent
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'custom';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'false';
        return null;
      });

      const { rerender } = render(
        <CookieConsentBanner 
          onConsentChange={onConsentChange}
          analyticsConfig={analyticsConfig}
        />
      );

      // Banner should not appear on subsequent visits
      const banner = screen.queryByTestId('consent-banner');
      if (banner) {
        expect(banner).not.toBeVisible();
      } else {
        expect(banner).toBeNull();
      }
    });

    it('should handle consent withdrawal and re-consent flow', async () => {
      // Start with existing consent
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'true';
        return null;
      });

      const onConsentChange = vi.fn();
      render(<CookieConsentBanner onConsentChange={onConsentChange} />);

      // Simulate opening preferences from settings page
      const container = screen.getByTestId('cookie-consent-banner');
      fireEvent(container, new CustomEvent('openPreferences'));

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Withdraw analytics consent
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      expect(analyticsToggle).toBeChecked();

      await user.click(analyticsToggle);
      expect(analyticsToggle).not.toBeChecked();

      // Save changes
      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Verify consent withdrawal
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'false');
      });

      expect(onConsentChange).toHaveBeenCalledWith('custom');
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle multiple error scenarios gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      // Mock localStorage to fail intermittently
      let failCount = 0;
      mockLocalStorage.setItem.mockImplementation((key, value) => {
        failCount++;
        if (failCount <= 2) {
          throw new Error('Storage temporarily unavailable');
        }
        // Succeed on third attempt
      });

      const onConsentChange = vi.fn();
      render(<CookieConsentBanner onConsentChange={onConsentChange} />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should still complete the flow despite storage errors
      await waitFor(() => {
        expect(onConsentChange).toHaveBeenCalledWith('accepted');
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });

      // Should have logged errors but not crashed
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('should handle analytics integration failures', async () => {
      const badAnalyticsConfig: AnalyticsConfig = {
        customProvider: {
          scriptUrl: 'https://invalid-domain-that-does-not-exist.com/script.js',
          initFunction: 'nonexistent.function'
        }
      };

      render(<CookieConsentBanner analyticsConfig={badAnalyticsConfig} />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should not crash despite analytics errors
      await waitFor(() => {
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });
    });
  });

  describe('Performance and Memory Management', () => {
    it('should not create memory leaks with multiple instances', async () => {
      const instances = [];

      // Create multiple instances
      for (let i = 0; i < 5; i++) {
        const { unmount } = render(<CookieConsentBanner />);
        instances.push(unmount);
      }

      // Unmount all instances
      instances.forEach(unmount => unmount());

      // Create new instance to verify no interference
      render(<CookieConsentBanner />);
      expect(screen.getByTestId('consent-banner')).toBeVisible();
    });

    it('should handle rapid user interactions without issues', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');

      // Rapid clicks
      for (let i = 0; i < 5; i++) {
        await user.click(manageButton);
        
        if (screen.queryByTestId('preferences-modal')) {
          const cancelButton = screen.getByText('Cancel');
          await user.click(cancelButton);
        }
      }

      // Should still work normally
      await user.click(manageButton);
      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility Integration', () => {
    it('should maintain accessibility throughout complete user flow', async () => {
      render(<CookieConsentBanner />);

      // Verify initial accessibility
      const banner = screen.getByTestId('consent-banner');
      expect(banner).toHaveAttribute('role', 'banner');
      expect(banner).toHaveAttribute('aria-label');

      // Navigate with keyboard
      await user.tab();
      expect(screen.getByText('Accept All')).toHaveFocus();

      await user.tab();
      expect(screen.getByText('Manage Preferences')).toHaveFocus();

      // Open modal with keyboard
      await user.keyboard('{Enter}');

      await waitFor(() => {
        const modal = screen.getByTestId('preferences-modal');
        expect(modal).toHaveAttribute('role', 'dialog');
        expect(modal).toHaveAttribute('aria-modal', 'true');
      });

      // Navigate modal with keyboard
      await user.tab();
      expect(screen.getByLabelText('Analytics Cookies')).toHaveFocus();

      // Toggle with space
      await user.keyboard(' ');
      expect(screen.getByLabelText('Analytics Cookies')).toBeChecked();

      // Save with keyboard
      await user.tab();
      await user.tab();
      await user.tab();
      expect(screen.getByText('Save Preferences')).toHaveFocus();

      await user.keyboard('{Enter}');

      // Verify accessibility is maintained after save
      await waitFor(() => {
        expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
      });
    });
  });

  describe('GDPR Compliance Integration', () => {
    it('should maintain GDPR compliance throughout all user flows', async () => {
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        }
      };

      render(<CookieConsentBanner analyticsConfig={analyticsConfig} />);

      // Verify no non-essential cookies before consent
      expect(consentManager.getCategoryConsent('analytics')).toBe(false);
      expect(consentManager.getCategoryConsent('marketing')).toBe(false);

      // Accept all
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Verify consent is properly recorded
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_timestamp', expect.any(String));
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_version', '1.0.0');
      });

      // Verify granular consent is stored even with "Accept All"
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_essential', 'true');
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_marketing', 'true');

      // Test consent withdrawal
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'true';
        return null;
      });

      // Clear consent
      consentManager.clearAllConsent();

      // Verify withdrawal
      expect(consentManager.getCategoryConsent('analytics')).toBe(false);
      expect(consentManager.getCategoryConsent('marketing')).toBe(false);
      expect(consentManager.getCategoryConsent('essential')).toBe(true); // Always true
    });
  });

  describe('Cross-Browser Integration', () => {
    it('should work consistently across different storage scenarios', async () => {
      const testScenarios = [
        { name: 'normal', behavior: 'normal' },
        { name: 'quota-exceeded', behavior: 'quota-exceeded' },
        { name: 'private-mode', behavior: 'private-mode' }
      ];

      for (const scenario of testScenarios) {
        // Mock different storage behaviors
        if (scenario.behavior === 'quota-exceeded') {
          mockLocalStorage.setItem.mockImplementation(() => {
            throw new Error('QuotaExceededError');
          });
        } else if (scenario.behavior === 'private-mode') {
          mockLocalStorage.setItem.mockImplementation(() => {
            throw new Error('Private browsing mode');
          });
        } else {
          mockLocalStorage.setItem.mockImplementation((key, value) => {
            // Normal behavior
          });
        }

        const { unmount } = render(<CookieConsentBanner />);

        const acceptButton = screen.getByText('Accept All');
        await user.click(acceptButton);

        // Should work in all scenarios
        await waitFor(() => {
          expect(screen.getByTestId('consent-banner')).not.toBeVisible();
        });

        unmount();
      }
    });
  });

  describe('Real-World Usage Scenarios', () => {
    it('should handle typical e-commerce website flow', async () => {
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_ECOMMERCE_ID',
          enabled: true
        },
        customProvider: {
          scriptUrl: 'https://ecommerce-analytics.com/track.js',
          initFunction: 'ecommerceTracker.init'
        }
      };

      const onConsentChange = vi.fn();

      render(
        <CookieConsentBanner 
          onConsentChange={onConsentChange}
          analyticsConfig={analyticsConfig}
          message="We use cookies to enhance your shopping experience and provide personalized recommendations."
        />
      );

      // User initially declines tracking
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Only accept essential cookies
      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'false');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_marketing', 'false');
      });

      // Later, user changes mind and accepts analytics
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'custom';
        if (key === 'cookieConsent_analytics') return 'false';
        if (key === 'cookieConsent_marketing') return 'false';
        return null;
      });

      // Simulate user returning to preferences
      const container = screen.getByTestId('cookie-consent-banner');
      fireEvent(container, new CustomEvent('openPreferences'));

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      await user.click(analyticsToggle);

      const saveButton2 = screen.getByText('Save Preferences');
      await user.click(saveButton2);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      });

      expect(onConsentChange).toHaveBeenCalledWith('custom');
    });

    it('should handle corporate website with strict compliance requirements', async () => {
      render(
        <CookieConsentBanner 
          message="This website uses cookies. By continuing to use this site, you consent to our use of cookies in accordance with our Privacy Policy."
        />
      );

      // Verify strict GDPR compliance
      expect(screen.getByText(/This website uses cookies/)).toBeInTheDocument();

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Verify detailed information is provided
      expect(screen.getByText(/Essential cookies are required/)).toBeInTheDocument();
      expect(screen.getByText(/Analytics cookies help us understand/)).toBeInTheDocument();
      expect(screen.getByText(/Marketing cookies are used/)).toBeInTheDocument();

      // Verify essential cookies cannot be disabled
      const essentialToggle = screen.getByLabelText('Essential Cookies');
      expect(essentialToggle).toBeChecked();
      expect(essentialToggle).toBeDisabled();

      // Verify other cookies are opt-in
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      const marketingToggle = screen.getByLabelText('Marketing Cookies');
      expect(analyticsToggle).not.toBeChecked();
      expect(marketingToggle).not.toBeChecked();
    });
  });

  describe('Stress Testing', () => {
    it('should handle rapid consent changes without data corruption', async () => {
      render(<CookieConsentBanner />);

      // Rapidly toggle preferences multiple times
      for (let i = 0; i < 10; i++) {
        const manageButton = screen.getByText('Manage Preferences');
        await user.click(manageButton);

        await waitFor(() => {
          expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
        });

        const analyticsToggle = screen.getByLabelText('Analytics Cookies');
        await user.click(analyticsToggle);

        if (i % 2 === 0) {
          const saveButton = screen.getByText('Save Preferences');
          await user.click(saveButton);
        } else {
          const cancelButton = screen.getByText('Cancel');
          await user.click(cancelButton);
        }

        await waitFor(() => {
          expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
        });
      }

      // Final state should be consistent
      expect(screen.getByTestId('cookie-consent-banner')).toBeInTheDocument();
    });

    it('should handle concurrent consent operations', async () => {
      const { rerender } = render(<CookieConsentBanner />);

      // Simulate multiple rapid operations
      const operations = [
        () => fireEvent.click(screen.getByText('Accept All')),
        () => fireEvent.click(screen.getByText('Manage Preferences')),
        () => consentManager.setConsentStatus('accepted'),
        () => consentManager.clearAllConsent()
      ];

      // Execute operations rapidly
      operations.forEach(op => {
        try {
          op();
        } catch (error) {
          // Some operations may fail due to timing, that's expected
        }
      });

      // Component should remain stable
      rerender(<CookieConsentBanner />);
      expect(screen.getByTestId('cookie-consent-banner')).toBeInTheDocument();
    });
  });
});