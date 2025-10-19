import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ConsentManager } from '../ConsentManager';
import type { ConsentStatus, CookieCategory } from '../../types';

describe('ConsentManager', () => {
  let consentManager: ConsentManager;
  let mockLocalStorage: { [key: string]: string };

  beforeEach(() => {
    // Mock localStorage
    mockLocalStorage = {};
    
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: vi.fn((key: string) => mockLocalStorage[key] || null),
        setItem: vi.fn((key: string, value: string) => {
          mockLocalStorage[key] = value;
        }),
        removeItem: vi.fn((key: string) => {
          delete mockLocalStorage[key];
        }),
        clear: vi.fn(() => {
          mockLocalStorage = {};
        }),
      },
      writable: true,
    });

    consentManager = new ConsentManager();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('localStorage operations', () => {
    it('should read consent status from localStorage', () => {
      mockLocalStorage['cookieConsent'] = 'accepted';
      
      const status = consentManager.getConsentStatus();
      
      expect(status).toBe('accepted');
      expect(localStorage.getItem).toHaveBeenCalledWith('cookieConsent');
    });

    it('should write consent status to localStorage', () => {
      consentManager.setConsentStatus('accepted');
      
      expect(localStorage.setItem).toHaveBeenCalledWith('cookieConsent', 'accepted');
      expect(localStorage.setItem).toHaveBeenCalledWith('cookieConsent_timestamp', expect.any(String));
      expect(localStorage.setItem).toHaveBeenCalledWith('cookieConsent_version', '1.0.0');
    });

    it('should remove consent status when set to null', () => {
      consentManager.setConsentStatus(null);
      
      expect(localStorage.removeItem).toHaveBeenCalledWith('cookieConsent');
    });

    it('should handle localStorage unavailable gracefully', () => {
      // Mock localStorage to throw error
      vi.mocked(localStorage.getItem).mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });
      vi.mocked(localStorage.setItem).mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });

      // Should not throw and should use memory storage
      expect(() => {
        consentManager.setConsentStatus('accepted');
        const status = consentManager.getConsentStatus();
        expect(status).toBe('accepted');
      }).not.toThrow();
    });
  });

  describe('consent status management', () => {
    it('should return null for no consent', () => {
      const status = consentManager.getConsentStatus();
      expect(status).toBeNull();
    });

    it('should return true for consent required when no consent exists', () => {
      expect(consentManager.isConsentRequired()).toBe(true);
    });

    it('should return false for consent required when consent exists', () => {
      consentManager.setConsentStatus('accepted');
      expect(consentManager.isConsentRequired()).toBe(false);
    });

    it('should handle custom consent status', () => {
      consentManager.setConsentStatus('custom');
      expect(consentManager.getConsentStatus()).toBe('custom');
      expect(consentManager.isConsentRequired()).toBe(false);
    });
  });

  describe('category-specific consent management', () => {
    it('should always return true for essential cookies', () => {
      expect(consentManager.getCategoryConsent('essential')).toBe(true);
    });

    it('should return false for analytics cookies by default', () => {
      expect(consentManager.getCategoryConsent('analytics')).toBe(false);
    });

    it('should return false for marketing cookies by default', () => {
      expect(consentManager.getCategoryConsent('marketing')).toBe(false);
    });

    it('should set and get analytics consent', () => {
      consentManager.setCategoryConsent('analytics', true);
      expect(consentManager.getCategoryConsent('analytics')).toBe(true);
      
      consentManager.setCategoryConsent('analytics', false);
      expect(consentManager.getCategoryConsent('analytics')).toBe(false);
    });

    it('should set and get marketing consent', () => {
      consentManager.setCategoryConsent('marketing', true);
      expect(consentManager.getCategoryConsent('marketing')).toBe(true);
      
      consentManager.setCategoryConsent('marketing', false);
      expect(consentManager.getCategoryConsent('marketing')).toBe(false);
    });

    it('should throw error for unknown category', () => {
      expect(() => {
        consentManager.getCategoryConsent('unknown' as CookieCategory);
      }).toThrow('Unknown cookie category: unknown');
    });
  });

  describe('consent preferences management', () => {
    it('should get default consent preferences', () => {
      const preferences = consentManager.getConsentPreferences();
      
      expect(preferences).toEqual({
        essential: true,
        analytics: false,
        marketing: false,
        timestamp: 0,
        version: '1.0.0'
      });
    });

    it('should set partial consent preferences', () => {
      consentManager.setConsentPreferences({
        analytics: true,
        marketing: false
      });
      
      const preferences = consentManager.getConsentPreferences();
      expect(preferences.analytics).toBe(true);
      expect(preferences.marketing).toBe(false);
      expect(preferences.essential).toBe(true);
      expect(preferences.timestamp).toBeGreaterThan(0);
    });

    it('should update timestamp when setting preferences', () => {
      const beforeTime = Date.now();
      consentManager.setConsentPreferences({ analytics: true });
      const afterTime = Date.now();
      
      const preferences = consentManager.getConsentPreferences();
      expect(preferences.timestamp).toBeGreaterThanOrEqual(beforeTime);
      expect(preferences.timestamp).toBeLessThanOrEqual(afterTime);
    });
  });

  describe('clear all consent', () => {
    it('should clear all consent data', () => {
      // Set some consent data
      consentManager.setConsentStatus('accepted');
      consentManager.setCategoryConsent('analytics', true);
      consentManager.setCategoryConsent('marketing', true);
      
      // Clear all consent
      consentManager.clearAllConsent();
      
      // Verify all data is cleared
      expect(consentManager.getConsentStatus()).toBeNull();
      expect(consentManager.isConsentRequired()).toBe(true);
      
      // Essential should still be true, others should be false
      expect(consentManager.getCategoryConsent('essential')).toBe(true);
      expect(consentManager.getCategoryConsent('analytics')).toBe(false);
      expect(consentManager.getCategoryConsent('marketing')).toBe(false);
    });
  });

  describe('fallback storage behavior', () => {
    it('should use memory storage when localStorage fails', () => {
      // Mock localStorage to always throw
      vi.mocked(localStorage.getItem).mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });
      vi.mocked(localStorage.setItem).mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });
      vi.mocked(localStorage.removeItem).mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });

      // Should work with memory storage
      consentManager.setConsentStatus('accepted');
      expect(consentManager.getConsentStatus()).toBe('accepted');
      
      consentManager.setCategoryConsent('analytics', true);
      expect(consentManager.getCategoryConsent('analytics')).toBe(true);
      
      const preferences = consentManager.getConsentPreferences();
      expect(preferences.analytics).toBe(true);
    });

    it('should clear memory storage when clearAllConsent is called', () => {
      // Mock localStorage to always throw
      vi.mocked(localStorage.getItem).mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });
      vi.mocked(localStorage.setItem).mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });
      vi.mocked(localStorage.removeItem).mockImplementation(() => {
        throw new Error('localStorage unavailable');
      });

      // Set data in memory storage
      consentManager.setConsentStatus('accepted');
      consentManager.setCategoryConsent('analytics', true);
      
      // Clear all
      consentManager.clearAllConsent();
      
      // Verify memory storage is cleared
      expect(consentManager.getConsentStatus()).toBeNull();
      expect(consentManager.getCategoryConsent('analytics')).toBe(false);
    });
  });

  describe('GDPR compliance features', () => {
    it('should track consent timestamp', () => {
      const beforeTime = Date.now();
      consentManager.setConsentStatus('accepted');
      const afterTime = Date.now();
      
      const preferences = consentManager.getConsentPreferences();
      expect(preferences.timestamp).toBeGreaterThanOrEqual(beforeTime);
      expect(preferences.timestamp).toBeLessThanOrEqual(afterTime);
    });

    it('should track consent version', () => {
      consentManager.setConsentStatus('accepted');
      
      const preferences = consentManager.getConsentPreferences();
      expect(preferences.version).toBe('1.0.0');
    });

    it('should update timestamp when preferences change', () => {
      consentManager.setConsentStatus('accepted');
      const firstTimestamp = consentManager.getConsentPreferences().timestamp;
      
      // Wait a bit and update preferences
      setTimeout(() => {
        consentManager.setConsentPreferences({ analytics: true });
        const secondTimestamp = consentManager.getConsentPreferences().timestamp;
        
        expect(secondTimestamp).toBeGreaterThan(firstTimestamp);
      }, 10);
    });
  });
});