// ConsentManager service for localStorage operations and consent state management
import type {
  ConsentStatus,
  CookieCategory,
  ConsentPreferences,
  ConsentManagerInterface
} from '../types';

export class ConsentManager implements ConsentManagerInterface {
  private static readonly STORAGE_KEYS = {
    CONSENT: 'cookieConsent',
    ESSENTIAL: 'cookieConsent_essential',
    ANALYTICS: 'cookieConsent_analytics',
    MARKETING: 'cookieConsent_marketing',
    TIMESTAMP: 'cookieConsent_timestamp',
    VERSION: 'cookieConsent_version'
  } as const;

  private static readonly CURRENT_VERSION = '1.0.0';
  private memoryStorage: Map<string, string> = new Map();

  getConsentStatus(): ConsentStatus {
    const stored = this.getStorageItem(ConsentManager.STORAGE_KEYS.CONSENT);
    return stored as ConsentStatus || null;
  }

  setConsentStatus(status: ConsentStatus): void {
    if (status === null) {
      this.removeStorageItem(ConsentManager.STORAGE_KEYS.CONSENT);
    } else {
      this.setStorageItem(ConsentManager.STORAGE_KEYS.CONSENT, status);
      this.setStorageItem(ConsentManager.STORAGE_KEYS.TIMESTAMP, Date.now().toString());
      this.setStorageItem(ConsentManager.STORAGE_KEYS.VERSION, ConsentManager.CURRENT_VERSION);
    }
  }

  getCategoryConsent(category: CookieCategory): boolean {
    const key = this.getCategoryKey(category);
    const stored = this.getStorageItem(key);
    
    // Essential cookies are always enabled
    if (category === 'essential') {
      return true;
    }
    
    return stored === 'true';
  }

  setCategoryConsent(category: CookieCategory, enabled: boolean): void {
    const key = this.getCategoryKey(category);
    this.setStorageItem(key, enabled.toString());
  }

  clearAllConsent(): void {
    Object.values(ConsentManager.STORAGE_KEYS).forEach(key => {
      this.removeStorageItem(key);
    });
    this.memoryStorage.clear();
  }

  isConsentRequired(): boolean {
    return this.getConsentStatus() === null;
  }

  getConsentPreferences(): ConsentPreferences {
    return {
      essential: this.getCategoryConsent('essential'),
      analytics: this.getCategoryConsent('analytics'),
      marketing: this.getCategoryConsent('marketing'),
      timestamp: parseInt(this.getStorageItem(ConsentManager.STORAGE_KEYS.TIMESTAMP) || '0'),
      version: this.getStorageItem(ConsentManager.STORAGE_KEYS.VERSION) || ConsentManager.CURRENT_VERSION
    };
  }

  setConsentPreferences(preferences: Partial<ConsentPreferences>): void {
    if (preferences.analytics !== undefined) {
      this.setCategoryConsent('analytics', preferences.analytics);
    }
    if (preferences.marketing !== undefined) {
      this.setCategoryConsent('marketing', preferences.marketing);
    }
    
    this.setStorageItem(ConsentManager.STORAGE_KEYS.TIMESTAMP, Date.now().toString());
    this.setStorageItem(ConsentManager.STORAGE_KEYS.VERSION, ConsentManager.CURRENT_VERSION);
  }

  private getCategoryKey(category: CookieCategory): string {
    switch (category) {
      case 'essential':
        return ConsentManager.STORAGE_KEYS.ESSENTIAL;
      case 'analytics':
        return ConsentManager.STORAGE_KEYS.ANALYTICS;
      case 'marketing':
        return ConsentManager.STORAGE_KEYS.MARKETING;
      default:
        throw new Error(`Unknown cookie category: ${category}`);
    }
  }

  private getStorageItem(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      // Fallback to memory storage if localStorage is unavailable
      return this.memoryStorage.get(key) || null;
    }
  }

  private setStorageItem(key: string, value: string): void {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Fallback to memory storage if localStorage is unavailable
      this.memoryStorage.set(key, value);
    }
  }

  private removeStorageItem(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch {
      // Fallback to memory storage if localStorage is unavailable
      this.memoryStorage.delete(key);
    }
  }
}