// Constants for cookie consent system
export const CONSENT_VERSION = '1.0.0';

export const STORAGE_KEYS = {
  CONSENT: 'cookieConsent',
  ESSENTIAL: 'cookieConsent_essential',
  ANALYTICS: 'cookieConsent_analytics',
  MARKETING: 'cookieConsent_marketing',
  TIMESTAMP: 'cookieConsent_timestamp',
  VERSION: 'cookieConsent_version'
} as const;

export const DEFAULT_MESSAGES = {
  BANNER_TEXT: 'We use cookies to improve your experience. By continuing, you agree to our use of cookies.',
  ACCEPT_ALL: 'Accept All',
  MANAGE_PREFERENCES: 'Manage Preferences',
  SAVE_PREFERENCES: 'Save Preferences',
  CANCEL: 'Cancel',
  ESSENTIAL_TITLE: 'Essential Cookies',
  ESSENTIAL_DESCRIPTION: 'These cookies are necessary for the website to function and cannot be switched off.',
  ANALYTICS_TITLE: 'Analytics Cookies',
  ANALYTICS_DESCRIPTION: 'These cookies help us understand how visitors interact with our website.',
  MARKETING_TITLE: 'Marketing Cookies',
  MARKETING_DESCRIPTION: 'These cookies are used to deliver personalized advertisements.'
} as const;

export const COOKIE_CATEGORIES = {
  ESSENTIAL: 'essential',
  ANALYTICS: 'analytics',
  MARKETING: 'marketing'
} as const;

export const CONSENT_STATUSES = {
  ACCEPTED: 'accepted',
  CUSTOM: 'custom',
  NULL: null
} as const;

export const ANIMATION_DURATIONS = {
  FAST: 150,
  NORMAL: 300,
  SLOW: 500
} as const;

export const Z_INDEX = {
  BANNER: 1000,
  MODAL: 1050,
  OVERLAY: 1040
} as const;