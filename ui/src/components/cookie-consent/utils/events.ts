// Event utilities for consent changes
import type { ConsentStatus, ConsentPreferences } from '../types';

export interface ConsentChangeEvent {
  type: 'consent-change';
  status: ConsentStatus;
  preferences: ConsentPreferences;
  timestamp: number;
}

export function createConsentEvent(
  status: ConsentStatus,
  preferences: ConsentPreferences
): ConsentChangeEvent {
  return {
    type: 'consent-change',
    status,
    preferences,
    timestamp: Date.now()
  };
}

export function dispatchConsentEvent(event: ConsentChangeEvent): void {
  const customEvent = new CustomEvent('cookieConsentChange', {
    detail: event,
    bubbles: true
  });
  
  document.dispatchEvent(customEvent);
}