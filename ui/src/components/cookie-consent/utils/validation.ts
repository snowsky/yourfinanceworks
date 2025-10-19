// Validation utilities for consent preferences
import type { ConsentPreferences, CookieCategory } from '../types';

export function validateConsentPreferences(preferences: Partial<ConsentPreferences>): boolean {
  // Essential cookies must always be true
  if (preferences.essential === false) {
    return false;
  }

  // Analytics and marketing can be true or false
  if (preferences.analytics !== undefined && typeof preferences.analytics !== 'boolean') {
    return false;
  }

  if (preferences.marketing !== undefined && typeof preferences.marketing !== 'boolean') {
    return false;
  }

  // Timestamp should be a valid number
  if (preferences.timestamp !== undefined && (!Number.isInteger(preferences.timestamp) || preferences.timestamp < 0)) {
    return false;
  }

  // Version should be a non-empty string
  if (preferences.version !== undefined && (typeof preferences.version !== 'string' || preferences.version.trim() === '')) {
    return false;
  }

  return true;
}

export function validateCookieCategory(category: string): category is CookieCategory {
  return ['essential', 'analytics', 'marketing'].includes(category);
}