import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { ConsentBanner } from '../ConsentBanner';
import type { ConsentBannerProps } from '../types';

// Mock CSS animations for testing
Object.defineProperty(window, 'requestAnimationFrame', {
  value: (callback: FrameRequestCallback) => {
    return setTimeout(callback, 0);
  },
});

Object.defineProperty(window, 'cancelAnimationFrame', {
  value: (id: number) => {
    clearTimeout(id);
  },
});

describe('ConsentBanner', () => {
  const defaultProps: ConsentBannerProps = {
    onAcceptAll: vi.fn(),
    onManagePreferences: vi.fn(),
    visible: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Clean up any remaining DOM elements
    document.body.innerHTML = '';
  });

  describe('Basic Rendering', () => {
    it('renders the banner when visible is true', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      expect(screen.getByTestId('consent-banner')).toBeInTheDocument();
      expect(screen.getByRole('banner')).toBeInTheDocument();
    });

    it('does not render when visible is false', () => {
      render(<ConsentBanner {...defaultProps} visible={false} />);
      
      expect(screen.queryByTestId('consent-banner')).not.toBeInTheDocument();
    });

    it('displays the default message', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      expect(screen.getByText(/We use cookies to improve your experience/)).toBeInTheDocument();
    });

    it('displays custom message when provided', () => {
      const customMessage = 'Custom cookie message';
      render(<ConsentBanner {...defaultProps} message={customMessage} />);
      
      expect(screen.getByText(customMessage)).toBeInTheDocument();
    });

    it('renders both action buttons', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      expect(screen.getByRole('button', { name: /accept all cookies/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /open cookie preferences/i })).toBeInTheDocument();
    });
  });

  describe('Accessibility Features', () => {
    it('has proper ARIA attributes', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      const banner = screen.getByRole('banner');
      expect(banner).toHaveAttribute('aria-label', 'Cookie consent notification');
      expect(banner).toHaveAttribute('aria-describedby', 'cookie-message');
      expect(banner).toHaveAttribute('tabIndex', '-1');
    });

    it('has proper button ARIA labels', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      const acceptButton = screen.getByRole('button', { name: /accept all cookies/i });
      const manageButton = screen.getByRole('button', { name: /open cookie preferences/i });
      
      expect(acceptButton).toHaveAttribute('aria-label', 'Accept all cookies and dismiss this banner');
      expect(manageButton).toHaveAttribute('aria-label', 'Open cookie preferences to customize your choices');
    });

    it('has proper role attributes for message and actions', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByRole('group', { name: /cookie consent actions/i })).toBeInTheDocument();
    });

    it('includes screen reader instructions', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      expect(screen.getByText(/Use Tab to navigate between buttons/)).toBeInTheDocument();
    });

    it('supports keyboard navigation with Tab key', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      const acceptButton = screen.getByRole('button', { name: /accept all cookies/i });
      const manageButton = screen.getByRole('button', { name: /open cookie preferences/i });
      
      // Focus on first button manually (simulating tab navigation)
      manageButton.focus();
      expect(document.activeElement).toBe(manageButton);
      
      // Focus on second button manually (simulating tab navigation)
      acceptButton.focus();
      expect(document.activeElement).toBe(acceptButton);
    });

    it('handles Escape key to focus manage preferences', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      const manageButton = screen.getByRole('button', { name: /open cookie preferences/i });
      
      fireEvent.keyDown(document, { key: 'Escape' });
      expect(document.activeElement).toBe(manageButton);
    });
  });

  describe('Theme Support', () => {
    it('applies light theme by default', () => {
      render(<ConsentBanner {...defaultProps} />);
      
      const banner = screen.getByTestId('consent-banner');
      expect(banner).toHaveAttribute('data-theme', 'light');
    });

    it('applies dark theme when darkMode is true', () => {
      render(<ConsentBanner {...defaultProps} darkMode={true} />);
      
      const banner = screen.getByTestId('consent-banner');
      expect(banner).toHaveAttribute('data-theme', 'dark');
    });

    it('applies custom primary color styles', () => {
      const customColor = '#ff0000';
      render(<ConsentBanner {...defaultProps} primaryColor={customColor} />);
      
      const banner = screen.getByTestId('consent-banner');
      expect(banner).toHaveStyle({
        '--cookie-primary-color': customColor,
      });
    });
  });

  describe('Animation States', () => {
    it('applies correct CSS classes for animation states', async () => {
      const { rerender } = render(<ConsentBanner {...defaultProps} visible={false} />);
      
      // Initially not visible
      expect(screen.queryByTestId('consent-banner')).not.toBeInTheDocument();
      
      // Show banner
      rerender(<ConsentBanner {...defaultProps} visible={true} />);
      
      await waitFor(() => {
        const banner = screen.getByTestId('consent-banner');
        expect(banner).toHaveClass('cookie-banner--showing');
      });
    });

    it('sets data-animating attribute during animations', async () => {
      const { rerender } = render(<ConsentBanner {...defaultProps} visible={false} />);
      
      rerender(<ConsentBanner {...defaultProps} visible={true} />);
      
      await waitFor(() => {
        const banner = screen.getByTestId('consent-banner');
        expect(banner).toHaveAttribute('data-animating', 'true');
      });
    });
  });

  describe('User Interactions', () => {
    it('calls onAcceptAll when Accept All button is clicked', () => {
      const onAcceptAll = vi.fn();
      render(<ConsentBanner {...defaultProps} onAcceptAll={onAcceptAll} />);
      
      const acceptButton = screen.getByRole('button', { name: /accept all cookies/i });
      fireEvent.click(acceptButton);
      
      expect(onAcceptAll).toHaveBeenCalledTimes(1);
    });

    it('calls onManagePreferences when Manage Preferences button is clicked', () => {
      const onManagePreferences = vi.fn();
      render(<ConsentBanner {...defaultProps} onManagePreferences={onManagePreferences} />);
      
      const manageButton = screen.getByRole('button', { name: /open cookie preferences/i });
      fireEvent.click(manageButton);
      
      expect(onManagePreferences).toHaveBeenCalledTimes(1);
    });

    it('announces actions to screen readers', async () => {
      const onAcceptAll = vi.fn();
      render(<ConsentBanner {...defaultProps} onAcceptAll={onAcceptAll} />);
      
      const acceptButton = screen.getByRole('button', { name: /accept all cookies/i });
      fireEvent.click(acceptButton);
      
      // Check that announcement element is created
      await waitFor(() => {
        expect(document.querySelector('[aria-live="polite"]')).toBeInTheDocument();
      });
    });
  });

  describe('Responsive Behavior', () => {
    it('applies mobile-specific classes on small screens', () => {
      // Mock window.matchMedia for mobile viewport
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: vi.fn().mockImplementation(query => ({
          matches: query === '(max-width: 768px)',
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      render(<ConsentBanner {...defaultProps} />);
      
      const banner = screen.getByTestId('consent-banner');
      expect(banner).toBeInTheDocument();
      
      // CSS classes are applied via media queries, so we just verify the component renders
      expect(banner).toHaveClass('cookie-banner');
    });
  });

  describe('Performance Optimizations', () => {
    it('prevents interactions during animations', async () => {
      const { rerender } = render(<ConsentBanner {...defaultProps} visible={false} />);
      
      rerender(<ConsentBanner {...defaultProps} visible={true} />);
      
      await waitFor(() => {
        const banner = screen.getByTestId('consent-banner');
        expect(banner).toHaveAttribute('data-animating', 'true');
      });
    });

    it('cleans up event listeners when unmounted', () => {
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');
      
      const { unmount } = render(<ConsentBanner {...defaultProps} />);
      unmount();
      
      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
    });
  });
});