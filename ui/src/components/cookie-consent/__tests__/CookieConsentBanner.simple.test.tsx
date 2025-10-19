import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { CookieConsentBanner } from '../CookieConsentBanner';

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

describe('CookieConsentBanner - Basic Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.getItem.mockReturnValue(null);
  });

  it('should render the main container', () => {
    render(<CookieConsentBanner />);
    
    expect(screen.getByTestId('cookie-consent-banner')).toBeInTheDocument();
  });

  it('should apply theme attributes', () => {
    render(<CookieConsentBanner darkMode={true} />);
    
    const container = screen.getByTestId('cookie-consent-banner');
    expect(container).toHaveAttribute('data-theme', 'dark');
  });

  it('should apply position attributes', () => {
    render(<CookieConsentBanner position="top" />);
    
    const container = screen.getByTestId('cookie-consent-banner');
    expect(container).toHaveAttribute('data-position', 'top');
    expect(container).toHaveClass('cookie-consent-system--top');
  });

  it('should apply custom primary color', () => {
    const customColor = '#ff0000';
    render(<CookieConsentBanner primaryColor={customColor} />);
    
    const container = screen.getByTestId('cookie-consent-banner');
    expect(container).toHaveStyle(`--cookie-primary-color: ${customColor}`);
  });

  it('should render banner when no consent exists', () => {
    render(<CookieConsentBanner />);
    
    // The banner should be present in the DOM
    expect(screen.getByTestId('consent-banner')).toBeInTheDocument();
  });

  it('should render with custom message', () => {
    const customMessage = 'Custom cookie message';
    render(<CookieConsentBanner message={customMessage} />);
    
    expect(screen.getByText(customMessage)).toBeInTheDocument();
  });
});