// AnalyticsIntegration service for conditional script loading
import type {
  ConsentPreferences,
  AnalyticsConfig,
  AnalyticsIntegrationInterface
} from '../types';

export interface ScriptLoadOptions {
  async?: boolean;
  defer?: boolean;
  crossOrigin?: string;
  integrity?: string;
}

export interface ConsentChangeCallback {
  (consent: ConsentPreferences): void;
}

export class AnalyticsIntegration implements AnalyticsIntegrationInterface {
  private config: AnalyticsConfig;
  private loadedScripts: Set<string> = new Set();
  private consentChangeCallbacks: Set<ConsentChangeCallback> = new Set();
  private retryAttempts: Map<string, number> = new Map();
  private maxRetries: number = 3;
  private retryDelay: number = 1000;

  constructor(config: AnalyticsConfig = {}) {
    this.config = config;
  }

  loadScripts(consent: ConsentPreferences): void {
    // Only load analytics scripts if analytics consent is given
    if (!consent.analytics) {
      return;
    }

    // Load Google Analytics if configured and enabled
    if (this.config.googleAnalytics?.enabled && this.config.googleAnalytics.trackingId) {
      this.loadGoogleAnalytics(this.config.googleAnalytics.trackingId);
    }

    // Load custom analytics provider if configured
    if (this.config.customProvider?.scriptUrl) {
      this.loadCustomProvider(this.config.customProvider);
    }

    // Load marketing scripts if marketing consent is given
    if (consent.marketing) {
      this.loadMarketingScripts();
    }
  }

  handleConsentChange(consent: ConsentPreferences): void {
    // Notify all registered callbacks about consent change
    this.consentChangeCallbacks.forEach(callback => {
      try {
        callback(consent);
      } catch (error) {
        console.warn('Error in consent change callback:', error);
      }
    });

    if (!consent.analytics) {
      // Remove analytics scripts if consent is withdrawn
      this.removeAnalyticsScripts();
    } else {
      // Load analytics scripts if consent is given
      this.loadScripts(consent);
    }

    if (!consent.marketing) {
      // Remove marketing scripts if consent is withdrawn
      this.removeMarketingScripts();
    }
  }

