// TypeScript interfaces for cookie consent management

export type ConsentStatus = 'accepted' | 'custom' | null;

export type CookieCategory = 'essential' | 'analytics' | 'marketing';

export interface ConsentPreferences {
  essential: boolean;
  analytics: boolean;
  marketing: boolean;
  timestamp: number;
  version: string;
}

export interface CookieConsentProps {
  primaryColor?: string;
  darkMode?: boolean;
  position?: 'bottom' | 'top';
  message?: string;
  onConsentChange?: (consent: ConsentStatus) => void;
  analyticsConfig?: AnalyticsConfig;
}

export interface AnalyticsConfig {
  googleAnalytics?: {
    trackingId: string;
    enabled: boolean;
  };
  customProvider?: {
    scriptUrl: string;
    initFunction: string;
  };
}

export interface ConsentManagerInterface {
  getConsentStatus(): ConsentStatus;
  setConsentStatus(status: ConsentStatus): void;
  getCategoryConsent(category: CookieCategory): boolean;
  setCategoryConsent(category: CookieCategory, enabled: boolean): void;
  clearAllConsent(): void;
  isConsentRequired(): boolean;
}

export interface ConsentBannerProps {
  message?: string;
  primaryColor?: string;
  darkMode?: boolean;
  onAcceptAll: () => void;
  onManagePreferences: () => void;
  visible: boolean;
}

export interface PreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (preferences: Partial<ConsentPreferences>) => void;
  currentPreferences: ConsentPreferences;
  primaryColor?: string;
  darkMode?: boolean;
}

export interface AnalyticsIntegrationInterface {
  loadScripts(consent: ConsentPreferences): void;
  handleConsentChange(consent: ConsentPreferences): void;
  cleanup(): void;
  onConsentChange(callback: (consent: ConsentPreferences) => void): () => void;
  isScriptLoaded(scriptId: string): boolean;
  getConfig(): AnalyticsConfig;
  updateConfig(newConfig: Partial<AnalyticsConfig>): void;
}