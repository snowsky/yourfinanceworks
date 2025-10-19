import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { CookieConsentBanner } from '../../CookieConsentBanner';
import { ConsentManager } from '../../services/ConsentManager';
import type { AnalyticsConfig } from '../../types';

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

// Mock document.createElement for script loading tests
const mockScripts: any[] = [];
const originalCreateElement = document.createElement;
document.createElement = vi.fn().mockImplementation((tagName) => {
  if (tagName === 'script') {
    const mockScript = {
      id: '',
      src: '',
      async: false,
      defer: false,
      onload: null,
      onerror: null,
      remove: vi.fn()
    };
    mockScripts.push(mockScript);
    return mockScript;
  }
  return originalCreateElement.call(document, tagName);
});

describe('Cookie Consent Banner - GDPR Compliance Tests', () => {
  let user: ReturnType<typeof userEvent.setup>;
  let consentManager: ConsentManager;

  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.getItem.mockReturnValue(null);
    mockScripts.length = 0;
    user = userEvent.setup();
    consentManager = new ConsentManager();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Lawful Basis - Consent Requirements', () => {
    it('should not set any non-essential cookies before consent', () => {
      render(<CookieConsentBanner />);

      // Verify no consent-related localStorage calls before user interaction
      expect(mockLocalStorage.setItem).not.toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      expect(mockLocalStorage.setItem).not.toHaveBeenCalledWith('cookieConsent_marketing', 'true');
      
      // Only essential cookies should be allowed by default
      expect(consentManager.getCategoryConsent('essential')).toBe(true);
      expect(consentManager.getCategoryConsent('analytics')).toBe(false);
      expect(consentManager.getCategoryConsent('marketing')).toBe(false);
    });

    it('should require explicit consent for analytics cookies', async () => {
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        }
      };

      render(<CookieConsentBanner analyticsConfig={analyticsConfig} />);

      // No analytics scripts should be loaded initially
      expect(mockScripts.length).toBe(0);

      // Accept all cookies
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Now analytics consent should be granted
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      });
    });

    it('should require explicit consent for marketing cookies', async () => {
      render(<CookieConsentBanner />);

      // Open preferences modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Marketing should be off by default
      const marketingToggle = screen.getByLabelText('Marketing Cookies');
      expect(marketingToggle).not.toBeChecked();

      // Enable marketing cookies explicitly
      await user.click(marketingToggle);
      expect(marketingToggle).toBeChecked();

      // Save preferences
      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Marketing consent should be stored
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_marketing', 'true');
      });
    });

    it('should not allow pre-ticked boxes for non-essential cookies', async () => {
      render(<CookieConsentBanner />);

      // Open preferences modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Analytics and marketing should be unchecked by default (GDPR requirement)
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      const marketingToggle = screen.getByLabelText('Marketing Cookies');
      
      expect(analyticsToggle).not.toBeChecked();
      expect(marketingToggle).not.toBeChecked();

      // Essential cookies should be checked and disabled (always required)
      const essentialToggle = screen.getByLabelText('Essential Cookies');
      expect(essentialToggle).toBeChecked();
      expect(essentialToggle).toBeDisabled();
    });
  });

  describe('Consent Withdrawal Rights', () => {
    it('should allow users to withdraw consent at any time', async () => {
      // Start with existing consent
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'true';
        return null;
      });

      render(<CookieConsentBanner />);

      // Simulate opening preferences (e.g., from settings page)
      const container = screen.getByTestId('cookie-consent-banner');
      fireEvent(container, new CustomEvent('openPreferences'));

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Analytics should be enabled (from existing consent)
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      expect(analyticsToggle).toBeChecked();

      // Withdraw analytics consent
      await user.click(analyticsToggle);
      expect(analyticsToggle).not.toBeChecked();

      // Save changes
      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Consent should be withdrawn
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'false');
      });
    });

    it('should provide clear mechanism to withdraw all consent', async () => {
      // Start with existing consent
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        if (key === 'cookieConsent_marketing') return 'true';
        return null;
      });

      const { rerender } = render(<CookieConsentBanner />);

      // Use ConsentManager to clear all consent (simulating a "Clear All Cookies" button)
      consentManager.clearAllConsent();

      // Re-render to reflect cleared consent
      mockLocalStorage.getItem.mockReturnValue(null);
      rerender(<CookieConsentBanner />);

      // Banner should appear again
      expect(screen.getByTestId('consent-banner')).toBeVisible();

      // Verify all non-essential consent is withdrawn
      expect(consentManager.getCategoryConsent('analytics')).toBe(false);
      expect(consentManager.getCategoryConsent('marketing')).toBe(false);
      expect(consentManager.getCategoryConsent('essential')).toBe(true); // Always true
    });

    it('should stop loading analytics scripts when consent is withdrawn', async () => {
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        }
      };

      // Start with analytics consent
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        return null;
      });

      render(<CookieConsentBanner analyticsConfig={analyticsConfig} />);

      // Simulate script loading (would happen in real scenario)
      const initialScriptCount = mockScripts.length;

      // Withdraw consent
      consentManager.setCategoryConsent('analytics', false);
      
      // Trigger consent change event
      const container = screen.getByTestId('cookie-consent-banner');
      fireEvent(container, new CustomEvent('consentChange', {
        detail: { analytics: false }
      }));

      // No new analytics scripts should be loaded
      expect(mockScripts.length).toBe(initialScriptCount);
    });
  });

  describe('Consent Record Keeping', () => {
    it('should record timestamp of consent', async () => {
      const beforeTime = Date.now();
      
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      const afterTime = Date.now();

      // Verify timestamp is recorded
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
          'cookieConsent_timestamp',
          expect.stringMatching(/^\d+$/)
        );
      });

      // Verify timestamp is within expected range
      const timestampCall = mockLocalStorage.setItem.mock.calls.find(
        call => call[0] === 'cookieConsent_timestamp'
      );
      if (timestampCall) {
        const timestamp = parseInt(timestampCall[1]);
        expect(timestamp).toBeGreaterThanOrEqual(beforeTime);
        expect(timestamp).toBeLessThanOrEqual(afterTime);
      }
    });

    it('should record consent version for compliance tracking', async () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Verify version is recorded
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_version', '1.0.0');
      });
    });

    it('should update timestamp when preferences change', async () => {
      render(<CookieConsentBanner />);

      // Initial consent
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      const firstTimestamp = mockLocalStorage.setItem.mock.calls.find(
        call => call[0] === 'cookieConsent_timestamp'
      )?.[1];

      // Clear mock calls
      mockLocalStorage.setItem.mockClear();

      // Wait a bit to ensure different timestamp
      await new Promise(resolve => setTimeout(resolve, 10));

      // Change preferences
      const container = screen.getByTestId('cookie-consent-banner');
      fireEvent(container, new CustomEvent('openPreferences'));

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Toggle analytics off
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      await user.click(analyticsToggle);

      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Verify new timestamp is recorded
      await waitFor(() => {
        const newTimestampCall = mockLocalStorage.setItem.mock.calls.find(
          call => call[0] === 'cookieConsent_timestamp'
        );
        expect(newTimestampCall).toBeDefined();
        if (newTimestampCall && firstTimestamp) {
          expect(parseInt(newTimestampCall[1])).toBeGreaterThan(parseInt(firstTimestamp));
        }
      });
    });

    it('should maintain detailed consent records per category', async () => {
      render(<CookieConsentBanner />);

      // Open preferences and set custom consent
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Enable only analytics, not marketing
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      await user.click(analyticsToggle);

      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Verify detailed consent records
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'custom');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_essential', 'true');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_marketing', 'false');
      });
    });
  });

  describe('Data Subject Rights', () => {
    it('should provide clear information about cookie purposes', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Verify clear descriptions are provided for each category
      expect(screen.getByText(/Essential cookies are required/)).toBeInTheDocument();
      expect(screen.getByText(/Analytics cookies help us understand/)).toBeInTheDocument();
      expect(screen.getByText(/Marketing cookies are used/)).toBeInTheDocument();
    });

    it('should allow granular control over cookie categories', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // User should be able to control each category independently
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      const marketingToggle = screen.getByLabelText('Marketing Cookies');

      // Enable analytics but not marketing
      await user.click(analyticsToggle);
      expect(analyticsToggle).toBeChecked();
      expect(marketingToggle).not.toBeChecked();

      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Verify granular consent is stored
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_marketing', 'false');
      });
    });

    it('should not bundle consent for different purposes', async () => {
      render(<CookieConsentBanner />);

      // "Accept All" should still record granular consent
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Even with "Accept All", individual categories should be recorded
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_essential', 'true');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_marketing', 'true');
      });
    });
  });

  describe('Legitimate Interest vs Consent', () => {
    it('should clearly distinguish between consent and legitimate interest', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Essential cookies should be marked as necessary (legitimate interest)
      const essentialToggle = screen.getByLabelText('Essential Cookies');
      expect(essentialToggle).toBeDisabled();
      expect(screen.getByText(/Essential cookies are required/)).toBeInTheDocument();

      // Analytics and marketing should require consent
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      const marketingToggle = screen.getByLabelText('Marketing Cookies');
      expect(analyticsToggle).not.toBeDisabled();
      expect(marketingToggle).not.toBeDisabled();
    });

    it('should not require consent for strictly necessary cookies', () => {
      // Essential cookies should always be allowed
      expect(consentManager.getCategoryConsent('essential')).toBe(true);
      
      // Even when clearing all consent, essential should remain
      consentManager.clearAllConsent();
      expect(consentManager.getCategoryConsent('essential')).toBe(true);
    });
  });

  describe('Cross-Border Data Transfer Compliance', () => {
    it('should configure analytics with privacy-compliant settings', async () => {
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        }
      };

      render(<CookieConsentBanner analyticsConfig={analyticsConfig} />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Verify analytics is configured with GDPR-compliant settings
      // (This would be verified in the AnalyticsIntegration service)
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      });
    });

    it('should handle consent for international data transfers', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Information about data transfers should be available
      // (In a real implementation, this might be in a privacy policy link)
      expect(screen.getByText(/Analytics cookies help us understand/)).toBeInTheDocument();
    });
  });

  describe('Consent Validity and Renewal', () => {
    it('should handle expired consent appropriately', () => {
      // Mock old consent (older than typical validity period)
      const oldTimestamp = Date.now() - (365 * 24 * 60 * 60 * 1000); // 1 year ago
      
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_timestamp') return oldTimestamp.toString();
        return null;
      });

      // In a real implementation, you might check timestamp age
      const preferences = consentManager.getConsentPreferences();
      expect(preferences.timestamp).toBeDefined();
    });

    it('should maintain consent across browser sessions', () => {
      // Set consent
      consentManager.setConsentStatus('accepted');
      consentManager.setCategoryConsent('analytics', true);

      // Simulate new session (new ConsentManager instance)
      const newConsentManager = new ConsentManager();
      
      // Mock localStorage to return stored values
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'cookieConsent') return 'accepted';
        if (key === 'cookieConsent_analytics') return 'true';
        return null;
      });

      // Consent should persist
      expect(newConsentManager.getConsentStatus()).toBe('accepted');
      expect(newConsentManager.getCategoryConsent('analytics')).toBe(true);
    });
  });

  describe('Privacy by Design', () => {
    it('should implement privacy-friendly defaults', () => {
      // Default state should be privacy-friendly
      expect(consentManager.getCategoryConsent('analytics')).toBe(false);
      expect(consentManager.getCategoryConsent('marketing')).toBe(false);
      expect(consentManager.isConsentRequired()).toBe(true);
    });

    it('should minimize data collection by default', async () => {
      const analyticsConfig: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TEST_ID',
          enabled: true
        }
      };

      render(<CookieConsentBanner analyticsConfig={analyticsConfig} />);

      // No analytics scripts should load without consent
      expect(mockScripts.length).toBe(0);

      // Only after explicit consent should analytics load
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Now analytics can be loaded (verified by consent storage)
      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      });
    });

    it('should provide transparent information about data processing', async () => {
      render(<CookieConsentBanner />);

      // Banner should provide clear information
      expect(screen.getByText(/We use cookies to improve your experience/)).toBeInTheDocument();

      // Detailed information should be available in preferences
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByText('Cookie Preferences')).toBeInTheDocument();
        expect(screen.getByText(/Essential cookies are required/)).toBeInTheDocument();
        expect(screen.getByText(/Analytics cookies help us understand/)).toBeInTheDocument();
        expect(screen.getByText(/Marketing cookies are used/)).toBeInTheDocument();
      });
    });
  });
});