  /**
   * Register a callback to be called when consent changes
   */
  onConsentChange(callback: ConsentChangeCallback): () => void {
    this.consentChangeCallbacks.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.consentChangeCallbacks.delete(callback);
    };
  }

  /**
   * Check if a specific script is loaded
   */
  isScriptLoaded(scriptId: string): boolean {
    return this.loadedScripts.has(scriptId);
  }

  /**
   * Get the current analytics configuration
   */
  getConfig(): AnalyticsConfig {
    return { ...this.config };
  }

  /**
   * Update the analytics configuration
   */
  updateConfig(newConfig: Partial<AnalyticsConfig>): void {
    this.config = { ...this.config, ...newConfig };
  }

  cleanup(): void {
    this.removeAnalyticsScripts();
    this.removeMarketingScripts();
    this.loadedScripts.clear();
    this.consentChangeCallbacks.clear();
    this.retryAttempts.clear();
  }

  private loadGoogleAnalytics(trackingId: string): void {
    const scriptId = `ga-script-${trackingId}`;
    
    if (this.loadedScripts.has(scriptId)) {
      return;
    }

    this.loadScriptWithRetry(
      `https://www.googletagmanager.com/gtag/js?id=${trackingId}`,
      scriptId,
      {
        async: true,
        onLoad: () => {
          try {
            // Initialize Google Analytics dataLayer
            (window as any).dataLayer = (window as any).dataLayer || [];
            function gtag(...args: any[]) {
              (window as any).dataLayer.push(args);
            }
            (window as any).gtag = gtag;
            
            // Configure Google Analytics
            gtag('js', new Date());
            gtag('config', trackingId, {
              anonymize_ip: true, // GDPR compliance
              cookie_flags: 'SameSite=None;Secure'
            });

            // Set consent mode
            gtag('consent', 'default', {
              analytics_storage: 'granted',
              ad_storage: 'denied'
            });

            console.log('Google Analytics loaded successfully');
          } catch (error) {
            console.warn('Failed to initialize Google Analytics:', error);
          }
        },
        onError: (error) => {
          console.warn('Failed to load Google Analytics script:', error);
        }
      }
    );
  }

  private loadCustomProvider(provider: { scriptUrl: string; initFunction: string }): void {
    const scriptId = `custom-analytics-${this.generateScriptId(provider.scriptUrl)}`;
    
    if (this.loadedScripts.has(scriptId)) {
      return;
    }

    this.loadScriptWithRetry(
      provider.scriptUrl,
      scriptId,
      {
        async: true,
        onLoad: () => {
          try {
            // Call initialization function if it exists
            const initFn = this.getNestedProperty(window, provider.initFunction);
            if (typeof initFn === 'function') {
              initFn();
              console.log(`Custom analytics provider initialized: ${provider.initFunction}`);
            } else {
              console.warn(`Initialization function not found: ${provider.initFunction}`);
            }
          } catch (error) {
            console.warn('Failed to initialize custom analytics provider:', error);
          }
        },
        onError: (error) => {
          console.warn('Failed to load custom analytics provider:', error);
        }
      }
    );
  }

  /**
   * Load marketing scripts (placeholder for future marketing integrations)
   */
  private loadMarketingScripts(): void {
    // Placeholder for marketing script loading
    // This can be extended to load Facebook Pixel, Google Ads, etc.
    console.log('Marketing scripts would be loaded here');
  }

  /**
   * Generic script loader with retry mechanism
   */
  private loadScriptWithRetry(
    src: string,
    scriptId: string,
    options: {
      async?: boolean;
      defer?: boolean;
      crossOrigin?: string;
      integrity?: string;
      onLoad?: () => void;
      onError?: (error: Event) => void;
    } = {}
  ): void {
    const attemptCount = this.retryAttempts.get(scriptId) || 0;
    
    if (attemptCount >= this.maxRetries) {
      console.warn(`Max retry attempts reached for script: ${scriptId}`);
      return;
    }

    try {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = src;
      
      if (options.async !== undefined) script.async = options.async;
      if (options.defer !== undefined) script.defer = options.defer;
      if (options.crossOrigin) script.crossOrigin = options.crossOrigin;
      if (options.integrity) script.integrity = options.integrity;

      script.onload = () => {
        this.loadedScripts.add(scriptId);
        this.retryAttempts.delete(scriptId);
        options.onLoad?.();
      };

      script.onerror = (error) => {
        console.warn(`Failed to load script ${scriptId}, attempt ${attemptCount + 1}/${this.maxRetries}`);
        this.retryAttempts.set(scriptId, attemptCount + 1);
        
        // Retry after delay
        setTimeout(() => {
          this.loadScriptWithRetry(src, scriptId, options);
        }, this.retryDelay * (attemptCount + 1));
        
        options.onError?.(error);
      };

      document.head.appendChild(script);
    } catch (error) {
      console.warn('Failed to create script element:', error);
    }
  }

  private removeAnalyticsScripts(): void {
    // Remove analytics-related scripts
    const analyticsScripts = Array.from(this.loadedScripts).filter(scriptId => 
      scriptId.includes('ga-script') || scriptId.includes('custom-analytics')
    );

    analyticsScripts.forEach(scriptId => {
      const script = document.getElementById(scriptId);
      if (script) {
        script.remove();
        this.loadedScripts.delete(scriptId);
      }
    });

    // Update Google Analytics consent
    if ((window as any).gtag) {
      try {
        (window as any).gtag('consent', 'update', {
          analytics_storage: 'denied'
        });
      } catch (error) {
        console.warn('Failed to update Google Analytics consent:', error);
      }
    }
  }

  private removeMarketingScripts(): void {
    // Remove marketing-related scripts
    const marketingScripts = Array.from(this.loadedScripts).filter(scriptId => 
      scriptId.includes('marketing') || scriptId.includes('ads')
    );

    marketingScripts.forEach(scriptId => {
      const script = document.getElementById(scriptId);
      if (script) {
        script.remove();
        this.loadedScripts.delete(scriptId);
      }
    });

    // Update Google Analytics marketing consent
    if ((window as any).gtag) {
      try {
        (window as any).gtag('consent', 'update', {
          ad_storage: 'denied'
        });
      } catch (error) {
        console.warn('Failed to update Google Analytics marketing consent:', error);
      }
    }
  }

  /**
   * Generate a unique script ID from URL
   */
  private generateScriptId(url: string): string {
    return btoa(url).replace(/[^a-zA-Z0-9]/g, '').substring(0, 10);
  }

  private getNestedProperty(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  /**
   * Force reload all scripts based on current consent
   */
  reloadScripts(consent: ConsentPreferences): void {
    this.cleanup();
    this.loadScripts(consent);
  }

  /**
   * Get retry statistics for debugging
   */
  getRetryStats(): { [scriptId: string]: number } {
    const stats: { [scriptId: string]: number } = {};
    this.retryAttempts.forEach((attempts, scriptId) => {
      stats[scriptId] = attempts;
    });
    return stats;
  }

  /**
   * Set retry configuration
   */
  setRetryConfig(maxRetries: number, retryDelay: number): void {
    this.maxRetries = Math.max(0, maxRetries);
    this.retryDelay = Math.max(100, retryDelay);
  }
}

// Export utility functions for external use
export const createAnalyticsIntegration = (config?: AnalyticsConfig): AnalyticsIntegration => {
  return new AnalyticsIntegration(config);
};

// Example configurations for common analytics providers
export const analyticsProviders = {
  googleAnalytics: (trackingId: string): AnalyticsConfig => ({
    googleAnalytics: {
      trackingId,
      enabled: true
    }
  }),
  
  customProvider: (scriptUrl: string, initFunction: string): AnalyticsConfig => ({
    customProvider: {
      scriptUrl,
      initFunction
    }
  }),
  
  // Example: Matomo analytics
  matomo: (siteUrl: string, siteId: string): AnalyticsConfig => ({
    customProvider: {
      scriptUrl: `${siteUrl}/matomo.js`,
      initFunction: '_paq.push'
    }
  }),
  
  // Example: Adobe Analytics
  adobe: (scriptUrl: string): AnalyticsConfig => ({
    customProvider: {
      scriptUrl,
      initFunction: 's.t'
    }
  })
};