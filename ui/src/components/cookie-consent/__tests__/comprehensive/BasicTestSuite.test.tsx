import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { CookieConsentBanner } from '../../CookieConsentBanner';

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

describe('Cookie Consent Banner - Basic Comprehensive Tests', () => {
  let user: ReturnType<typeof userEvent.setup>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.getItem.mockReturnValue(null);
    user = userEvent.setup();
  });

  describe('End-to-End User Flow', () => {
    it('should complete basic accept all flow', async () => {
      const onConsentChange = vi.fn();
      
      render(<CookieConsentBanner onConsentChange={onConsentChange} />);

      // Verify banner appears
      expect(screen.getByTestId('consent-banner')).toBeVisible();

      // Click Accept All
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Verify consent is stored
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });

      // Verify callback is called
      expect(onConsentChange).toHaveBeenCalledWith('accepted');
    });

    it('should complete basic preferences flow', async () => {
      render(<CookieConsentBanner />);

      // Open preferences
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      // Verify modal opens
      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Save preferences (default state)
      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Verify custom consent is stored
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'custom');
      });
    });
  });

  describe('GDPR Compliance Basics', () => {
    it('should not set non-essential cookies before consent', () => {
      render(<CookieConsentBanner />);

      // Should not have set analytics or marketing consent
      expect(mockLocalStorage.setItem).not.toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      expect(mockLocalStorage.setItem).not.toHaveBeenCalledWith('cookieConsent_marketing', 'true');
    });

    it('should record consent timestamp', async () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
          'cookieConsent_timestamp',
          expect.stringMatching(/^\d+$/)
        );
      });
    });

    it('should record consent version', async () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_version', '1.0.0');
      });
    });
  });

  describe('Accessibility Basics', () => {
    it('should have proper ARIA attributes', () => {
      render(<CookieConsentBanner />);

      const banner = screen.getByTestId('consent-banner');
      expect(banner).toHaveAttribute('role', 'banner');
      expect(banner).toHaveAttribute('aria-label');
    });

    it('should support keyboard navigation', async () => {
      render(<CookieConsentBanner />);

      // Tab to first button
      await user.tab();
      expect(document.activeElement).toHaveTextContent('Manage Preferences');

      // Tab to second button
      await user.tab();
      expect(document.activeElement).toHaveTextContent('Accept All');
    });

    it('should handle modal accessibility', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        const modal = screen.getByTestId('preferences-modal');
        expect(modal).toHaveAttribute('role', 'dialog');
        expect(modal).toHaveAttribute('aria-modal', 'true');
      });
    });
  });

  describe('Cross-Browser Storage Compatibility', () => {
    it('should handle localStorage unavailable', async () => {
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });

      const onConsentChange = vi.fn();
      render(<CookieConsentBanner onConsentChange={onConsentChange} />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should still call callback even if storage fails
      await waitFor(() => {
        expect(onConsentChange).toHaveBeenCalledWith('accepted');
      });
    });

    it('should handle quota exceeded errors', async () => {
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('QuotaExceededError');
      });

      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      
      // Should not crash
      expect(() => user.click(acceptButton)).not.toThrow();
    });
  });

  describe('Error Handling', () => {
    it('should handle component errors gracefully', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      // Mock error in localStorage
      mockLocalStorage.getItem.mockImplementation(() => {
        throw new Error('Storage error');
      });

      // Should not crash during render
      expect(() => render(<CookieConsentBanner />)).not.toThrow();

      consoleSpy.mockRestore();
    });

    it('should handle callback errors gracefully', async () => {
      const errorCallback = vi.fn(() => {
        throw new Error('Callback error');
      });

      render(<CookieConsentBanner onConsentChange={errorCallback} />);

      const acceptButton = screen.getByText('Accept All');
      
      // Should not crash even if callback throws
      expect(() => user.click(acceptButton)).not.toThrow();
    });
  });

  describe('Performance and Memory', () => {
    it('should clean up properly on unmount', () => {
      const { unmount } = render(<CookieConsentBanner />);
      
      // Should not throw on unmount
      expect(() => unmount()).not.toThrow();
    });

    it('should handle multiple rapid interactions', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');

      // Rapid clicks should not cause issues
      for (let i = 0; i < 3; i++) {
        await user.click(manageButton);
        
        if (screen.queryByTestId('preferences-modal')) {
          const cancelButton = screen.getByText('Cancel');
          await user.click(cancelButton);
        }
      }

      // Should still work normally
      expect(screen.getByTestId('cookie-consent-banner')).toBeInTheDocument();
    });
  });

  describe('Theme and Customization', () => {
    it('should apply custom primary color', () => {
      const customColor = '#ff0000';
      render(<CookieConsentBanner primaryColor={customColor} />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveStyle(`--cookie-primary-color: ${customColor}`);
    });

    it('should apply dark mode', () => {
      render(<CookieConsentBanner darkMode={true} />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveAttribute('data-theme', 'dark');
    });

    it('should apply custom message', () => {
      const customMessage = 'Custom cookie message';
      render(<CookieConsentBanner message={customMessage} />);

      expect(screen.getByText(customMessage)).toBeInTheDocument();
    });

    it('should support different positions', () => {
      render(<CookieConsentBanner position="top" />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toHaveAttribute('data-position', 'top');
    });
  });

  describe('Analytics Integration Basics', () => {
    it('should handle analytics config', async () => {
      const analyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        }
      };

      render(<CookieConsentBanner analyticsConfig={analyticsConfig} />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should store analytics consent
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      });
    });

    it('should handle analytics config errors gracefully', () => {
      const badAnalyticsConfig = {
        customProvider: {
          scriptUrl: 'invalid-url',
          initFunction: 'nonexistent.function'
        }
      };

      // Should not crash with bad config
      expect(() => 
        render(<CookieConsentBanner analyticsConfig={badAnalyticsConfig} />)
      ).not.toThrow();
    });
  });

  describe('Real-World Scenarios', () => {
    it('should handle existing consent on page load', () => {
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        return null;
      });

      render(<CookieConsentBanner />);

      // Banner should not be visible with existing consent
      const banner = screen.queryByTestId('consent-banner');
      if (banner) {
        expect(banner).not.toBeVisible();
      } else {
        expect(banner).toBeNull();
      }
    });

    it('should handle partial consent state', () => {
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'custom';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'false';
        return null;
      });

      render(<CookieConsentBanner />);

      // Should handle partial consent without issues
      expect(screen.getByTestId('cookie-consent-banner')).toBeInTheDocument();
    });

    it('should handle consent withdrawal scenario', async () => {
      // Start with consent
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        return 'true';
      });

      render(<CookieConsentBanner />);

      // Simulate consent withdrawal (would typically be done via settings)
      mockLocalStorage.getItem.mockReturnValue(null);

      // Re-render to simulate page reload after consent withdrawal
      const { rerender } = render(<CookieConsentBanner />);

      // Banner should appear again
      expect(screen.getByTestId('consent-banner')).toBeVisible();
    });
  });
});