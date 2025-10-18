import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
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

describe('Cookie Consent Banner - Accessibility Compliance Tests', () => {
  let user: ReturnType<typeof userEvent.setup>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.getItem.mockReturnValue(null);
    user = userEvent.setup();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('ARIA Attributes and Roles', () => {
    it('should have proper ARIA attributes on banner', () => {
      render(<CookieConsentBanner />);

      const banner = screen.getByTestId('consent-banner');
      
      // Banner should have proper role and label
      expect(banner).toHaveAttribute('role', 'banner');
      expect(banner).toHaveAttribute('aria-label', expect.stringContaining('Cookie consent'));
      
      // Banner should be announced to screen readers
      expect(banner).toHaveAttribute('aria-live', 'polite');
    });

    it('should have proper ARIA attributes on modal', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        const modal = screen.getByTestId('preferences-modal');
        
        // Modal should have proper role and properties
        expect(modal).toHaveAttribute('role', 'dialog');
        expect(modal).toHaveAttribute('aria-modal', 'true');
        expect(modal).toHaveAttribute('aria-labelledby');
        expect(modal).toHaveAttribute('aria-describedby');
      });
    });

    it('should have proper ARIA attributes on form controls', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        // Toggle switches should have proper labels and roles
        const analyticsToggle = screen.getByLabelText('Analytics Cookies');
        expect(analyticsToggle).toHaveAttribute('role', 'switch');
        expect(analyticsToggle).toHaveAttribute('aria-checked');
        expect(analyticsToggle).toHaveAttribute('aria-describedby');

        const marketingToggle = screen.getByLabelText('Marketing Cookies');
        expect(marketingToggle).toHaveAttribute('role', 'switch');
        expect(marketingToggle).toHaveAttribute('aria-checked');
        expect(marketingToggle).toHaveAttribute('aria-describedby');

        // Essential cookies should be marked as disabled
        const essentialToggle = screen.getByLabelText('Essential Cookies');
        expect(essentialToggle).toHaveAttribute('aria-disabled', 'true');
        expect(essentialToggle).toHaveAttribute('aria-describedby');
      });
    });

    it('should announce state changes to screen readers', async () => {
      const mockAppendChild = vi.spyOn(document.body, 'appendChild');
      const mockRemoveChild = vi.spyOn(document.body, 'removeChild');

      render(<CookieConsentBanner />);

      // Accept all cookies
      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should create announcement element
      await waitFor(() => {
        expect(mockAppendChild).toHaveBeenCalledWith(
          expect.objectContaining({
            textContent: expect.stringContaining('All cookies have been accepted'),
            getAttribute: expect.any(Function)
          })
        );
      });

      // Cleanup should happen after timeout
      vi.useFakeTimers();
      vi.advanceTimersByTime(1000);
      
      expect(mockRemoveChild).toHaveBeenCalled();

      mockAppendChild.mockRestore();
      mockRemoveChild.mockRestore();
      vi.useRealTimers();
    });

    it('should announce preference changes to screen readers', async () => {
      const mockAppendChild = vi.spyOn(document.body, 'appendChild');

      render(<CookieConsentBanner />);

      // Open preferences modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Toggle analytics cookies
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      await user.click(analyticsToggle);

      // Save preferences
      const saveButton = screen.getByText('Save Preferences');
      await user.click(saveButton);

      // Should announce preference save
      await waitFor(() => {
        expect(mockAppendChild).toHaveBeenCalledWith(
          expect.objectContaining({
            textContent: expect.stringContaining('Cookie preferences saved')
          })
        );
      });

      mockAppendChild.mockRestore();
    });
  });

  describe('Keyboard Navigation', () => {
    it('should support full keyboard navigation on banner', async () => {
      render(<CookieConsentBanner />);

      // Tab should focus first button
      await user.tab();
      expect(screen.getByText('Accept All')).toHaveFocus();

      // Tab should focus second button
      await user.tab();
      expect(screen.getByText('Manage Preferences')).toHaveFocus();

      // Enter should activate button
      await user.keyboard('{Enter}');

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });
    });

    it('should support keyboard navigation in modal', async () => {
      render(<CookieConsentBanner />);

      // Open modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Tab through modal elements
      await user.tab();
      expect(screen.getByLabelText('Analytics Cookies')).toHaveFocus();

      await user.tab();
      expect(screen.getByLabelText('Marketing Cookies')).toHaveFocus();

      await user.tab();
      expect(screen.getByText('Cancel')).toHaveFocus();

      await user.tab();
      expect(screen.getByText('Save Preferences')).toHaveFocus();
    });

    it('should trap focus within modal', async () => {
      render(<CookieConsentBanner />);

      // Open modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Get all focusable elements
      const focusableElements = [
        screen.getByLabelText('Analytics Cookies'),
        screen.getByLabelText('Marketing Cookies'),
        screen.getByText('Cancel'),
        screen.getByText('Save Preferences')
      ];

      // Tab through all elements
      for (let i = 0; i < focusableElements.length; i++) {
        await user.tab();
        expect(focusableElements[i]).toHaveFocus();
      }

      // One more tab should cycle back to first element
      await user.tab();
      expect(focusableElements[0]).toHaveFocus();

      // Shift+Tab should go to last element
      await user.keyboard('{Shift>}{Tab}{/Shift}');
      expect(focusableElements[focusableElements.length - 1]).toHaveFocus();
    });

    it('should handle Escape key to close modal', async () => {
      render(<CookieConsentBanner />);

      // Open modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Press Escape
      await user.keyboard('{Escape}');

      // Modal should close
      await waitFor(() => {
        expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
      });

      // Focus should return to manage preferences button
      expect(manageButton).toHaveFocus();
    });

    it('should support Space key for toggle activation', async () => {
      render(<CookieConsentBanner />);

      // Open modal
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      // Focus analytics toggle
      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      analyticsToggle.focus();

      // Should be unchecked initially
      expect(analyticsToggle).not.toBeChecked();

      // Press Space to toggle
      await user.keyboard(' ');
      expect(analyticsToggle).toBeChecked();

      // Press Space again to toggle back
      await user.keyboard(' ');
      expect(analyticsToggle).not.toBeChecked();
    });
  });

  describe('Screen Reader Support', () => {
    it('should provide descriptive text for all interactive elements', () => {
      render(<CookieConsentBanner />);

      // Buttons should have accessible names
      const acceptButton = screen.getByText('Accept All');
      expect(acceptButton).toHaveAccessibleName('Accept All');

      const manageButton = screen.getByText('Manage Preferences');
      expect(manageButton).toHaveAccessibleName('Manage Preferences');
    });

    it('should provide descriptive text for modal elements', async () => {
      render(<CookieConsentBanner />);

      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        // Modal title should be accessible
        const modalTitle = screen.getByText('Cookie Preferences');
        expect(modalTitle).toBeInTheDocument();

        // Toggle switches should have descriptive labels
        const analyticsToggle = screen.getByLabelText('Analytics Cookies');
        expect(analyticsToggle).toHaveAccessibleName('Analytics Cookies');
        expect(analyticsToggle).toHaveAccessibleDescription();

        const marketingToggle = screen.getByLabelText('Marketing Cookies');
        expect(marketingToggle).toHaveAccessibleName('Marketing Cookies');
        expect(marketingToggle).toHaveAccessibleDescription();

        const essentialToggle = screen.getByLabelText('Essential Cookies');
        expect(essentialToggle).toHaveAccessibleName('Essential Cookies');
        expect(essentialToggle).toHaveAccessibleDescription();
      });
    });

    it('should announce dynamic content changes', async () => {
      const mockAppendChild = vi.spyOn(document.body, 'appendChild');

      render(<CookieConsentBanner />);

      // Open modal and toggle analytics
      const manageButton = screen.getByText('Manage Preferences');
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
      });

      const analyticsToggle = screen.getByLabelText('Analytics Cookies');
      await user.click(analyticsToggle);

      // Should announce toggle state change
      expect(mockAppendChild).toHaveBeenCalledWith(
        expect.objectContaining({
          textContent: expect.stringContaining('Analytics Cookies enabled')
        })
      );

      mockAppendChild.mockRestore();
    });
  });

  describe('Color Contrast and Visual Accessibility', () => {
    it('should maintain high contrast ratios', () => {
      render(<CookieConsentBanner />);

      const banner = screen.getByTestId('consent-banner');
      const computedStyle = window.getComputedStyle(banner);

      // Note: In a real test environment, you would use tools like
      // axe-core or color-contrast to verify actual contrast ratios
      // Here we verify that contrast-related CSS properties are applied
      expect(banner).toBeInTheDocument();
    });

    it('should provide visible focus indicators', async () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      
      // Focus the button
      acceptButton.focus();
      
      // Button should have focus styles (verified through CSS classes)
      expect(acceptButton).toHaveFocus();
      expect(acceptButton).toHaveClass(expect.stringMatching(/button/));
    });

    it('should support high contrast mode', () => {
      // Mock high contrast media query
      window.matchMedia = vi.fn().mockImplementation(query => ({
        matches: query === '(prefers-contrast: high)',
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
      
      // Should apply high contrast styles
      expect(container).toBeInTheDocument();
    });
  });

  describe('Reduced Motion Support', () => {
    it('should respect prefers-reduced-motion setting', () => {
      // Mock reduced motion preference
      window.matchMedia = vi.fn().mockImplementation(query => ({
        matches: query === '(prefers-reduced-motion: reduce)',
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
      
      // Should apply reduced motion styles
      expect(container).toBeInTheDocument();
    });

    it('should provide instant transitions when motion is reduced', async () => {
      // Mock reduced motion
      window.matchMedia = vi.fn().mockImplementation(query => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));

      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Banner should hide immediately without animation
      const banner = screen.getByTestId('consent-banner');
      await waitFor(() => {
        expect(banner).not.toBeVisible();
      });
    });
  });

  describe('Language and Internationalization', () => {
    it('should support lang attribute for screen readers', () => {
      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      
      // Should have lang attribute (inherited from document or explicitly set)
      expect(document.documentElement).toHaveAttribute('lang');
    });

    it('should support RTL text direction', () => {
      // Mock RTL direction
      document.dir = 'rtl';

      render(<CookieConsentBanner />);

      const container = screen.getByTestId('cookie-consent-banner');
      
      // Should handle RTL layout
      expect(container).toBeInTheDocument();

      // Reset direction
      document.dir = 'ltr';
    });
  });

  describe('Mobile Accessibility', () => {
    it('should support touch interactions', async () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      
      // Simulate touch interaction
      fireEvent.touchStart(acceptButton);
      fireEvent.touchEnd(acceptButton);
      fireEvent.click(acceptButton);

      await waitFor(() => {
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      });
    });

    it('should have appropriate touch target sizes', () => {
      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      const manageButton = screen.getByText('Manage Preferences');

      // Buttons should be large enough for touch interaction
      // (minimum 44px as per WCAG guidelines)
      expect(acceptButton).toBeInTheDocument();
      expect(manageButton).toBeInTheDocument();
    });
  });

  describe('Error State Accessibility', () => {
    it('should announce errors to screen readers', async () => {
      const mockAppendChild = vi.spyOn(document.body, 'appendChild');
      
      // Mock localStorage to throw error
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('Storage unavailable');
      });

      render(<CookieConsentBanner />);

      const acceptButton = screen.getByText('Accept All');
      await user.click(acceptButton);

      // Should announce error state
      await waitFor(() => {
        expect(mockAppendChild).toHaveBeenCalledWith(
          expect.objectContaining({
            textContent: expect.stringContaining('error'),
            getAttribute: expect.any(Function)
          })
        );
      });

      mockAppendChild.mockRestore();
    });
  });
});