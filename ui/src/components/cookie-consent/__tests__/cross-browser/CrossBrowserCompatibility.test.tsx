import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { CookieConsentBanner } from '../../CookieConsentBanner';

// Mock different browser environments
const createBrowserMock = (browserName: string, version: string) => {
  const userAgent = {
    chrome: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${version}.0.0.0 Safari/537.36`,
    firefox: `Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:${version}.0) Gecko/20100101 Firefox/${version}.0`,
    safari: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/${version}.0 Safari/605.1.15`,
    edge: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${version}.0.0.0 Safari/537.36 Edg/${version}.0.0.0`,
    ie11: 'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko'
  }[browserName] || userAgent.chrome;

  Object.defineProperty(navigator, 'userAgent', {
    value: userAgent,
    configurable: true
  });
};

// Mock localStorage with different browser behaviors
const createLocalStorageMock = (behavior: 'normal' | 'quota-exceeded' | 'unavailable' | 'private-mode') => {
  const storage: { [key: string]: string } = {};
  
  const mockLocalStorage = {
    getItem: vi.fn((key: string) => {
      if (behavior === 'unavailable') throw new Error('localStorage unavailable');
      return storage[key] || null;
    }),
    setItem: vi.fn((key: string, value: string) => {
      if (behavior === 'unavailable') throw new Error('localStorage unavailable');
      if (behavior === 'quota-exceeded') throw new Error('QuotaExceededError');
      if (behavior === 'private-mode') throw new Error('Private mode');
      storage[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      if (behavior === 'unavailable') throw new Error('localStorage unavailable');
      delete storage[key];
    }),
    clear: vi.fn(() => {
      if (behavior === 'unavailable') throw new Error('localStorage unavailable');
      Object.keys(storage).forEach(key => delete storage[key]);
    }),
  };

  Object.defineProperty(window, 'localStorage', {
    value: mockLocalStorage,
    configurable: true
  });

  return mockLocalStorage;
};

// Mock CSS support detection
const createCSSMock = (supports: { [property: string]: boolean }) => {
  Object.defineProperty(window, 'CSS', {
    value: {
      supports: vi.fn((property: string, value?: string) => {
        const key = value ? `${property}: ${value}` : property;
        return supports[key] || false;
      })
    },
    configurable: true
  });
};

describe('Cookie Consent Banner - Cross-Browser Compatibility Tests', () => {
  let user: ReturnType<typeof userEvent.setup>;
  let mockLocalStorage: ReturnType<typeof createLocalStorageMock>;

  beforeEach(() => {
    vi.clearAllMocks();
    user = userEvent.setup();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Chrome Browser Compatibility', () => {
    beforeEach(() => {
      createBrowserMock('chrome', '120');
      mockLocalStorage = createLocalStorageMock('normal');
    });

    it('should work correctly in Chrome', async () => {
      render(<CookieConsentBanner />);

      expect(screen.getByTestId('consent-banner')).toBeVisible();

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });
    });

    it('should handle Chrome-specific localStorage behavior', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      await user.click(analyticsToggle);

      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent_analytics', 'true');
      });
    });
  });

  describe('Firefox Browser Compatibility', () => {
    beforeEach(() => {
      createBrowserMock('firefox', '121');
      mockLocalStorage = createLocalStorageMock('normal');
    });

    it('should work correctly in Firefox', async () => {
      render(<CookieConsentBanner />);

      expect(screen.getByTestId('consent-banner')).toBeVisible();

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });
    });

    it('should handle Firefox private browsing mode', async () => {
      mockLocalStorage = createLocalStorageMock('private-mode');

      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should handle private mode gracefully (using memory storage)
      await waitFor(() => {
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });
    });

    it('should handle Firefox-specific CSS features', () => {
      createCSSMock({
        'backdrop-filter': true,
        'position: sticky': true
      });

      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toBeInTheDocument();
    });
  });

  describe('Safari Browser Compatibility', () => {
    beforeEach(() => {
      createBrowserMock('safari', '17');
      mockLocalStorage = createLocalStorageMock('normal');
    });

    it('should work correctly in Safari', async () => {
      render(<CookieConsentBanner />);

      expect(screen.getByTestId('consent-banner')).toBeVisible();

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });
    });

    it('should handle Safari ITP (Intelligent Tracking Prevention)', async () => {
      // Mock Safari's stricter localStorage behavior
      mockLocalStorage = createLocalStorageMock('quota-exceeded');

      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should handle quota exceeded error gracefully
      await waitFor(() => {
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });
    });

    it('should handle Safari-specific modal behavior', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        const modal = screen.getByTestId('preferences-modal');
        expect(modal).toBeInTheDocument();
        
        // Safari should handle modal focus trapping
        expect(modal).toHaveAttribute('role', 'dialog');
      });
    });
  });

  describe('Edge Browser Compatibility', () => {
    beforeEach(() => {
      createBrowserMock('edge', '120');
      mockLocalStorage = createLocalStorageMock('normal');
    });

    it('should work correctly in Edge', async () => {
      render(<CookieConsentBanner />);

      expect(screen.getByTestId('consent-banner')).toBeVisible();

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });
    });

    it('should handle Edge-specific localStorage behavior', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Test Edge-specific keyboard navigation
      await user.keyboard('{Escape}');

      await waitFor(() => {
        expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
      });
    });
  });

  describe('Internet Explorer 11 Compatibility', () => {
    beforeEach(() => {
      createBrowserMock('ie11', '11');
      mockLocalStorage = createLocalStorageMock('normal');
      
      // Mock IE11-specific missing features
      delete (window as any).CustomEvent;
      delete (window as any).Promise;
      
      // Mock IE11 CustomEvent polyfill
      (window as any).CustomEvent = function(event: string, params: any) {
        params = params || { bubbles: false, cancelable: false, detail: undefined };
        const evt = document.createEvent('CustomEvent');
        evt.initCustomEvent(event, params.bubbles, params.cancelable, params.detail);
        return evt;
      };
    });

    it('should work with IE11 polyfills', async () => {
      render(<CookieConsentBanner />);

      expect(screen.getByTestId('consent-banner')).toBeVisible();

      const acceptButton = screen.getByText('Accept All');
      fireEvent.click(acceptButton); // Use fireEvent for IE11 compatibility

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });
    });

    it('should handle IE11 CSS limitations', () => {
      createCSSMock({
        'display: flex': false,
        'position: sticky': false,
        'backdrop-filter': false
      });

      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toBeInTheDocument();
      
      // Should apply IE11-compatible styles
      expect(container).toHaveClass('cookie-consent-system');
    });

    it('should handle IE11 event handling', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      
      // IE11 event handling
      fireEvent.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });
    });
  });

  describe('Mobile Browser Compatibility', () => {
    beforeEach(() => {
      // Mock mobile viewport
      Object.defineProperty(window, 'innerWidth', { value: 375, configurable: true });
      Object.defineProperty(window, 'innerHeight', { value: 667, configurable: true });
      
      // Mock touch events
      Object.defineProperty(window, 'ontouchstart', { value: null, configurable: true });
    });

    it('should work on mobile Chrome', async () => {
      createBrowserMock('chrome', '120');
      mockLocalStorage = createLocalStorageMock('normal');

      render(<CookieConsentBanner />);

      expect(screen.getByTestId('consent-banner')).toBeVisible();

      const acceptButton = screen.getByText('Accept All');
      
      // Simulate touch interaction
      fireEvent.touchStart(acceptButton);
      fireEvent.touchEnd(acceptButton);
      fireEvent.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });
    });

    it('should work on mobile Safari', async () => {
      createBrowserMock('safari', '17');
      mockLocalStorage = createLocalStorageMock('normal');

      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      
      // Mobile Safari touch interaction
      fireEvent.touchStart(manageButton);
      fireEvent.touchEnd(manageButton);
      fireEvent.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });
    });

    it('should handle mobile viewport changes', () => {
      mockLocalStorage = createLocalStorageMock('normal');

      render(<CookieConsentBanner />);

      // Simulate orientation change
      Object.defineProperty(window, 'innerWidth', { value: 667, configurable: true });
      Object.defineProperty(window, 'innerHeight', { value: 375, configurable: true });
      
      fireEvent(window, new Event('resize'));

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toBeInTheDocument();
    });
  });

  describe('Storage Fallback Mechanisms', () => {
    it('should handle localStorage unavailable across browsers', async () => {
      mockLocalStorage = createLocalStorageMock('unavailable');

      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should work with memory storage fallback
      await waitFor(() => {
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });
    });

    it('should handle quota exceeded errors', async () => {
      mockLocalStorage = createLocalStorageMock('quota-exceeded');

      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should handle quota exceeded gracefully
      await waitFor(() => {
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      });
    });

    it('should handle private browsing mode across browsers', async () => {
      mockLocalStorage = createLocalStorageMock('private-mode');

      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      await user.click(analyticsToggle);

      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Should work with memory storage in private mode
      await waitFor(() => {
        expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
      });
    });
  });

  describe('CSS Feature Detection', () => {
    it('should handle browsers without CSS Grid support', () => {
      createCSSMock({
        'display: grid': false,
        'display: flex': true
      });

      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toBeInTheDocument();
    });

    it('should handle browsers without Flexbox support', () => {
      createCSSMock({
        'display: flex': false,
        'display: block': true
      });

      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toBeInTheDocument();
    });

    it('should handle browsers without CSS custom properties', () => {
      createCSSMock({
        '--custom-property': false
      });

      render(<CookieConsentBanner primaryColor="#ff0000" />);

      const container = screen.getByTestId('cookie-consent-banner');
      expect(container).toBeInTheDocument();
    });

    it('should handle browsers without backdrop-filter support', () => {
      createCSSMock({
        'backdrop-filter': false
      });

      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      fireEvent.click(manageButton);

      const modal = screen.getByTestId('preferences-modal');
      expect(modal).toBeInTheDocument();
    });
  });

  describe('Event Handling Compatibility', () => {
    it('should handle different event models across browsers', async () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');

      // Test different event types
      fireEvent.mouseDown(acceptButton);
      fireEvent.mouseUp(acceptButton);
      fireEvent.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });
    });

    it('should handle keyboard events across browsers', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      manageButton.focus();

      // Test Enter key
      fireEvent.keyDown(manageButton, { key: 'Enter', code: 'Enter' });
      fireEvent.keyUp(manageButton, { key: 'Enter', code: 'Enter' });

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Test Escape key
      fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' });

      await waitFor(() => {
        expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
      });
    });

    it('should handle focus events across browsers', async () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      const manageButton = screen.getByText('Manage Preferences');

      // Test focus/blur events
      fireEvent.focus(acceptButton);
      expect(acceptButton).toHaveFocus();

      fireEvent.blur(acceptButton);
      fireEvent.focus(manageButton);
      expect(manageButton).toHaveFocus();
    });
  });

  describe('Performance Across Browsers', () => {
    it('should handle animation performance differences', async () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Banner should hide with appropriate timing across browsers
      await waitFor(() => {
        expect(screen.getByTestId('consent-banner')).not.toBeVisible();
      }, { timeout: 1000 });
    });

    it('should handle modal rendering performance', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      // Modal should appear quickly across browsers
      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      }, { timeout: 500 });
    });
  });
});